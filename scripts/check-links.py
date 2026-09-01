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
AUTOLINK = re.compile(r"<([^<>\s]+)>")
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
HTML_TAGS = {
    "a",
    "abbr",
    "address",
    "article",
    "aside",
    "b",
    "bdi",
    "bdo",
    "blockquote",
    "body",
    "br",
    "button",
    "canvas",
    "caption",
    "cite",
    "code",
    "col",
    "colgroup",
    "data",
    "datalist",
    "dd",
    "del",
    "details",
    "dfn",
    "dialog",
    "div",
    "dl",
    "dt",
    "em",
    "embed",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hr",
    "html",
    "i",
    "iframe",
    "img",
    "input",
    "ins",
    "kbd",
    "label",
    "legend",
    "li",
    "link",
    "main",
    "map",
    "mark",
    "meta",
    "meter",
    "nav",
    "noscript",
    "object",
    "ol",
    "optgroup",
    "option",
    "output",
    "p",
    "param",
    "picture",
    "pre",
    "progress",
    "q",
    "rp",
    "rt",
    "ruby",
    "s",
    "samp",
    "script",
    "section",
    "select",
    "small",
    "source",
    "span",
    "strong",
    "style",
    "sub",
    "summary",
    "sup",
    "svg",
    "table",
    "tbody",
    "td",
    "template",
    "textarea",
    "tfoot",
    "th",
    "thead",
    "time",
    "title",
    "tr",
    "track",
    "u",
    "ul",
    "var",
    "video",
    "wbr",
}

broken: list[str] = []
checked = 0


def is_external(target: str) -> bool:
    return (
        target.startswith(SKIP_PREFIXES)
        or "://" in target
        or ("@" in target and "/" not in target)
    )


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def check_target(
    target: str,
    md: Path,
    root: Path = ROOT,
    *,
    is_autolink: bool = False,
) -> None:
    global checked
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # drop a trailing `"title"` if present
    target = target.split(" ", 1)[0].strip()
    if not target or is_external(target):
        return
    if is_autolink:
        if target.startswith("/") and "." not in target:
            return  # HTML closing tag, e.g. </details>
        if target.startswith(("!", "?")):
            return  # HTML comments / directives
    if "<" in target or ">" in target:
        return  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:  # pure in-page anchor
        return
    if "/" not in path_part and "." not in path_part:
        return  # bare-word placeholder in an example, e.g. (url)
    if is_autolink and path_part.lower() in HTML_TAGS:
        return
    checked += 1
    resolved = (md.parent / path_part).resolve()
    if not resolved.exists():
        broken.append(f"{_rel_path(md, root)} -> {target}")


def check_file(md: Path, root: Path = ROOT) -> None:
    global checked
    text = md.read_text(encoding="utf-8")
    text = strip_fences(text)
    text = strip_code_spans(text)

    # Footnote definitions and references (ai-config#2538, ai-config#2526)
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

    # Autolinks <target> (including those inside footnote definitions)
    for match in AUTOLINK.finditer(text):
        check_target(match.group(1).strip(), md, root=root, is_autolink=True)


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
