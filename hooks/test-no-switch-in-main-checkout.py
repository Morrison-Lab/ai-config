"""Test no-switch-in-main-checkout on real throwaway repos, so git answers.
Run: python3 hooks/test-no-switch-in-main-checkout.py hooks/no-switch-in-main-checkout.py"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
FAILS = []


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=cwd, check=True, capture_output=True, encoding="utf-8")


def run(command, cwd, tool="Bash", env_extra=None):
    env = dict(os.environ)
    env.pop("ALLOW_MAIN_CHECKOUT_SWITCH", None)
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


def write(path, text="x\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


with tempfile.TemporaryDirectory() as root:
    main = os.path.join(root, "main")
    os.makedirs(main)
    git("init", "-q", "-b", "main", cwd=main)
    write(os.path.join(main, "a.txt"))
    git("add", "a.txt", cwd=main)
    git("commit", "-q", "-m", "init", cwd=main)
    git("branch", "feature", cwd=main)
    git("update-ref", "refs/remotes/origin/remote-only", "HEAD", cwd=main)
    sub = os.path.join(main, "sub")
    os.makedirs(sub)

    # One worktree: nothing else reads the checkout, so a switch passes.
    check("single worktree switch", run("git switch feature", main), "allow")
    check("single worktree checkout", run("git checkout feature", main), "allow")

    wt = os.path.join(root, "wt")
    git("worktree", "add", "-q", "-b", "other", wt, cwd=main)
    for command, cwd, want in [
            ("git switch feature", main, "deny"),
            ("git switch -c new", main, "deny"),
            ("git checkout feature", main, "deny"),
            ("git checkout -b new", main, "deny"),
            ("git checkout -B feature", main, "deny"),
            ("git checkout --detach", main, "deny"),
            ("git checkout -", main, "deny"),
            ("git checkout remote-only", main, "deny"),
            ("git checkout --no-guess remote-only", main, "allow"),
            ("git checkout feature", sub, "deny"),
            ("git -C .. checkout feature", sub, "deny"),
            ("cd ../main && git checkout feature", wt, "deny"),
            (f"git -C {main} switch feature", wt, "deny"),
            ("sh -c 'git checkout feature'", main, "deny"),
            ("git checkout -- a.txt", main, "allow"),
            ("git checkout a.txt", main, "allow"),
            ("git checkout .", main, "allow"),
            ("git checkout feature a.txt", main, "allow"),
            ("git checkout -p", main, "allow"),
            ("git switch -h", main, "allow"),
            ("git switch feature", wt, "allow"),
            ("git checkout feature", wt, "allow"),
            ("git status", main, "allow"),
            ("echo git switch feature", main, "allow"),
            ("git --git-dir=.git checkout feature", main, "allow"),
            ("GIT_DIR=.git git checkout feature", main, "allow"),
            ("ALLOW_MAIN_CHECKOUT_SWITCH=1 git switch feature", main, "allow"),
            ("sh -c 'ALLOW_MAIN_CHECKOUT_SWITCH=1 git switch feature'", main, "allow")]:
        check(f"{command} in {os.path.relpath(cwd, root)}", run(command, cwd), want)
    check("env override", run("git switch feature", main,
                              env_extra={"ALLOW_MAIN_CHECKOUT_SWITCH": "1"}), "allow")
    check("non-shell tool", run("git switch feature", main, tool="Read"), "allow")
    check("outside a repository", run("git switch feature", root), "allow")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("no-switch-in-main-checkout: all cases pass")
