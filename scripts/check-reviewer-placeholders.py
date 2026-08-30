#!/usr/bin/env python3
"""Fail when a person-shaped placeholder sits in a VALUE position.

Morrison-Lab/ai-config#2627. This plugin is used by people other than its
author, so a hardcoded login is correct for at most one of them (user
directive, 2026-08-29). The corpus had 103 occurrences of the phrase "the
repository owner"; most were fine, because a sentence like "request the
repository owner as reviewer" is a ROLE reference and is exactly the
user-agnostic form wanted.

What is not fine is the same phrase in a value position -- an `owner:`
argument, a `--reviewer` flag, a `reviewers[]=` field, a `"login"` value --
where a literal string is passed to an API. There it is a username containing
spaces, valid for nobody. `scripts/orchestrator/subagents.py` shipped exactly
that: `reviewers=["the repository owner"]`, POSTed verbatim.

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
PATTERNS = [
    (r"owner\s*[:=]\s*[\"']?the repository owner", "an `owner:` argument"),
    (r"reviewers?\[\]\s*=\s*the repository owner", "a `reviewers[]=` field"),
    (r"--(?:add-)?reviewers?\s+the repository owner", "a `--reviewer` flag"),
    (r"--head\s+the repository owner", "a `--head` argument"),
    (r"[\"']login[\"']\s*:\s*[\"']the repository owner", "a `login` value"),
    (r"reviewers\s*=\s*\[\s*[\"']the repository owner", "a `reviewers=[...]` literal"),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
SUFFIXES = {".md", ".py", ".sh", ".json", ".yml", ".yaml"}


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
        if SKIP_DIRS & set(path.relative_to(REPO).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        examined += 1
        for i, line in enumerate(text.splitlines(), 1):
            for pattern, what in PATTERNS:
                if re.search(pattern, line):
                    findings.append((path.relative_to(REPO), i, what, line.strip()))
    return findings, examined


def main(argv=None):
    findings, examined = scan(tracked_files())
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
