#!/usr/bin/env python3
"""PreToolUse: refuse copying a file from one repository checkout into another.

Ezra, 2026-11-16: "don't copy; decompose" (#5709, shared/principles/dont-copy-decompose.md).
Denies a Write of a NEW file sharing at least MIN_LINES meaningful lines (stripped, over
3 chars), and at least MIN_SHARE of its own, with a same-named file in a sibling repository.
A repository is identified by its COMMON git dir, so a linked worktree is the
same repository as its main checkout, and siblings are listed beside the main
checkout. Not judged: Edit, MultiEdit and a Write over an existing file (they
change a file rather than create a copy); vendored paths (EXEMPT_PATH), which a
sync workflow should write; a thin caller of a `gha` reusable workflow, which
is the decomposed form; a copy within one repo, which is not compared (see the fragment).
A line comment `decompose: allow <reason>` passes (`<!--` only in Markdown, where `#` is a heading).
Fails OPEN and SILENT on any parse trouble, and stops after TIME_BUDGET.
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

MIN_LINES = 15
MIN_SHARE = 0.7
MAX_SIBLINGS = 80
MAX_BYTES = 1_000_000
TIME_BUDGET = 6.0
ALLOW = re.compile(r"^\s*(?:#|<!--|//|/\*|--|%|;)\s*decompose:\s*allow\s+\S", re.I | re.M)
ALLOW_MD = re.compile(r"^\s*<!--\s*decompose:\s*allow\s+\S", re.I | re.M)
MARKDOWN = re.compile(r"\.(?:md|qmd|rmd|markdown)$", re.I)
WORKFLOW_PATH = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$")
CALLER = re.compile(r"^\s*uses:\s*Morrison-Lab/gha/\.github/workflows/", re.M | re.I)
STEP = re.compile(r"^\s*(?:-\s*)?(?:run|steps):", re.M)
EXEMPT_PATH = re.compile(
    r"(?:^|/)(?:_extensions|vendor|node_modules)/|(?:^|/)shared/vendored/"
    r"|(?:^|/)(?:LICEN[CS]E|COPYING)(?:\.[A-Za-z]+)?$",
    re.I,
)
REASON = (
    "[hook: no-cross-repo-copy] {what}\n\nEzra, 2026-11-16: \"don't copy; decompose\" "
    "(shared/principles/dont-copy-decompose.md). Factor the shared part into one component "
    "both repositories call, the original included (a `Morrison-Lab/gha` reusable workflow, "
    "a package function, or one canonical file), with what differs as inputs. A move (port) "
    "or a copy that truly cannot be shared passes with a line comment `decompose: allow <reason>` in the file's own syntax."
)


def common_dir(path):
    """(checkout root, realpath of its common git dir) for `path`, or (None, None)."""
    cur = os.path.abspath(path)
    while True:
        dotgit = os.path.join(cur, ".git")
        if os.path.isdir(dotgit):
            return cur, os.path.realpath(dotgit)
        if os.path.isfile(dotgit):
            with open(dotgit, encoding="utf-8") as fh:
                line = fh.readline().strip()
            gitdir = os.path.join(cur, line[len("gitdir:"):].strip()) if line.startswith("gitdir:") else ""
            common = os.path.join(gitdir, "commondir")
            if os.path.isfile(common):
                with open(common, encoding="utf-8") as fh:
                    gitdir = os.path.join(gitdir, fh.read().strip())
            return cur, os.path.realpath(gitdir) if gitdir else None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent


def meaningful_lines(text):
    return [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 3]


def shared_lines(new_lines, old_text):
    """Lines of `new_lines` also in `old_text`, counted as a multiset."""
    return sum((Counter(new_lines) & Counter(meaningful_lines(old_text))).values())


def is_caller(path, text):
    """A workflow that only calls gha reusable workflows: no job has `steps:` or `run:`."""
    return bool(WORKFLOW_PATH.search(path) and CALLER.search(text)) and not STEP.search(text)


def allowed(path, text):
    return bool((ALLOW_MD if MARKDOWN.search(path) else ALLOW).search(text))


def sibling_roots(common):
    """Main checkouts beside this repository's main checkout (none for a submodule)."""
    if os.path.basename(common) != ".git":
        return []
    main = os.path.dirname(common)
    parent = os.path.dirname(main)
    try:
        cands = [os.path.join(parent, n) for n in sorted(os.listdir(parent))]
    except OSError:
        return []
    return [c for c in cands if c != main and os.path.isdir(os.path.join(c, ".git"))][:MAX_SIBLINGS]


def same_name_files(sib, basename, deadline):
    try:
        res = subprocess.run(
            ["git", "-C", sib, "ls-files", "-z", "--", basename, "*/" + basename],
            capture_output=True, timeout=max(0.5, deadline - time.monotonic()), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [os.path.join(sib, p) for p in res.stdout.decode("utf-8", "replace").split("\0") if p]


def copied_source(path, content):
    """Path of a sibling-repo file that new file `content` mostly repeats, or None."""
    if os.path.exists(path) or EXEMPT_PATH.search(path) or allowed(path, content) or is_caller(path, content):
        return None
    new_lines = meaningful_lines(content)
    _root, common = common_dir(os.path.dirname(path))
    if len(new_lines) < MIN_LINES or not common:
        return None
    deadline = time.monotonic() + TIME_BUDGET
    for sib in sibling_roots(common):
        if time.monotonic() > deadline:
            return None
        for cand in same_name_files(sib, os.path.basename(path), deadline):
            if time.monotonic() > deadline:
                return None
            try:
                if os.path.getsize(cand) > MAX_BYTES:
                    continue
                with open(cand, encoding="utf-8", errors="replace") as fh:
                    hits = shared_lines(new_lines, fh.read())
            except OSError:
                continue
            if hits >= MIN_LINES and hits / len(new_lines) >= MIN_SHARE:
                return cand
    return None


def verdict(payload):
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    if payload.get("tool_name") == "Write" and isinstance(inp.get("content"), str):
        path = str(inp.get("file_path") or "")
        src = path and copied_source(path, inp["content"])
        return src and f"New file `{path}` repeats most of `{src}`, a file in another repository."
    return None


def main() -> int:
    try:
        what = verdict(json.load(sys.stdin))
    except Exception:
        return 0
    if not what:
        return 0
    reason = REASON.format(what=what)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": reason,
        },
        "systemMessage": "Blocked: don't copy a file between repositories; decompose it into a shared component.",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
