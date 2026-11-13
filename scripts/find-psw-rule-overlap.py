#!/usr/bin/env python3
"""List the psw lines that already use a fragment's example words.

ai-config#5628. On 2026-11-13 a thread porting ai-config fragments to psw
searched psw for a fragment's concept words ("volatile", "timestamp"), found
nothing, and added a rule psw already had: word-choice.qmd's time-relative
word rule (psw#418), which names "now" and "recently", the very words the
fragment quotes as examples. Only psw CI's check-avoided-words warning
exposed it.

A rule's example words are often the only words two statements of the same
rule share, so this script searches for them deterministically: it extracts
the short double-quoted phrases a fragment uses (one to three words of
letters, apostrophes and hyphens, at least two characters) and greps every
.qmd and .md file under a psw checkout for each, as a whole word (a hyphen
does not count as a boundary) and ignoring case. Curly apostrophes in psw are
read as straight ones.

It does not decide whether a hit is the same rule; read the hits. It exits 0
whether or not anything matched, 2 on a missing path or when the fragment
yields no phrases (an empty search space is not a clean result).

No CI gate runs it: nothing in ai-config's CI knows a port is under way, and
psw's own check-avoided-words already warns after the fact. The point is to
run the search before drafting.

Usage:
  find-psw-rule-overlap.py FRAGMENT [FRAGMENT ...] --psw DIR
"""
import argparse
import re
import sys
from pathlib import Path

QUOTED = re.compile(r'"([A-Za-z][A-Za-z\' -]{1,40})"')
MAX_WORDS = 3
CURLY_APOSTROPHE = chr(0x2019)
SKIP_DIRS = {"_site", "_freeze", ".quarto", "_extensions", "node_modules", ".git"}


def example_phrases(text):
    """Short double-quoted phrases, lower-cased, in first-seen order."""
    seen = []
    for match in QUOTED.finditer(text):
        phrase = match.group(1).strip().lower()
        if not phrase or len(phrase.split()) > MAX_WORDS:
            continue
        if phrase not in seen:
            seen.append(phrase)
    return seen


def psw_files(root):
    """The prose files under a psw checkout, skipping build output."""
    files = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".qmd", ".md"} or not path.is_file():
            continue
        if SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def hits(phrase, files, root):
    """(quoted, relative path, line number, line) for each line holding the phrase.

    `quoted` is True when the line quotes the phrase itself, as a rule naming
    the word does ("Do not write "now""); those hits sort first, since common
    example words ("now", "still") also appear in ordinary prose.
    """
    word = r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])"
    pattern = re.compile(word, re.IGNORECASE)
    quoted_pattern = re.compile(r"[\"*`]" + word + r"[\"*`]", re.IGNORECASE)
    found = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace").replace(CURLY_APOSTROPHE, "'")
        lines = text.splitlines()
        for number, line in enumerate(lines, start=1):
            if pattern.search(line):
                quoted = bool(quoted_pattern.search(line))
                found.append((quoted, path.relative_to(root).as_posix(), number, line.strip()))
    found.sort(key=lambda hit: not hit[0])
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fragments", nargs="+", type=Path)
    parser.add_argument("--psw", required=True, type=Path, help="a psw checkout")
    parser.add_argument("--max-lines", type=int, default=5,
                        help="hit lines shown per phrase (default 5)")
    args = parser.parse_args(argv)

    if not args.psw.is_dir():
        print(f"error: {args.psw} is not a directory", file=sys.stderr)
        return 2
    files = psw_files(args.psw)
    if not files:
        print(f"error: no .qmd or .md files under {args.psw}", file=sys.stderr)
        return 2

    phrases = []
    for fragment in args.fragments:
        if not fragment.is_file():
            print(f"error: {fragment} is not a file", file=sys.stderr)
            return 2
        for phrase in example_phrases(fragment.read_text(encoding="utf-8")):
            if phrase not in phrases:
                phrases.append(phrase)
    if not phrases:
        print("error: no quoted example phrases found in the fragment(s)", file=sys.stderr)
        return 2

    matched = 0
    quoting = {}
    for phrase in phrases:
        found = hits(phrase, files, args.psw)
        if not found:
            continue
        matched += 1
        n_quoted = sum(1 for hit in found if hit[0])
        print(f'"{phrase}": {len(found)} line(s), {n_quoted} quoting it')
        for quoted, rel, number, line in found[:args.max_lines]:
            mark = "Q" if quoted else " "
            print(f"  {mark} {rel}:{number}: {line[:120]}")
            if quoted:
                quoting.setdefault(rel, set()).add(phrase)
    print(f"{matched} of {len(phrases)} phrase(s) found across {len(files)} psw file(s).")
    if quoting:
        print("Files quoting the fragment's example phrases (most likely to state the rule):")
        for rel, quoted_phrases in sorted(quoting.items(), key=lambda item: -len(item[1])):
            print(f"  {rel}: {', '.join(sorted(quoted_phrases))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
