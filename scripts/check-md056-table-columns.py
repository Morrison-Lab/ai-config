#!/usr/bin/env python3
"""Check markdown files for table column count mismatches (MD056).

Morrison-Lab/ai-config#3764.

## What this checks

In GitHub Flavored Markdown (GFM), tables are parsed line-by-line before inline
elements (such as code spans) are evaluated. A table consists of a header row,
a delimiter row (specifying alignment and column count), and zero or more body
rows.

Markdownlint rule MD056 (`table-column-count`) enforces that every row in a
table has the same number of columns as the header/delimiter row.

When an unescaped pipe character `|` is written inside backticks in a table row
(e.g. `gh issue|pr comment`), GFM splits the table cell on the pipe rather than
treating it as inline code alternation. This inflates the cell count (e.g. from
3 columns to 7 columns) and breaks the table in rendered output, causing MD056
violations in CI.

Because npm-based linters (`markdownlint-cli2`) can fail locally in remote or
restricted environments (e.g. npm 503 errors or execution policy restrictions),
this pure-Python checker provides a local, deterministic, zero-dependency gate
that catches MD056 violations and unescaped pipes before commit and push.

## Exit codes:
  0: Clean --- all tables examined have matching column counts and valid spans.
  1: Violations found --- one or more MD056 errors detected.
  2: Execution failure or invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent

# Import shared fence-stripping utility so lines inside fenced code blocks are ignored
try:
    from lib.fences import find_fence_spans
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib.fences import find_fence_spans

DELIM_CELL_RE = re.compile(r"^[ \t]*:?-+:?[ \t]*$")

DEFAULT_SCAN_GLOBS = [
    "skills/**/*.md",
    "codex-skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "plugins/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    ".claude/**/*.md",
    "*.md",
    "*.qmd",
]

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".quarto",
    "_site",
    "site",
    "dist",
    "build",
    ".gemini",
    ".cursor",
    "worktrees",
}


class TableViolation(NamedTuple):
    file_path: str
    line_number: int
    expected_cols: int
    actual_cols: int
    message: str
    line_text: str
    unescaped_pipes_in_code_spans: list[int]


def get_unescaped_pipe_indices(line: str) -> list[int]:
    """Return 0-based indices of all unescaped pipe characters in line.

    A pipe character is escaped if and only if it is preceded by an odd number
    of backslashes (e.g. \\| is escaped, but \\\\| is unescaped).
    """
    pipes: list[int] = []
    for i, ch in enumerate(line):
        if ch == "|":
            bs_count = 0
            k = i - 1
            while k >= 0 and line[k] == "\\":
                bs_count += 1
                k -= 1
            if bs_count % 2 == 0:
                pipes.append(i)
    return pipes


def find_unescaped_pipes_in_code_spans(line: str) -> list[int]:
    """Find 0-based indices of unescaped pipes that fall inside inline code spans.

    CommonMark code spans on a single line begin and end with matching runs
    of backticks. Any unescaped pipe inside such a span will be treated as a
    cell delimiter by GFM table parsing, breaking the table structure.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "`":
            start_backticks = i
            while i < n and line[i] == "`":
                i += 1
            k = i - start_backticks
            close_idx = -1
            j = i
            while j < n:
                if line[j] == "`":
                    run_start = j
                    while j < n and line[j] == "`":
                        j += 1
                    if (j - run_start) == k:
                        close_idx = run_start
                        break
                else:
                    j += 1
            if close_idx != -1:
                spans.append((i, close_idx))
                i = close_idx + k
            else:
                i = start_backticks + k
        else:
            i += 1

    bad_pipes: list[int] = []
    for start, end in spans:
        for idx in range(start, end):
            if line[idx] == "|":
                bs = 0
                k = idx - 1
                while k >= 0 and line[k] == "\\":
                    bs += 1
                    k -= 1
                if bs % 2 == 0:
                    bad_pipes.append(idx)
    return bad_pipes


