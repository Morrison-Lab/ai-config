"""Test no-bare-stash-pop on real throwaway repos, so git counts worktrees.
Run: python3 hooks/test-no-bare-stash-pop.py hooks/no-bare-stash-pop.py"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
FAILS = []


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   encoding="utf-8")


def make_repo(root, worktrees):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    git("init", "-q", "-b", "main", cwd=repo)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
        "--allow-empty", "-m", "init", cwd=repo)
    for n in range(worktrees - 1):
        git("worktree", "add", "-q", "-b", f"wt{n}",
            os.path.join(root, f"wt{n}"), cwd=repo)
    return repo


def run(command, cwd, tool="Bash", env_extra=None):
    env = dict(os.environ)
    env.pop("ALLOW_BARE_STASH_POP", None)
    env.update(env_extra or {})
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": cwd}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env,
                          encoding="utf-8")
    if proc.returncode != 0 or not proc.stdout.strip():
        return "allow" if proc.returncode == 0 else "error:" + proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


with tempfile.TemporaryDirectory() as multi_root, \
        tempfile.TemporaryDirectory() as single_root:
    multi = make_repo(multi_root, worktrees=2)
    single = make_repo(single_root, worktrees=1)
    wt = os.path.join(multi_root, "wt0")
    cases = [
        # Bare takes in a multi-worktree repo are refused, from either worktree.
        ("git stash pop", multi, "deny"),
        ("git stash apply", multi, "deny"),
        ("git stash pop", wt, "deny"),
        ("git stash pop --index", multi, "deny"),
        ("git stash pop -q", multi, "deny"),
        ("git stash && make && git stash pop", multi, "deny"),
        (f"cd {multi} && git stash pop", single_root, "deny"),
        (f"git -C {multi} stash pop", single_root, "deny"),
        ("git -C repo stash pop", multi_root, "deny"),
        ("FOO=1 git stash pop", multi, "deny"),
        ("git stash pop --", multi, "deny"),
        ("git -c a.b=c --no-pager stash pop", multi, "deny"),
        ("env git stash pop", multi, "deny"),
        ("git stash pop 2>&1", multi, "deny"),
        ("git stash pop -q 2>&1 | tail", multi, "deny"),
        ("git stash pop >/dev/null", multi, "deny"),
        ("git stash pop 2>/dev/null", multi, "deny"),
        ("git stash pop > out.txt", multi, "deny"),
        ("git stash pop &>/dev/null", multi, "deny"),
        ("sh -c 'git stash pop'", multi, "deny"),
        ('bash -c "git stash apply"', multi, "deny"),
        (f"(cd {multi} && git stash pop)", single_root, "deny"),
        # An explicit entry is allowed.
        ("git stash pop 'stash@{1}'", multi, "allow"),
        ("git stash apply 0", multi, "allow"),
        ('git stash apply "$sha"', multi, "allow"),
        ("git stash pop -- 'stash@{0}'", multi, "allow"),
        # Other verbs and other commands are not this guard's business.
        ("git stash push -u -m tag", multi, "allow"),
        ("git stash list", multi, "allow"),
        ("git stash drop", multi, "allow"),
        ("git stash show", multi, "allow"),
        ("git status", multi, "allow"),
        ("echo git stash pop", multi, "allow"),
        # A single-worktree repository is allowed; so are overrides.
        ("git stash pop", single, "allow"),
        (f"cd {single} && git stash pop", multi, "allow"),
        ("ALLOW_BARE_STASH_POP=1 git stash pop", multi, "allow"),
        # Fail open outside a repository and on a redirected repository.
        ("git stash pop", multi_root, "allow"),
        ("git --git-dir=/x/.git stash pop", multi, "allow"),
        ("GIT_DIR=/x/.git git stash pop", multi, "allow"),
        ("GIT_WORK_TREE=/x git stash pop", multi, "allow"),
        ("git --work-tree /x stash pop", multi, "allow"),
        ('cd "$X" && git stash pop', multi, "allow"),
        ("git stash pop --help", multi, "allow"),
        ("git stash pop 2> 'stash@{1}'", multi, "deny"),
        (f"(cd {single} && git stash pop)", multi, "allow"),
    ]
    for command, cwd, want in cases:
        check(f"{command} in {cwd}", run(command, cwd), want)
    check("env override", run("git stash pop", multi,
                              env_extra={"ALLOW_BARE_STASH_POP": "1"}), "allow")
    check("non-shell tool", run("git stash pop", multi, tool="Read"), "allow")
    # A worktree whose directory is gone is prunable and is not counted.
    git("worktree", "add", "-q", "-b", "gone", os.path.join(single_root, "g"),
        cwd=single)
    subprocess.run(["rm", "-rf", os.path.join(single_root, "g")], check=True)
    check("prunable", run("git stash pop", single), "allow")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("no-bare-stash-pop: all cases pass")
