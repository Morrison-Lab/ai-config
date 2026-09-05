#!/usr/bin/env python3
"""Check tracked source files for banned non-ASCII punctuation glyphs.

Per `shared/coding/ascii-punctuation-in-source.md`, tracked source files must not
contain em-dashes (U+2014), en-dashes (U+2013), curly quotes (U+201C, U+201D,
U+2018, U+2019), or the multiplication sign (U+00D7).

This checker operates in two modes:
1. Whole-tree / file mode (default): Scans whole files matching specified
   extensions (.py, .R by default).
2. Diff / working-tree mode (--diff): Scans added lines against a base ref
   (including unstaged working tree edits, staged index changes, branch commits,
   and untracked files).

Exit codes:
  0: Clean --- files examined (> 0 search space) and no banned glyphs found.
  1: Violations found --- one or more banned glyphs detected.
  2: Error / empty search space --- search space is 0 in diff mode, invalid
     arguments, unreadable paths, or execution failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

# The 7 banned punctuation glyphs defined in ascii-punctuation-in-source.md.
# Built dynamically via chr() so this script's own source remains pure ASCII.
BANNED_GLYPHS: Dict[str, str] = {
    chr(0x2014): "EM DASH (U+2014)",
    chr(0x2013): "EN DASH (U+2013)",
    chr(0x201C): "LEFT DOUBLE QUOTATION MARK (U+201C)",
    chr(0x201D): "RIGHT DOUBLE QUOTATION MARK (U+201D)",
    chr(0x2018): "LEFT SINGLE QUOTATION MARK (U+2018)",
    chr(0x2019): "RIGHT SINGLE QUOTATION MARK (U+2019)",
    chr(0x00D7): "MULTIPLICATION SIGN (U+00D7)",
}

BANNED_REGEX = re.compile("[" + "".join(re.escape(c) for c in BANNED_GLYPHS) + "]")

DEFAULT_EXTENSIONS = {".py", ".R"}
DIFF_DEFAULT_EXTENSIONS = {".py", ".R", ".qmd", ".md", ".sh", ".yml", ".yaml"}

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
}


class Violation(NamedTuple):
    file_path: str
    line_number: int
    column_number: int
    char: str
    char_name: str
    line_content: str


class ScanResult(NamedTuple):
    files_count: int
    lines_count: int
    violations: List[Violation]
    status: str  # "clean", "violations", "empty", "error"
    message: str = ""


def find_banned_in_line(line: str, file_path: str, line_no: int) -> List[Violation]:
    """Return all banned glyph violations found on a single line."""
    violations: List[Violation] = []
    for match in BANNED_REGEX.finditer(line):
        c = match.group(0)
        col = match.start() + 1
        violations.append(
            Violation(
                file_path=file_path,
                line_number=line_no,
                column_number=col,
                char=c,
                char_name=BANNED_GLYPHS.get(c, f"U+{ord(c):04X}"),
                line_content=line.rstrip("\r\n"),
            )
        )
    return violations


def scan_file(path: Path) -> Tuple[int, List[Violation]]:
    """Scan an entire file line-by-line. Return (line_count, violations)."""
    violations: List[Violation] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise OSError(f"Could not read {path}: {exc}") from exc

    lines = content.splitlines()
    for line_no, line in enumerate(lines, start=1):
        violations.extend(find_banned_in_line(line, str(path), line_no))
    return len(lines), violations


def collect_tree_files(
    targets: List[Path],
    extensions: Set[str],
) -> List[Path]:
    """Collect all files matching extensions under the target paths."""
    found: List[Path] = []
    for target in targets:
        if target.is_file():
            if not extensions or target.suffix in extensions:
                found.append(target)
        elif target.is_dir():
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for f in files:
                    p = Path(root) / f
                    if not extensions or p.suffix in extensions:
                        found.append(p)
    return sorted(found)


def scan_tree(
    targets: List[Path],
    extensions: Set[str],
) -> ScanResult:
    """Scan whole files in the tree or specified paths."""
    files = collect_tree_files(targets, extensions)
    total_lines = 0
    violations: List[Violation] = []

    for path in files:
        lines_count, file_violations = scan_file(path)
        total_lines += lines_count
        violations.extend(file_violations)

    if not files:
        return ScanResult(
            files_count=0,
            lines_count=0,
            violations=[],
            status="empty",
            message="No files found matching criteria.",
        )

    if violations:
        return ScanResult(
            files_count=len(files),
            lines_count=total_lines,
            violations=violations,
            status="violations",
        )

    return ScanResult(
        files_count=len(files),
        lines_count=total_lines,
        violations=[],
        status="clean",
    )


def resolve_base_ref(repo_root: Path, requested_base: Optional[str]) -> str:
    """Resolve a valid base git ref for diff comparisons."""
    candidates = [requested_base] if requested_base else ["origin/main", "main", "origin/master", "master", "HEAD~1"]
    for ref in candidates:
        if not ref:
            continue
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return ref
    raise ValueError(f"Could not resolve any valid base git ref from candidates: {candidates}")


def parse_diff_added_lines(diff_text: str) -> Dict[str, List[Tuple[int, str]]]:
    """Parse unified diff text into a mapping of filename -> [(line_no, line_text)]."""
    added_lines: Dict[str, List[Tuple[int, str]]] = {}
    current_file: Optional[str] = None
    current_line_no = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            current_file = None
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in added_lines:
                added_lines[current_file] = []
        elif line.startswith("@@ ") and current_file:
            # Format: @@ -old_start,old_count +new_start,new_count @@
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_line_no = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            added_lines[current_file].append((current_line_no, line[1:]))
            current_line_no += 1
        elif line.startswith("\\"):
            # Git marker lines, e.g. "\ No newline at end of file".
            # Do NOT increment current_line_no for these marker lines.
            continue
        elif not line.startswith("-") and current_file:
            current_line_no += 1

    return added_lines


def get_untracked_files(repo_root: Path, extensions: Set[str]) -> List[Path]:
    """Get list of untracked files from git status."""
    proc = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []

    untracked: List[Path] = []
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        p = repo_root / rel
        if p.is_file() and (not extensions or p.suffix in extensions):
            # Check if directory should be ignored
            if not any(part in IGNORED_DIRS for part in p.parts):
                untracked.append(p)
    return untracked


def resolve_merge_base(repo_root: Path, base_ref: str) -> str:
    """Resolve merge-base between base_ref and HEAD to avoid moving-base false positives."""
    proc = subprocess.run(
        ["git", "merge-base", base_ref, "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        mb = proc.stdout.strip()
        if mb:
            return mb
    return base_ref


def scan_diff(
    repo_root: Path,
    base_ref: str,
    extensions: Set[str],
) -> ScanResult:
    """Scan added lines between merge-base(base_ref, HEAD) and current working tree."""
    diff_base = resolve_merge_base(repo_root, base_ref)
    diff_proc = subprocess.run(
        ["git", "diff", "--unified=0", diff_base],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if diff_proc.returncode != 0:
        return ScanResult(
            files_count=0,
            lines_count=0,
            violations=[],
            status="error",
            message=f"git diff failed: {diff_proc.stderr.strip()}",
        )

    file_added_lines = parse_diff_added_lines(diff_proc.stdout)
    untracked_files = get_untracked_files(repo_root, extensions)

    # Filter diff files by extension and ignored directories
    scanned_files_set: Set[str] = set()
    total_added_lines = 0
    violations: List[Violation] = []

    for rel_path, lines in file_added_lines.items():
        p = Path(rel_path)
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if extensions and p.suffix not in extensions:
            continue

        scanned_files_set.add(rel_path)
        total_added_lines += len(lines)
        for line_no, content in lines:
            violations.extend(find_banned_in_line(content, rel_path, line_no))

    # Add all lines from untracked files
    for p in untracked_files:
        rel_path = str(p.relative_to(repo_root))
        scanned_files_set.add(rel_path)
        lines_count, file_violations = scan_file(p)
        total_added_lines += lines_count
        violations.extend(file_violations)

    if not scanned_files_set or total_added_lines == 0:
        return ScanResult(
            files_count=0,
            lines_count=0,
            violations=[],
            status="empty",
            message=f"0 files and 0 added lines examined (empty diff against base '{base_ref}'). Nothing was checked.",
        )

    if violations:
        return ScanResult(
            files_count=len(scanned_files_set),
            lines_count=total_added_lines,
            violations=violations,
            status="violations",
        )

    return ScanResult(
        files_count=len(scanned_files_set),
        lines_count=total_added_lines,
        violations=[],
        status="clean",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific files or directories to scan (default: repository root)",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Scan added lines relative to a base ref (working-tree aware: includes staged, unstaged, and untracked changes)",
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help="Base git ref for diff mode (default: origin/main or main)",
    )
    parser.add_argument(
        "--extensions",
        "-e",
        type=str,
        default=None,
        help="Comma-separated file extensions to scan (default: .py,.R in tree mode; .py,.R,.qmd,.md,.sh,.yml,.yaml in diff mode)",
    )
    parser.add_argument(
        "--fail-if-empty",
        action="store_true",
        help="Exit with code 2 if 0 files or 0 lines were examined",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit output as JSON",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode (only report errors)",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()

    # Determine extensions
    if args.extensions is not None:
        extensions = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in args.extensions.split(",")
            if ext.strip()
        }
    elif args.diff:
        extensions = DIFF_DEFAULT_EXTENSIONS
    else:
        extensions = DEFAULT_EXTENSIONS

    if args.diff:
        try:
            base_ref = resolve_base_ref(repo_root, args.base)
        except ValueError as exc:
            if args.as_json:
                print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
            else:
                print(f"error: {exc}", file=sys.stderr)
            return 2

        result = scan_diff(repo_root, base_ref, extensions)
    else:
        target_paths = args.paths if args.paths else [repo_root]
        result = scan_tree(target_paths, extensions)

    # Handle output
    if args.as_json:
        payload = {
            "status": result.status,
            "files_examined": result.files_count,
            "lines_examined": result.lines_count,
            "violations_count": len(result.violations),
            "violations": [
                {
                    "file": v.file_path,
                    "line": v.line_number,
                    "column": v.column_number,
                    "char": v.char,
                    "char_name": v.char_name,
                    "line_content": v.line_content,
                }
                for v in result.violations
            ],
        }
        if result.message:
            payload["message"] = result.message
        print(json.dumps(payload, indent=2))
    else:
        if result.status == "error":
            print(f"error: {result.message}", file=sys.stderr)
        elif result.status == "empty":
            prefix = "error: " if (args.diff or args.fail_if_empty) else "notice: "
            print(f"{prefix}{result.message or 'No files or lines were examined.'}", file=sys.stderr if (args.diff or args.fail_if_empty) else sys.stdout)
        elif result.status == "violations":
            print(
                f"error: Found {len(result.violations)} non-ASCII punctuation glyph(s) across {result.files_count} file(s) ({result.lines_count} lines examined):",
                file=sys.stderr,
            )
            for v in result.violations:
                print(
                    f"  {v.file_path}:{v.line_number}:{v.column_number}: {v.char_name}",
                    file=sys.stderr,
                )
                print(f"      > {v.line_content}", file=sys.stderr)
        elif result.status == "clean":
            if not args.quiet:
                scope_label = "added line(s)" if args.diff else "line(s)"
                print(
                    f"✓ Checked {result.files_count} file(s), {result.lines_count} {scope_label}: no non-ASCII punctuation found."
                )

    if result.status == "violations":
        return 1
    if result.status in ("error", "empty") and (args.diff or args.fail_if_empty):
        return 2
    if result.status == "empty":
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
