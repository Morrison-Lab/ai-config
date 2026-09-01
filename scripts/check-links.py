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
from fences import strip_code_spans, strip_fences, strip_math  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Matches [text](target) but not image links ![alt](target)
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
REF_DEF = re.compile(
    r"^[ \t]{0,3}\[(?!\^)(?P<label>[^\]]+)\]:[ \t]*(?P<target>\S.*)$",
    re.MULTILINE,
)

# External schemes and pure in-page anchors
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "ftp://")

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

broken: list[str] = []
checked = 0


def is_external(target: str) -> bool:
    return any(target.startswith(p) for p in EXTERNAL_PREFIXES) or "://" in target


def parse_link_target(raw: str) -> str:
    """Extract destination path/URL from a raw link target or reference definition.

    Handles angle-bracket enclosed destinations (`<path/to/file>`) and drops
    trailing optional title attributes enclosed in quotes or parentheses
    (e.g. `"title"`, `'title'`, `(title)`).
    """
    target = raw.strip()
    if not target:
        return ""
    if target.startswith("<"):
        end = target.find(">")
        if end != -1:
            destination = target[1:end].strip()
            rest = target[end + 1:].strip()
            if rest and not (
                (rest.startswith('"') and rest.endswith('"'))
                or (rest.startswith("'") and rest.endswith("'"))
                or (rest.startswith("(") and rest.endswith(")"))
            ):
                return target
            return destination
    parts = target.split(None, 1)
    return parts[0] if parts else ""


def resolve_target(base_dir: Path, target: str) -> Path | None:
    """Resolve a relative markdown target to an existing file.

    Supports:
    - Direct file paths (with optional anchor/query fragments)
    - Extensionless markdown paths (path/to/doc -> path/to/doc.md)
    - Directory paths resolving to index.md or README.md
    """
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:
        return None

    candidates = [
        (base_dir / path_part).resolve(),
        (base_dir / f"{path_part}.md").resolve(),
        (base_dir / path_part / "index.md").resolve(),
        (base_dir / path_part / "README.md").resolve(),
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def check_file(md: Path) -> None:
    global checked
    text = md.read_text(encoding="utf-8")
    # Strip code regions and math blocks first so code examples and LaTeX math
    # aren't mistaken for real links, while preserving prose and link targets.
    text = strip_fences(text)
    text = strip_code_spans(text)
    text = strip_math(text)

    raw_targets: list[str] = []
    for match in LINK.finditer(text):
        raw_targets.append(match.group(2))
    for match in REF_DEF.finditer(text):
        raw_targets.append(match.group("target"))

    for raw in raw_targets:
        target = parse_link_target(raw)
        if not target or is_external(target):
            continue
        if "<" in target or ">" in target:
            continue  # angle-bracket placeholder, e.g. <owner>/<repo>
        path_part = re.split(r"[#?]", target, maxsplit=1)[0]
        if not path_part:  # pure in-page anchor
            continue
        has_fragment = len(path_part) < len(target)
        is_bare = "/" not in path_part and "." not in path_part
        resolved = resolve_target(md.parent, target)
        if resolved is not None:
            checked += 1
        elif is_bare and not has_fragment:
            continue  # bare-word placeholder in an example, e.g. (url)
        else:
            checked += 1
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
