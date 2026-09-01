"""Shared CommonMark-compliant fenced code block and code span stripping.

Consolidates positional fence-stripping across check-links.py,
check-pr-fully-clean.py, check-stale-records.py, and check-context-closure.py
(ai-config#1567).

A whole-document regex like ```` ```.*?``` ```` cannot handle nested fences:
it pairs backtick runs across the file, so a four-backtick fence wrapping an
inner three-backtick block throws every later region out of phase and swallows
real content (or wrongly treats prose as code).

CommonMark's rule is positional:
- An opener is up to 3 spaces of indent, then 3 or more backticks or tildes.
- A backtick opener's info string cannot contain backticks.
- A closer is up to 3 spaces of indent, the same character, length >= opener length,
  with no info string (optional trailing whitespace only).
- Code spans (`...`) cannot span blank lines.
"""
from __future__ import annotations

import re

FENCE_LINE = re.compile(
    r"^(?P<indent> {0,3})(?P<run>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
CODE_SPAN_RE = re.compile(
    r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
)
MULTI_BACKTICK_CODE_SPAN_RE = re.compile(
    r"(?<!`)(`{2,})(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
)
SINGLE_BACKTICK_CODE_SPAN_RE = re.compile(
    r"(?<!`)(`)(?!`)[^\n\r`]+?(?<!`)\1(?!`)"
)
DISPLAY_MATH_RE = re.compile(
    r"(?<!\\)\$\$.*?(?<!\\)\$\$", re.DOTALL
)
INLINE_MATH_RE = re.compile(
    r"(?<![\\$\w])\$(?!\s)(?:\\.|[^\\\$\n\r])+?(?<![\s\\\$])\$(?![0-9\w])"
)


def find_fence_spans(
    text: str,
    *,
    swallow_unclosed: bool = False,
) -> tuple[set[int], int, set[int]]:
    """Scan text line-by-line for CommonMark fenced code blocks.

    Returns:
        (fenced_line_indices, unclosed_fence_count, orphan_marker_indices)
    """
    lines = text.split("\n")
    fenced_lines: set[int] = set()
    orphan_markers: set[int] = set()
    in_fence = False
    fence_char = ""
    fence_len = 0
    start_idx = 0

    for idx, line in enumerate(lines):
        line_clean = line.rstrip("\r")
        m = FENCE_LINE.match(line_clean)
        if not in_fence:
            if m:
                run = m.group("run")
                info = m.group("info")
                # An opener's info string may not contain a backtick fence's own delimiter
                if run[0] == "`" and "`" in info:
                    continue
                in_fence = True
                fence_char = run[0]
                fence_len = len(run)
                start_idx = idx
        else:
            if m:
                run = m.group("run")
                info = m.group("info")
                if (
                    run[0] == fence_char
                    and len(run) >= fence_len
                    and not info.strip()
                ):
                    for i in range(start_idx, idx + 1):
                        fenced_lines.add(i)
                    in_fence = False

    unclosed_count = 0
    if in_fence:
        unclosed_count = 1
        if swallow_unclosed:
            for i in range(start_idx, len(lines)):
                fenced_lines.add(i)
        else:
            # When not swallowing unclosed fences to EOF, record the orphan opener marker line
            orphan_markers.add(start_idx)

    return fenced_lines, unclosed_count, orphan_markers


def strip_fences(
    text: str,
    *,
    swallow_unclosed: bool = False,
    replacement: str = "",
) -> str:
    """Strip fenced code blocks from markdown text, blanking block lines."""
    lines = text.split("\n")
    fenced_lines, _, orphan_markers = find_fence_spans(
        text, swallow_unclosed=swallow_unclosed
    )
    to_strip = fenced_lines | orphan_markers
    out: list[str] = []
    for idx, line in enumerate(lines):
        if idx in to_strip:
            out.append(replacement)
        else:
            out.append(line)
    return "\n".join(out)


def strip_code_spans(text: str, replacement: str = " ") -> str:
    """Strip inline code spans (`...`), bounded by blank lines.

    Multi-backtick spans (2+ backticks) may cross non-blank newlines to match
    CommonMark code spans enclosing multi-line content. Single-backtick spans
    are bounded to a single line so an unclosed stray backtick cannot match
    across lines to swallow distant headings.
    """
    s = MULTI_BACKTICK_CODE_SPAN_RE.sub(replacement, text)
    return SINGLE_BACKTICK_CODE_SPAN_RE.sub(replacement, s)


def strip_code(
    text: str,
    *,
    swallow_unclosed: bool = False,
    fence_replacement: str = "",
    span_replacement: str = " ",
) -> str:
    """Strip fenced code blocks and inline code spans."""
    stripped = strip_fences(
        text, swallow_unclosed=swallow_unclosed, replacement=fence_replacement
    )
    return strip_code_spans(stripped, replacement=span_replacement)


def strip_display_math(text: str, replacement: str = " ") -> str:
    """Strip display math blocks ($$...$$) from markdown text."""
    return DISPLAY_MATH_RE.sub(replacement, text)


def strip_inline_math(text: str, replacement: str = " ") -> str:
    """Strip inline math spans ($...$), bounded by blank lines and unescaped delimiters."""
    return INLINE_MATH_RE.sub(replacement, text)


def strip_math(text: str, replacement: str = " ") -> str:
    """Strip display math blocks and inline math spans."""
    return strip_inline_math(
        strip_display_math(text, replacement=replacement),
        replacement=replacement,
    )


def count_unbalanced_fences(text: str) -> int:
    """Count unclosed / unbalanced fence markers in text."""
    _, unclosed_count, _ = find_fence_spans(text, swallow_unclosed=False)
    return unclosed_count
