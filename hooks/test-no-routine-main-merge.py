"""Test no-routine-main-merge on real throwaway repos, so git answers.
Run: python3 hooks/test-no-routine-main-merge.py hooks/no-routine-main-merge.py"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
FAILS = []


def git(*args, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True,
                          encoding="utf-8").stdout.strip()


def run(command, cwd, tool="Bash", env_extra=None):
    env = dict(os.environ)
    env.pop("MERGE_MAIN_FOR", None)
    env.update(env_extra or {})
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": cwd}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, encoding="utf-8")
    if proc.returncode != 0 or not proc.stdout.strip():
        return "allow" if proc.returncode == 0 else "error:" + proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


def write(path, text="x\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def commit(cwd, path, text, msg):
    write(os.path.join(cwd, path), text)
    git("add", path, cwd=cwd)
    git("commit", "-q", "-m", msg, cwd=cwd)
    return git("rev-parse", "HEAD", cwd=cwd)


with tempfile.TemporaryDirectory() as root:
    origin = os.path.join(root, "origin")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    commit(origin, "a.txt", "a\n", "init")
    commit(origin, "c.txt", "base\n", "add c")
    repo = os.path.join(root, "repo")
    git("clone", "-q", "-b", "main", origin, repo, cwd=root)
    git("switch", "-q", "-c", "pr", cwd=repo)
    commit(repo, "b.txt", "b\n", "pr work")

    # main moves on with content only, so a merge is routine.
    fix = commit(origin, "d.txt", "d\n", "Fix the widget (#42)")
    other = commit(origin, "e.txt", "e\n", "Unrelated content (#43)")
    git("fetch", "-q", "origin", cwd=repo)

    for command, want in [
            ("git merge origin/main", "deny"),
            ("git merge --no-edit origin/main", "deny"),
            ("git merge -m 'sync' origin/main 2>&1 | tail -1", "deny"),
            ("git merge refs/remotes/origin/main", "deny"),
            ("git pull origin main", "deny"),
            ("git pull --no-rebase origin main", "deny"),
            ("git -C . merge origin/main", "deny"),
            ("bash -c 'git merge origin/main'", "deny"),
            ("cd / && cd " + repo + " && git merge origin/main", "deny"),
            # Not main: the PR branch's own remote, a feature branch, no-ops.
            ("git pull", "allow"),
            ("git pull origin pr", "allow"),
            ("git merge --abort", "allow"),
            ("git merge --continue", "allow"),
            ("git log origin/main", "allow"),
            ("echo git merge origin/main", "allow"),
            ("git merge origin/nosuch", "allow"),
            # (b): the named fix is on main and missing from the branch.
            (f"MERGE_MAIN_FOR={fix[:10]} git merge origin/main", "allow"),
            ("MERGE_MAIN_FOR='#42' git merge origin/main", "allow"),
            ("MERGE_MAIN_FOR=42 git merge origin/main", "allow"),
            ("MERGE_MAIN_FOR=Morrison-Lab/x#42 git merge origin/main", "allow"),
            ("MERGE_MAIN_FOR='#42,#43' git merge origin/main", "allow"),
            # (b) that does not hold is still denied.
            ("MERGE_MAIN_FOR='#99' git merge origin/main", "deny"),
            ("MERGE_MAIN_FOR= git merge origin/main", "deny"),
            ("MERGE_MAIN_FOR=1 git merge origin/main", "deny"),
            ("MERGE_MAIN_FOR=yes git merge origin/main", "deny"),
            ("MERGE_MAIN_FOR=deadbeefdead git merge origin/main", "deny"),
            # The value counts only on the merge command itself.
            ("MERGE_MAIN_FOR='#42' true && git merge origin/main", "deny"),
    ]:
        check(command, run(command, repo), want)

    # A local branch whose name only ends in /main is not main.
    # A bare pull on a branch that tracks origin/main pulls main.
    git("switch", "-q", "-c", "feat/main", "--track", "origin/main", cwd=repo)
    git("switch", "-q", "-c", "ci/master", "pr", cwd=repo)
    git("branch", "-q", "--set-upstream-to=origin/main", cwd=repo)
    for command, want in [("git merge feat/main", "allow"), ("git pull", "deny"),
                          ("git pull origin", "deny"), ("git pull upstream", "allow")]:
        check(command, run(command, repo), want)
    git("switch", "-q", "pr", cwd=repo)
    git("branch", "-D", "-q", "feat/main", "ci/master", cwd=repo)

    # A session-wide value does not pass by default.
    check("environment value ignored",
          run("git merge origin/main", repo, env_extra={"MERGE_MAIN_FOR": "#42"}),
          "deny")

    # A commit already on the branch is not a reason to merge.
    pr_sha = git("rev-parse", "HEAD", cwd=repo)
    check("named commit already on branch",
          run(f"MERGE_MAIN_FOR={pr_sha[:10]} git merge origin/main", repo), "deny")

    # FETCH_HEAD holding main is main; holding the PR branch is not.
    git("fetch", "-q", "origin", "main", cwd=repo)
    check("FETCH_HEAD main", run("git merge FETCH_HEAD", repo), "deny")
    check("fetch then FETCH_HEAD on one line",
          run("git fetch origin main && git merge --no-edit FETCH_HEAD", repo), "deny")
    git("push", "-q", "origin", "pr", cwd=repo)
    git("fetch", "-q", "origin", "pr", cwd=repo)
    check("FETCH_HEAD own branch", run("git merge --no-edit FETCH_HEAD", repo), "allow")
    check("fetch own branch then merge",
          run("git fetch origin pr && git merge --no-edit FETCH_HEAD", repo), "allow")

    # Server-side updates name no reason.
    check("MCP update branch",
          run("", repo, tool="mcp__github__update_pull_request_branch"), "deny")
    check("gh pr update-branch", run("gh pr update-branch 12", repo), "deny")
    check("gh api update-branch",
          run("gh api -X PUT repos/o/r/pulls/12/update-branch", repo), "deny")
    check("gh api other", run("gh api repos/o/r/pulls/12", repo), "allow")

    # On main itself, pulling main is fine.
    git("switch", "-q", "main", cwd=repo)
    check("on main", run("git pull origin main", repo), "allow")
    check("on main merge", run("git merge origin/main", repo), "allow")
    git("switch", "-q", "pr", cwd=repo)

    # Already up to date: nothing changes.
    git("merge", "-q", "--no-edit", "origin/main", cwd=repo)
    check("up to date", run("git merge origin/main", repo), "allow")

    # (c): main changed a workflow since the merge base.
    commit(origin, ".github/workflows/ci.yml", "on: push\n", "Add CI")
    git("fetch", "-q", "origin", cwd=repo)
    check("workflow drift", run("git merge origin/main", repo), "allow")
    git("merge", "-q", "--no-edit", "origin/main", cwd=repo)

    # (a): a conflict with main.
    commit(repo, "c.txt", "pr side\n", "pr edits c")
    commit(origin, "c.txt", "main side\n", "main edits c")
    git("fetch", "-q", "origin", cwd=repo)
    check("conflict", run("git merge origin/main", repo), "allow")
    check("conflict pull", run("git pull origin main", repo), "allow")

    # origin/HEAD naming another default branch counts as main.
    git("switch", "-q", "-c", "trunk", "main", cwd=origin)
    commit(origin, "t.txt", "t\n", "trunk work")
    git("fetch", "-q", "origin", cwd=repo)
    git("remote", "set-head", "origin", "trunk", cwd=repo)
    git("switch", "-q", "-c", "pr2", "origin/main", cwd=repo)
    commit(repo, "p2.txt", "p\n", "pr2")
    check("origin/HEAD default", run("git merge origin/trunk", repo), "deny")

    # Redirected repository: fail open.
    check("GIT_DIR redirect", run("GIT_DIR=/nonexistent git merge origin/trunk", repo),
          "allow")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("no-routine-main-merge: all cases pass")
