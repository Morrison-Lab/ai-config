#!/usr/bin/env python3
"""PreToolUse guard: a staged file whose test sibling is not staged with it.

Measured on ai-config#3415 (2026-09-09). Raising `tui-alloc`'s default
walltime changed `dotfiles/shiva/bin/tui-alloc` and
`scripts/check-tui-alloc-readme.py`. The suite guarding that check,
`scripts/test_check_tui_alloc_readme.py`, hard-coded the old default as its
mutation source, so three of its mutations silently stopped applying and CI
failed -- twice, because the first fix round did not look at the test file
either.

The session had looked. It searched for `test-check-tui-alloc-readme.py`
(hyphens, matching the checker's own name) and for a function the tests never
import, concluded "no test file for this checker", and proceeded. Both
searches were reasonable and both missed, because the file uses underscores
and drives the checker as a subprocess.

That is `shared/workflow/grep-is-not-coverage.md` exactly: a search returning
nothing is not evidence of absence. That rule was loaded and did not fire,
because nothing about typing a `grep` announces that its result is about to
become a claim of absence. A rule is consulted at read time and broken at
composition time, which is why this is a hook.

WHY THE SEPARATORS MATTER MORE THAN THEY LOOK
---------------------------------------------
The naming list is the whole risk: too narrow and this guard reproduces the
miss it exists to catch. So it was derived from the corpus rather than
assumed. Of this repo's test files, 61 are `test_<stem>` and 55 are
`test-<stem>`, and 58 of the 59 checked sit in the same directory as their
subject. Crucially, `scripts/test_validate_skills.py` tests
`scripts/validate-skills.py` -- an underscore test naming a hyphen subject,
which is the same mismatch that defeated the original search. Comparing stems
without normalizing the separators would therefore miss real pairs, so this
compares them with `-` and `_` folded together.

It warns and never blocks. A change genuinely confined to a comment does not
owe its test anything, and a blocking guard on that judgment would be switched
off, taking the real cases with it. Nearly all of the value is in naming the
file so it gets opened at all: opening the suite in #3415 would have shown the
hard-coded literal on sight.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Extensions worth checking. A data or docs file has no test sibling to name.
SUBJECT_SUFFIXES = (".py", ".sh", ".bash")

# `test_<stem>.py` / `test-<stem>.sh` and the trailing `<stem>-test.py` form,
# all three of which this corpus uses.
LEADING = re.compile(r"^test[-_](?P<stem>.+)$")
TRAILING = re.compile(r"^(?P<stem>.+)[-_]test$")

NOTE = """A commit is staging {subject} while its test sibling {test} is \
not staged.

That may be right -- a comment-only edit owes its test nothing. But read \
{test} before deciding, rather than reasoning about whether it needs \
changing: on ai-config#3415 a suite hard-coded the very default the commit \
was raising, and opening it would have shown that on sight.

If the test genuinely needs no change, say so in the commit message so the \
next reader knows it was considered."""


def norm(stem: str) -> str:
    """Fold `-` and `_`, which this corpus mixes across a test and its
    subject (`test_validate_skills.py` tests `validate-skills.py`)."""
    return stem.replace("_", "-").lower()


def is_test_name(basename: str) -> bool:
    stem = basename.rsplit(".", 1)[0]
    return bool(LEADING.match(stem) or TRAILING.match(stem))


def test_stem(basename: str) -> str | None:
    """The subject stem a test file's name refers to, or None."""
    stem = basename.rsplit(".", 1)[0]
    for rx in (LEADING, TRAILING):
        m = rx.match(stem)
        if m:
            return norm(m.group("stem"))
    return None


def git_lines(cwd: str, *args: str) -> list[str]:
    """Lines from a git command, or none.

    Fails open on every error: a hook that raises takes the tool call down
    with it, and this one only ever adds a reminder. A cwd that does not
    exist raises FileNotFoundError from Popen itself rather than returning
    non-zero, which is why OSError is caught alongside the exit code.
    """
    try:
        r = subprocess.run(["git", *args], capture_output=True,
                           text=True, cwd=cwd)
    except (OSError, ValueError):
        return []
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def staged_files(cwd: str) -> list[str]:
    return git_lines(cwd, "diff", "--cached", "--name-only")


def tracked_files(cwd: str) -> list[str]:
    return git_lines(cwd, "ls-files")


def dirname(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def basename(path: str) -> str:
    return path.rsplit("/", 1)[1] if "/" in path else path


def unstaged_test_siblings(staged: list[str],
                           tracked: list[str]) -> list[tuple[str, str]]:
    """Pairs of (subject, its test sibling) where the test is not staged."""
    staged_set = set(staged)
    # Index every tracked test file by (directory, normalized subject stem).
    index: dict[tuple[str, str], str] = {}
    for path in tracked:
        name = basename(path)
        stem = test_stem(name)
        if stem is not None:
            index.setdefault((dirname(path), stem), path)

    pairs = []
    for path in staged:
        name = basename(path)
        if not name.endswith(SUBJECT_SUFFIXES):
            continue
        if is_test_name(name):
            continue
        subject_stem = norm(name.rsplit(".", 1)[0])
        sibling = index.get((dirname(path), subject_stem))
        if sibling and sibling not in staged_set:
            pairs.append((path, sibling))
    return pairs


def is_git_commit(command: str) -> bool:
    """True for a `git commit` anywhere in the command line.

    Segment-split so a commit inside a compound (`git add -A && git commit`)
    is seen, which is how these are usually written.
    """
    for seg in re.split(r"&&|\|\||;|\|", command):
        toks = seg.split()
        if "git" in toks:
            i = toks.index("git")
            rest = [t for t in toks[i + 1:] if not t.startswith("-")]
            if rest and rest[0] == "commit":
                return True
    return False


def main() -> int:
    is_dry_run = "--dry-run" in sys.argv
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not is_git_commit(command):
        if is_dry_run:
            print(json.dumps(
                {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    pairs = unstaged_test_siblings(staged_files(cwd), tracked_files(cwd))
    if not pairs:
        if is_dry_run:
            print(json.dumps(
                {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    subject, test = pairs[0]
    note = NOTE.format(subject=subject, test=test)
    if len(pairs) > 1:
        others = ", ".join(t for _, t in pairs[1:])
        note += f"\n\nAlso unstaged: {others}"

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"{basename(test)} is not staged alongside {basename(subject)}. "
            "Read it before deciding it needs no change."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
