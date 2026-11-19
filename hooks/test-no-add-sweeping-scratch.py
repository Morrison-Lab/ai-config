"""Test no-add-sweeping-scratch on a real throwaway repo, so git answers.
Run: python3 hooks/test-no-add-sweeping-scratch.py hooks/no-add-sweeping-scratch.py"""
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
    env.pop("ALLOW_SCRATCH_ADD", None)
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
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    git("init", "-q", "-b", "main", cwd=repo)
    write(os.path.join(repo, "a.txt"))
    git("add", "a.txt", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    sub = os.path.join(repo, "sub")
    os.makedirs(sub)
    agent = os.path.join(repo, ".claude", "worktrees", "agent-1")
    os.makedirs(agent)
    git("init", "-q", "-b", "main", cwd=agent)
    write(os.path.join(agent, "f.txt"))
    git("add", "f.txt", cwd=agent)
    git("commit", "-q", "-m", "x", cwd=agent)
    for command, cwd, want in [
            ("git add -A", repo, "deny"),
            ("git add .", repo, "deny"),
            ("git add .claude", repo, "deny"),
            ("git add -A", sub, "deny"),
            ("git -C .. add -A", sub, "deny"),
            ("cd .. && git add .", sub, "deny"),
            ("git add a.txt", repo, "allow"),
            ("git add -u", repo, "allow"),
            ("git add -n -A", repo, "allow"),
            ("git add -An", repo, "allow"),
            ("git add -uv", repo, "allow"),
            ("git add -vu .", repo, "allow"),
            ("git add -Av", repo, "deny"),
            ("git add .", sub, "allow"),
            ("git add -A -- a.txt", repo, "allow"),
            ("git --git-dir=.git add -A", repo, "allow"),
            ("GIT_DIR=.git git add -A", repo, "allow"),
            ("ALLOW_SCRATCH_ADD=1 git add -A", repo, "allow"),
            ("echo git add -A", repo, "allow"),
            ("git add -A", root, "allow")]:
        check(f"{command} in {cwd}", run(command, cwd), want)
    check("env", run("git add -A", repo, env_extra={"ALLOW_SCRATCH_ADD": "1"}), "allow")
    check("non-shell tool", run("git add -A", repo, tool="Read"), "allow")
    write(os.path.join(repo, ".git", "index.lock"))  # read-only: a held lock
    check("index locked", run("git add -A", repo), "deny")  # changes nothing
    os.remove(os.path.join(repo, ".git", "index.lock"))
    write(os.path.join(repo, ".gitignore"), ".claude/worktrees/\n")
    check("ignored worktree", run("git add -A", repo), "allow")
    check("forced add of an ignored worktree",
          run("git add -f .claude/worktrees/agent-1", repo), "deny")
    check("forced cluster", run("git add -Af", repo), "deny")
    check("forced add of a plain file", run("git add -f a.txt", repo), "allow")
    cafe = os.path.join(repo, "café", "inner")
    os.makedirs(cafe)
    git("init", "-q", "-b", "main", cwd=cafe)
    check("non-ASCII embedded repo", run("git add -A", repo), "deny")

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("no-add-sweeping-scratch: all cases pass")
