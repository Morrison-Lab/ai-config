#!/usr/bin/env python3
"""Test ai-session.sh's MWC grant lifecycle.

Focused on `check-mwc`, which the merge guard's authorization rests on and
which ai-config#1279 reported answering "not active" for a grant that was live.
Two properties are pinned here:

  * `check-mwc` is a QUERY. Asking must not revoke. It used to `prune_stale`
    and then `rm -f` the marker whenever the session read stale, so a single
    liveness false negative destroyed a human-issued grant permanently -- and
    reported it in the same words as "never granted", leaving no way to tell
    the two apart or to recover.
  * Its three outcomes are distinguishable. Per shared/principles/fail-fast.md,
    "no grant" and "a grant whose session reads dead" want opposite responses,
    so collapsing them into one sentence and one exit code is the failure-path-
    looks-like-the-pass-path shape that rule exists to ban.

Runs against a throwaway git repo, never the real registry: the script keys its
registry off `git rev-parse --git-common-dir`, so a temp repo isolates it.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from findbash import find_bash  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "session-lock" / "scripts" / "ai-session.sh"

failures = []


def check(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        failures.append(f"{label}{(': ' + detail) if detail else ''}")


def rewrite_record(path, **fields):
    """Rewrite named `key=value` lines in a session record, in place.

    Only keys already present are rewritten; the rest of the record is
    preserved byte for byte apart from newline normalization.
    """
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    out = []
    for line in text.splitlines():
        key = line.split("=", 1)[0]
        out.append(f"{key}={fields[key]}" if key in fields else line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def dead_pid(bash):
    """Return a PID that is reliably dead, by ai-session.sh's own test.

    `session_liveness()` decides deadness with `kill -0`, so this asks the
    same shell the script runs under, rather than a Python-side proxy: an
    `os.kill` from this process cannot see a PID owned by another user, and
    would report it dead when the script would call it alive.
    """
    # Spawn, kill, and `wait` inside ONE shell, so the owning parent reaps the
    # child synchronously: `wait` returns only once it has (rc 143 on SIGTERM).
    #
    # Reaping from a second shell loses a race rather than hitting a permanent
    # state. A killed orphan reparents to PID 1, which here DOES reap it, but
    # takes ~1.6-2.0s. The check runs milliseconds after the kill, so it finds
    # the process still in `Z` and `kill -0` still returning 0, and each retry
    # spawns a fresh pid, so every iteration re-loses the same race. A second
    # shell cannot `wait` on it either: that is an error rather than a no-op,
    # `pid N is not a child of this shell`, rc 127.
    # (Measured 2026-08-12 in this container; PID 1 is `process_api`.)
    spawn = "sleep 30 & p=$!; kill $p 2>/dev/null; wait $p 2>/dev/null; echo $p"
    # The retry loop is not dead code even though `wait` reaps synchronously.
    # A PID freed by that reap can be reused before the check below runs, so
    # `kill -0` would then succeed on an unrelated process.
    # Retrying with a fresh PID is the cheapest way past that, and exhausting
    # the bound raises rather than returning a live one.
    for _ in range(20):
        p = subprocess.run([bash, "-c", spawn],
                           capture_output=True, text=True, check=True)
        pid = p.stdout.strip()
        # Confirm a fresh shell agrees the PID is gone.
        gone = subprocess.run([bash, "-c", f"kill -0 {pid} 2>/dev/null"],
                              capture_output=True)
        if gone.returncode != 0:
            return pid
    raise RuntimeError("could not obtain a reliably dead PID")


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_CONFIG_SYSTEM=os.devnull)
        for args in (["init", "-q", "-b", "main"],
                     ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=repo, env=env,
                           check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"],
                       cwd=repo, env=env, check=True, capture_output=True)

        bash = find_bash(SCRIPT, probe_args=("list",), cwd=repo)
        if bash is None:
            print("FATAL: no bash able to run ai-session.sh; set AI_SESSION_BASH")
            return 1

        def run(*args):
            return subprocess.run([bash, str(SCRIPT), *args], cwd=repo,
                                  env=env, capture_output=True, text=True)

        sid = "sess-1279"
        reg = repo / ".git" / "ai-sessions"
        marker = reg / f"{sid}.mwc"
        sess = reg / f"{sid}.session"

        print("MWC grant lifecycle:")

        # 1. No grant yet -> exit 1, and the message says WHY.
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 1, "no grant recorded exits 1", f"rc={p.returncode}")
        check("no grant recorded" in p.stdout,
              "no grant recorded says so explicitly", p.stdout.strip())

        # 2. Grant it -> active, exit 0.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        check(marker.is_file(), "enable-mwc writes the marker")
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 0, "a live grant exits 0", f"rc={p.returncode}")
        check("is active" in p.stdout, "a live grant reports active", p.stdout.strip())

        # 3. Resolving by --id and by AI_SESSION_ID must agree. ai-config#1279
        #    reported these disagreeing for one session in one repo.
        p_env = subprocess.run([bash, str(SCRIPT), "check-mwc"], cwd=repo,
                               env=dict(env, AI_SESSION_ID=sid),
                               capture_output=True, text=True)
        check(p_env.returncode == 0,
              "AI_SESSION_ID resolves the same grant as --id",
              f"rc={p_env.returncode} out={p_env.stdout.strip()}")

        old = str(int(time.time()) - 99999)

        # `is_stale()` reaches its verdict two ways, and each needs its own case
        # or one of them never runs. It tests liveness FIRST -- a dead PID on
        # this host is stale outright -- and consults the heartbeat only when
        # liveness is `unknown`. So ageing the heartbeat is not a portable way
        # to make a session stale: the record carries whatever PID
        # `find_agent_pid()` found, and on a host with a live `claude` ancestor
        # that is a live PID, so `alive)` returns "not stale" and the aged
        # heartbeat is never read. Measured: the pre-change suite passes in CI,
        # where no such ancestor exists and the `unknown` branch runs, and fails
        # four checks here with rc=0 where one does. The `dead)` branch ran in
        # neither, which is what step 4 below adds (ai-config#1327).

        # 4. A crashed session: the recorded PID is dead, and the heartbeat is
        #    deliberately left FRESH, so only the liveness branch can make this
        #    stale. The grant is no longer honourable -- but asking must NOT
        #    destroy it, and must say which of the two non-active states it is.
        rewrite_record(sess, pid=dead_pid(bash))

        p = run("check-mwc", "--id", sid)
        check(p.returncode == 2, "a dead-PID session exits 2, not 1",
              f"rc={p.returncode}")
        check("reads dead" in p.stdout,
              "a dead-PID session names the PID as the problem", p.stdout.strip())
        check("no grant recorded" not in p.stdout,
              "a dead-PID session is NOT reported as an absent grant",
              p.stdout.strip())
        check(marker.is_file(),
              "KEY: asking does not delete the marker (query stays read-only)")
        check("heartbeat" in p.stdout,
              "a dead-PID session names the recovery command", p.stdout.strip())

        # 5. A session whose liveness cannot be judged -- no recorded PID, as a
        #    record written where no agent process was found, or one carried in
        #    from another host. Here the aged heartbeat is the only thing that
        #    can make it stale, so this is the branch that runs in CI.
        rewrite_record(sess, pid="", heartbeat=old, started=old)

        p = run("check-mwc", "--id", sid)
        check(p.returncode == 2, "an aged-heartbeat session exits 2, not 1",
              f"rc={p.returncode}")
        check("reads unknown" in p.stdout,
              "an aged-heartbeat session says liveness is unknown", p.stdout.strip())
        check("no grant recorded" not in p.stdout,
              "an aged-heartbeat session is NOT reported as an absent grant",
              p.stdout.strip())
        check(marker.is_file(),
              "KEY: an aged-heartbeat read does not delete the marker either")

        # 6. Recovery: a heartbeat restores the grant, because step 5 kept it.
        run("heartbeat", "--id", sid)
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 0,
              "KEY: a heartbeat restores the grant a stale read did not destroy",
              f"rc={p.returncode} out={p.stdout.strip()}")

        # 7. Liveness outranks the heartbeat, and this is the direction the two
        #    cases above cannot pin: a live PID with a long-expired heartbeat is
        #    NOT stale. Without it, collapsing `is_stale()` to the heartbeat
        #    alone would still pass every other case here.
        rewrite_record(sess, pid=str(os.getpid()), heartbeat=old, started=old)
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 0,
              "KEY: a live PID keeps the grant despite an expired heartbeat",
              f"rc={p.returncode} out={p.stdout.strip()}")

        # 8. Marker with no session record is its own state, also exit 2.
        # Re-established from scratch rather than inherited from step 5, so a
        # regression earlier in the file cannot truncate the run and steal the
        # attribution for what follows.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        sess.unlink(missing_ok=True)
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 2, "grant with no session record exits 2",
              f"rc={p.returncode}")
        check("no session record" in p.stdout,
              "grant with no session record says so", p.stdout.strip())

        # 9. disable-mwc really does remove it -- the query being read-only must
        #    not have made revocation impossible.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        run("disable-mwc", "--id", sid)
        check(not marker.exists(), "disable-mwc removes the marker")
        check(run("check-mwc", "--id", sid).returncode == 1,
              "after disable-mwc the grant is gone")

        # 10. prune still sweeps a stale session's marker, so a genuinely dead
        #     session's grant does not linger forever. A dead PID makes this
        #     stale on any host, where ageing the heartbeat alone leaves it to
        #     whether the suite's own registration found a live agent process.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        rewrite_record(sess, pid=dead_pid(bash))
        run("prune")
        check(not marker.exists(), "prune sweeps a stale session's marker")

        # 11. A record that reached the registry with CRLF endings must still
        #    parse. `heartbeat=<n>\r` used to reach is_stale's arithmetic and
        #    raise "invalid arithmetic operator", which under `set -e` killed
        #    check-mwc mid-check -- so it exited 1, the code for "no grant
        #    recorded", while the grant sat right there. A crash reported as an
        #    absent grant is the exact conflation this command now avoids.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        crlf = sess.read_text(encoding="utf-8").replace("\n", "\r\n")
        sess.write_text(crlf, encoding="utf-8", newline="")
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 0,
              "a CRLF session record still reads as a live grant",
              f"rc={p.returncode} out={p.stdout.strip()} err={p.stderr.strip()}")
        check("invalid arithmetic" not in p.stderr,
              "a CRLF session record does not crash is_stale", p.stderr.strip())

    print()
    if failures:
        print(f"{len(failures)} FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all ai-session MWC checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
