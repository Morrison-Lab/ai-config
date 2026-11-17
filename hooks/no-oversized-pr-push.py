#!/usr/bin/env python3
"""PreToolUse guard: refuse a `git push` of a branch that is a massive PR.

Ezra, 2026-10-23: "don't allow massive sweep PRs like pds#244 anymore; do them
in minimal batches", and "every PR should be as small and focused as it can be
while completely solving its stated task" (ai-config#4698). The CI side is
gha's `check-pr-size` (gha#1188); this hook stops the push before CI is spent.

Measures the branch against the merge base with the remote default branch:
files changed and added plus deleted lines, not counting generated, lock,
image and data paths, nor a path `.gitattributes` marks `linguist-generated`
(a committed generator output, ai-config#5288), and not counting the lines of a newly added `_fig-*`
subfile (it still counts as a file), and not counting a pure rename (no line
changed). Over 10 files or 300 lines the push is denied.

The hook agrees with CI, so a push CI would pass is not denied
(ai-config#5749; 2026-11-17, a follow-up fix to gha#2082 needed a typed
approval from Ezra although CI passed):

* An open PR for the branch that carries the `size-exempt` label, or whose
  body says "mechanical, content-identical", passes, as in gha's
  `check-pr-size`. The PR is read with `gh api`; when that fails the push is
  measured as before.
* A branch that adds a new gha capability (a new `<name>/action.yml` together
  with `.github/workflows/<name>.yml`) does not count, as files, the files gha
  CI requires it to register in (gha#1264): `README.md`, `CLAUDE.md`,
  `website/_quarto.yml`, `website/reference/<name>.qmd`,
  `examples/<name>.yml`, the reusable workflow, `_selftest.yml`,
  `.github/dependabot.yml` and its new `changelog.d/` fragment. Their lines
  still count, and so does the capability's own directory.
* A push to a branch whose pushed tip (checked against the server with
  `git ls-remote`) was already over the cap passes when the commits it adds
  are within the cap on their own: the earlier over-cap push was already
  approved, and a review fix on top of it should not need the approval again.

Escape hatch for a deliberate exception (a mechanical rename the maintainer
asked for in one PR, a stacked branch whose base is not the default branch):
prefix the command with `ALLOW_LARGE_PR=1` and say why in the reply.

Fails open on any parse trouble, outside a repo, with no remote default
branch, and on any git error: a guard that blocks on its own failure gets
disabled.
"""
import json
import os
import re
import subprocess
import sys

MAX_FILES = 10
MAX_LINES = 300
# Keep in step with BUILTIN_IGNORE in gha's check-pr-size/check-pr-size.py.
IGNORE = [
    r"(?:.*/)?[^/]*\.lock", r"(?:.*/)?package-lock\.json",
    r"(?:.*/)?_freeze/.*", r"docs/.*",
    r"(?:.*/)?[^/]*\.(?:png|jpe?g|gif|svg|pdf|csv|rds|RData|min\.js)",
]
# Lines (not files) of a newly added figure subfile are free (ai-config#4928).
# Keep in step with NEW_FIGURE_LINES_FREE in gha's check-pr-size.
NEW_FIGURE_LINES_FREE = r"(?:.*/)?_fig-[^/]*"
# Files every new gha capability must be listed in (gha CLAUDE.md, "Adding a
# new check"; gha#1264). Keep in step with that list.
REGISTRATION_FILES = (
    "README.md", "CLAUDE.md", "website/_quarto.yml",
    ".github/workflows/_selftest.yml", ".github/dependabot.yml",
)
# Keep in step with gha's check-pr-size: MECHANICAL_RE and the reusable
# workflow's default `exempt-label`.
MECHANICAL = re.compile(r"mechanical,\s*content-identical", re.IGNORECASE)
EXEMPT_LABEL = "size-exempt"
PUSH = re.compile(r"(?:^|[;&|(\s])git\s+(?:-C\s+(\S+)\s+)?push\b")
ALLOW = re.compile(r"(?:^|[;&|\s])ALLOW_LARGE_PR=1\b")


def git(cwd, *args):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=15)
    return p.stdout.strip() if p.returncode == 0 else None


