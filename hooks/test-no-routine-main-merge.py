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

    M = " git merge origin/main"
    deny = [  # (b) that does not hold comes last; a value counts only on the merge.
        M[1:], "git merge --no-edit origin/main", "git merge -m 'sync' origin/main 2>&1 | tail -1",
        "git merge refs/remotes/origin/main", "git merge origin", "git merge origin/HEAD",
        "git pull origin main", "git pull --no-rebase origin main", "git -C . merge origin/main",
        "bash -c 'git merge origin/main'", "cd / && cd " + repo + " &&" + M,
        "MERGE_MAIN_FOR='#99'" + M, "MERGE_MAIN_FOR=" + M, "MERGE_MAIN_FOR=1" + M,
        "MERGE_MAIN_FOR=yes" + M, "MERGE_MAIN_FOR=deadbeefdead" + M, "MERGE_MAIN_FOR='#42' true &&" + M]
    allow = [  # Not main (own remote, a feature branch, no-ops), then (b) holding.
        "git pull", "git pull origin pr", "git merge --abort", "git merge --continue",
        "git log origin/main", "echo" + M, "git merge origin/nosuch",
        f"MERGE_MAIN_FOR={fix[:10]}" + M, "MERGE_MAIN_FOR='#42'" + M, "MERGE_MAIN_FOR=42" + M,
        "MERGE_MAIN_FOR=Morrison-Lab/x#42" + M, "MERGE_MAIN_FOR='#42,#43'" + M]
    for command, want in [(c, "deny") for c in deny] + [(c, "allow") for c in allow]:
        check(command, run(command, repo), want)

    # A branch named */main is not main; a bare pull of an origin/main upstream is.
    git("switch", "-q", "-c", "feat/main", "--track", "origin/main", cwd=repo)
    git("switch", "-q", "-c", "ci/master", "pr", cwd=repo)
    git("branch", "-q", "--set-upstream-to=origin/main", cwd=repo)
    for command, want in [("git merge feat/main", "allow"), ("git pull", "deny"),
                          ("git pull origin", "deny"), ("git pull upstream", "allow")]:
        check(command, run(command, repo), want)
    git("switch", "-q", "pr", cwd=repo)
    git("branch", "-D", "-q", "feat/main", "ci/master", cwd=repo)

    # A session-wide value does not pass by default.
    check("env value", run(M[1:], repo, env_extra={"MERGE_MAIN_FOR": "#42"}), "deny")

    # A commit already on the branch is not a reason to merge.
    pr_sha = git("rev-parse", "HEAD", cwd=repo)
    check("commit on branch", run(f"MERGE_MAIN_FOR={pr_sha[:10]}" + M, repo), "deny")

    # FETCH_HEAD holding main is main; holding the PR branch is not.
    git("fetch", "-q", "origin", "main", cwd=repo)
    check("FETCH_HEAD main", run("git merge FETCH_HEAD", repo), "deny")
    check("fetch then FETCH_HEAD", run("git fetch origin main && git merge FETCH_HEAD", repo), "deny")
    git("push", "-q", "origin", "pr", cwd=repo)
    git("fetch", "-q", "origin", "pr", cwd=repo)
    for command in ["git merge FETCH_HEAD", "git fetch origin pr && git merge FETCH_HEAD"]:
        check("own branch: " + command, run(command, repo), "allow")

    # Server-side updates name no reason.
    check("MCP update", run("", repo, tool="mcp__github__update_pull_request_branch"), "deny")
    for command, want in [("gh pr update-branch 12", "deny"), ("gh api repos/o/r/pulls/12", "allow"),
                          ("gh api -X PUT repos/o/r/pulls/12/update-branch", "deny")]:
        check(command, run(command, repo), want)

    # On main itself, pulling main is fine.
    git("switch", "-q", "main", cwd=repo)
    for command in ["git pull origin main", "git merge origin/main"]:
        check("on main: " + command, run(command, repo), "allow")
    git("switch", "-q", "pr", cwd=repo)

    # Already up to date: nothing changes.
    git("merge", "-q", "--no-edit", "origin/main", cwd=repo)
    check("up to date", run("git merge origin/main", repo), "allow")

    # main moved on and nothing has fetched it yet: the local origin/main is an
    # ancestor of HEAD, but a command that fetches first still brings main in.
    commit(origin, "f.txt", "f\n", "Unfetched content (#44)")
    F = "git fetch origin && git merge "
    for command, want in [("git pull origin main", "deny"), ("git merge origin/main", "allow"),
                          ("git fetch origin main && git merge FETCH_HEAD", "deny"),
                          ("git fetch origin main &&" + M, "deny"), (F + "origin", "deny"),
                          (F + "origin/HEAD", "deny"), (F + "FETCH_HEAD", "deny"),
                          ("git fetch && git merge FETCH_HEAD", "deny"),
                          ("git fetch origin pr && git merge FETCH_HEAD", "allow")]:
        check("unfetched: " + command, run(command, repo), want)
    git("branch", "-q", "--set-upstream-to=origin/main", cwd=repo)
    check("unfetched: bare pull", run("git pull", repo), "deny")
    git("branch", "-q", "--unset-upstream", cwd=repo)
    # A single-branch clone has no local origin/main; a pull still fetches it.
    git("update-ref", "-d", "refs/remotes/origin/main", cwd=repo)
    check("no local ref: pull", run("git pull origin main", repo), "deny")

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
    check("conflict pull", run("git pull origin main", repo), "deny")  # fetches first

    # origin/HEAD naming another default branch counts as main.
    git("switch", "-q", "-c", "trunk", "main", cwd=origin)
    commit(origin, "t.txt", "t\n", "trunk work")
    git("fetch", "-q", "origin", cwd=repo)
    git("remote", "set-head", "origin", "trunk", cwd=repo)
    git("switch", "-q", "-c", "pr2", "origin/main", cwd=repo)
    commit(repo, "p2.txt", "p\n", "pr2")
    check("origin/HEAD default", run("git merge origin/trunk", repo), "deny")

    # Redirected repository: fail open.
    check("GIT_DIR", run("GIT_DIR=/nonexistent git merge origin/trunk", repo), "allow")

