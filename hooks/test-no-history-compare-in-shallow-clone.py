"""Test the no-history-compare-in-shallow-clone guard.

Every case runs against throwaway repositories built in a temp directory.
No real repository is read or written, and nothing is pushed anywhere.

The origin has `main` (c0..c4) and `side`, which points at c1, so `side` is
fully merged into main: the true `origin/main..origin/side` is empty.

- FULL: a full clone. Nothing may be refused here.
- SHALLOW: `--depth 1 --no-single-branch`, plus one local commit L on main.
  Every branch tip is a cut-off commit, so ancestry between branches is
  wrong, while `origin/main..HEAD` (just L) is right.
- DEEP3: `--depth 3 --no-single-branch`. side's history (c1, c0) is complete,
  but main's stops at c2, so `origin/main..origin/side` wrongly lists c1 and
  c0: the EXCLUDED side ran out of history. This is the case a check of the
  positive side alone would miss.

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
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=GIT_ENV).stdout


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def build(root):
    origin = os.path.join(root, "origin")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    for i in range(5):
        write(os.path.join(origin, "f.txt"), str(i))
        git("add", "f.txt", cwd=origin)
        git("commit", "-q", "-m", f"c{i}", cwd=origin)
        if i == 1:
            git("branch", "side", cwd=origin)
    full = os.path.join(root, "full")
    shallow = os.path.join(root, "shallow")
    deep3 = os.path.join(root, "deep3")
    git("clone", "-q", "-b", "main", "--no-local", origin, full, cwd=root)
    git("clone", "-q", "-b", "main", "--depth", "1", "--no-single-branch",
        "file://" + origin, shallow, cwd=root)
    git("clone", "-q", "-b", "main", "--depth", "3", "--no-single-branch",
        "file://" + origin, deep3, cwd=root)
    write(os.path.join(shallow, "local.txt"), "L")
    git("add", "local.txt", cwd=shallow)
    git("commit", "-q", "-m", "L", cwd=shallow)
    os.makedirs(os.path.join(shallow, "sub"))
    write(os.path.join(shallow, "a..b.txt"), "a file whose name holds two dots")
    return full, shallow, deep3


def run(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (command, res.returncode, res.stderr)
    if not res.stdout.strip():
        return None
    return json.loads(res.stdout)["hookSpecificOutput"].get("permissionDecision")


# Each must be refused in SHALLOW and allowed in FULL.
REFUSED_IN_SHALLOW = [
    # The incident's own commands.
    "git merge-base origin/main origin/side",
    "git rev-list --count origin/main..origin/side",
    "git log --reverse --format=%s origin/main | head -1",
    # Ranges whose walk reaches the cut-off, in every spelling.
    "git log --oneline origin/main...origin/side",
    "git log ^origin/main origin/side",
    "git log origin/side --not origin/main",
    "git rev-list -n 5 origin/main..origin/side",
    "git cherry origin/main origin/side",
    # Ranges and merge-base forms the guard cannot check.
    "git log origin/main..origin/side origin/main~0..HEAD",
    # Three endpoints, though the first two alone would walk safely.
    "git log origin/main..HEAD origin/side",
    "git merge-base --is-ancestor origin/side origin/main",
    # An option the guard cannot check, though the walk alone is safe.
    "git merge-base --octopus HEAD origin/main",
    # A range whose walk query fails is refused rather than guessed.
    "git log nosuchref..HEAD",
    "git branch -r | xargs -n1 git merge-base origin/main",
    # First-commit and whole-history reads.
    "git log --root --oneline",
    "git log --max-parents=0 origin/main",
    "git log --format=%cs origin/main | tail -1",
    "git log --oneline | wc -l",
    "git log --format=%cs origin/main | sort | head -1",
    "git log --format=%cs origin/main | grep . | tail -1",
    "git rev-list --max-parents=0 HEAD",
    "git rev-list --all",
    "git rev-list --count HEAD",
    "git rev-list --reverse HEAD",
    # Ref filters, full and abbreviated as git accepts them.
    "git branch -r --merged origin/main",
    "git branch -r --merged=origin/main",
    "git branch -r --merg origin/main",
    "git branch -r --me origin/main",
    "git branch -a --contai HEAD",
    "git for-each-ref --contains origin/side refs/remotes",
    "git tag --merged HEAD",
    "git for-each-ref --format='%(refname) %(ahead-behind:origin/main)' refs/remotes",
    "git show-branch origin/main origin/side",
    "git range-diff origin/main...origin/side",
    "git bundle create /tmp/x.bundle origin/side",
    # Pushes that can delete a remote ref.
    "git push origin --delete side",
    "git push origin --de side",
    "git push -d origin side",
    "git push -fd origin side",
    "git push origin :side",
    "git push origin +:side",
    "git push --prune origin refs/heads/*:refs/heads/*",
    "git push --mirror origin",
    "git push --mi origin",
    # Placement and wrapping.
    "echo start && git rev-list --count origin/main..origin/side",
    "bash -c 'git merge-base origin/main origin/side'",
    "sh -c \"git rev-list --count origin/main..origin/side\"",
    # The override covers only its own command.
    "ALLOW_SHALLOW_HISTORY=1 git status; git merge-base origin/main origin/side",
    # A failed cd leaves the shell where it was.
    "cd /nonexistent-dir-for-test; git merge-base origin/main origin/side",
    # A subshell's cd does not move the parent.
    "(cd / && true); git merge-base origin/main origin/side",
]

# Each must be allowed in SHALLOW (and so in FULL).
ALLOWED_IN_SHALLOW = [
    # Ranges whose walk stays inside the fetched history.
    "git log --oneline origin/main..HEAD",
    "git rev-list --count origin/main..HEAD",
    "git log --oneline @{u}..HEAD",
    "git log --oneline origin/main...HEAD",
    "git merge-base HEAD origin/main",
    "git merge-base --is-ancestor origin/main HEAD",
    # An ambiguous prefix (--contains, --color, --column, --copy) is
    # rejected by git itself, so it is not a ref filter.
    "git branch --co",
    "git cherry origin/main HEAD",
    # Limited reads, paths, and option values holding "..".
    "git log -5 --oneline",
    "git log --oneline | head -3",
    "git log --reverse -3 --format=%s",
    "git log -1 --format=%H | tail -1",
    "git log -3 -- ../README.md",
    "git log --oneline -5 ../other/file",
    "git log -n 5 -- docs/a..b.md",
    "git log -3 a..b.txt",
    "git log -3 ./a..b",
    "git log --author 'a..b' -3",
    "git log -S 'x..y' -2",
    "git log -G foo..bar -2",
    "git log --since 2026-01-01.. -3",
    "git rev-list -n1 HEAD",
    "git rev-list -1 HEAD",
    "git rev-list -n 1 HEAD",
    "git rev-list --max-count=1 origin/main",
    "git rev-list --max-count 1 origin/main",
    # Everyday commands.
    "git status",
    "git status -sb",
    "git branch -a",
    "git branch --color",
    "git tag -l",
    "git fetch --unshallow origin",
    "git push origin HEAD:side",
    "git push -u origin side",
    "git push --dry-run origin :side",
    "git push -n origin --delete side",
    "echo 'git merge-base a b'",
    "ALLOW_SHALLOW_HISTORY=1 git merge-base origin/main origin/side",
    # A nested shell after a cd starts somewhere unknown, so it is skipped.
    "cd sub; bash -c 'git merge-base origin/main origin/side'",
]


def main():
    failures = []
    checks = 0
    with tempfile.TemporaryDirectory() as root:
        full, shallow, deep3 = build(root)
        for repo in (shallow, deep3):
            flag = git("rev-parse", "--is-shallow-repository", cwd=repo).strip()
            assert flag == "true", f"fixture: {repo} is not shallow"
        # The fixture really answers wrongly where the test says it does.
        assert git("rev-list", "--count", "origin/main..origin/side", cwd=full).strip() == "0"
        assert git("rev-list", "--count", "origin/main..origin/side", cwd=shallow).strip() != "0"
        assert git("rev-list", "--count", "origin/main..origin/side", cwd=deep3).strip() != "0"

        def expect(cmd, cwd, want, label):
            nonlocal checks
            checks += 1
            if run(cmd, cwd) != want:
                failures.append(f"{label}: {cmd}")

        for cmd in REFUSED_IN_SHALLOW:
            expect(cmd, shallow, "deny", "not refused in shallow clone")
            expect(cmd, full, None, "refused in FULL clone (false positive)")
        for cmd in ALLOWED_IN_SHALLOW:
            expect(cmd, shallow, None, "refused in shallow clone (false positive)")
            expect(cmd, full, None, "refused in FULL clone (false positive)")

        # The excluded side ran out of history: refused.
        expect("git rev-list --count origin/main..origin/side", deep3, "deny",
               "deep3: truncated excluded side not refused")
        expect("git log --oneline origin/main..HEAD", deep3, None,
               "deep3: empty walk refused")

        mb = "git merge-base origin/main origin/side"
        expect(f"git -C {shallow} {mb[4:]}", full, "deny", "git -C <shallow> not refused")
        expect(f"git -C shallow {mb[4:]}", root, "deny", "relative -C <shallow> not refused")
        expect(f"git -C full {mb[4:]}", root, None, "relative -C <full> refused")
        expect(f"cd {shallow} && {mb}", full, "deny", "cd <shallow> not refused")
        expect(f"cd {full} && {mb}", shallow, None, "cd <full> refused from a shallow cwd")
        expect(f"cd $SOMEWHERE && {mb}", shallow, None, "unresolvable cd not skipped")
        expect(f"env -C {shallow} {mb}", full, "deny", "env -C <shallow> not refused")
        expect(f"env -C {full} {mb}", shallow, None, "env -C <full> refused")
        expect(f"git --git-dir={full}/.git {mb[4:]}", shallow, None, "--git-dir=<full> refused")
        expect(f"git --git-dir {full}/.git {mb[4:]}", shallow, None, "--git-dir <full> refused")
        expect(f"git --git-dir={shallow}/.git {mb[4:]}", full, "deny", "--git-dir=<shallow> not refused")
        expect(f"git --git-dir {shallow}/.git {mb[4:]}", full, "deny", "--git-dir <shallow> not refused")
        expect(f"GIT_DIR={full}/.git {mb}", shallow, None, "GIT_DIR=<full> refused")
        expect(f"git -c core.pager=cat -C {shallow} {mb[4:]}", full, "deny", "-c before -C mis-read")
        expect(mb, root, None, "refused outside a repository")

        for raw in ('{"tool_name": "Read", "tool_input": {"file_path": "x"}}',
                    "not json", "[]", "null",
                    '{"tool_name": "Bash", "tool_input": {"command": ["git"]}}',
                    '{"tool_name": "Bash", "tool_input": {"command": "git log \'"}}',
                    '{"tool_name": "Bash", "tool_input": {"command": "git log"}, "cwd": 5}'):
            checks += 1
            res = subprocess.run([sys.executable, HOOK], input=raw,
                                 capture_output=True, text=True, timeout=30)
            if res.returncode != 0 or res.stdout.strip():
                failures.append(f"malformed payload not silent: {raw}")

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
