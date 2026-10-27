#!/usr/bin/env python3
"""Tests for no-commit-with-conflict-markers.py, with a mutation harness.

Each case builds a real repository, so the hook's live `git diff --check`
runs against a real index and working tree. Marker lines are built from
`"<" * 7` and friends so this file never holds one at the start of a line
itself (the hook would then refuse to commit its own test).

Run:  python3 hooks/test-no-commit-with-conflict-markers.py hooks/no-commit-with-conflict-markers.py
"""
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HOOK = os.path.realpath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "no-commit-with-conflict-markers.py"))
HOOKS_DIR = os.path.dirname(HOOK)
ROOT = os.path.dirname(HOOKS_DIR)
ELSEWHERE = tempfile.mkdtemp()  # a cwd that is not the repo under test
_SCRATCH = [ELSEWHERE]
atexit.register(lambda: [shutil.rmtree(p, ignore_errors=True)
                         for p in _SCRATCH])

OPEN, SEP, BASE, CLOSE = "<" * 7, "=" * 7, "|" * 7, ">" * 7
BLOCK = f"{OPEN} HEAD\nours\n{SEP}\ntheirs\n{CLOSE} origin/main\n"


def _run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def _write(repo, name, content):
    path = os.path.join(repo, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _init(path, first=True):
    _run(path, "init", "-q", "-b", "main")
    _run(path, "config", "user.email", "t@example.com")
    _run(path, "config", "user.name", "t")
    _run(path, "config", "commit.gpgsign", "false")
    if first:
        _write(path, "a.md", "start\n")
        _write(path, "b.md", "other\n")
        _run(path, "add", ".")
        _run(path, "commit", "-qm", "init")


# ------------------------------------------------------------------ fixtures

def staged_marker(p):
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)
    _run(p, "add", "a.md")


def clean_stage(p):
    _init(p)
    _write(p, "a.md", "start\nmore\n")
    _run(p, "add", "a.md")


def setext(p):
    _init(p)
    _write(p, "a.md", f"Title\n{SEP}\n\nbody\n\nSub\n-------\n")
    _run(p, "add", "a.md")


def unstaged_marker(p):
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)   # modified, NOT staged
    _write(p, "b.md", "other\nclean\n")
    _run(p, "add", "b.md")


def conflicted_merge(p):
    """A real `main` merge left conflicted (UU), nothing resolved."""
    _init(p)
    _run(p, "checkout", "-qb", "side")
    _write(p, "a.md", "side\n")
    _run(p, "commit", "-qam", "side")
    _run(p, "checkout", "-q", "main")
    _write(p, "a.md", "main\n")
    _run(p, "commit", "-qam", "main")
    _run(p, "merge", "side", check=False)


def markers_in_head(p):
    """Markers already committed; the staged edit to the SAME file adds a
    setext heading, so `--check` flags the file and its old markers are read
    but must not count: only added lines do."""
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)
    _run(p, "commit", "-qam", "oops")
    _write(p, "a.md", "start\n" + BLOCK + f"\nTail\n{SEP}\n")
    _run(p, "add", "a.md")


def markers_in_head_nothing_staged(p):
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)
    _run(p, "commit", "-qam", "oops")


def aider_block(p):
    _init(p)
    _write(p, "a.md", f"start\n{OPEN} SEARCH\nold\n{SEP}\nnew\n{CLOSE} REPLACE\n")
    _run(p, "add", "a.md")


def marker_staged_other_clean(p):
    """Markers staged in a.md; b.md modified in the working tree only."""
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)
    _run(p, "add", "a.md")
    _write(p, "b.md", "other\nclean\n")


def lone_open(p):
    _init(p)
    _write(p, "a.md", f"start\n{OPEN} HEAD\nhalf resolved\n")
    _run(p, "add", "a.md")


def diff3_base(p):
    _init(p)
    _write(p, "a.md", f"start\n{BASE} merged common ancestors\nx\n")
    _run(p, "add", "a.md")


def big_marker_size(p):
    _init(p)
    _write(p, ".gitattributes", "*.md conflict-marker-size=32\n")
    _run(p, "add", ".gitattributes")
    _run(p, "commit", "-qm", "attrs")
    _write(p, "a.md", "start\n" + BLOCK)
    _run(p, "add", "a.md")


def first_commit(p):
    _init(p, first=False)
    _write(p, "a.md", BLOCK)
    _run(p, "add", "a.md")


