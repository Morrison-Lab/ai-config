#!/usr/bin/env python3
"""Fail when a person-shaped placeholder sits in a VALUE position.

Morrison-Lab/ai-config#2627. This plugin is used by people other than its
author, so a hardcoded login is correct for at most one of them (user
directive, 2026-08-29). Most occurrences of that phrase in this corpus are fine, because a sentence like "request the
repository owner as reviewer" is a ROLE reference and is exactly the
user-agnostic form wanted.

What is not fine is the same phrase in a value position -- an `owner:`
argument, a `--reviewer` flag, a `reviewers[]=` field, a `"login"` value --
where a literal string is passed to an API. There it is a username containing
spaces, valid for nobody. `scripts/orchestrator/subagents.py` shipped exactly
that: the phrase as the sole element of a `reviewers=[...]` literal, POSTed
verbatim to the API.

So this gate keys on POSITION, not on the phrase. It is deliberately narrow:
a false positive here blocks CI over prose, and the prose form is the one the
corpus should keep using.

Exempt by construction: an angle-bracket placeholder (`<owner>`, `<reviewer>`,
`<pre-move-owner>`) is what a value position SHOULD contain, so those pass.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# A value position: the phrase reached where an API expects an identifier.
# Each alternative names a concrete call shape rather than matching loosely,
# so a new shape is a deliberate addition rather than an accidental catch.
# Every alternative allows an optional surrounding quote, because quoting is
# exactly what anyone writing a two-word value into a shell command does -- so
# an unquoted-only pattern is blind to the likeliest spelling of the defect.
# The command forms come from the set `hooks/no-unreviewed-pr.py` already
# enumerates for this one effect (see derive-dont-enumerate.md): the corpus
# knew the effect had several spellings while an earlier grep searched for one.
Q = r"[\"']?"
NAME = r"the repository owner"
PATTERNS = [
    (rf"owner\s*[:=]\s*{Q}{NAME}", "an `owner:` argument"),
    (rf"reviewers?\[\]\s*=\s*{Q}{NAME}", "a `reviewers[]=` field"),
    (rf"--(?:add-)?reviewers?[\s=]+{Q}{NAME}", "a `--reviewer` flag"),
    (rf"(?:^|\s)-r[\s=]+{Q}{NAME}", "a `-r` reviewer flag"),
    (rf"--head[\s=]+{Q}{NAME}", "a `--head` argument"),
    (rf"{Q}login{Q}\s*:\s*{Q}{NAME}", "a `login` value"),
    (rf"reviewers{Q}\s*[:=]\s*\[\s*{Q}{NAME}", "a `reviewers` array"),
    (rf"reviewers{Q}\s*:\s*(?:\n\s*)?-\s+{Q}{NAME}", "a YAML `reviewers:` list item"),
]

# .qmd is the published website source and .mdc mirrors cursor-rules/;
# omitting them hid the user-facing copy of this very instruction, which is
# the one surface a new user actually reads.
SUFFIXES = {".md", ".qmd", ".mdc", ".py", ".sh", ".json", ".yml", ".yaml"}


def tracked_files():
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            capture_output=True, encoding="utf-8", check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # Fail loudly rather than scanning nothing: a gate that examined zero
        # files reports clean and is indistinguishable from a passing one.
        print(f"::error::cannot list tracked files: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return [REPO / p for p in out.split("\0") if p]


def scan(paths):
    findings = []
    examined = 0
    for path in paths:
        if path.suffix not in SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        examined += 1
        # Match over the whole file with newlines folded to spaces: a value
        # position wrapped across a line break is invisible to a per-line scan,
        # and that is exactly how the published .qmd copy was written.
        flat = re.sub(r"\s+", " ", text)
        lines = text.splitlines()
        for pattern, what in PATTERNS:
            if not re.search(pattern, flat):
                continue
            # Report the first line whose own text starts the match, falling
            # back to the first line naming the phrase, so the annotation
            # points somewhere real rather than at line 1.
            line_no = next(
                (i for i, ln in enumerate(lines, 1) if NAME in ln), 1
            )
            findings.append(
                (path.relative_to(REPO), line_no, what, lines[line_no - 1].strip())
            )
    return findings, examined


def main():
    findings, examined = scan(tracked_files())
    if examined == 0:
        # A gate that examined nothing reports clean and is indistinguishable
        # from a passing one. The exception handler above covers only the git
        # failure; this covers every other route to an empty population.
        print("::error::examined 0 files -- the gate did not run", file=sys.stderr)
        return 2
    # Report the population, not just the hits: a zero with no denominator is
    # indistinguishable from a detector that never ran.
    print(f"Examined {examined} tracked file(s) for person-shaped values.")
    if not findings:
        print("✓ no hardcoded person-name in a value position.")
        return 0
    for rel, line_no, what, text in findings:
        print(f"::error file={rel},line={line_no}::"
              f"'the repository owner' used as {what}; it is not a username. "
              f"Use a placeholder (<owner>, <reviewer>) or read it from config. "
              f"| {text[:120]}")
    print(f"\n{len(findings)} value-position use(s) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
