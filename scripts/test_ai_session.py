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

        # 4. Age the heartbeat past the stale threshold. The grant is no longer
        #    honourable -- but asking must NOT destroy it, and must say which of
        #    the two non-active states this is.
        text = sess.read_text(encoding="utf-8")
        old = str(int(time.time()) - 99999)
        sess.write_text(
            "\n".join(
                f"heartbeat={old}" if l.startswith("heartbeat=") else
                (f"started={old}" if l.startswith("started=") else l)
                for l in text.splitlines()) + "\n",
            encoding="utf-8", newline="\n")

        p = run("check-mwc", "--id", sid)
        check(p.returncode == 2, "a stale session exits 2, not 1",
              f"rc={p.returncode}")
        check("stale" in p.stdout or "dead" in p.stdout,
              "a stale session says the session is the problem", p.stdout.strip())
        check("no grant recorded" not in p.stdout,
              "a stale session is NOT reported as an absent grant", p.stdout.strip())
        check(marker.is_file(),
              "KEY: asking does not delete the marker (query stays read-only)")
        check("heartbeat" in p.stdout,
              "a stale session names the recovery command", p.stdout.strip())

        # 5. Recovery: a heartbeat restores the grant, because step 4 kept it.
        run("heartbeat", "--id", sid)
        p = run("check-mwc", "--id", sid)
        check(p.returncode == 0,
              "KEY: a heartbeat restores the grant a stale read did not destroy",
              f"rc={p.returncode} out={p.stdout.strip()}")

        # 6. Marker with no session record is its own state, also exit 2.
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

        # 7. disable-mwc really does remove it -- the query being read-only must
        #    not have made revocation impossible.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        run("disable-mwc", "--id", sid)
        check(not marker.exists(), "disable-mwc removes the marker")
        check(run("check-mwc", "--id", sid).returncode == 1,
              "after disable-mwc the grant is gone")

        # 8. prune still sweeps a stale session's marker, so a genuinely dead
        #    session's grant does not linger forever.
        run("register", "--id", sid)
        run("enable-mwc", "--id", sid)
        text = sess.read_text(encoding="utf-8") if sess.exists() else ""
        sess.write_text(
            "\n".join(
                f"heartbeat={old}" if l.startswith("heartbeat=") else
                (f"started={old}" if l.startswith("started=") else l)
                for l in text.splitlines()) + "\n",
            encoding="utf-8", newline="\n")
        run("prune")
        check(not marker.exists(), "prune sweeps a stale session's marker")

        # 9. A record that reached the registry with CRLF endings must still
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
