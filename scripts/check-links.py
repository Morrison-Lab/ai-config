#!/usr/bin/env python3
"""Check that all relative markdown links point to existing files.

A fragment (`#slug`) on its own, or on a link to a Markdown file or to a
directory's README, must also name a heading or an HTML `id`/`name` there:
renaming a heading otherwise breaks every link to it silently (ai-config#3630).
A fragment on a link to a directory with no README at all fails too.
Files are parsed as CommonMark with markdown-it-py. A heading matches when its
text and the fragment have the same letters, marks and digits. GitHub's slug
keeps all of these except letters and marks added in Unicode 14 or later,
which github-slugger 2.0.0 drops, so the check fails no link GitHub resolves
unless its heading holds such a letter. The cost: a rename that changes only
punctuation or spacing, or a trailing -N on a fragment, is not caught.
markdown-it-py takes quadratic time on a long run of emphasis delimiters
(140 KB of "_a __b " takes several seconds), which ordinary prose does not
contain. The writer and reviewer instructions for the same defect are in
shared/writing/reorganize-prose.md and .claude/agents/adversarial-reviewer.md.
"""
from __future__ import annotations

import functools
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

# Add scripts/lib to import path for shared fences module
SCRIPTS_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(SCRIPTS_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_LIB_DIR))

from fences import strip_code_spans, strip_fences, strip_math  # noqa: E402

try:
    from markdown_it import MarkdownIt
except ImportError:
    sys.exit("error: check-links.py needs markdown-it-py: pip install markdown-it-py==3.0.0")

ROOT = Path(__file__).resolve().parent.parent

# Reference link definition (CommonMark 4.7): [label]: destination "optional title"
REF_DEF = re.compile(
    r"^[ \t]{0,3}\[(?!\^)(?P<label>[^\]]+)\]:[ \t]*(?P<target>\S.*)$",
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

MARKDOWN = MarkdownIt("commonmark")
FRONT_MATTER = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*\r?\n", re.DOTALL)
TAG = re.compile(r"<[A-Za-z][^<>]*>")
ID_ATTR = re.compile(r"""(?<![\w-])(?:id|name)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""")
LINE_ANCHOR = re.compile(r"L\d+(?:C\d+)?(?:-L\d+(?:C\d+)?)?")
NUMBERED = re.compile(r"-\d+$")  # github-slugger's suffix on a repeated heading
NUMBERS = {"Nd", "Nl"}  # digits and letter-numbers (U+216B, Roman XII), which GitHub's slug keeps

broken: list[str] = []
checked = 0


def loose(text: str) -> str:
    """The letters, marks, digits and letter-numbers of `text`, lowercased.

    A GitHub slug keeps these from a heading's text (letters and marks added
    in Unicode 14 or later aside), plus hyphens and underscores, so a fragment
    and the heading it names share this key.
    """
    return "".join(ch for ch in text.lower()
                   if unicodedata.category(ch)[0] in "LM" or unicodedata.category(ch) in NUMBERS)


def without_comments(html: str) -> str:
    """`html` with its <!-- ... --> comments removed, in one pass."""
    out, start = [], 0
    while (open_at := html.find("<!--", start)) != -1:
        out.append(html[start:open_at])
        close_at = html.find("-->", open_at + 4)
        if close_at == -1:
            return "".join(out)
        start = close_at + 3
    return "".join(out) + html[start:]


def html_ids(html: str) -> set[str]:
    return {next(v for v in m.groups() if v is not None)
            for tag in TAG.findall(without_comments(html)) for m in ID_ATTR.finditer(tag)}


@functools.cache
def anchors_in(md: Path) -> tuple[frozenset[str], frozenset[str]]:
    """HTML id/name anchors in `md`, and the loose keys of its headings' text.

    Parsed as CommonMark, so code, comments, setext, quoted and listed
    headings are read as GitHub reads them.
    """
    # utf-8-sig drops a leading BOM, as GitHub's cmark-gfm does.
    tokens = MARKDOWN.parse(FRONT_MATTER.sub("", md.read_text(encoding="utf-8-sig")))
    ids: set[str] = set()
    keys: set[str] = set()
    for i, token in enumerate(tokens):
        if token.type == "html_block":
            ids |= html_ids(token.content)
        for child in token.children or []:
            if child.type == "html_inline":
                ids |= html_ids(child.content)
        if token.type == "heading_open":
            parts = tokens[i + 1].children or []
            keys.add(loose("".join(c.content for c in parts if c.type in ("text", "code_inline"))))
    return frozenset(ids), frozenset(keys)


def check_fragment(fragment: str, page: Path, target: str, md: Path, root: Path) -> None:
    """Fail a fragment that names no anchor or heading in `page`.

    Headings match on loose keys (see the module docstring for the one kind
    of heading that can fail wrongly), at the cost of missing a rename that
    changes only punctuation, spacing or a trailing -N.
    """
    global checked
    checked += 1
    fragment = urllib.parse.unquote(fragment).removeprefix("user-content-")
    ids, keys = anchors_in(page)
    if fragment in ids or loose(fragment) in keys or loose(NUMBERED.sub("", fragment)) in keys:
        return
    if "plain=1" in target and LINE_ANCHOR.fullmatch(fragment):
        return  # a source-view line anchor, e.g. file.md?plain=1#L3
    try:
        rel = md.relative_to(root)
    except ValueError:
        rel = md
    broken.append(f"{rel} -> {target} (no such heading)")


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
        label = normalize_label(match.group("label"))
        raw_target = match.group("target")
        parsed = parse_link_target(raw_target)
        if label and label not in defs and parsed:
            defs[label] = parsed
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
    if "<" in target or ">" in target:
        return  # angle-bracket placeholder, e.g. <owner>/<repo> or #<slug>
    if len(target) > 1 and target.startswith("#"):
        check_fragment(target[1:], md, target, md, root)
        return
    if not target or is_external(target):  # is_external counts "#..." as external
        return
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:  # a query or bare "#" with no path
        return
    has_fragment = len(path_part) < len(target)
    is_bare = "/" not in path_part and "." not in path_part
    resolved = resolve_target(md.parent, target)
    fragment = target.split("#", 1)[1] if "#" in target else ""
    if resolved is not None and resolved.is_dir() and fragment:  # GitHub shows the README
        readme = resolved / "README.md"
        if readme.is_file():
            resolved = readme
        elif not any(p.name.lower().startswith("readme") for p in resolved.iterdir()):
            # Only a file listing, so no heading for the fragment to name;
            # another README format (readme.rst) is left unchecked.
            checked += 1
            rel = md.relative_to(root) if md.is_relative_to(root) else md
            broken.append(f"{rel} -> {target} (no README for the heading)")
            return
    if resolved is not None and fragment and resolved.suffix == ".md":
        check_fragment(fragment, resolved, target, md, root)
    elif resolved is not None:
        checked += 1
    elif is_bare and not has_fragment:
        return  # bare-word placeholder in an example, e.g. (url)
    else:
        checked += 1
        try:
            rel = md.relative_to(root)
        except ValueError:
            rel = md
        broken.append(f"{rel} -> {target}")


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
            parsed = parse_link_target(inline_url)
            if parsed:
                check_target(parsed, md, root=root)
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
