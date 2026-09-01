#!/usr/bin/env python3
"""Check that relative markdown links in this repo point to real files.

Guards this repo's cross-referenced markdown --- every tree named in
`SCAN_GLOBS` below --- against broken relative links (e.g. a renamed or
deleted target).
External links (http(s), mailto, anchors) are skipped.
Clean-room; convention noted in CREDITS.md.

Exits non-zero if any relative link target is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import strip_code_spans, strip_fences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REF_DEF = re.compile(
    r"^[ ]{0,3}\[[^\]\n]+\]:[ \t]*(?:\r?\n[ \t]*)?(?:<([^>\r\n]+)>|(\S+))"
    r"(?:[ \t]*(?:\r?\n[ \t]*)?(?:"
    r'"(?:[^"\\\n\r]|\\.|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*"'
    r"|'(?:[^'\\\n\r]|\\.|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*'"
    r"|\((?:[^()\\\n\r]|\\.|(?:\([^\(\)]*\))|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*\)"
    r"))?[ \t]*$",
    re.MULTILINE,
)
SCAN_GLOBS = [
    "skills/**/*.md",
    "codex-skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    "*.md",
]
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

broken: list[str] = []
checked = 0


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def clean_target(target: str) -> str | None:
    """Normalize a link target, returning the relative path or None if skipped."""
    target = target.strip()
    # drop a trailing `"title"` if present
    target = target.split(" ", 1)[0]
    target = target.split("\t", 1)[0]
    target = target.split("\n", 1)[0]
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:  # pure in-page anchor
        return None
    if "/" not in path_part and "." not in path_part:
        return None  # bare-word placeholder in an example, e.g. (url)
    return path_part


def find_targets(text: str) -> list[str]:
    """Find all relative link targets in markdown text."""
    cleaned = strip_code_spans(strip_fences(text))
    targets: list[str] = []

    # 1. Inline links: [text](url)
    for match in INLINE_LINK.finditer(cleaned):
        path = clean_target(match.group(1))
        if path is not None:
            targets.append(path)

    # 2. Link reference definitions: [label]: url (title)
    for match in REF_DEF.finditer(cleaned):
        raw = match.group(1) or match.group(2)
        if raw:
            path = clean_target(raw)
            if path is not None:
                targets.append(path)

    return targets


def check_file(md: Path) -> None:
    global checked
    text = md.read_text(encoding="utf-8")
    for target in find_targets(text):
        checked += 1
        resolved = (md.parent / target).resolve()
        if not resolved.exists():
            try:
                rel = md.relative_to(ROOT)
            except ValueError:
                rel = md
            broken.append(f"{rel} -> {target}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    seen: set[Path] = set()
    for glob in SCAN_GLOBS:
        for md in ROOT.glob(glob):
            if md.is_file() and md not in seen:
                seen.add(md)
                check_file(md)
    print(f"Checked {checked} relative links across {len(seen)} markdown files.")
    if broken:
        print(f"\n✗ {len(broken)} broken link(s):")
        for b in broken:
            print(f"  - {b}")
        sys.exit(1)
    print("✓ no broken relative links")


if __name__ == "__main__":
    main()
