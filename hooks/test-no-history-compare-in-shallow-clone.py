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
- FETCHED: `--depth 1` of main, then `feat` (forked at c2, commit Y, main
  merged in) fetched with no depth. main's old commits return through Y,
  the edge below main's cut-off stays hidden, and `origin/main..origin/feat`
  lists them as "ahead". No commit in that walk is a cut-off commit, so only
  their age gives them away (third review of ai-config#5323). `late` (forked
  at c3, commit Z, main merged in) is fetched too, which brings c3 back with
  its parent c2.
- BROKEN: `--depth 1` of main plus two local commits, the first of whose
  objects is deleted, so revisions resolve but the walk fails.

Commit dates rise one minute per commit, as real history does, except that
c4 shares c3's date, so the age rule is tested on a tie.

Run:  python3 hooks/test-no-history-compare-in-shallow-clone.py \\
          hooks/no-history-compare-in-shallow-clone.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HOOK = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-history-compare-in-shallow-clone.py")

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=GIT_ENV).stdout


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


_CLOCK = [1_700_000_000]


def commit(name, cwd, *extra, same_time=False):
    """Commit with a committer date one minute after the last one, so commit
    ages follow commit order as they do in real history. `same_time` reuses
    the last date, as a scripted or rebased commit can."""
    if not same_time:
        _CLOCK[0] += 60
    stamp = f"{_CLOCK[0]} +0000"
    subprocess.run(["git", "commit", "-q", "-m", name, *extra], cwd=cwd, check=True,
                   capture_output=True,
                   env={**GIT_ENV, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})


def build(root):
    origin = os.path.join(root, "origin")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    for i in range(5):
        write(os.path.join(origin, "f.txt"), str(i))
        git("add", "f.txt", cwd=origin)
        if i == 0:
            write(os.path.join(origin, "old.txt"), "old")
            git("add", "old.txt", cwd=origin)
        # mid.txt changes in c2 and c3 only: from feat in FETCHED, c3 is
        # hidden and the cut-off c4 lists as its last change; from late, c3
        # lists and ties c4's date.
        if i in (2, 3):
            write(os.path.join(origin, "mid.txt"), str(i))
            git("add", "mid.txt", cwd=origin)
        # c4 shares c3's date, so the age rule is tested on a tie.
        commit(f"c{i}", origin, same_time=(i == 4))
        if i == 1:
            git("branch", "side", cwd=origin)
        if i == 2:
            git("branch", "feat", cwd=origin)
    # feat: forked at c2, one commit Y, then main merged into it.
    git("checkout", "-q", "feat", cwd=origin)
    write(os.path.join(origin, "y.txt"), "Y")
    git("add", "y.txt", cwd=origin)
    commit("Y", origin)
    subprocess.run(["git", "merge", "-q", "--no-edit", "main"], cwd=origin, check=True,
                   capture_output=True,
                   env={**GIT_ENV, "GIT_AUTHOR_DATE": f"{_CLOCK[0] + 60} +0000",
                        "GIT_COMMITTER_DATE": f"{_CLOCK[0] + 60} +0000"})
    _CLOCK[0] += 60
    # late: forked at c3, one commit Z, then main merged into it.
    git("checkout", "-q", "-b", "late", "main~1", cwd=origin)
    write(os.path.join(origin, "z.txt"), "Z")
    git("add", "z.txt", cwd=origin)
    commit("Z", origin)
    subprocess.run(["git", "merge", "-q", "--no-edit", "main"], cwd=origin, check=True,
                   capture_output=True,
                   env={**GIT_ENV, "GIT_AUTHOR_DATE": f"{_CLOCK[0] + 60} +0000",
                        "GIT_COMMITTER_DATE": f"{_CLOCK[0] + 60} +0000"})
    _CLOCK[0] += 60
    git("checkout", "-q", "main", cwd=origin)
    full = os.path.join(root, "full")
    shallow = os.path.join(root, "shallow")
    deep3 = os.path.join(root, "deep3")
    fetched = os.path.join(root, "fetched")
    git("clone", "-q", "-b", "main", "--no-local", origin, full, cwd=root)
    git("clone", "-q", "-b", "main", "--depth", "1", "--no-single-branch",
        "file://" + origin, shallow, cwd=root)
    git("clone", "-q", "-b", "main", "--depth", "3", "--no-single-branch",
        "file://" + origin, deep3, cwd=root)
    # A shallow clone of main, then feat fetched with no depth: feat brings
    # main's old commits back through Y, but the edge below main's cut-off
    # stays hidden.
    git("clone", "-q", "-b", "main", "--depth", "1",
        "file://" + origin, fetched, cwd=root)
    git("fetch", "-q", "origin", "feat:refs/remotes/origin/feat", cwd=fetched)
    git("fetch", "-q", "origin", "late:refs/remotes/origin/late", cwd=fetched)
    # BROKEN: a shallow clone whose local history is missing a commit object,
    # so the revisions resolve but the walk itself fails.
    broken = os.path.join(root, "broken")
    git("clone", "-q", "-b", "main", "--depth", "1", "file://" + origin, broken, cwd=root)
    for name in ("L1", "L2"):
        write(os.path.join(broken, name), name)
        git("add", name, cwd=broken)
        commit(name, broken)
    gone = git("rev-parse", "HEAD~1", cwd=broken).strip()
    os.remove(os.path.join(broken, ".git", "objects", gone[:2], gone[2:]))
    write(os.path.join(shallow, "local.txt"), "L")
    git("add", "local.txt", cwd=shallow)
    commit("L", shallow)
    os.makedirs(os.path.join(shallow, "sub"))
    write(os.path.join(shallow, "a..b.txt"), "a file whose name holds two dots")
    skew = _build_skew(root)
    return full, shallow, deep3, fetched, broken, skew