def split_row_cells(line: str) -> tuple[list[str], bool, bool]:
    """Split a GFM table row into individual cell contents.

    Returns (cells, has_leading_pipe, has_trailing_pipe).
    Outer pipes (leading and trailing) are stripped if present, and internal
    unescaped pipes delimit cell boundaries.
    """
    stripped = line.strip()
    if not stripped:
        return [], False, False
    pipes = get_unescaped_pipe_indices(stripped)
    if not pipes:
        return [], False, False

    has_leading = (pipes[0] == 0)
    has_trailing = (pipes[-1] == len(stripped) - 1)

    slice_start = 1 if has_leading else 0
    slice_end = len(stripped) - 1 if has_trailing else len(stripped)
    inner = stripped[slice_start:slice_end]
    inner_pipes = get_unescaped_pipe_indices(inner)

    cells: list[str] = []
    last_p = 0
    for p in inner_pipes:
        cells.append(inner[last_p:p])
        last_p = p + 1
    cells.append(inner[last_p:])
    return cells, has_leading, has_trailing


def is_delimiter_row(line: str) -> tuple[bool, int]:
    """Check if a line is a GFM table delimiter row.

    A delimiter row must:
    - Have <= 3 leading spaces (indented code blocks start at 4 spaces).
    - Contain at least one cell matching :?-+:?
    - If outer pipes are omitted, contain at least two cells.
    Returns (is_delimiter, column_count).
    """
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3:
        return False, 0
    cells, has_leading, has_trailing = split_row_cells(line)
    if not cells:
        return False, 0
    if len(cells) < 2 and not (has_leading and has_trailing):
        return False, 0
    for c in cells:
        if not DELIM_CELL_RE.match(c) or "-" not in c:
            return False, 0
    return True, len(cells)


def check_content(text: str, file_path: str = "<input>") -> tuple[list[TableViolation], int]:
    """Check markdown content for table column count mismatches and unescaped pipes.

    Returns (violations, table_count).
    """
    lines = text.split("\n")
    fenced_lines, _, _ = find_fence_spans(text, swallow_unclosed=True)

    violations: list[TableViolation] = []
    table_count = 0
    i = 0
    n = len(lines)

    while i < n:
        if i in fenced_lines:
            i += 1
            continue

        # Check if line i+1 exists and is a delimiter row
        if i + 1 < n and (i + 1) not in fenced_lines:
            header_candidate = lines[i].strip()
            # A table header row cannot be blank or an ATX/Setext heading
            if not header_candidate or header_candidate.startswith("#"):
                i += 1
                continue

            is_delim, delim_cols = is_delimiter_row(lines[i + 1])
            if is_delim:
                table_count += 1
                header_line = lines[i]
                header_cells, _, _ = split_row_cells(header_line)
                header_cols = len(header_cells)
                bad_pipes_header = find_unescaped_pipes_in_code_spans(header_line)

                # Check header column count
                if header_cols != delim_cols or bad_pipes_header:
                    msg = (
                        f"Table column count [Expected: {delim_cols}; Actual: {header_cols}; "
                        f"{'Too many cells' if header_cols > delim_cols else 'Too few cells'}]"
                    )
                    if bad_pipes_header:
                        msg += " (unescaped '|' inside code span; backticks do not protect pipes in GFM tables; escape with '\\|')"
                    violations.append(
                        TableViolation(
                            file_path=file_path,
                            line_number=i + 1,
                            expected_cols=delim_cols,
                            actual_cols=header_cols,
                            message=msg,
                            line_text=header_line.strip(),
                            unescaped_pipes_in_code_spans=bad_pipes_header,
                        )
                    )

                # Scan table data rows
                row_idx = i + 2
                while row_idx < n:
                    if row_idx in fenced_lines:
                        break
                    row_line = lines[row_idx]
                    stripped = row_line.strip()
                    if not stripped:
                        break  # Blank line ends GFM table
                    if stripped.startswith("#"):
                        break  # Heading ends GFM table
                    if len(row_line) - len(row_line.lstrip(" ")) > 3:
                        break  # Indented code block ends table

                    pipes = get_unescaped_pipe_indices(stripped)
                    if not pipes:
                        break  # Non-pipe line ends table

                    row_cells, _, _ = split_row_cells(row_line)
                    row_cols = len(row_cells)
                    bad_pipes_row = find_unescaped_pipes_in_code_spans(row_line)

                    if row_cols != delim_cols or bad_pipes_row:
                        msg = (
                            f"Table column count [Expected: {delim_cols}; Actual: {row_cols}; "
                            f"{'Too many cells' if row_cols > delim_cols else 'Too few cells'}]"
                        )
                        if bad_pipes_row:
                            msg += " (unescaped '|' inside code span; backticks do not protect pipes in GFM tables; escape with '\\|')"
                        violations.append(
                            TableViolation(
                                file_path=file_path,
                                line_number=row_idx + 1,
                                expected_cols=delim_cols,
                                actual_cols=row_cols,
                                message=msg,
                                line_text=stripped,
                                unescaped_pipes_in_code_spans=bad_pipes_row,
                            )
                        )

                    row_idx += 1

                i = row_idx
                continue
        i += 1

    return violations, table_count


