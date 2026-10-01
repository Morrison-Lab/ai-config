#!/usr/bin/env python3
"""Tests for no-pr-work-without-claim.py (ai-config#4155).

Each case runs the hook as a subprocess against a REAL temporary git repo whose
`origin` is a Morrison-Lab URL, with `gh` replaced by a fake (PR_CLAIM_GH_CMD)
that serves canned forge responses. The fake is a fixture, so these cases show
the hook's decisions given those responses, not what the real forge returns
(shared/workflow/fixtures-are-not-evidence.md).

The negatives carry the weight: this guard DENIES, and `git commit` / `git push`
are the commonest strings in the corpus.

Run: python3 hooks/test-no-pr-work-without-claim.py [hooks/no-pr-work-without-claim.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SUBJECT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "no-pr-work-without-claim.py")

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"
SID = "session_test_AAAA"
FAKE_GH = """\
import json, os, sys
data = json.load(open(os.environ["FAKE_GH_DATA"]))
path = sys.argv[-1]
for needle, resp in data.items():
    if needle in path:
        if resp == "FAIL":
            sys.stderr.write("HTTP 502 simulated")
            sys.exit(1)
        print(json.dumps(resp))
        sys.exit(0)
print("[]")
"""

FAILURES = []
COUNT = [0]


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          check=True).stdout.strip()


def make_repo(tmp, remote="https://github.com/Morrison-Lab/test-repo.git",
              branch="feat/x"):
    repo = os.path.join(tmp, "wt-one")
    os.makedirs(repo)
    sh(repo, "git", "init", "-q", "-b", "main")
    sh(repo, "git", "config", "user.email", "t@example.com")
    sh(repo, "git", "config", "user.name", "t")
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "init")
    if branch != "main":
        sh(repo, "git", "checkout", "-q", "-b", branch)
    sh(repo, "git", "remote", "add", "origin", remote)
    return repo, sh(repo, "git", "rev-parse", "--show-toplevel")


def claim(body_extra="", marker=True, phrase="hold off", at="2026-09-30T20:00:00Z",
          url="https://github.com/x/y/pull/1#c1"):
    body = (f"Claude Code CLI (local session) is working on this --- please "
            f"{phrase} on pushing to this branch.\n\n{body_extra}\n\n")
    return {"body": body + (MARKER if marker else ""), "created_at": at,
            "html_url": url}


def run(name, command, expect, *, comments=None, prs="open", repo_kwargs=None,
        activity=None, env=None, stdin_raw=None, tool="Bash", branch="feat/x",
        gh_fail=False, check_in_ctx=None, extra_payload=None):
    """expect: None (silent) | 'deny' | 'ctx' (additionalContext, no decision)."""
    COUNT[0] += 1
    with tempfile.TemporaryDirectory() as tmp:
        repo, top = make_repo(tmp, branch=branch, **(repo_kwargs or {}))
        if callable(comments):
            comments = comments(top)
        pr_list = ([{"number": 7, "html_url": "https://github.com/Morrison-Lab/"
                     "test-repo/pull/7"}] if prs == "open" else [])
        data = {"pulls?state=open": "FAIL" if gh_fail else pr_list,
                "/comments": comments or [],
                "/activity": activity if activity is not None else []}
        data_path = os.path.join(tmp, "data.json")
        fake_path = os.path.join(tmp, "fakegh.py")
        with open(data_path, "w") as f:
            json.dump(data, f)
        with open(fake_path, "w") as f:
            f.write(FAKE_GH)
        e = dict(os.environ)
        e.pop("ALLOW_UNCLAIMED_PR_WORK", None)
        e["FAKE_GH_DATA"] = data_path
        e["PR_CLAIM_GH_CMD"] = (f'"{sys.executable.replace(chr(92), "/")}" '
                                f'"{fake_path.replace(chr(92), "/")}"')
        e.update(env or {})
        payload = {"tool_name": tool, "tool_input": {"command": command},
                   "cwd": repo, "session_id": SID}
        payload.update(extra_payload or {})
        stdin = stdin_raw if stdin_raw is not None else json.dumps(payload)
        r = subprocess.run([sys.executable, SUBJECT], input=stdin,
                           capture_output=True, text=True, env=e, timeout=60)
        out = r.stdout.strip()
        spec = json.loads(out)["hookSpecificOutput"] if out else {}
        got = ("deny" if spec.get("permissionDecision") == "deny"
               else "ctx" if spec.get("additionalContext") else None)
        ok = got == expect and r.returncode == 0
        if ok and check_in_ctx:
            blob = (spec.get("additionalContext", "") + r.stderr
                    + spec.get("permissionDecisionReason", ""))
            ok = check_in_ctx in blob
        if not ok:
            FAILURES.append(f"{name}: expected {expect}, got {got} "
                            f"(rc={r.returncode}) out={out[:300]!r} "
                            f"err={r.stderr[:200]!r}")
    return


def mine(top):
    return [claim(f"Session worktree: `{top}`")]


COMMIT = 'git commit -m "fix: x"'
PUSH = "git push origin feat/x"

# --- silent cases ---------------------------------------------------------
run("N1 unrelated command", "git status", None)
run("N2 quoted mention of commit", 'echo "git commit -m x && git push"', None)
run("N3 commit-tree is not commit", "git commit-tree HEAD^{tree}", None)
run("N4 dry-run push", "git push --dry-run origin feat/x", None)
run("N5 branch deletion push", "git push --delete origin old", None)
run("N6 on main", COMMIT, None, branch="main")
run("N7 foreign owner", COMMIT, None,
    repo_kwargs={"remote": "https://github.com/someone/else.git"})
run("N8 no open PR", COMMIT, None, prs="none")
run("N9 non-Bash tool", COMMIT, None, tool="Read")
run("N10 malformed stdin", COMMIT, None, stdin_raw="{not json")
run("N11 heredoc body naming commit",
    "cat <<'EOF'\ngit commit -m x\nEOF", None)

# --- the claim requirement -------------------------------------------------
run("D1 commit, PR has no claim", COMMIT, "deny")
run("D2 push, PR has no claim", PUSH, "deny")
run("D3 claim without session identity", COMMIT, "deny",
    comments=[claim()])
run("D4 claim naming session lacks the agent marker", COMMIT, "deny",
    comments=[claim(f"Session id: {SID}", marker=False)])
run("D5 claim lacks the hold-off wording", COMMIT, "deny",
    comments=[claim(f"Session id: {SID}", phrase="please note")])
run("D6 claim names a prefix-colliding worktree", COMMIT, "deny",
    comments=lambda top: [claim(f"Session worktree: `{top}-ab`")])
run("A1 claim naming session id", COMMIT, None,
    comments=[claim(f"Session id: `{SID}`")])
run("A2 claim naming worktree path", PUSH, None, comments=mine)
run("A3 worktree path written with backslashes", COMMIT, None,
    comments=lambda top: [claim("Session worktree: `"
                                + top.replace("/", chr(92)) + "`")])
run("A4 legacy 'paws off' wording", COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: `{top}`",
                                phrase="paws off")])
run("A5 commit chained before push", f"{COMMIT} && {PUSH}", None,
    comments=mine)

# --- takeover --------------------------------------------------------------
other_newer = lambda top: [
    claim(f"Session worktree: `{top}`", at="2026-09-30T20:00:00Z"),
    claim("Session id: `session_other_BBBB`", at="2026-09-30T21:00:00Z")]
other_older = lambda top: [
    claim("Session id: `session_other_BBBB`", at="2026-09-30T19:00:00Z"),
    claim(f"Session worktree: `{top}`", at="2026-09-30T20:00:00Z")]
anon_newer = lambda top: [
    claim(f"Session worktree: `{top}`", at="2026-09-30T20:00:00Z"),
    claim(at="2026-09-30T21:00:00Z")]
run("T1 another session claimed after mine", COMMIT, "deny",
    comments=other_newer)
run("T2 another session claimed before mine", COMMIT, None,
    comments=other_older)
run("T3 anonymous newer claim only warns", COMMIT, "ctx",
    comments=anon_newer, check_in_ctx="names no session")

# --- override --------------------------------------------------------------
run("O1 env prefix", f"ALLOW_UNCLAIMED_PR_WORK=1 {COMMIT}", None)
run("O2 leading export", f"export ALLOW_UNCLAIMED_PR_WORK=1 && {COMMIT}", None)
run("O3 process environment", COMMIT, None,
    env={"ALLOW_UNCLAIMED_PR_WORK": "1"})
run("O4 override =0 does not clear", f"ALLOW_UNCLAIMED_PR_WORK=0 {COMMIT}",
    "deny")
run("O5 override on an unrelated command does not clear",
    f"ALLOW_UNCLAIMED_PR_WORK=1 git status && {COMMIT}", "deny")

# --- fail open, visibly ----------------------------------------------------
run("F1 forge error allows and says so", COMMIT, "ctx", gh_fail=True,
    check_in_ctx="could not verify")
run("F2 missing gh allows and says so", COMMIT, "ctx",
    env={"PR_CLAIM_GH_CMD": "definitely-not-a-real-gh-binary"},
    check_in_ctx="could not verify")

# --- activity warning on push ----------------------------------------------
foreign = [{"activity_type": "push", "timestamp": "2026-09-30T22:00:00Z",
            "after": "d" * 40, "actor": {"login": "peer"}}]
old_foreign = [{"activity_type": "push", "timestamp": "2026-09-30T10:00:00Z",
                "after": "d" * 40, "actor": {"login": "peer"}}]
branch_del = [{"activity_type": "branch_deletion",
               "timestamp": "2026-09-30T22:00:00Z", "after": "d" * 40,
               "actor": {"login": "peer"}}]
run("P1 foreign push since claim warns", PUSH, "ctx", comments=mine,
    activity=foreign, check_in_ctx="NOT in your local history")
run("P2 foreign push BEFORE claim is silent", PUSH, None, comments=mine,
    activity=old_foreign)
run("P3 foreign push but verb is commit: no activity check", COMMIT, None,
    comments=mine, activity=foreign)
run("P4 non-push activity ignored", PUSH, None, comments=mine,
    activity=branch_del)

# P6: own push already in local history is silent. HEAD sha is only known once
# the repo exists, so this case builds its own activity from inside the repo.
COUNT[0] += 1
with tempfile.TemporaryDirectory() as tmp:
    repo, top = make_repo(tmp)
    head = sh(repo, "git", "rev-parse", "HEAD")
    data = {"pulls?state=open": [{"number": 7, "html_url": "u"}],
            "/comments": mine(top),
            "/activity": [{"activity_type": "push",
                           "timestamp": "2026-09-30T22:00:00Z", "after": head,
                           "actor": {"login": "me"}}]}
    dp, fp = os.path.join(tmp, "d.json"), os.path.join(tmp, "f.py")
    json.dump(data, open(dp, "w"))
    open(fp, "w").write(FAKE_GH)
    e = dict(os.environ, FAKE_GH_DATA=dp, PR_CLAIM_GH_CMD=(
        f'"{sys.executable.replace(chr(92), "/")}" "{fp.replace(chr(92), "/")}"'))
    e.pop("ALLOW_UNCLAIMED_PR_WORK", None)
    r = subprocess.run([sys.executable, SUBJECT], capture_output=True,
                       text=True, env=e, input=json.dumps(
                           {"tool_name": "Bash", "cwd": repo,
                            "session_id": SID,
                            "tool_input": {"command": PUSH}}))
    if r.stdout.strip():
        FAILURES.append(f"P6 own push in history should be silent: {r.stdout}")

print(f"{COUNT[0]} cases, {len(FAILURES)} failures")
for f in FAILURES:
    print("FAIL", f)
sys.exit(1 if FAILURES else 0)
