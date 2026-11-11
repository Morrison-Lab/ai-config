"""Test the no-history-compare-in-shallow-clone guard.

Every case runs against throwaway repositories built in a temp directory:
an origin with a branch that forks from an early commit, a FULL clone of it,
and a SHALLOW (`--depth 1`) clone of it. No real repository is read or written.

Each refused command is also run in the full clone, where it must be allowed,
so a guard that refuses everything, or nothing, fails here.
Cases marked "mutation" pin a branch of the hook that an adversarial review
(ai-config#5323) found the first suite let a mutation remove unnoticed.

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

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=GIT_ENV)


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
    git("clone", "-q", "-b", "main", "--no-local", origin, full, cwd=root)
    git("clone", "-q", "-b", "main", "--depth", "1", "--no-single-branch",
        "file://" + origin, shallow, cwd=root)
    os.makedirs(os.path.join(shallow, "sub"))
    return full, shallow


def run(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (command, res.returncode, res.stderr)
    if not res.stdout.strip():
        return None
    return json.loads(res.stdout)["hookSpecificOutput"].get("permissionDecision")


REFUSED_IN_SHALLOW = [
    # The incident's own commands.
    "git merge-base origin/main origin/side",
    "git rev-list --count origin/main..origin/side",
    "git log --reverse --format=%s origin/main | head -1",
    # Ranges in other spellings.
    "git log --oneline origin/main...origin/side",
    "git log ^origin/main origin/side",
    "git log origin/side --not origin/main",
    "git rev-list -n 5 origin/main..origin/side",
    # First-commit reads.
    "git log --root --oneline",                       # mutation: --root
    "git log --max-parents=0 origin/main",
    "git log --format=%cs origin/main | tail -1",
    "git rev-list --max-parents=0 HEAD",
    "git rev-list --all",
    # Ref filters, full and abbreviated.
    "git branch -r --merged origin/main",
    "git branch -r --merged=origin/main",             # mutation: --merged= form
    "git branch -r --merg origin/main",
    "git branch -a --contai HEAD",
    "git for-each-ref --contains origin/side refs/remotes",
    "git tag --merged HEAD",                          # mutation: tag
    "git cherry origin/main origin/side",
    "git bundle create /tmp/x.bundle origin/side",
    # Remote deletion.
    "git push origin --delete side",
    "git push origin --del side",
    "git push -d origin side",
    "git push -fd origin side",                       # mutation: short cluster
    "git push origin :side",
    "git push origin +:side",
    "git push --prune origin refs/heads/*:refs/heads/*",
    "git push --mirror origin",
    # Placement and wrapping.
    "echo start && git rev-list --count origin/main..origin/side",
    "git -C sub merge-base origin/main origin/side",  # mutation: relative -C
    "bash -c 'git merge-base origin/main origin/side'",
    "sh -c \"git rev-list --count origin/main..origin/side\"",
    # The override covers only its own command.
    "ALLOW_SHALLOW_HISTORY=1 git status; git merge-base origin/main origin/side",
    # A failed cd leaves the shell where it was.
    "cd /nonexistent-dir-for-test; git merge-base origin/main origin/side",
    # A subshell's cd does not move the parent.
    "(cd / && true); git merge-base origin/main origin/side",
]

ALLOWED_EVERYWHERE = [
    "git log -5 --oneline",
    "git log -3 -- ../README.md",
    "git log --oneline -5 ../other/file",
    "git log -n 5 -- docs/a..b.md",
    "git log --author 'a..b' -3",
    "git log -S 'x..y' -2",
    "git log -G foo..bar -2",
    "git log --since 2026-01-01.. -3",
    "git log -1 --format=%H | tail -1",
    "git rev-list -n1 HEAD",
    "git rev-list -1 HEAD",
    "git rev-list --max-count=1 origin/main",
    "git status",
    "git branch -a",
    "git tag -l",
    "git fetch --unshallow origin",
    "git push origin HEAD:side",
    "git push -u origin side",
    "echo 'git merge-base a b'",
    "ALLOW_SHALLOW_HISTORY=1 git merge-base origin/main origin/side",
]


def main():
    failures = []
    checks = 0
    with tempfile.TemporaryDirectory() as root:
        full, shallow = build(root)
        flag = subprocess.run(["git", "-C", shallow, "rev-parse", "--is-shallow-repository"],
                              capture_output=True, text=True).stdout.strip()
        assert flag == "true", "fixture: shallow clone is not shallow"

        for cmd in REFUSED_IN_SHALLOW:
            checks += 2
            if run(cmd, shallow) != "deny":
                failures.append(f"not refused in shallow clone: {cmd}")
            if run(cmd, full) is not None:
                failures.append(f"refused in FULL clone (false positive): {cmd}")
        for cmd in ALLOWED_EVERYWHERE:
            checks += 1
            if run(cmd, shallow) is not None:
                failures.append(f"refused in shallow clone (false positive): {cmd}")

        def expect(cmd, cwd, want, label):
            nonlocal checks
            checks += 1
            if run(cmd, cwd) != want:
                failures.append(f"{label}: {cmd}")

        mb = "git merge-base origin/main origin/side"
        expect(f"git -C {shallow} {mb[4:]}", full, "deny", "git -C <shallow> not refused")
        expect(f"cd {shallow} && {mb}", full, "deny", "cd <shallow> not refused")
        expect(f"cd {full} && {mb}", shallow, None, "cd <full> refused from a shallow cwd")
        # mutation: a relative -C resolves against the cwd.
        expect(f"git -C shallow {mb[4:]}", root, "deny", "relative -C <shallow> not refused")
        expect(f"git -C full {mb[4:]}", root, None, "relative -C <full> refused")
        # mutation: an unresolvable cd makes the directory unknown, so skip.
        expect(f"cd $SOMEWHERE && {mb}", shallow, None, "unresolvable cd not skipped")
        # --git-dir and GIT_DIR name the repository, whatever the cwd.
        expect(f"git --git-dir={full}/.git {mb[4:]}", shallow, None, "--git-dir=<full> refused")
        expect(f"git --git-dir={shallow}/.git {mb[4:]}", full, "deny", "--git-dir=<shallow> not refused")
        expect(f"GIT_DIR={full}/.git {mb}", shallow, None, "GIT_DIR=<full> refused")
        # Outside any repository: silent.
        expect(mb, root, None, "refused outside a repository")
        # Non-Bash tool, malformed payloads: silent and exit 0.
        for raw in ('{"tool_name": "Read", "tool_input": {"file_path": "x"}}',
                    "not json", "[]", "null",
                    '{"tool_name": "Bash", "tool_input": {"command": ["git"]}}',
                    '{"tool_name": "Bash", "tool_input": {"command": "git log \'"}}'):
            checks += 1
            res = subprocess.run([sys.executable, HOOK], input=raw,
                                 capture_output=True, text=True, timeout=30)
            if res.returncode != 0 or res.stdout.strip():
                failures.append(f"malformed payload not silent: {raw}")

        # After unshallowing, the same command is allowed.
        git("fetch", "-q", "--unshallow", "origin", cwd=shallow)
        expect(mb, shallow, None, "still refused after --unshallow")

    if failures:
        print("\n".join(failures))
        print(f"FAIL: {len(failures)} of {checks} checks")
        return 1
    print(f"ok: {checks} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