def worktree_marker_only(p):
    """Markers in the working tree of a.md, nothing staged."""
    _init(p)
    _write(p, "a.md", "start\n" + BLOCK)


def subdir_marker(p):
    _init(p)
    _write(p, "sub/c.md", BLOCK)
    _run(p, "add", "sub/c.md")


def diff_relative_subdir(p):
    subdir_marker(p)
    _run(p, "config", "diff.relative", "true")


def staged_marker_worktree_fixed(p):
    """Markers staged; the working tree is already resolved."""
    staged_marker(p)
    _write(p, "a.md", "start\nresolved\n")


def head_markers_worktree_fixed(p):
    """Markers committed in HEAD, fixed in the working tree, nothing staged:
    the repair is `git commit -a --amend`."""
    markers_in_head_nothing_staged(p)
    _write(p, "a.md", "start\nresolved\n")


def root_commit_markers(p):
    first_commit(p)
    _run(p, "commit", "-qm", "root")


def merge_staged(p):
    """A real merge, conflicted, then staged unresolved: MERGE_HEAD set."""
    conflicted_merge(p)
    _run(p, "add", "-A")


def merge_brings_markers(p):
    """`main` already holds a guide with a fenced conflict example; a side
    branch merges it, resolving an unrelated conflict cleanly."""
    _init(p)
    _run(p, "checkout", "-qb", "side")
    _write(p, "a.md", "side\n")
    _run(p, "commit", "-qam", "side")
    _run(p, "checkout", "-q", "main")
    _write(p, "a.md", "main\n")
    _write(p, "guide.md", "Example:\n\n```\n" + BLOCK + "```\n")
    _run(p, "add", ".")
    _run(p, "commit", "-qm", "main")
    _run(p, "checkout", "-q", "side")
    _run(p, "merge", "main", check=False)
    _write(p, "a.md", "both\n")
    _run(p, "add", "a.md")


# command templates: {repo} is the fixture path; the hook runs from ELSEWHERE
# when the command names the repo, else from the repo itself.
CASES = {
    # must deny
    "staged-marker":       (staged_marker, "git commit -m x", True),
    "incident":            (conflicted_merge,
                            "git add -A && git commit --no-edit", True),
    "commit-a":            (worktree_marker_only, "git commit -am x", True),
    "add-path-then-commit": (worktree_marker_only,
                             "git add a.md && git commit -m x", True),
    "dash-C":              (staged_marker, "@git -C {repo} commit -m x", True),
    "cd-and":              (staged_marker, "@cd {repo} && git commit -m x",
                            True),
    "bash-c":              (staged_marker, "@bash -c 'git -C {repo} commit -m x'",
                            True),
    "amend":               (markers_in_head_nothing_staged,
                            "git commit --amend --no-edit", True),
    "include-paths":       (marker_staged_other_clean,
                            "git commit -i -m x -- b.md", True),
    "lone-open":           (lone_open, "git commit -m x", True),
    "diff3-base":          (diff3_base, "git commit -m x", True),
    "merge-continue":      (merge_staged, "git merge --continue", True),
    "merge-commit":        (merge_staged, "git commit --no-edit", True),
    "first-commit":        (first_commit, "git commit -m init", True),
    "root-amend":          (root_commit_markers,
                            "git commit --amend --no-edit", True),
    "subdir":              (subdir_marker, "%git commit -m x", True),
    "diff-relative-subdir": (diff_relative_subdir, "%git commit -m x", True),
    "staged-marker-worktree-fixed": (staged_marker_worktree_fixed,
                                     "git commit -m x", True),
    # must pass
    "clean-stage":         (clean_stage, "git commit -m x", False),
    "setext-underline":    (setext, "git commit -m x", False),
    "unstaged-marker":     (unstaged_marker, "git commit -m x", False),
    "markers-only-in-head": (markers_in_head, "git commit -m y", False),
    "aider-search-replace": (aider_block, "git commit -m x", False),
    "only-paths":          (marker_staged_other_clean,
                            "git commit -m x -- b.md", False),
    "dry-run":             (staged_marker, "git commit --dry-run -m x", False),
    "echoed":              (staged_marker, "echo 'git commit -m x'", False),
    "heredoc-message":     (clean_stage,
                            "git commit -F - <<'EOF'\nmsg\nEOF", False),
    "marker-size-attr":    (big_marker_size, "git commit -m x", False),
    # the repair commands, after the working tree is fixed
    "stale-staged-commit-a": (staged_marker_worktree_fixed,
                              "git commit -am x", False),
    "stale-staged-add-A":  (staged_marker_worktree_fixed,
                            "git add -A && git commit -m x", False),
    "stale-staged-add-path": (staged_marker_worktree_fixed,
                              "git add a.md && git commit -m x", False),
    "stale-head-amend-a":  (head_markers_worktree_fixed,
                            "git commit -a --amend --no-edit", False),
    # `--only` commits the named path, not what an earlier add staged
    "add-A-then-only":     (unstaged_marker,
                            "git add -A && git commit -m x -- b.md", False),
    "add-then-only":       (unstaged_marker,
                            "git add a.md && git commit -m x b.md", False),
    # lines the merged side already holds are not added by the merge
    "merge-brings-existing-markers": (merge_brings_markers,
                                      "git commit --no-edit", False),
    "merge-continue-existing-markers": (merge_brings_markers,
                                        "git merge --continue", False),
    "not-a-commit":        (staged_marker, "git status", False),
}

