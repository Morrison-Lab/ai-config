"""Test the no-history-compare-in-shallow-clone guard.

Every case runs against throwaway repositories built in a temp directory:
an origin with a branch that forks from an early commit, a FULL clone of it,
and a SHALLOW (`--depth 1`) clone of it. No real repository is read or written.

The negative controls come first in spirit: the same command must be allowed
in the full clone and refused in the shallow one, so a guard that refuses
everything, or nothing, fails here.

Run:  python3 hooks/test-no-history-compare-in-shallow-clone.py \\
          hooks/no-history-compare-in-shallow-clone.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-history-compare-in-shallow-clone.py")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def build(root):
    origin = os.path.join(root, "origin")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    for i in range(5):
        with open(os.path.join(origin, "f.txt"), "w") as fh:
            fh.write(str(i))
        git("add", "f.txt", cwd=origin)
        git("commit", "-q", "-m", f"c{i}", cwd=origin)
        if i == 1:
            git("branch", "side", cwd=origin)
    full = os.path.join(root, "full")
    shallow = os.path.join(root, "shallow")
    git("clone", "-q", "--no-local", origin, full, cwd=root)
    git("clone", "-q", "--depth", "1", "--no-single-branch",
        "file://" + origin, shallow, cwd=root)
    return full, shallow


def run(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, (command, res.returncode, res.stderr)
    if not res.stdout.strip():
        return None
    return json.loads(res.stdout)["hookSpecificOutput"].get("permissionDecision")


REFUSED_IN_SHALLOW = [
    "git merge-base origin/main origin/side",
    "git rev-list --count origin/main..origin/side",
    "git log --reverse --format=%s origin/main | head -1",
    "git log --oneline origin/main...origin/side",
    "git branch -r --merged origin/main",
    "git for-each-ref --contains origin/side refs/remotes",
    "git cherry origin/main origin/side",
    "git bundle create /tmp/x.bundle origin/side",
    "git push origin --delete side",
    "git push -d origin side",
    "git push origin :side",
    "echo start && git rev-list --count origin/main..origin/side",
]

ALLOWED_EVERYWHERE = [
    "git log -5 --oneline",
    "git status",
    "git fetch --unshallow origin",
    "git push origin HEAD:side",
    "echo 'git merge-base a b'",
    "ALLOW_SHALLOW_HISTORY=1 git merge-base origin/main origin/side",
]


def main():
    failures = []
    with tempfile.TemporaryDirectory() as root:
        full, shallow = build(root)
        flag = subprocess.run(["git", "-C", shallow, "rev-parse", "--is-shallow-repository"],
                              capture_output=True, text=True).stdout.strip()
        assert flag == "true", "fixture: shallow clone is not shallow"

        for cmd in REFUSED_IN_SHALLOW:
            if run(cmd, shallow) != "deny":
                failures.append(f"not refused in shallow clone: {cmd}")
            if run(cmd, full) is not None:
                failures.append(f"refused in FULL clone (false positive): {cmd}")
        for cmd in ALLOWED_EVERYWHERE:
            if run(cmd, shallow) is not None:
                failures.append(f"refused in shallow clone (false positive): {cmd}")

        # Directory resolution: `git -C <shallow>` and `cd <shallow> &&` from a
        # full-clone cwd are refused; `cd <full> &&` from a shallow cwd is not.
        if run(f"git -C {shallow} merge-base origin/main origin/side", full) != "deny":
            failures.append("git -C <shallow> not refused")
        if run(f"cd {shallow} && git merge-base origin/main origin/side", full) != "deny":
            failures.append("cd <shallow> && ... not refused")
        if run(f"cd {full} && git merge-base origin/main origin/side", shallow) is not None:
            failures.append("cd <full> && ... refused from a shallow cwd")
        # Outside any repository: silent.
        if run("git merge-base a b", root) is not None:
            failures.append("refused outside a repository")
        # Non-Bash tool: silent.
        res = subprocess.run([sys.executable, HOOK], input=json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": shallow}),
            capture_output=True, text=True)
        if res.stdout.strip():
            failures.append("fired on a non-Bash tool")

        # After unshallowing, the same command is allowed.
        git("fetch", "-q", "--unshallow", "origin", cwd=shallow)
        if run("git merge-base origin/main origin/side", shallow) is not None:
            failures.append("still refused after --unshallow")

    total = len(REFUSED_IN_SHALLOW) * 2 + len(ALLOWED_EVERYWHERE) + 6
    if failures:
        print("\n".join(failures))
        print(f"FAIL: {len(failures)} of {total} checks")
        return 1
    print(f"ok: {total} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
