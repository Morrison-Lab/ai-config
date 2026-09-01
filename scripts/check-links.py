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
REF_DEF = re.compile(
    r"^[ ]{0,3}\[(?!\^)(?P<label>[^\]]+)\]:[ \t]*(?:<(?P<dest_bracket>[^>\r\n]+)>|(?P<dest_bare>\S+))(?:[ \t]+(?:"
    r'"[^"\r\n]*"'
    r"|'[^'\r\n]*'"
    r"|\([^)\r\n]*\)))?[ \t]*$",
    re.MULTILINE,
)
LINK_PATTERN = re.compile(
    r"\[(?P<text>[^\]]*)\](?:"
    r"\((?P<inline_dest>[^)]+)\)"
    r"|\[\]"
    r"|\[(?P<ref_label>[^\]]+)\]"
    r")?"
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


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip()).casefold()


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def check_target(md: Path, target: str) -> None:
    global checked
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
    try:
        rel_path = md.relative_to(ROOT)
    except ValueError:
        rel_path = md
    if not resolved.exists():
        broken.append(f"{rel_path} -> {target}")


def check_file(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_code(text)

    defs: dict[str, str] = {}
    for match in REF_DEF.finditer(text):
        label = match.group("label")
        target = match.group("dest_bracket") or match.group("dest_bare")
        key = normalize_label(label)
        if key not in defs:
            defs[key] = target

    text_no_defs = REF_DEF.sub("", text)
    used_def_keys: set[str] = set()

    for match in LINK_PATTERN.finditer(text_no_defs):
        text_content = match.group("text")
        inline_dest = match.group("inline_dest")
        ref_label = match.group("ref_label")
        full_match = match.group(0)

        if inline_dest is not None:
            check_target(md, inline_dest.strip())
        elif full_match.endswith("[]"):
            # Collapsed reference link: [label][]
            key = normalize_label(text_content)
            if key in defs:
                used_def_keys.add(key)
                check_target(md, defs[key])
        elif ref_label is not None:
            # Full reference link: [text][ref_label]
            key = normalize_label(ref_label)
            if key in defs:
                used_def_keys.add(key)
                check_target(md, defs[key])
        else:
            # Shortcut reference link: [label]
            key = normalize_label(text_content)
            if key in defs:
                used_def_keys.add(key)
                check_target(md, defs[key])

    for key, target in defs.items():
        if key not in used_def_keys:
            check_target(md, target)


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
