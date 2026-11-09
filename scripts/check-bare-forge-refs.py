#!/usr/bin/env python3
"""Fail on a bare `repo#N` or `owner/repo#N` on a line a branch adds to a `.md` file.

`shared/writing/link-forge-artifacts.md` requires every PR, issue or run a
document names to be a link.  Chat replies are covered by the
`warn-bare-forge-reference` hook; nothing covered committed prose, and the
Claude review caught a bare `pds#364` on ai-config#5131 (ai-config#5132).

Scope, decided so the check can gate without crying wolf:

* only lines the branch ADDS (`git diff -U0 <base>...HEAD`), so an old bare
  reference elsewhere never blocks an unrelated PR;
* fenced code blocks and inline code spans are skipped, as are the text and
  target of a markdown link, bare URLs, and HTML comments;
* the gating form is `name#N` or `owner/name#N`, where `name` is a lowercase
  repository-shaped word (`pre-#2085` and `v1.2.3#4` do not match; a rare word
  such as `section#4` still can, and `<!-- bare-ref: allow -->` clears it).
  A bare `#N` is reported as advisory only, because
  within the repository that owns the file it can be a heading anchor or a
  citation style the file chose;
* `<!-- bare-ref: allow -->` on the line exempts it, for prose that discusses
  the notation itself (the same shape as `check-term-links: allow`).

Exit status 1 when a gating finding exists, 0 otherwise; `--advisory` always
exits 0.  CI runs it with `--advisory` because the corpus already holds many
bare references (14 gating findings on the last 40 commits of main,
2026-11-09), so gating there would block unrelated PRs until a cleanup lands.
Run it without the flag before pushing a prose change.  It reports how many
files and added lines it examined, so a run that scanned nothing is
distinguishable from a clean branch.

Usage:
    python3 scripts/check-bare-forge-refs.py [--advisory] [BASE]    # BASE defaults to origin/main
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.fences import strip_fences  # noqa: E402

ALLOW = "bare-ref: allow"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
CODE_SPAN = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")
URL = re.compile(r"https?://\S+")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# A repository name is lowercase, hyphenated at most, and ends in a letter or
# digit, so `pre-#2085`, `v1.2.3#4` and `CVE-2021-1234#5` do not match.
REPO = r"[a-z][a-z0-9_\-]*[a-z0-9]|[a-z]"
STRONG = re.compile(rf"(?<![\w/#@.\-])(?:[\w.\-]+/)?(?:{REPO})#\d+\b")
WEAK = re.compile(r"(?<![\w&/#\-])#\d+\b")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def added_lines(base: str) -> dict[str, set[int]]:
    """Map each changed `.md` path to the line numbers the branch adds."""
    out: dict[str, set[int]] = {}
    path = None
    for row in git("diff", "-U0", "--no-color", f"{base}...HEAD", "--", "*.md").splitlines():
        if row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else None
            continue
        match = HUNK.match(row)
        if match and path:
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            out.setdefault(path, set()).update(range(start, start + count))
    return out


def scrub(line: str) -> str:
    for pattern in (COMMENT, CODE_SPAN, LINK, URL):
        line = pattern.sub(" ", line)
    return line


def scan(text: str, wanted: set[int]) -> list[tuple[int, str, bool]]:
    """Return (line number, reference, gating) for each bare reference."""
    findings = []
    # Blank comments over the whole text, newlines kept, so a comment whose
    # delimiters sit on different lines hides what is inside it.
    blanked = COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    fenced = strip_fences(blanked).split("\n")
    raw = text.split("\n")
    for number in sorted(wanted):
        if number > len(fenced) or ALLOW in raw[number - 1]:
            continue
        line = scrub(fenced[number - 1])
        for match in STRONG.finditer(line):
            findings.append((number, match.group(0), True))
        for match in WEAK.finditer(line):
            findings.append((number, match.group(0), False))
    return findings


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--advisory"]
    advisory = "--advisory" in argv[1:]
    base = args[0] if args else "origin/main"
    try:
        changed = added_lines(base)
    except subprocess.CalledProcessError as error:
        print(f"check-bare-forge-refs: cannot diff against {base}: {error.stderr.strip()}")
        return 1
    gating = 0
    total_lines = 0
    for path, wanted in sorted(changed.items()):
        file = Path(path)
        if not file.is_file():
            continue
        total_lines += len(wanted)
        for number, ref, strong in scan(file.read_text(encoding="utf-8"), wanted):
            kind = "bare reference" if strong else "bare #N (advisory)"
            print(f"{path}:{number}: {kind} `{ref}`: write it as a link")
            gating += strong
    print(f"examined {len(changed)} changed .md file(s), {total_lines} added line(s) against {base}")
    return 1 if gating and not advisory else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
