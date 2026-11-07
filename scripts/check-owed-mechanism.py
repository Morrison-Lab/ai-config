#!/usr/bin/env python3
"""Fail when a memory note says a check/hook is owed with no linked issue.

ai-config#5049.  Ezra, 2026-11-07 ("why not?", then "empty promise?"): project
memory said a hook was "owed" (the Stop hook for announced-but-undone work, owed
since 2026-10-30) and nobody filed the issue, so it was never built.  A note
that names a debt without a tracker link is itself an empty promise, and an
issue is the only form of the debt another session can find.

A unit (bullet item or paragraph) is *owed-without-a-link* when one sentence
says a check, hook or other mechanism is owed, needed, a TODO, not yet filed or
to be built, and the unit holds no issue or PR reference (`#NNN`,
`owner/repo#NNN`, or a `/issues/N` or `/pull/N` URL).  A sentence that is
conditional or instructional ("when a rule needs a check, file its issue")
describes a procedure, not a debt, so it is not flagged.  A unit that names
the phrase only as wording takes `<!-- owed-mechanism: allow -->`.

Only unit text changed against the base ref is checked, so an existing note is
never reflagged for a line nobody touched.  The unit and diff helpers are
imported from check-dynamic-note-expiry.py so the two never drift.

Usage:
  check-owed-mechanism.py [--base REF]    diff mode (default base: origin/main)
  check-owed-mechanism.py --all           scan every covered file

Exit codes: 0 clean, 1 violations, 2 error or an empty search space.
"""
import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "cdne", REPO / "scripts" / "check-dynamic-note-expiry.py")
cdne = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdne)

MECH = r"(?:checks?|hooks?|lint(?:er|s)?|guards?|mechanisms?|instruments?|gates?)"
# "needed" alone is ordinary prose; it counts only right after the mechanism word.
OWED = re.compile(
    r"\bowed\b|\bTODO\b|"
    rf"\b{MECH}\s+(?:is|are|still)\s+(?:still\s+)?needed\b|"
    r"\bnot\s+yet\s+(?:filed|built|written|implemented)\b|"
    r"\bto\s+be\s+(?:built|written|implemented|filed)\b",
    re.I)
MECHANISM_WORD = re.compile(rf"\b{MECH}\b", re.I)
# A conditional or instructional sentence describes a procedure, not a debt.
PROCEDURE = re.compile(
    r"\b(?:if|when|whenever|once|unless|whether|how\s+to|before|after|in\s+case)\b", re.I)
# "No separate hook is needed" denies a debt. "not yet filed" is a debt, so
# `not` counts as a negation only when `yet` does not follow it.
NEGATED = re.compile(r"\b(?:no|never|nothing)\b|n't\b|\bnot\b(?!\s+yet\b)", re.I)
CLAUSE = re.compile(r"[,;:]|\s+(?:but|although|though|while|and)\s+", re.I)
LINK = re.compile(r"(?:^|[\s(\[])(?:[\w.-]+/[\w.-]+)?#\d+\b|/(?:issues|pull)/\d+")
ALLOW = "<!-- owed-mechanism: allow -->"
# Straight-quoted, curly-quoted and code-span text is wording, not an assertion.
# The curly quotes come from code points so this source stays ASCII
# (check-ascii-punctuation).
LQ, RQ = chr(0x201C), chr(0x201D)
QUOTED = "\"[^\"]*\"|" + LQ + "[^" + RQ + "]*" + RQ + "|`[^`]*`"


def is_owed_claim(unit):
    """True when some sentence of *unit* says a mechanism is owed."""
    unit = re.sub(QUOTED, " ", unit)
    for s in cdne.SENTENCE.split(" ".join(unit.split())):
        if not (MECHANISM_WORD.search(s) and not PROCEDURE.search(s)):
            continue
        # Negation is judged per clause: "the old guard isn't needed, but a new
        # check is owed" denies one need and asserts another debt.
        if any(OWED.search(c) and not NEGATED.search(c) for c in CLAUSE.split(s)):
            return True
    return False


def violations(lines, changed=None):
    """(line_no, text) for each owed-claim unit holding no issue/PR reference.
    *changed* limits the check to units that hold a changed line number."""
    found = []
    for first, last, text in cdne.units(lines):
        if changed is not None and not any(first <= n <= last for n in changed):
            continue
        if ALLOW in text or LINK.search(text):
            continue
        if is_owed_claim(text):
            found.append((first, text.splitlines()[0].strip()))
    return found


def covered_files(root):
    files = sorted((root / "memories").glob("**/*.md"))
    files += sorted(root.glob("**/project-memory.md"))
    return [f for f in dict.fromkeys(files) if ".git" not in f.parts]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--all", action="store_true", help="scan every covered file")
    args = ap.parse_args(argv)
    files = covered_files(REPO)
    if not files:
        print("error: no covered files found; the search space is empty", file=sys.stderr)
        return 2
    bad, scanned = [], 0
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        if args.all:
            changed = None
        else:
            try:
                changed = cdne.added_lines(REPO, args.base, f.relative_to(REPO))
            except subprocess.CalledProcessError as e:
                print(f"error: git diff against {args.base} failed: {e.stderr}", file=sys.stderr)
                return 2
            if not changed:
                continue
        scanned += 1
        bad += [(f.relative_to(REPO), n, t) for n, t in violations(lines, changed)]
    for path, n, text in bad:
        print(f"{path}:{n}: says a check or hook is owed with no issue or PR link: {text[:100]}")
    if bad:
        print("\nFile the issue now and link it in the same unit (`#NNN` or its URL); "
              "a note that names a debt without a tracker link is an empty promise "
              f"(shared/workflow/no-empty-promises.md). `{ALLOW}` if the wording is "
              "not a claim of a debt.", file=sys.stderr)
        return 1
    print(f"ok: {scanned} file(s) examined, no owed mechanism without a link")
    return 0


if __name__ == "__main__":
    sys.exit(main())