def _build_skew(root):
    """SKEWO: r0 and r1 carry dates a day AHEAD of r2, their child, as a
    wrong clock gives. `b` forks at r1 (commit B), then merges r2. SKEW is a
    depth-1 clone of main (cut-off r2) with b fetched in full: main..b lists
    r1 and r0, which are newer than the cut-off, so only r0 having no parent
    shows that they may sit below it."""
    origin = os.path.join(root, "skewo")
    os.makedirs(origin)
    git("init", "-q", "-b", "main", cwd=origin)
    ahead = _CLOCK[0] + 86400

    def dated(name, stamp, *extra):
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", name, *extra],
                       cwd=origin, check=True, capture_output=True,
                       env={**GIT_ENV, "GIT_AUTHOR_DATE": f"{stamp} +0000",
                            "GIT_COMMITTER_DATE": f"{stamp} +0000"})

    dated("r0", ahead)
    dated("r1", ahead + 60)
    git("branch", "b", cwd=origin)
    _CLOCK[0] += 60
    dated("r2", _CLOCK[0])
    git("checkout", "-q", "b", cwd=origin)
    dated("B", ahead + 120)
    subprocess.run(["git", "merge", "-q", "--no-edit", "main"], cwd=origin, check=True,
                   capture_output=True,
                   env={**GIT_ENV, "GIT_AUTHOR_DATE": f"{ahead + 180} +0000",
                        "GIT_COMMITTER_DATE": f"{ahead + 180} +0000"})
    git("checkout", "-q", "main", cwd=origin)
    skew = os.path.join(root, "skew")
    git("clone", "-q", "-b", "main", "--depth", "1", "file://" + origin, skew, cwd=root)
    git("fetch", "-q", "origin", "b:refs/remotes/origin/b", cwd=skew)
    skew_full = os.path.join(root, "skew_full")
    git("clone", "-q", "-b", "main", "--no-local", origin, skew_full, cwd=root)
    return skew, skew_full


