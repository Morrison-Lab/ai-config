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
# Reference link definition (CommonMark 4.7): [label]: destination "optional title"
REF_DEF = re.compile(
    r"^[ ]{0,3}\[([^\]]+)\]:[ \t]*\n?[ \t]*(?:<([^>\n]+)>|(\S+))"
    r'(?:[ \t]+(?:"([^"\n]*)"|\'([^\'\n]*)\'|\(([^)\n]*)\)))?[ \t]*$',
    re.MULTILINE,
)

# Inline, full reference, collapsed reference, or shortcut reference links
LINK_PATTERN = re.compile(r"\[([^\]]*)\](?:\(([^)]+)\)|\[([^\]]*)\])?")

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
    return target.startswith(SKIP_PREFIXES) or "://" in target


def normalize_label(label: str) -> str:
    """Normalize a Markdown reference link label per CommonMark."""
    return " ".join(label.strip().split()).casefold()


def extract_reference_definitions(text: str) -> tuple[dict[str, str], str]:
    """Extract link reference definitions and return definitions dict and remaining text."""
    defs: dict[str, str] = {}
    for match in REF_DEF.finditer(text):
        raw_label = match.group(1)
        dest = match.group(2) if match.group(2) is not None else match.group(3)
        label = normalize_label(raw_label)
        # In CommonMark, the first definition takes precedence
        if label and label not in defs:
            defs[label] = dest
    # Remove definition lines so they aren't parsed as shortcut links in prose
    text_without_defs = REF_DEF.sub("", text)
    return defs, text_without_defs


def clean_target(target: str) -> str | None:
    """Clean and filter link target, returning None if skipped."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # drop a trailing `"title"`, `'title'`, or `(title)` if present
    target = target.split(" ", 1)[0]
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:  # pure in-page anchor
        return None
    if "/" not in path_part and "." not in path_part:
        return None  # bare-word placeholder in an example, e.g. (url)
    return target


def check_target(target: str, md: Path) -> None:
    global checked
    cleaned = clean_target(target)
    if not cleaned:
        return
    path_part = re.split(r"[#?]", cleaned, maxsplit=1)[0]
    checked += 1
    resolved = (md.parent / path_part).resolve()
    if not resolved.exists():
        try:
            rel_path = md.relative_to(ROOT)
        except ValueError:
            rel_path = md
        broken.append(f"{rel_path} -> {cleaned}")


def check_file(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = INLINE.sub("", text)
    defs, text_body = extract_reference_definitions(text)

    referenced_labels: set[str] = set()

    for match in LINK_PATTERN.finditer(text_body):
        first_bracket = match.group(1)
        inline_url = match.group(2)
        ref_label = match.group(3)

        if inline_url is not None:
            # Inline link: [text](url)
            check_target(inline_url, md)
        elif ref_label is not None:
            # Full reference link [text][label] or collapsed reference link [label][]
            label = ref_label if ref_label != "" else first_bracket
            norm = normalize_label(label)
            if norm in defs:
                referenced_labels.add(norm)
                check_target(defs[norm], md)
        else:
            # Shortcut reference link: [label]
            norm = normalize_label(first_bracket)
            if norm in defs:
                referenced_labels.add(norm)
                check_target(defs[norm], md)
            # If not in defs, ignore (non-link bracketed text)

    # Also validate any unused link reference definitions pointing to relative paths
    for norm, dest in defs.items():
        if norm not in referenced_labels:
            check_target(dest, md)


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
