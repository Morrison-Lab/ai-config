#!/usr/bin/env python3
"""Check that all relative markdown links point to existing files."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Add scripts/lib to import path for shared fences module
SCRIPTS_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(SCRIPTS_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_LIB_DIR))

from fences import strip_code_spans, strip_fences, strip_math  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Reference link definition (CommonMark 4.7): [label]: destination "optional title"
REF_DEF = re.compile(
    r"^[ \t]{0,3}\[(?!\^)([^\]]+)\]:[ \t]*\n?[ \t]*(?:<([^>\n]+)>|(\S+))"
    r'(?:[ \t]+(?:"([^"\n]*)"|\'([^\'\n]*)\'|\(([^)\n]*)\)))?[ \t]*$',
    re.MULTILINE,
)

# Inline, full reference, collapsed reference, or shortcut reference links
LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\](?:\(([^)]+)\)|\[([^\]]*)\])?")

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
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "ftp://")
URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]{1,31}:")
EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

broken: list[str] = []
checked = 0


def is_external(target: str) -> bool:
    if any(target.startswith(p) for p in SKIP_PREFIXES) or "://" in target:
        return True
    if URI_RE.match(target):
        return True
    if EMAIL_RE.match(target):
        return True
    return False


def normalize_label(label: str) -> str:
    """Normalize a Markdown reference link label per CommonMark."""
    return re.sub(r"\s+", " ", label.strip()).casefold()


def parse_link_target(raw: str) -> str:
    """Extract destination path/URL from a raw link target or reference definition."""
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


def resolve_target(base_dir: Path, target: str) -> Path | None:
    """Resolve a relative markdown target to an existing file."""
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


def check_target(target: str, md: Path, root: Path = ROOT) -> None:
    global checked
    parsed = parse_link_target(target)
    if not parsed or is_external(parsed):
        return
    if "<" in parsed or ">" in parsed:
        return  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", parsed, maxsplit=1)[0]
    if not path_part:  # pure in-page anchor
        return
    has_fragment = len(path_part) < len(parsed)
    is_bare = "/" not in path_part and "." not in path_part
    resolved = resolve_target(md.parent, parsed)
    if resolved is not None:
        checked += 1
    elif is_bare and not has_fragment:
        return  # bare-word placeholder in an example, e.g. (url)
    else:
        checked += 1
        try:
            rel = md.relative_to(root)
        except ValueError:
            rel = md
        broken.append(f"{rel} -> {parsed}")


def check_file(md: Path, root: Path = ROOT) -> None:
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = strip_code_spans(text)
    text = strip_math(text)

    defs, text_body = extract_reference_definitions(text)
    referenced_labels: set[str] = set()

    for match in LINK_PATTERN.finditer(text_body):
        first_bracket = match.group(1)
        inline_url = match.group(2)
        ref_label = match.group(3)

        if inline_url is not None:
            # Inline link: [text](url)
            check_target(inline_url, md, root=root)
        elif ref_label is not None:
            # Full reference link [text][label] or collapsed reference link [label][]
            label = ref_label if ref_label != "" else first_bracket
            norm = normalize_label(label)
            if norm in defs:
                referenced_labels.add(norm)
                check_target(defs[norm], md, root=root)
        else:
            # Shortcut reference link: [label]
            norm = normalize_label(first_bracket)
            if norm in defs:
                referenced_labels.add(norm)
                check_target(defs[norm], md, root=root)

    # Also validate any unused link reference definitions pointing to relative paths
    for norm, dest in defs.items():
        if norm not in referenced_labels:
            check_target(dest, md, root=root)


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