def check_file(path: Path) -> tuple[list[TableViolation], int, bool]:
    """Check a single markdown file for table column count violations.

    Returns (violations, table_count, had_error).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return [], 0, True
    violations, table_count = check_content(text, str(path))
    return violations, table_count, False


def resolve_files(
    root: Path,
    explicit_paths: Optional[list[str]] = None,
    diff_base: Optional[str] = None,
) -> list[Path]:
    """Resolve the list of markdown files to check."""
    if explicit_paths:
        result: list[Path] = []
        for p in explicit_paths:
            path = Path(p)
            if not path.is_absolute():
                path = root / path
            if path.is_file():
                result.append(path)
            elif path.is_dir():
                for ext in (".md", ".qmd"):
                    result.extend(path.rglob(f"*{ext}"))
        return sorted(set(result))

    if diff_base:
        try:
            cmd = ["git", "diff", "--name-only", f"{diff_base}...HEAD"]
            out = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True, check=True
            ).stdout
            diff_files = [
                root / line.strip()
                for line in out.splitlines()
                if line.strip().endswith((".md", ".qmd"))
            ]
            return sorted(f for f in diff_files if f.is_file())
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(
                f"warning: could not compute git diff against {diff_base} ({exc}); falling back to full scan",
                file=sys.stderr,
            )

    seen: set[Path] = set()
    for glob_pattern in DEFAULT_SCAN_GLOBS:
        for p in root.glob(glob_pattern):
            if p.is_file() and not any(part in IGNORED_DIRS for part in p.parts):
                seen.add(p)
    return sorted(seen)


def main(argv: Optional[list[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional specific file or directory paths to check",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root directory (default: parent of scripts/)",
    )
    parser.add_argument(
        "--diff",
        nargs="?",
        const="origin/main",
        default=None,
        metavar="BASE",
        help="Diff-scoped check: scan files changed relative to BASE (default: origin/main)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings as JSON",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    files = resolve_files(root, explicit_paths=args.paths, diff_base=args.diff)

    all_violations: list[TableViolation] = []
    total_tables = 0
    had_read_errors = False

    for f in files:
        violations, tables, had_error = check_file(f)
        if had_error:
            had_read_errors = True
        all_violations.extend(violations)
        total_tables += tables

    if had_read_errors:
        if args.json:
            print(json.dumps({"status": "error", "message": "one or more files could not be read"}))
        else:
            print("ERROR: execution failed due to unreadable files.", file=sys.stderr)
        return 2

    if args.json:
        payload = {
            "status": "clean" if not all_violations else "violations_found",
            "files_checked": len(files),
            "tables_checked": total_tables,
            "violations_count": len(all_violations),
            "violations": [
                {
                    "file": str(v.file_path),
                    "line": v.line_number,
                    "expected_cols": v.expected_cols,
                    "actual_cols": v.actual_cols,
                    "message": v.message,
                    "text": v.line_text,
                    "unescaped_pipes_in_code_spans": v.unescaped_pipes_in_code_spans,
                }
                for v in all_violations
            ],
        }
        print(json.dumps(payload, indent=2))
        return 1 if all_violations else 0

    rel_prefix = str(root) + os.sep
    for v in all_violations:
        disp_path = v.file_path
        if disp_path.startswith(rel_prefix):
            disp_path = disp_path[len(rel_prefix):]
        print(f"{disp_path}:{v.line_number}: error MD056/table-column-count {v.message}")
        if len(v.line_text) > 120:
            print(f"  {v.line_text[:117]}...")
        else:
            print(f"  {v.line_text}")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(
        f"Checked {total_tables} table(s) across {len(files)} markdown file(s)."
    )
    if all_violations:
        print(f"\nERROR: {len(all_violations)} MD056 table column count violation(s) found.")
        return 1

    print("OK: all table column counts match (MD056 clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
