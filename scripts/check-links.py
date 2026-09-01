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
FOOTNOTE_DEF = re.compile(r"^[ ]{0,3}\[\^([^\]\s]+)\]:[ \t]*(.*)$", re.MULTILINE)
FOOTNOTE_REF = re.compile(r"\[\^([^\]\s]+)\](?!:)")
REF_LINK_DEF = re.compile(
    r"^[ ]{0,3}\[(?!\^)([^\]]+)\]:[ \t]*<?([^\s>]+)>?(?:[ \t]+.*)?$",
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


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def check_target(target: str, md: Path, root: Path = ROOT) -> None:
    global checked
    # drop a trailing `"title"` if present
    target = target.split(" ", 1)[0].strip()
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
        broken.append(f"{_rel_path(md, root)} -> {target}")


def check_file(md: Path, root: Path = ROOT) -> None:
    global checked
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = strip_code_spans(text)

    # Footnote definitions and references (ai-config#2538)
    footnote_defs = {m.group(1).strip() for m in FOOTNOTE_DEF.finditer(text)}
    for match in FOOTNOTE_REF.finditer(text):
        ref = match.group(1).strip()
        checked += 1
        if ref not in footnote_defs:
            broken.append(f"{_rel_path(md, root)} -> [^{ref}]")

    # Inline links [text](target)
    for match in LINK.finditer(text):
        check_target(match.group(1).strip(), md, root=root)

    # Reference link definitions [label]: target
    for match in REF_LINK_DEF.finditer(text):
        check_target(match.group(2).strip(), md, root=root)


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