def default_base(cwd):
    head = git(cwd, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    for ref in (head, "origin/main", "origin/master"):
        if ref and git(cwd, "rev-parse", "--verify", "-q", ref + "^{commit}"):
            return ref
    return None


def new_path(name):
    """The post-rename path in a numstat name: `a => b` or `pre/{a => b}/post`."""
    name = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", name)
    return re.sub(r"/{2,}", "/", name.split(" => ")[-1])


def generated(cwd, paths):
    """The paths among `paths` that `.gitattributes` marks `linguist-generated`.

    A repo marks its committed generator outputs once, and GitHub folds them in
    review as well (ai-config#5288).
    """
    if not paths:
        return set()
    p = subprocess.run(["git", "check-attr", "-z", "--stdin", "linguist-generated"],
                       cwd=cwd, input="\0".join(paths) + "\0",
                       capture_output=True, text=True, timeout=15)
    if p.returncode != 0:
        return set()
    f = p.stdout.split("\0")
    return {f[i] for i in range(0, len(f) - 2, 3) if f[i + 2] in ("set", "true")}


def registration_paths(added):
    """The registration files a new gha capability must touch (gha#1264).

    A capability is new when the diff adds both `<name>/action.yml` and
    `.github/workflows/<name>.yml`. With none, the set is empty. A
    `changelog.d/` fragment counts as registration only when it is new and
    names the capability.
    """
    names = {m.group(1) for p in added
             for m in [re.fullmatch(r"([^/]+)/action\.yml", p)] if m}
    names = {n for n in names if f".github/workflows/{n}.yml" in added}
    if not names:
        return set()
    paths = set(REGISTRATION_FILES)
    for n in names:
        paths |= {f".github/workflows/{n}.yml", f"examples/{n}.yml",
                  f"website/reference/{n}.qmd"}
        paths |= {p for p in added if p.startswith("changelog.d/") and n in p}
    return paths


def measure(cwd, base, tip="HEAD"):
    mb = git(cwd, "merge-base", base, tip)
    if not mb:
        return None
    out = git(cwd, "diff", "--numstat", "-M", mb, tip)
    if out is None:
        return None
    added = git(cwd, "diff", "--name-only", "--diff-filter=A", "-M", mb, tip)
    added = set((added or "").splitlines())
    registration = registration_paths(added)
    rows = [r.split("\t", 2) for r in out.splitlines()]
    rows = [r for r in rows if len(r) == 3]
    gen = generated(cwd, [new_path(r[2]) for r in rows])
    files = lines = 0
    for parts in rows:
        path = new_path(parts[2])
        if path in gen or any(re.fullmatch(p, path) for p in IGNORE):
            continue
        # A pure rename (no line changed) is content-identical (ai-config#5128).
        if " => " in parts[2] and parts[:2] == ["0", "0"]:
            continue
        # A registration file does not count as a file, but its lines still
        # count, so a new capability cannot carry unrelated prose for free.
        if path not in registration:
            files += 1
        if path in added and re.fullmatch(NEW_FIGURE_LINES_FREE, path):
            continue
        if parts[0] != "-":
            lines += int(parts[0]) + int(parts[1])
    return files, lines


def over_cap(result):
    return result is not None and (result[0] > MAX_FILES or result[1] > MAX_LINES)


def open_pr(cwd, branch):
    """The open PR for `branch` on origin as a dict, or None.

    `NO_OVERSIZED_PR_PUSH_PR_JSON` stands in for the API answer in the tests.
    """
    fake = os.environ.get("NO_OVERSIZED_PR_PUSH_PR_JSON")
    if fake is not None:
        return json.loads(fake) or None
    url = git(cwd, "remote", "get-url", "origin") or ""
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        return None
    owner, repo = m.groups()
    p = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/pulls?state=open&head={owner}:{branch}"],
        cwd=cwd, capture_output=True, text=True, timeout=15)
    if p.returncode != 0:
        return None
    prs = json.loads(p.stdout or "[]")
    return prs[0] if prs else None


def pr_exempt(pr):
    """True when CI's check-pr-size would pass the PR whatever its size."""
    if not pr:
        return False
    labels = {(lb.get("name") or "").lower() for lb in pr.get("labels") or []}
    return EXEMPT_LABEL in labels or bool(MECHANICAL.search(pr.get("body") or ""))


def delta_within_cap(cwd, branch):
    """True when the pushed tip was already over the cap and the new commits are not.

    The remote branch must be an ancestor of HEAD, so a rewrite is measured whole.
    """
    remote = f"origin/{branch}"
    local = git(cwd, "rev-parse", "--verify", "-q", remote + "^{commit}")
    if not local:
        return False
    # The tracking ref can be stale after a force push elsewhere, so the
    # server's tip must be the commit measured.
    live = git(cwd, "ls-remote", "--heads", "origin", branch)
    if not live or live.split()[0] != local:
        return False
    if git(cwd, "merge-base", "--is-ancestor", remote, "HEAD") is None:
        return False
    base = default_base(cwd)
    if not base or not over_cap(measure(cwd, base, remote)):
        return False
    delta = measure(cwd, remote)
    return delta is not None and not over_cap(delta)


def decide(command, cwd):
    """Return the denial reason, or None to allow."""
    m = PUSH.search(command)
    if not m or ALLOW.search(command):
        return None
    where = m.group(1) or cwd
    if not where or not os.path.isdir(where):
        return None
    base = default_base(where)
    if not base:
        return None
    branch = git(where, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in (None, "HEAD", base.split("/", 1)[-1]):
        return None
    result = measure(where, base)
    if result is None or not over_cap(result):
        return None
    files, lines = result
    if delta_within_cap(where, branch):
        return None
    try:
        if pr_exempt(open_pr(where, branch)):
            return None
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return (
        f"This branch changes {files} files and {lines} lines against {base} "
        f"(cap {MAX_FILES} files, {MAX_LINES} lines). Every PR should be as small and "
        "focused as it can be while completely solving its stated task, and a sweep goes "
        "out as minimal batches (Ezra, 2026-10-23, ai-config#4698). Split the work: one "
        "branch and PR per batch of one concern, each opened with its own issue, and "
        "push the first batch now. gha's check-pr-size fails the same PR in CI. "
        "This hook already passes what CI passes: an open PR labelled size-exempt or "
        "saying 'mechanical, content-identical', a new gha capability's registration "
        "files, and a within-cap push on top of an already-pushed over-cap tip. If this "
        "is a stacked branch whose base is not the default branch, or a mechanical, "
        "content-identical PR (a move or split with no wording change; the PR body "
        "must say so), rerun with the prefix ALLOW_LARGE_PR=1 and state why."
    )


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") not in (None, "Bash"):
            return 0
        command = (data.get("tool_input") or {}).get("command") or ""
        reason = decide(command, data.get("cwd") or os.getcwd())
    except Exception:
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
