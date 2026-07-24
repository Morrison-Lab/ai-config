#!/usr/bin/env python3
"""Flag newly-added Markdown lines that pack more than one sentence/clause.

Advisory counterpart to `semantic-line-breaks.py` (which reformats a whole
file in place). This script is diff-scoped: it only looks at lines *added*
since a base ref, reusing that script's own sentence-splitter and block
detectors rather than re-deriving them.

Scoping to the diff (not the whole file, and not a fixed line-length like
MD013) matters because most of the corpus has drifted from the last
semantic-line-breaks reformat (#263/#265) --- as of 2026-07-24, running the
reformatter in check mode over every tracked .md file reports 231 of 240
files as needing changes. A whole-file or whole-corpus gate would flood CI
with pre-existing drift; this only reports content this diff itself added.
See ai-config#682.

Always exits 0 (advisory, matches shared/writing/semantic-line-breaks.md's
"worth raising, not worth blocking approval over") unless --strict is given.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same ignore globs as .markdownlint-cli2.jsonc, so this check and the
# markdownlint step agree on what counts as source prose.
_IGNORED_PREFIXES = ("codex-skills/", "docs/", "_site/", ".quarto/")

_spec = importlib.util.spec_from_file_location(
    "slb", Path(__file__).parent / "semantic-line-breaks.py"
)
slb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slb)  # type: ignore[union-attr]

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_line_numbers(base: str, pathspec: str = "*.md") -> dict[str, set[int]]:
    """Return {file: {new-file line numbers added or modified vs `base`}}."""
    diff = subprocess.run(
        ["git", "diff", "-U0", "--no-color", base, "--", pathspec],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout

    result: dict[str, set[int]] = {}
    current_file: str | None = None
    current_line = 0
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            path = line[4:]
            current_file = None if path == "/dev/null" else path.removeprefix("b/")
            if current_file is not None:
                result.setdefault(current_file, set())
            continue
        if line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if m:
                current_line = int(m.group(1))
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result[current_file].add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # a deletion doesn't consume a new-file line number
    return result


def prose_line_numbers(text: str) -> set[int]:
    """1-indexed lines eligible for a sentence-count check.

    Excludes frontmatter, fenced code, tables, headings, horizontal rules,
    blockquotes, HTML comments, and @-import directives --- the same block
    types `semantic-line-breaks.py` passes through untouched.
    """
    lines = text.split("\n")
    prose: set[int] = set()
    in_frontmatter = False
    frontmatter_done = False
    in_code = False
    fence_len = 0
    fence_char: str | None = None

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not frontmatter_done and not in_frontmatter and idx == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
                frontmatter_done = True
            continue

        fence_m = slb._FENCE_RE.match(stripped)
        if fence_m:
            fence_str = fence_m.group(1)
            fl, fc = len(fence_str), fence_str[0]
            if not in_code:
                in_code, fence_len, fence_char = True, fl, fc
            elif fc == fence_char and fl >= fence_len:
                in_code, fence_len, fence_char = False, 0, None
            continue
        if in_code:
            continue

        if (
            slb._BLANK_RE.match(line)
            or slb._HEADING_RE.match(line)
            or slb._TABLE_RE.match(line)
            or slb._HR_RE.match(stripped)
            or slb._AT_DIRECTIVE_RE.match(line)
            or slb._BQ_RE.match(line)
            or slb._HTML_COMMENT_RE.match(line)
        ):
            continue

        prose.add(idx)

    return prose


def line_content(line: str) -> str:
    """Strip a bullet marker (if any) so the sentence-splitter sees prose."""
    bullet_m = slb._BULLET_RE.match(line)
    return bullet_m.group(3) if bullet_m else line.strip()


def find_violations(base: str, pathspec: str = "*.md") -> list[tuple[str, int, str]]:
    """Return (file, line_no, preview) for added prose lines with 2+ sentences."""
    violations: list[tuple[str, int, str]] = []
    for rel_path, added in sorted(added_line_numbers(base, pathspec).items()):
        if any(rel_path.startswith(p) for p in _IGNORED_PREFIXES):
            continue
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue  # renamed/deleted after the diff was computed

        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        prose = prose_line_numbers(text)

        for line_no in sorted(added & prose):
            if line_no > len(lines):
                continue
            content = line_content(lines[line_no - 1])
            if len(slb.split_sentences(content)) > 1:
                preview = content if len(content) <= 80 else content[:77] + "..."
                violations.append((rel_path, line_no, preview))
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="git ref to diff against (default: HEAD~1; CI passes the PR base)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any violation is found (default: advisory, always exits 0)",
    )
    args = parser.parse_args()

    violations = find_violations(args.base)

    if not violations:
        print("No new lines missing semantic breaks.")
        return

    print(
        f"{len(violations)} newly-added line(s) pack more than one "
        f"sentence/clause (see shared/writing/semantic-line-breaks.md):\n"
    )
    for rel_path, line_no, preview in violations:
        print(f"  {rel_path}:{line_no}: {preview}")
    print(
        "\nConsider a semantic-break pass: "
        "python3 scripts/semantic-line-breaks.py <file>"
    )

    if args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
