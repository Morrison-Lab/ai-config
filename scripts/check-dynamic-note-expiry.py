#!/usr/bin/env python3
"""Fail when a memory note states a changing condition without an expiry date.

ai-config#5018.  Ezra, 2026-11-06: "cai: notes on dynamic conditions must
record their expiration dates", after a thread waived a review because a
project-memory note said the agy and OpenCode quotas were exhausted.  Both were
available.  `shared/workflow/live-state-over-notes.md` says a note never decides
a changing condition (the live probe does); this check makes the other half
mechanical: a note that does state one carries `expires YYYY-MM-DD`, so a
later reader can see that it has lapsed.

A note is a *state claim* when one sentence names a changing resource (a
reviewer, quota, runner, cluster, service) and says it is currently exhausted,
down, offline, unavailable or rate-limited.  A sentence that is conditional or
instructional ("when the quota is exhausted ...", "diagnose a runner that is
down") describes a mechanism, not the present, so it is not a state claim.
Known limitation: a sentence that opens with while/until is flagged even when
it is a conditional, since it cannot be told from a stative clause; it takes
the allow marker (ai-config#5035).

The unit is a bullet item or a paragraph.  The unit needs `expires
YYYY-MM-DD` (or `expire: ...`) somewhere in it, or the marker
`<!-- dynamic-note: allow -->` when the sentence is a state claim by wording
only.  Only unit text changed against the base ref is checked, so an existing
note is never reflagged for a line nobody touched.

Usage:
  check-dynamic-note-expiry.py [--base REF]    diff mode (default base: origin/main)
  check-dynamic-note-expiry.py --all           scan every memory file

Exit codes: 0 clean, 1 violations, 2 error or an empty search space.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RESOURCE = re.compile(
    r"\b(?:agy|antigravity|opencode|codex|gemini|copilot|cursor|claude(?:\s+code)?\s+(?:quota|budget)|"
    r"quotas?|budgets?|runners?|cf463\S*|clusters?|csci-\S+|cse-\S+|github\s+actions|pages|apis?|services?|servers?|reviewers?)\b", re.I)
STATE = re.compile(
    r"\b(?:is|are|remains?|stays?)\s+(?:currently\s+|still\s+|now\s+)?"
    r"(?:exhausted|offline|down|unavailable|rate[- ]limited|out\s+of\s+quota|over\s+(?:its\s+|the\s+)?(?:quota|limit)|"
    r"unreachable|blocked)\b|"
    r"\b(?:currently|right\s+now|at\s+the\s+moment|as\s+of\s+now)\b[^.]*"
    r"\b(?:exhausted|offline|down|unavailable|rate[- ]limited|unreachable|blocked)\b", re.I)
# A conditional or instructional sentence describes a mechanism, not the present.
MECHANISM = re.compile(
    r"\b(?:if|when|whenever|once|unless|how\s+to|diagnos\w*|detect\w*|check\w*|probe\w*|"
    r"means|looks?\s+like|returns?|before|after|so\s+that|in\s+case)\b", re.I)
# until/while are NOT mechanism words ("down until Monday", "While X holds, Y is
# down" claim the present); see the docstring's known limitation.
EXPIRES = re.compile(r"\bexpires?\b\s*:?\s*20\d\d-\d\d-\d\d", re.I)
ALLOW = "<!-- dynamic-note: allow -->"
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def is_state_claim(unit):
    """True when some sentence of *unit* claims a resource is currently down."""
    # A quoted phrase is an example of wording, not an assertion by the note.
    unit = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', " ", unit)
    for s in SENTENCE.split(" ".join(unit.split())):
        if STATE.search(s) and RESOURCE.search(s) and not MECHANISM.search(s):
            return True
    return False


def units(lines):
    """Yield (first_line_no, last_line_no, text) for each bullet, paragraph,
    or table row.

    A table row is its own unit. To the blank-line rule a table is one
    paragraph, so a row added to a table made every older row a changed unit,
    and one row's wording could fail the whole table. A plain line after a row
    starts a new unit too, so it cannot shelter under the row's expiry date.
    """
    start, buf = None, []
    for i, line in enumerate(lines, 1):
        blank = not line.strip()
        after_row = bool(buf) and TABLE_ROW.match(buf[-1])
        if blank or BULLET.match(line) or TABLE_ROW.match(line) or after_row:
            if buf:
                yield start, i - 1, "\n".join(buf)
            start, buf = (None, []) if blank else (i, [line])
        else:
            if not buf:
                start = i
            buf.append(line)
    if buf:
        yield start, len(lines), "\n".join(buf)


def violations(lines, changed=None):
    """(line_no, text) for each state-claim unit lacking an expiry date.
    *changed* limits the check to units that hold a changed line number."""
    found = []
    for first, last, text in units(lines):
        if changed is not None and not any(first <= n <= last for n in changed):
            continue
        if ALLOW in text or EXPIRES.search(text):
            continue
        if is_state_claim(text):
            found.append((first, text.splitlines()[0].strip()))
    return found


def memory_files(root):
    files = sorted((root / "memories").glob("**/*.md"))
    files += sorted(root.glob("**/project-memory.md"))
    return [f for f in files if ".git" not in f.parts]


def added_lines(root, base, path):
    out = subprocess.run(
        ["git", "diff", "--unified=0", f"{base}...HEAD", "--", str(path)],
        cwd=root, capture_output=True, text=True, check=True).stdout
    nums = set()
    for m in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        nums.update(range(start, start + count))
    return nums


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--all", action="store_true", help="scan every memory file")
    args = ap.parse_args(argv)
    files = memory_files(REPO)
    if not files:
        print("error: no memory files found; the search space is empty", file=sys.stderr)
        return 2
    bad, scanned = [], 0
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        if args.all:
            changed = None
        else:
            try:
                changed = added_lines(REPO, args.base, f.relative_to(REPO))
            except subprocess.CalledProcessError as e:
                print(f"error: git diff against {args.base} failed: {e.stderr}", file=sys.stderr)
                return 2
            if not changed:
                continue
        scanned += 1
        bad += [(f.relative_to(REPO), n, t) for n, t in violations(lines, changed)]
    for path, n, text in bad:
        print(f"{path}:{n}: states a changing condition with no `expires YYYY-MM-DD`: {text[:100]}")
    if bad:
        print("\nAdd `expires YYYY-MM-DD` to the note (a live probe, not this note, "
              "decides the condition; shared/workflow/live-state-over-notes.md), or "
              f"`{ALLOW}` if the wording is not a claim about the present.", file=sys.stderr)
        return 1
    print(f"ok: {scanned} changed memory file(s) examined, no undated state claim"
          if not args.all else f"ok: {len(files)} memory file(s) examined, no undated state claim")
    return 0


if __name__ == "__main__":
    sys.exit(main())
