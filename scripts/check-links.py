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
from fences import strip_fences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
AUTOLINK = re.compile(r"<([a-zA-Z][a-zA-Z0-9+.-]*:[^<>\s]+|[^<>\s]+@[^<>\s]+)>")
# Strip code regions first so link-shaped examples inside fences / backticks
# (regexes, `[text](url)` snippets) aren't mistaken for real links.
INLINE = re.compile(r"`[^`]*`")
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
    return (
        target.startswith(SKIP_PREFIXES)
        or "://" in target
        or ("@" in target and ":" not in target and "/" not in target)
    )


def extract_targets(text: str) -> list[str]:
    """Extract link targets from markdown text after stripping code blocks."""
    text = strip_fences(text)
    text = INLINE.sub("", text)
    targets: list[str] = []
    for match in LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1].strip()
        # drop a trailing `"title"` if present
        target = target.split(" ", 1)[0]
        if target:
            targets.append(target)
    # Strip standard links before scanning autolinks so destinations in `[text](<url>)`
    # are not matched twice.
    text_without_links = LINK.sub("", text)
    for match in AUTOLINK.finditer(text_without_links):
        target = match.group(1).strip()
        if target:
            targets.append(target)
    return targets


def check_target(target: str, md: Path) -> None:
    global checked
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
            rel_path = md.relative_to(ROOT)
        except ValueError:
            rel_path = md
        broken.append(f"{rel_path} -> {target}")


def check_file(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    for target in extract_targets(text):
        check_target(target, md)


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
