#!/usr/bin/env python3
"""Check that relative markdown links in this repo point to real files.

Guards this repo's cross-referenced markdown --- every tree named in
`SCAN_GLOBS` below --- against broken relative links (e.g. a renamed or
deleted target).
External links (http(s), mailto, anchors) and autolinks are skipped
when external or verified when relative.
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
AUTOLINK = re.compile(r"<([^<>\s]+)>")
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
    """Return True if target is an external URL, email, or in-page anchor."""
    return (
        target.startswith(SKIP_PREFIXES)
        or "://" in target
        or ("@" in target and "." in target and "/" not in target)
    )


def is_html_tag_or_placeholder(target: str) -> bool:
    """Return True if target is an HTML tag, comment, or placeholder."""
    if target.startswith(("!", "/", "?")) or target.endswith("/"):
        return True
    if re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", target):
        return True
    return False


def check_target(
    target: str,
    md: Path,
    *,
    is_autolink: bool = False,
    root: Path = ROOT,
) -> None:
    """Validate a single link target against the filesystem."""
    global checked
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split(" ", 1)[0]
    if not target or is_external(target):
        return
    if is_autolink and is_html_tag_or_placeholder(target):
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
        formatted = f"<{target}>" if is_autolink else target
        try:
            rel_path = md.relative_to(root)
        except ValueError:
            rel_path = md.name
        broken.append(f"{rel_path} -> {formatted}")


def check_file(md: Path, *, root: Path = ROOT) -> None:
    """Check all markdown inline links and autolinks in a single file."""
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = strip_code_spans(text)
    for match in LINK.finditer(text):
        check_target(match.group(1), md, is_autolink=False, root=root)
    text_without_links = LINK.sub(" ", text)
    for match in AUTOLINK.finditer(text_without_links):
        check_target(match.group(1), md, is_autolink=True, root=root)


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
