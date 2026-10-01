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
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SUBJECT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "no-pr-work-without-claim.py")

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"
SID = "session_test_AAAA"
FAKE_GH = """\
import json, os, sys, time
data = json.load(open(os.environ["FAKE_GH_DATA"], encoding="utf-8"))
path = sys.argv[-1]
with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(path + "\\n")
if os.environ.get("FAKE_GH_SLEEP"):
    time.sleep(float(os.environ["FAKE_GH_SLEEP"]))
for needle, resp in data.items():
    if needle in path:
        if resp == "FAIL":
            sys.stderr.write("HTTP 502 simulated")
            sys.exit(1)
        if isinstance(resp, dict) and "pages" in resp:
            for page in resp["pages"]:  # --paginate: one array per page
                print(json.dumps(page))
        else:
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
              branch="feat/x", name="wt-one"):
    repo = os.path.join(tmp, name)
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
        gh_fail=False, check_in_ctx=None, extra_payload=None, cwd_other=False,
        expect_paths=None, pr_updated_at=None, repo_name="wt-one"):
    """expect: None (silent) | 'deny' | 'ctx' (additionalContext, no decision).

    `command` may be a callable (repo_path, other_path) -> str. `other` is a
    second checkout on `main`; `cwd_other` makes it the payload cwd.
    """
    COUNT[0] += 1
    with tempfile.TemporaryDirectory() as tmp:
        repo, top = make_repo(tmp, branch=branch, name=repo_name,
                              **(repo_kwargs or {}))
        other, other_top = make_repo(tmp, branch="main", name="wt-other")
        if callable(command):
            command = command(top, other_top)
        if callable(comments):
            comments = comments(top)
        pr_list = ([{"number": 7, "html_url": "https://github.com/Morrison-Lab/"
                     "test-repo/pull/7",
                     **({"updated_at": pr_updated_at} if pr_updated_at
                        else {})}] if prs == "open" else [])
        data = {"pulls?state=open": "FAIL" if gh_fail else pr_list,
                "/comments": comments or [],
                "/activity": activity if activity is not None else []}
        data_path = os.path.join(tmp, "data.json")
        fake_path = os.path.join(tmp, "fakegh.py")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        with open(fake_path, "w", encoding="utf-8") as f:
            f.write(FAKE_GH)
        e = dict(os.environ)
        e.pop("ALLOW_UNCLAIMED_PR_WORK", None)
        e["FAKE_GH_DATA"] = data_path
        log_path = os.path.join(tmp, "requests.log")
        e["FAKE_GH_LOG"] = log_path
        e["PR_CLAIM_GH_CMD"] = (f'"{sys.executable.replace(chr(92), "/")}" '
                                f'"{fake_path.replace(chr(92), "/")}"')
        e.update(env or {})
        payload = {"tool_name": tool, "tool_input": {"command": command},
                   "cwd": other if cwd_other else repo, "session_id": SID}
        payload.update(extra_payload or {})
        stdin = stdin_raw if stdin_raw is not None else json.dumps(payload)
        r = subprocess.run([sys.executable, SUBJECT], input=stdin,
                           capture_output=True, text=True, env=e, timeout=60)
        out = r.stdout.strip()
        spec = json.loads(out)["hookSpecificOutput"] if out else {}
        got = ("deny" if spec.get("permissionDecision") == "deny"
               else "ctx" if spec.get("additionalContext") else None)
        ok = got == expect and r.returncode == 0
        if ok and expect_paths:
            requested = ""
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8") as f:
                    requested = f.read()
            ok = all(p in requested for p in expect_paths)
            if not ok:
                FAILURES.append(f"{name}: requested paths lacked "
                                f"{expect_paths}: {requested!r}")
                return
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
run("D3 claim without session identity only warns", COMMIT, "ctx",
    comments=[claim()], check_in_ctx="names no session")
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

def real_commit_case(name, pick_sha, expect_warning):
    """A push whose `after` is a REAL commit of the test repo.

    `pick_sha(repo)` returns it: HEAD (own push, an ancestor) or the tip of a
    side branch (a real commit that is NOT an ancestor of HEAD). A made-up SHA
    would pass through `merge-base`'s exit 128 (unknown object) instead, which
    is a different branch of the hook.
    """
    COUNT[0] += 1
    with tempfile.TemporaryDirectory() as tmp:
        repo, top = make_repo(tmp)
        sha = pick_sha(repo)
        data = {"pulls?state=open": [{"number": 7, "html_url": "u"}],
                "/comments": mine(top),
                "/activity": [{"activity_type": "push",
                               "timestamp": "2026-09-30T22:00:00Z",
                               "after": sha, "actor": {"login": "me"}}]}
        dp, fp = os.path.join(tmp, "d.json"), os.path.join(tmp, "f.py")
        with open(dp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(FAKE_GH)
        e = dict(os.environ, FAKE_GH_DATA=dp,
                 FAKE_GH_LOG=os.path.join(tmp, "requests.log"),
                 PR_CLAIM_GH_CMD=(f'"{sys.executable.replace(chr(92), "/")}" '
                                  f'"{fp.replace(chr(92), "/")}"'))
        e.pop("ALLOW_UNCLAIMED_PR_WORK", None)
        r = subprocess.run([sys.executable, SUBJECT], capture_output=True,
                           text=True, env=e, input=json.dumps(
                               {"tool_name": "Bash", "cwd": repo,
                                "session_id": SID,
                                "tool_input": {"command": PUSH}}))
        warned = "NOT in your local history" in r.stdout
        if warned != expect_warning:
            FAILURES.append(f"{name}: warned={warned}, expected "
                            f"{expect_warning}: {r.stdout!r} {r.stderr!r}")


def head_sha(repo):
    return sh(repo, "git", "rev-parse", "HEAD")


def side_branch_sha(repo):
    sh(repo, "git", "checkout", "-q", "-b", "side")
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "side")
    sha = sh(repo, "git", "rev-parse", "HEAD")
    sh(repo, "git", "checkout", "-q", "feat/x")
    return sha


real_commit_case("P6 own push (real HEAD commit) is silent", head_sha, False)
real_commit_case("P7 real non-ancestor commit warns", side_branch_sha, True)

# --- review round 1 (adversarial-reviewer, 2026-09-30) ----------------------
# Nested worktree path: a claim naming a checkout UNDER mine is not mine.
run("R1-1 claim names a worktree nested under mine", COMMIT, "deny",
    comments=lambda top: [claim(f"Session worktree: `{top}/.claude/worktrees/x`")])
# Session-id prefix collision.
run("R1-2 claim names a longer session id", COMMIT, "deny",
    comments=[claim(f"Session id: `{SID}B`")])
# Pagination join: a body containing `] [` must survive, and an empty page
# must not corrupt the decode.
run("R1-3 multi-page comments, `] [` in a body", COMMIT, None,
    comments={"pages": [[claim("notes [a] [b] [c]")],
                        [claim(f"Session id: `{SID}`")]]})
run("R1-4 empty first page", COMMIT, None,
    comments={"pages": [[], [claim(f"Session id: `{SID}`")]]})
# Directory: cd and git -C move the repository the command acts on.
run("R1-5 cd to a main checkout before commit is silent",
    lambda top, other: f"cd '{other}' && git commit -m x", None)
run("R1-6 git -C a main checkout is silent",
    lambda top, other: f"git -C '{other}' commit -m x", None)
run("R1-7 cwd on main but git -C the claimed-less PR checkout denies",
    lambda top, other: f"git -C '{top}' commit -m x", "deny", cwd_other=True)
run("R1-8 cd - is indeterminate: visible fail-open", "cd - && " + COMMIT,
    "ctx", check_in_ctx="cannot tell which repository")
run("R1-9 --git-dir is indeterminate: visible fail-open",
    "git --git-dir=/elsewhere/.git commit -m x", "ctx",
    check_in_ctx="cannot tell which repository")
# Dry-run grammar: -n on push, last occurrence wins, -n on commit is --no-verify.
run("R1-10 push -n is a dry run", "git push -n origin feat/x", None)
run("R1-11 --dry-run --no-dry-run is a live push", "git push --dry-run "
    "--no-dry-run origin feat/x", "deny")
run("R1-12 commit -n is --no-verify, not a dry run", "git commit -n -m x",
    "deny")
run("R1-13 commit --dry-run creates nothing", "git commit --dry-run", None)
# Activity read failure must not discard the claim outcomes.
run("R1-14 activity failure is a visible note", PUSH, "ctx", comments=mine,
    activity="FAIL", check_in_ctx="could not read the forge activity")
run("R1-15 activity failure keeps the anonymous-claim note", PUSH, "ctx",
    comments=anon_newer, activity="FAIL", check_in_ctx="names no session")
# Claim recognition: a release or a stray "hold off" is not a claim.
run("R1-16 release comment naming this session is not a claim", COMMIT, "deny",
    comments=[{"body": f"Was working on this; you can stop having to hold "
                       f"off now --- unclaiming. Session id: `{SID}`\n\n{MARKER}",
               "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}])
run("R1-17 'no need to hold off' status comment is not a claim", COMMIT, "deny",
    comments=[{"body": f"No need to hold off. Session id: `{SID}`\n\n{MARKER}",
               "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}])
# Message split: a standing peer claim gets stand-down advice, not "post a claim".
run("R1-18 peer claim: stand down, do not post over it", COMMIT, "deny",
    comments=[claim("Session id: `session_other_BBBB`")],
    check_in_ctx="Do not post a competing")
run("R1-19 no claim at all: how to post one", COMMIT, "deny",
    check_in_ctx="gh pr comment 7")

# --- review round 2 --------------------------------------------------------
# Claim wordings emitted elsewhere in skills/ must still count.
ardi_claim = lambda top: [{
    "body": f"Driving this PR to clean --- please hold off until done.\n\n"
            f"Session id: `{SID}`\n\n{MARKER}",
    "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}]
review_claim = lambda top: [{
    "body": f"claude is reviewing this PR --- please hold off on pushing to "
            f"this branch until the review comment lands.\n\nSession id: "
            f"`{SID}`\n\n{MARKER}",
    "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}]
run("R2-1 ardi wording claim counts", COMMIT, None, comments=ardi_claim)
run("R2-2 review-only wording claim counts", COMMIT, None,
    comments=review_claim)
# Path boundaries: sentence-final period is fine, a left-extension is not.
run("R2-3 worktree path ending a sentence (no backticks)", COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: {top}.")])
run("R2-4 worktree path inside a longer path is not mine", COMMIT, "deny",
    comments=lambda top: [claim(f"Session worktree: `x{top}`")])
# Push refspec: the destination branch is the one checked.
run("R2-5 HEAD:refs/heads/foo checks foo", "git push origin HEAD:refs/heads/foo",
    "deny", expect_paths=["head=Morrison-Lab:foo"])
run("R2-6 plain refspec checks that branch", "git push origin other-branch",
    "deny", expect_paths=["head=Morrison-Lab:other-branch"])
run("R2-7 a tag push is not a branch", "git push origin refs/tags/v1", None)
run("R2-8 git push -u origin HEAD checks the current branch",
    "git push -u origin HEAD", "deny", expect_paths=["head=Morrison-Lab:feat/x"])
# URL encoding and remote shapes.
run("R2-9 branch with # is encoded in the pulls query", COMMIT, "deny",
    branch="feat/a#b", expect_paths=["head=Morrison-Lab:feat/a%23b"])
run("R2-10 branch with # is encoded in the activity query", "git push origin HEAD",
    None, branch="feat/a#b", comments=mine,
    expect_paths=["ref=refs/heads/feat/a%23b"])
run("R2-11 remote URL with a trailing slash", COMMIT, "deny",
    repo_kwargs={"remote": "https://github.com/Morrison-Lab/test-repo/"})
# Activity cap and total budget.
many = [{"activity_type": "push", "timestamp": "2026-09-30T22:00:00Z",
         "after": "d" * 40, "actor": {"login": "peer"}}] * 14
run("R2-12 many foreign pushes are capped", PUSH, "ctx", comments=mine,
    activity=many, check_in_ctx="more pushes not examined")
run("R2-13 a spent time budget is a visible fail-open", COMMIT, "ctx",
    env={"PR_CLAIM_TOTAL_BUDGET": "1", "FAKE_GH_SLEEP": "4"},
    check_in_ctx="could not verify")

# --- review round 3 --------------------------------------------------------
gitbash = lambda top: ("/" + top[0].lower() + top[2:]
                       if re.match(r"[A-Za-z]:/", top) else top)
run("R3-1 Git Bash /c/... spelling of the worktree matches", COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: `{gitbash(top)}`")])
run("R3-2 older anonymous claim plus my own claim is silent", COMMIT, None,
    comments=lambda top: [claim(at="2026-09-30T19:00:00Z"),
                          claim(f"Session worktree: `{top}`",
                                at="2026-09-30T20:00:00Z")])
# A commit inside `bash -c` starts in an unknowable directory: visible, not silent.
run("R3-3 commit inside bash -c is a visible fail-open",
    "bash -c 'git commit -m x'", "ctx", check_in_ctx="cannot tell which")
run("R3-4 bash -c that cd's to an absolute main checkout is silent",
    lambda top, other: f"bash -c \"cd '{other}' && git commit -m x\"", None)
# Option values are not options.
run("R3-5 a commit message equal to --dry-run is still a commit",
    "git commit -m --dry-run", "deny")
run("R3-6 -am message value is skipped too", 'git commit -am "--dry-run"', "deny")
# Push shapes.
run("R3-7 delete by colon refspec is skipped", "git push origin :old", None)
run("R3-8 --tags pushes a ref set: skipped", "git push --tags origin", None)
run("R3-9 a non-origin remote is skipped", "git push fork feat/x", None)
run("R3-10 bare --signed does not swallow the remote",
    "git push --signed origin feat/x", "deny",
    expect_paths=["head=Morrison-Lab:feat/x"])

# --- review round 4 --------------------------------------------------------
from datetime import datetime, timezone  # noqa: E402

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
peer = lambda top: [claim("Session id: `session_other_BBBB`")]
run("R4-1 push to a $VAR destination falls back to the current branch",
    'git push origin "$BRANCH"', "deny",
    expect_paths=["head=Morrison-Lab:feat/x"])
run("R4-2 HEAD:$B destination falls back too", "git push origin HEAD:$B",
    "deny", expect_paths=["head=Morrison-Lab:feat/x"])
run("R4-3 anonymous-only claim still gets the push activity warning", PUSH,
    "ctx", comments=[claim()], activity=foreign,
    check_in_ctx="NOT in your local history")
run("R4-4 peer claim on a PR idle for years is treated as lapsed", COMMIT,
    "ctx", comments=peer, pr_updated_at="2020-01-01T00:00:00Z",
    check_in_ctx="treated as lapsed")
run("R4-5 peer claim on a PR touched just now still denies", COMMIT, "deny",
    comments=peer, pr_updated_at=NOW)
run("R4-6 releasing-my-claim comment is not a claim", COMMIT, "deny",
    comments=[{"body": f"Releasing my claim, hold off no more. Session id: "
                       f"`{SID}`\n\n{MARKER}",
               "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}])
run("R4-7 ssh host-alias remote", COMMIT, "deny",
    repo_kwargs={"remote": "git@github.com-work:Morrison-Lab/test-repo.git"})

# --- review round 5 -------------------------------------------------------
run("R5-1 a claim that says it WILL release the claim is still a claim",
    COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: `{top}`. I will release "
                                f"the claim when done.")])
run("R5-2 the retired 'paws off released' wording is a release", COMMIT,
    "deny", comments=[{"body": f"Done --- paws off released. Session id: "
                               f"`{SID}`\n\n{MARKER}",
                       "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}])
run("R5-3 'PR is free' is a release", COMMIT, "deny",
    comments=[{"body": f"PR is free; hold off no more. Session id: `{SID}`"
                       f"\n\n{MARKER}",
               "created_at": "2026-09-30T20:00:00Z", "html_url": "u"}])
run("R5-4 worktree path with a trailing slash matches", COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: {top}/ (this one)")])
run("R5-5 a path extended by a child directory does not match", COMMIT,
    "deny", comments=lambda top: [claim(f"Session worktree: {top}/sub/dir")])
run("R5-6 a different worktree's claim (e.g. a parent's) reads as a peer's",
    COMMIT, "deny",
    comments=lambda top: [claim("Session worktree: `/somewhere/else/entirely`")],
    check_in_ctx="working this branch now")

# --- review round 6 -------------------------------------------------------
# Worktrees are named after issue slugs, and the repo's vocabulary includes the
# release terms: a path or id carrying one must not make a good claim fail.
run("R6-1 worktree named after a release term still matches", COMMIT, None,
    repo_name="fix-unclaim-wording",
    comments=lambda top: [claim(f"Session worktree: `{top}`")])
run("R6-2 worktree named 'pr-released' still matches", COMMIT, None,
    repo_name="pr-released",
    comments=lambda top: [claim(f"Session worktree: `{top}`")])
run("R6-3 session id containing a release term still matches", COMMIT, None,
    comments=[claim("Session id: `session_now-mergeable_1`")],
    extra_payload={"session_id": "session_now-mergeable_1"})
run("R6-4 'back off' wording is a claim", COMMIT, None,
    comments=lambda top: [claim(f"Session worktree: `{top}`",
                                phrase="back off")])
# Wrapped invocations resolve through strip_env (checked here, not assumed).
run("R6-5 /usr/bin/git commit", "/usr/bin/git commit -m x", "deny")
run("R6-6 timeout 60 git push", "timeout 60 git push origin feat/x", "deny")
run("R6-7 command git commit", "command git commit -m x", "deny")
# A directory that does not exist is a quiet pass, not a warning.
run("R6-8 cd into a missing directory", "cd /no/such/dir/at/all && " + COMMIT,
    None)

# A broken install (no scripts/lib beside the hook) must be visible, not inert.
COUNT[0] += 1
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "hooks"))
    lone = os.path.join(tmp, "hooks", "no-pr-work-without-claim.py")
    with open(SUBJECT, encoding="utf-8") as src, open(
            lone, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    r = subprocess.run([sys.executable, lone], capture_output=True, text=True,
                       input=json.dumps({"tool_name": "Bash", "cwd": tmp,
                                         "tool_input": {"command": COMMIT}}))
    quiet = subprocess.run([sys.executable, lone], capture_output=True,
                           text=True, input=json.dumps(
                               {"tool_name": "Bash", "cwd": tmp,
                                "tool_input": {"command": "ls"}}))
    if "could not be loaded" not in r.stdout:
        FAILURES.append(f"R4-8 broken install must warn on a git command: "
                        f"{r.stdout!r} {r.stderr!r}")
    if quiet.stdout.strip():
        FAILURES.append(f"R4-9 broken install must stay quiet on `ls`: "
                        f"{quiet.stdout!r}")

print(f"{COUNT[0]} cases, {len(FAILURES)} failures")
for f in FAILURES:
    print("FAIL", f)
sys.exit(1 if FAILURES else 0)
