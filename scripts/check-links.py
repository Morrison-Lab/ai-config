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
from fences import strip_code  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
AUTOLINK = re.compile(
    r"<("
    r"[a-zA-Z][a-zA-Z0-9+.-]{1,31}:[^<>\x00-\x20]*"
    r"|"
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*"
    r")>"
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
URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]{1,31}:")
EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

broken: list[str] = []
checked = 0


def is_external(target: str) -> bool:
    if target.startswith(SKIP_PREFIXES) or "://" in target:
        return True
    if URI_RE.match(target):
        return True
    if EMAIL_RE.match(target):
        return True
    return False


def extract_target(raw: str) -> str:
    target = raw.strip()
    m = re.match(r"^<([^>]+)>(?:\s+.*)?$", target)
    if m:
        return m.group(1).strip()
    return target.split(" ", 1)[0].strip()


def check_target(target: str, md: Path, root: Path = ROOT) -> None:
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
        broken.append(f"{md.relative_to(root)} -> {target}")


def check_file(md: Path, root: Path = ROOT) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_code(text)
    for match in LINK.finditer(text):
        target = extract_target(match.group(1))
        check_target(target, md, root=root)
    for match in AUTOLINK.finditer(text):
        target = match.group(1).strip()
        check_target(target, md, root=root)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    seen: set[Path] = set()
    for glob in SCAN_GLOBS:
        for md in ROOT.glob(glob):
            if md.is_file() and md not in seen:
                seen.add(md)
                check_file(md, root=ROOT)
    print(f"Checked {checked} relative links across {len(seen)} markdown files.")
    if broken:
        print(f"\n✗ {len(broken)} broken link(s):")
        for b in broken:
            print(f"  - {b}")
        sys.exit(1)
    print("✓ no broken relative links")


if __name__ == "__main__":
    main()
