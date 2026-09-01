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

# Link reference definition: [label]: target "optional title"
REF_DEF = re.compile(
    r"^[ ]{0,3}\[([^\]\r\n]+)\]:[ \t]*(?:\r?\n[ \t]*)?(?:<([^>\r\n]+)>|(\S+))",
    re.MULTILINE,
)

# Inline links, full/collapsed reference links, or potential shortcut reference links.
LINK_USAGE = re.compile(
    r"\[(?P<inline_text>[^\]]*)\]\((?P<inline_dest>[^)]+)\)"
    r"|\[(?P<ref_text>[^\]]+)\]\[(?P<ref_label>[^\]]*)\]"
    r"|\[(?P<shortcut_label>[^\]]+)\]"
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


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip()).casefold()


def check_target(md: Path, raw_target: str, *, root: Path = ROOT) -> None:
    global checked
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # drop a trailing `"title"` if present
    target = target.split(" ", 1)[0]
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


def check_file(md: Path, *, root: Path = ROOT) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_code(text)

    ref_defs: dict[str, str] = {}
    for match in REF_DEF.finditer(text):
        label = normalize_label(match.group(1))
        if label and label not in ref_defs:
            dest = match.group(2) if match.group(2) is not None else match.group(3)
            ref_defs[label] = dest

    # Remove definitions before scanning usages so definition labels are not
    # treated as shortcut links.
    text_without_defs = REF_DEF.sub("", text)
    used_labels: set[str] = set()

    for match in LINK_USAGE.finditer(text_without_defs):
        if match.group("inline_dest") is not None:
            check_target(md, match.group("inline_dest"), root=root)
        elif match.group("ref_text") is not None:
            raw_label = match.group("ref_label")
            label = (
                normalize_label(raw_label)
                if raw_label.strip()
                else normalize_label(match.group("ref_text"))
            )
            if label in ref_defs:
                used_labels.add(label)
                check_target(md, ref_defs[label], root=root)
        elif match.group("shortcut_label") is not None:
            label = normalize_label(match.group("shortcut_label"))
            if label in ref_defs:
                used_labels.add(label)
                check_target(md, ref_defs[label], root=root)

    # Check any definitions not referenced in link usages.
    for label, dest in ref_defs.items():
        if label not in used_labels:
            check_target(md, dest, root=root)


def main(root: Path = ROOT) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    seen: set[Path] = set()
    for glob in SCAN_GLOBS:
        for md in root.glob(glob):
            if md.is_file() and md not in seen:
                seen.add(md)
                check_file(md, root=root)
    print(f"Checked {checked} relative links across {len(seen)} markdown files.")
    if broken:
        print(f"\n✗ {len(broken)} broken link(s):")
        for b in broken:
            print(f"  - {b}")
        return 1
    print("✓ no broken relative links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