# (d): a stacked PR whose base merged into main and was deleted (ai-config#6001).
with tempfile.TemporaryDirectory() as root:
    origin = os.path.join(root, "origin")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    commit(origin, "a.txt", "a\n", "init")
    git("switch", "-q", "-c", "stackbase", cwd=origin)
    commit(origin, "s.txt", "s\n", "base work")
    git("switch", "-q", "-c", "other", "main", cwd=origin)
    commit(origin, "o.txt", "o\n", "other work")
    git("switch", "-q", "main", cwd=origin)
    repo = os.path.join(root, "repo")
    git("clone", "-q", origin, repo, cwd=root)
    git("switch", "-q", "-c", "child", "origin/stackbase", cwd=repo)
    commit(repo, "c.txt", "c\n", "child work")
    M = " git merge origin/main"
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #50 from Morrison-Lab/stackbase",
        "stackbase", cwd=origin)
    git("fetch", "-q", "origin", cwd=repo)
    check("base still on remote", run("MERGE_MAIN_FOR=base:stackbase" + M, repo), "deny")
    git("branch", "-q", "-D", "stackbase", cwd=origin)
    git("update-ref", "-d", "refs/remotes/origin/stackbase", cwd=repo)
    for command, want in [("MERGE_MAIN_FOR=base:stackbase" + M, "allow"),
                          (M[1:], "deny"), ("MERGE_MAIN_FOR=base:" + M, "deny"),
                          ("MERGE_MAIN_FOR=base:main" + M, "deny"),
                          ("MERGE_MAIN_FOR=base:nosuch" + M, "deny"),
                          ("MERGE_MAIN_FOR=base:other" + M, "deny")]:
        check("deleted base: " + command, run(command, repo), want)
    # A branch deleted without merging is not (d), even with a stale local ref.
    git("branch", "-q", "-D", "other", cwd=origin)
    check("deleted unmerged base", run("MERGE_MAIN_FOR=base:other" + M, repo), "deny")
    # A squash-merged base leaves only a stale tracking ref; it counts when main has it.
    git("switch", "-q", "-c", "sq", "main", cwd=origin)
    sq = commit(origin, "q.txt", "q\n", "squash base")
    git("switch", "-q", "main", cwd=origin)
    git("merge", "-q", "--ff-only", "sq", cwd=origin)
    git("fetch", "-q", "origin", cwd=repo)
    git("branch", "-q", "-D", "sq", cwd=origin)
    check("stale ref on main", run("MERGE_MAIN_FOR=base:sq" + M, repo), "allow")
    git("update-ref", "-d", "refs/remotes/origin/sq", cwd=repo)
    check("no trace of base", run("MERGE_MAIN_FOR=base:sq" + M, repo), "deny")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("no-routine-main-merge: all cases pass")
