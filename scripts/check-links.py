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
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REF_DEF = re.compile(
    r"^[ ]{0,3}\[(?!\^)(?P<label>(?:\\\]|[^\]\n])+)\]:[ \t]*(?:\r?\n[ \t]*)?"
    r"(?:<(?P<dest_bracket>[^>\r\n]+)>|(?P<dest_bare>[^ \t\r\n]+))"
    r"(?:[ \t]*(?:\r?\n[ \t]*)?(?:"
    r'"(?:[^"\\\r\n]|\\.|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*"'
    r"|'(?:[^'\\\r\n]|\\.|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*'"
    r"|\((?:[^()\\\r\n]|\\.|\([^\(\)\r\n]*\)|(?:\r?\n(?![ \t]*\r?\n)[ \t]*))*\)"
    r"))?"
    r"[ \t]*(?:<!--.*?-->[ \t]*)*(?:\r?\n|$)",
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


def check_target(md: Path, raw_target: str) -> None:
    global checked
    target = raw_target.strip()
    target = target.split(None, 1)[0]
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target or is_external(target):
        return
    if "<" in target or ">" in target:
        return  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:  # pure in-page anchor
        return
    if "/" not in path_part and "." not in path_part:
        return  # bare-word placeholder in an example, e.g. (url)
    checked += 1
    resolved = (md.parent / path_part).resolve()
    if not resolved.exists():
        try:
            rel = md.relative_to(ROOT)
        except ValueError:
            rel = md
        broken.append(f"{rel} -> {target}")


def check_file(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = strip_code_spans(text)
    for match in LINK.finditer(text):
        check_target(md, match.group(1))
    for match in REF_DEF.finditer(text):
        dest = match.group("dest_bracket") or match.group("dest_bare")
        if dest:
            check_target(md, dest)


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