def run_full(command, cwd):
    """(decision, reason) for one command; (None, "") when the hook is silent."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (command, res.returncode, res.stderr)
    if not res.stdout.strip():
        return None, ""
    out = json.loads(res.stdout)["hookSpecificOutput"]
    return out.get("permissionDecision"), out.get("permissionDecisionReason", "")


def run(command, cwd):
    return run_full(command, cwd)[0]


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
    # Revision-set options are not option values: each read below lists
    # main's old commits as only on the remotes (fourth review).
    "git log --oneline --remotes ^origin/main",
    "git log --oneline --remotes --not origin/main",
    "git log --pretty origin/main..origin/side",
    "git log --oneline --all origin/main..HEAD",
    # Right here, but a range beside --remotes is refused unread.
    "git log -1 --remotes ^origin/main",
    # Two log reads and one head: the head limit is not credited to either.
    "git log --oneline | head -2; git log --oneline | wc -l",
    "git branch -r | xargs -n1 git merge-base origin/main",
    # First-commit and whole-history reads, and limited reads that run past
    # the cut-off (here HEAD is L, then the cut-off c4).
    "git log --root --oneline",
    "git log -5 --oneline",
    "git log --oneline | head -3",
    "git log --reverse -3 --format=%s",
    "git log --reverse -n 100000 --format=%cs origin/main | head -1",
    "git rev-list --count --max-count=100000 origin/main",
    "git rev-list --count HEAD | head -1",
    "git log --oneline origin/main | awk 'END{print NR}'",
    "git log --oneline origin/main | grep -c .",
    "git log --oneline | grep c0",
    "git log --format=%cs origin/main",
    "git shortlog -sn origin/main",
    "git shortlog -sn HEAD | head -1",
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
    "git push --dry-run --no-dry-run origin :side",
    # A cut-off commit's diff shows it adding every file.
    "git log --oneline -n 2 --stat",
    "git log -2 --word-diff",
    "git log -1 --stat origin/main",
    "git show --stat origin/main",
    "git show origin/main",
    "git whatchanged -1 origin/main",
    # A head limit belongs to the read piped into head, not to other text.
    "grep -rn 'git log' /dev/null | head -5; git log --oneline | wc -l",
    "echo git log | head -5; git log --oneline | wc -l",
    "git log --oneline | head -1; git log --oneline | wc -l",
    # head after ';' reads its own input, not the log's output.
    "git log --oneline; head -1",
    "git log --oneline | head",
    # mirror=false does not hide a deleting refspec after it.
    "git -c remote.origin.mirror=false -c remote.origin.push=:refs/heads/side push origin",
    # A variable can hold ":branch".
    "git push -u origin $BRANCH",
    # Pushes whose deletion comes from config, xargs or a substitution.
    "git -c remote.origin.push=:refs/heads/side push origin",
    "git -c remote.origin.mirror=true push origin",
    "printf ':side ' | xargs git push origin",
    "git push origin $(printf ':%s' side)",
    # Ranges read by other commands, and merge bases used by diff/rev-parse.
    "git show --oneline -s origin/main..origin/side",
    "git whatchanged --oneline origin/main..origin/side",
    "git format-patch origin/main..origin/side",
    "git format-patch origin/side",
    "git cherry-pick origin/main..origin/side",
    "git diff --stat origin/main...origin/side",
    "git diff --merge-base origin/main origin/side",
    "git rev-parse origin/main...origin/side",
    # Command substitutions, quoted or in backticks: how an audit loop is written.
    'for b in side feat; do echo "$b $(git rev-list --count origin/main..origin/$b)"; done',
    'echo "base=$(git merge-base origin/main origin/side)"',
    "echo `git rev-list --count origin/main..origin/side`",
    "X=`git merge-base origin/main origin/side`",
    'echo "first: $(git log --reverse --format=%cs origin/main | head -1)"',
    'echo "$(echo "$(git merge-base origin/main origin/side)")"',
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

# Each must be refused in SHALLOW, where its filtered walk runs out at the
# cut-off, and allowed in FULL. The reason shows that the ".." in a path or an
# option value was not read as a range.
FILTERED_IN_SHALLOW = [
    "git log -3 -- ../README.md",
    "git log --oneline -5 ../other/file",
    "git log -n 5 -- docs/a..b.md",
    "git log -3 a..b.txt",
    "git log -3 ./a..b",
    "git log --author 'a..b' -3",
    "git log -S 'x..y' -2",
    "git log -G foo..bar -2",
    "git log --since 2026-01-01.. -3",
    "git log -1 -- f.txt",
]

# Each must be allowed in SHALLOW (and so in FULL).
ALLOWED_IN_SHALLOW = [
    # Ranges whose walk stays inside the fetched history.
    "git log --oneline origin/main..HEAD",
    "git rev-list --count origin/main..HEAD",
    "git log --oneline @{u}..HEAD",
    "git log --oneline origin/main...HEAD",
    # --reverse and --max-parents inside a range that checks out.
    "git log --reverse --oneline origin/main..HEAD",
    "git rev-list --reverse origin/main..HEAD",
    "git log --max-parents=0 origin/main..HEAD",
    "git merge-base HEAD origin/main",
    "git merge-base --is-ancestor origin/main HEAD",
    # An ambiguous prefix (--contains, --color, --column, --copy) is
    # rejected by git itself, so it is not a ref filter.
    "git branch --co",
    "git cherry origin/main HEAD",
    # Limited reads that stop at or before the cut-off: HEAD is L, then the
    # cut-off c4, so two commits are exactly what the full history lists.
    "git log -1 --oneline",
    "git log -2 --oneline",
    "git log --oneline -n 1 --stat",
    # --pretty takes no separate value, so -2 is the limit.
    "git log --pretty -2",
    "git log -1 --word-diff",
    "git log -1 -U1 --oneline",
    # The cut-off commit listed last with no diff shown is right.
    "git log -1 --oneline origin/main",
    "git show -s origin/main",
    "git show --no-patch --format=%s origin/main",
    # The reflog is local.
    "git log -g -3 --oneline",
    # A quoted current-branch name cannot name a deletion.
    'git push -u origin "$(git branch --show-current)"',
    'git push origin "HEAD:$(git rev-parse --abbrev-ref HEAD)"',
    # Filtered reads whose answer is newer than every cut-off commit.
    "git log -1 -- local.txt",
    "git log -1 --format=%H -- local.txt",
    "git log --no-merges -1",
    "git log -1 --author=t",
    "git log -1 --author t",
    "git log --oneline | head -2",
    "git log --oneline | head -n 1",
    "git log -1 --format=%H | tail -1",
    "git log --reverse -2 --format=%s",
    "git rev-list --count -2 HEAD",
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
    "echo '$(git merge-base origin/main origin/side)'",
    'echo "$(git log -1 --format=%h)"',
    "git diff origin/main...HEAD",
    "git diff --stat origin/main",
    "git show HEAD",
    "git show --stat",
    "git format-patch -1 HEAD",
    "git push -nd origin side",
    "ALLOW_SHALLOW_HISTORY=1 git merge-base origin/main origin/side",
    # A nested shell after a cd starts somewhere unknown, so it is skipped.
    "cd sub; bash -c 'git merge-base origin/main origin/side'",
]


def main():
    failures = []
    checks = 0
    with tempfile.TemporaryDirectory() as root:
        full, shallow, deep3, fetched, broken, (skew, skew_full) = build(root)
        for repo in (shallow, deep3, fetched, broken, skew):
            flag = git("rev-parse", "--is-shallow-repository", cwd=repo).strip()
            assert flag == "true", f"fixture: {repo} is not shallow"
        # The fixture really answers wrongly where the test says it does.
        count = "origin/main..origin/side"
        assert git("rev-list", "--count", count, cwd=full).strip() == "0"
        assert git("rev-list", "--count", count, cwd=shallow).strip() != "0"
        assert git("rev-list", "--count", count, cwd=deep3).strip() != "0"
        feat = "origin/main..origin/feat"
        true_feat = git("rev-list", "--count", feat, cwd=full).strip()
        assert true_feat == "2", true_feat
        assert git("rev-list", "--count", feat, cwd=fetched).strip() != true_feat, \
            "fixture: the fetched clone does not overcount"
        # Each FETCHED case below answers wrongly, as the test claims.
        for rng, true in (("origin/feat~1..origin/feat", "3"),
                          ("origin/feat...origin/main", "2"),
                          ("origin/feat..origin/late", "2")):
            assert git("rev-list", "--count", rng, cwd=full).strip() == true, rng
            assert git("rev-list", "--count", rng, cwd=fetched).strip() != true, \
                f"fixture: the fetched clone answers {rng} rightly"
        # FETCHED names the cut-off c4, not c3, as feat's last change to mid.txt.
        last_mid = ["log", "-1", "--format=%s", "origin/feat", "--", "mid.txt"]
        assert git(*last_mid, cwd=full).strip() == "c3"
        assert git(*last_mid, cwd=fetched).strip() == "c4"
        # SKEW overcounts main..b, and DEEP3 names the wrong last change to old.txt.
        assert git("rev-list", "--count", "origin/main..origin/b", cwd=skew_full).strip() == "2"
        assert git("rev-list", "--count", "origin/main..origin/b", cwd=skew).strip() != "2"
        last_old = ["log", "-1", "--format=%s", "--", "old.txt"]
        assert git(*last_old, cwd=full).strip() == "c0"
        assert git(*last_old, cwd=deep3).strip() != "c0"
        # c3 is in FETCHED (through late) and ties c4, the cut-off.
        assert git("log", "-1", "--format=%ct", "origin/late~2", cwd=fetched) == \
            git("log", "-1", "--format=%ct", "origin/main", cwd=fetched)

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
        for cmd in FILTERED_IN_SHALLOW:
            checks += 1
            decision, reason = run_full(cmd, shallow)
            if decision != "deny" or "range" in reason or "endpoints" in reason:
                failures.append(f"filtered read not refused as filtered: {cmd}: {reason}")
            expect(cmd, full, None, "refused in FULL clone (false positive)")

        for cmd, want in (
                ('for b in side; do echo "$(git rev-list --count origin/main..origin/side)"; done',
                 "cut-off"),
                ("git log --oneline | wc -l", "no limit"),
                ("git show --stat origin/main", "adding every file"),
                ("git log -1 --author=t -- f.txt", "filtered walk"),
                ("git push origin :side", "can delete a remote ref"),
                ("git rev-list --count origin/main..origin/side", "cut-off")):
            checks += 1
            decision, reason = run_full(cmd, shallow)
            if decision != "deny" or want not in reason:
                failures.append(f"refused for the wrong reason ({want!r}): {cmd}: {reason[:160]}")

        # A long command line is evaluated quickly (a regex once took
        # seconds here).
        checks += 1
        started = time.time()
        run("echo " + "git log " * 5000, shallow)
        if time.time() - started > 5:
            failures.append("a 40k-character command took over 5 s")

        # An endpoint that git would read as an option is refused before any
        # query runs, so the guard's own git call cannot write a file.
        victim = os.path.join(root, "victim")
        write(victim + "^{commit}", "keep me")
        expect(f"git log ^--output={victim} HEAD", shallow, "deny",
               "option-shaped endpoint not refused")
        with open(victim + "^{commit}", encoding="utf-8") as fh:
            checks += 1
            if fh.read() != "keep me":
                failures.append("the guard's own query wrote to a file")

        # The excluded side ran out of history: refused.
        expect("git rev-list --count origin/main..origin/side", deep3, "deny",
               "deep3: truncated excluded side not refused")
        expect("git log --oneline origin/main..HEAD", deep3, None,
               "deep3: empty walk refused")
        # Hidden edge: main's old commits came back through feat, and their
        # age is the only local sign that they sit below main's cut-off.
        expect("git rev-list --count origin/main..origin/feat", fetched, "deny",
               "fetched: hidden-edge overcount not refused")
        expect("git log --oneline origin/main..origin/feat", fetched, "deny",
               "fetched: hidden-edge log not refused")
        expect("git rev-list --count origin/main..origin/feat", full, None,
               "full: feat range refused")
        # The included side reaches main's cut-off and the excluded side does
        # not: Y..feat misses c3, which lies below the cut-off. Only rule 1
        # sees it, since no other walk reaches a cut-off.
        expect("git rev-list --count origin/feat~1..origin/feat", fetched, "deny",
               "fetched: walk into the included side's cut-off not refused")
        # The hidden commits sit on the second endpoint's side only, so only
        # the check with the endpoints swapped sees them.
        expect("git rev-list --count origin/feat...origin/main", fetched, "deny",
               "fetched: symmetric range with hidden commits on one side not refused")
        # Both sides reach the same cut-off, and the hidden commit c3 has its
        # parent: only its age, equal to the cut-off's, gives it away.
        expect("git rev-list --count origin/feat..origin/late", fetched, "deny",
               "fetched: hidden commit tying the cut-off's date not refused")
        expect("git rev-list --count origin/feat..origin/late", full, None,
               "full: late range refused")
        # A filtered read that lists the cut-off commit itself, and one whose
        # last listed commit ties the cut-off's date.
        expect("git log -1 --format=%s origin/feat -- mid.txt", fetched, "deny",
               "fetched: filtered read listing the cut-off not refused")
        expect("git log -1 --format=%s origin/late -- mid.txt", fetched, "deny",
               "fetched: filtered read tying the cut-off not refused")
        expect("git log -1 --format=%s origin/feat -- y.txt", fetched, None,
               "fetched: filtered read newer than the cut-off refused")
        # Only the parentless clause of rule 2 sees the skewed hidden commits.
        expect("git rev-list --count origin/main..origin/b", skew, "deny",
               "skew: hidden commits with skewed dates not refused")
        expect("git rev-list --count origin/main..origin/b", skew_full, None,
               "skew_full: range refused")
        # The cut-off commit lists as the last change to every file.
        expect("git log -1 --format=%s -- old.txt", deep3, "deny",
               "deep3: last change to a file below the cut-off not refused")
        expect("git log -1 --format=%s -- f.txt", deep3, None,
               "deep3: last change above the cut-off refused")
        # A configured deleting refspec applies to a bare push.
        git("config", "remote.origin.push", ":refs/heads/side", cwd=shallow)
        expect("git push origin", shallow, "deny", "configured deleting refspec not refused")
        expect("git push", shallow, "deny", "configured deleting refspec not refused (bare)")
        expect("git push origin HEAD:side", shallow, None, "explicit refspec refused")
        git("config", "--unset", "remote.origin.push", cwd=shallow)
        expect("git push origin", shallow, None, "plain push refused")
        # The revisions resolve but the walk fails: refused, not guessed.
        expect("git log --oneline origin/main..HEAD", broken, "deny",
               "broken: failed walk not refused")
        expect("git log -3 --oneline", broken, "deny",
               "broken: failed plain walk not refused")
        expect("git log -1 --author=t", broken, "deny",
               "broken: failed filtered walk not refused")

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
            res = subprocess.run([sys.executable, HOOK], input=raw, cwd=root,
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
