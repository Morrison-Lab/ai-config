#!/usr/bin/env python3
"""PreToolUse guard: refuse a `git push` of a branch that is a massive PR.

Ezra, 2026-10-23: "don't allow massive sweep PRs like pds#244 anymore; do them
in minimal batches", and "every PR should be as small and focused as it can be
while completely solving its stated task" (ai-config#4698). The CI side is
gha's `check-pr-size` (gha#1188); this hook stops the push before CI is spent.

Measures the branch against the merge base with the remote default branch:
files changed and added plus deleted lines, not counting generated, lock,
image and data paths. Over 10 files or 300 lines the push is denied.

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


def measure(cwd, base):
    mb = git(cwd, "merge-base", base, "HEAD")
    if not mb:
        return None
    out = git(cwd, "diff", "--numstat", "-M", mb, "HEAD")
    if out is None:
        return None
    files = lines = 0
    for row in out.splitlines():
        parts = row.split("\t", 2)
        if len(parts) != 3:
            continue
        path = parts[2].split(" => ")[-1]
        if any(re.fullmatch(p, path) for p in IGNORE):
            continue
        files += 1
        if parts[0] != "-":
            lines += int(parts[0]) + int(parts[1])
    return files, lines


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
    if git(where, "rev-parse", "--abbrev-ref", "HEAD") in (None, "HEAD", base.split("/", 1)[-1]):
        return None
    result = measure(where, base)
    if result is None:
        return None
    files, lines = result
    if files <= MAX_FILES and lines <= MAX_LINES:
        return None
    return (
        f"This branch changes {files} files and {lines} lines against {base} "
        f"(cap {MAX_FILES} files, {MAX_LINES} lines). Every PR should be as small and "
        "focused as it can be while completely solving its stated task, and a sweep goes "
        "out as minimal batches (Ezra, 2026-10-23, ai-config#4698). Split the work: one "
        "branch and PR per batch of one concern, each opened with its own issue, and "
        "push the first batch now. gha's check-pr-size fails the same PR in CI. If this "
        "is a stacked branch whose base is not the default branch, or the maintainer asked "
        "for one mechanical PR, rerun with the prefix ALLOW_LARGE_PR=1 and state why."
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