_REPOS = {}


def _repo(builder):
    if builder not in _REPOS:
        path = tempfile.mkdtemp()
        _SCRATCH.append(path)
        builder(path)
        _REPOS[builder] = path
    return _REPOS[builder]


def run_hook(hook_path, builder, command):
    """The parsed hook output ({} when silent)."""
    repo = _repo(builder)
    if command.startswith("@"):
        cwd, command = ELSEWHERE, command[1:].format(repo=repo)
    elif command.startswith("%"):  # run from the repo's `sub/` directory
        cwd, command = os.path.join(repo, "sub"), command[1:]
    else:
        cwd = repo
    payload = json.dumps({"tool_name": "Bash", "cwd": cwd,
                          "tool_input": {"command": command}})
    proc = subprocess.run([sys.executable, hook_path], input=payload,
                          capture_output=True, text=True, timeout=30,
                          cwd=ELSEWHERE)
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def denies(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


failures = []


def expect(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# ------------------------------------------------------------- the cases

print("cases:")
for cid, (builder, command, want) in CASES.items():
    got = denies(run_hook(HOOK, builder, command))
    expect(cid, got, want)
    print(f"  {'ok  ' if got == want else 'FAIL'} {cid:<24} "
          f"{'deny' if got else 'pass'}")

# Payload shape: the deny names file:line and carries a systemMessage.
out = run_hook(HOOK, conflicted_merge, "git add -A && git commit --no-edit")
reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
expect("reason names a.md:1", "a.md:1: " + OPEN in reason, True)
expect("reason names the separator line", f"a.md:3: {SEP}" in reason, True)
expect("systemMessage present", "systemMessage" in out, True)
out = run_hook(HOOK, subdir_marker, "%git commit -m x")
reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
expect("subdir path is top-level relative", "sub/c.md:1:" in reason, True)
# Silence is silence: no stdout at all on a pass outside --dry-run.
expect("pass prints nothing", run_hook(HOOK, clean_stage, "git commit -m x"),
       {})

# Non-Bash tools and a malformed tool_input are ignored.
for payload in ({"tool_name": "Read", "tool_input": {"command": "git commit"}},
                {"tool_name": "Bash", "tool_input": "git commit"}):
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)
    expect(f"ignored {payload['tool_name']}", (proc.returncode, proc.stdout),
           (0, ""))

# The repo under test is never modified (the hook only reads): neither the
# status nor the index file's bytes change.
def _state(repo):
    with open(os.path.join(repo, ".git", "index"), "rb") as fh:
        return _run(repo, "status", "--porcelain").stdout, fh.read()


before = _state(_repo(staged_marker_worktree_fixed))
run_hook(HOOK, staged_marker_worktree_fixed, "git add -A && git commit -am x")
expect("repo untouched", _state(_repo(staged_marker_worktree_fixed)), before)


# ---------------------------------------------------------- mutation harness
# Each clause is reverted in a copy of the hook; the declared cases must flip
# and no others. A clause whose reversion flips nothing is untested.

MUTATIONS = [
    ("separator-needs-block",
     "bad = open_label is not None and open_label != \"SEARCH\"",
     "bad = True",
     # the SEARCH block's separator, and markers-only-in-head's added
     # setext underline, then count too
     {"setext-underline", "aider-search-replace", "markers-only-in-head"}),
    ("search-exempt",
     "bad = mk[1] != \"SEARCH\"",
     "bad = True",
     {"aider-search-replace"}),
    ("open-marker-counts",
     "bad = mk[1] != \"SEARCH\"",
     "bad = False",
     {"lone-open"}),
    ("diff3-line-counts",
     "elif kind == \"|\":\n            bad = True",
     "elif kind == \"|\":\n            bad = False",
     {"diff3-base"}),
    ("preceding-add",
     "whole, add_paths = worktree",
     "whole, add_paths = False, []",
     # unseen adds: the worktree is not read, and the stale index counts
     {"incident", "add-path-then-commit", "stale-staged-add-A",
      "stale-staged-add-path"}),
    ("commit-a",
     "    if spec.all:\n        whole = True\n",
     "",
     {"commit-a", "stale-staged-commit-a", "stale-head-amend-a"}),
    ("amend-parents",
     "    if amend:\n",
     "    if False:\n",
     {"amend", "root-amend"}),
    ("merge-head-parent",
     "([m] if (m := commit(\"MERGE_HEAD\")) else [])",
     "[]",
     {"merge-brings-existing-markers", "merge-continue-existing-markers"}),
    ("whole-tree-skips-index",
     "if spec.staged_counts() and not whole and covered is not None:",
     "if spec.staged_counts() and covered is not None:",
     {"stale-staged-commit-a", "stale-staged-add-A", "stale-head-amend-a"}),
    ("covered-paths-skip-index",
     "if p not in covered}",
     "if True}",
     {"stale-staged-add-path"}),
    ("only-drops-earlier-adds",
     "whole, wt_paths = False, list(spec.paths)",
     "wt_paths = list(add_paths) + list(spec.paths)",
     {"add-A-then-only", "add-then-only"}),
    ("staged-blob-read",
     "    if staged:\n        return _git(cwd, \"show\"",
     "    if False:\n        return _git(cwd, \"show\"",
     {"staged-marker-worktree-fixed"}),
    ("diff-relative-off",
     "\"-c\", \"diff.relative=false\", ",
     "",
     {"diff-relative-subdir"}),
    ("only-excludes-index",
     "return self.include or not self.paths",
     "return True",
     {"only-paths", "add-A-then-only", "add-then-only"}),
    ("include-keeps-index",
     "return self.include or not self.paths",
     "return not self.paths",
     {"include-paths"}),
    ("added-lines-only",
     "if bad and no in flagged:",
     "if bad:",
     {"markers-only-in-head"}),
    ("continue",
     "elif sub in _CONTINUES and \"--continue\" in args:",
     "elif False:",
     {"merge-continue"}),
    ("dry-run-skip",
     "        if spec.skip:\n            continue\n",
     "",
     {"dry-run"}),
]

with open(HOOK, encoding="utf-8") as fh:
    SOURCE = fh.read()

print("\nmutations:")
mutation_wrong = 0
tmp = tempfile.mkdtemp()
_SCRATCH.append(tmp)
# The mutant needs its sibling and scripts/lib beside it, as in the checkout.
os.makedirs(os.path.join(tmp, "hooks"))
os.makedirs(os.path.join(tmp, "scripts"))
shutil.copy(os.path.join(HOOKS_DIR, "flag-commit-a-sweeps-submodule.py"),
            os.path.join(tmp, "hooks"))
os.symlink(os.path.join(ROOT, "scripts", "lib"),
           os.path.join(tmp, "scripts", "lib"))
for clause, find, replace, want_flips in MUTATIONS:
    if SOURCE.count(find) != 1:
        failures.append(f"mutation {clause}: anchor found "
                        f"{SOURCE.count(find)} times, need exactly 1")
        mutation_wrong += 1
        continue
    path = os.path.join(tmp, "hooks", f"mutant-{clause}.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SOURCE.replace(find, replace))
    flipped = {cid for cid, (b, c, want) in CASES.items()
               if denies(run_hook(path, b, c)) != want}
    ok = flipped == want_flips
    mutation_wrong += not ok
    if not ok:
        failures.append(f"mutation {clause}: flipped {sorted(flipped)}, "
                        f"expected {sorted(want_flips)}")
    print(f"  {'ok  ' if ok else 'WRONG'} {clause:<24} flipped "
          f"{', '.join(sorted(flipped)) or 'nothing'}")

print()
if failures:
    print("FAILURES:")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print(f"all {len(CASES)} cases and {len(MUTATIONS)} mutations behaved")
