#!/usr/bin/env python3
"""Check Python source files for explicit text I/O encoding (ai-config#4121).

`pathlib.Path.read_text()`, `Path.write_text()`, and built-in `open()` without an
explicit `encoding` parameter default to `locale.getpreferredencoding(False)` in
Python <3.15. On Windows without `PYTHONUTF8=1`, this defaults to `cp1252`
(Windows-1252), causing `UnicodeDecodeError` or `UnicodeEncodeError` when reading
or writing files containing UTF-8 characters (e.g. smart quotes, em dashes,
international characters).

This checker enforces that all text-mode file I/O operations specify an explicit
encoding (e.g. `encoding="utf-8"`).

Operations checked:
- Built-in `open(...)` and `io.open(...)` (unless binary mode, e.g. `'rb'`, `'wb'`)
- `Path.open(...)` / `*.open(...)` (unless binary mode)
- `Path.read_text(...)` / `*.read_text(...)`
- `Path.write_text(...)` / `*.write_text(...)`
- `tempfile.NamedTemporaryFile(...)` / `TemporaryFile(...)` (when text mode, e.g. `mode='w'`)

Exemptions:
- Calls on a line carrying `# noqa: text-encoding` or `# pragma: no-encoding`.

Modes:
1. Whole-tree / file mode (default): Scans whole files matching `.py`.
2. Diff mode (`--diff`): Scans added lines in `.py` files against a base ref.

Exit codes:
  0: Clean --- files examined (> 0 search space) and no encoding violations.
  1: Violations found --- one or more text I/O calls omit explicit encoding.
  2: Error / empty search space --- search space is 0 in diff mode, invalid
     arguments, unreadable paths, or execution failure.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

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
    "vendor",
}


class Violation(NamedTuple):
    file_path: str
    line_number: int
    column_number: int
    call_kind: str
    message: str
    line_content: str
    end_line_number: int = 0


class ScanResult(NamedTuple):
    files_count: int
    lines_count: int
    calls_count: int
    violations: List[Violation]
    status: str  # "clean", "violations", "empty", "error"
    message: str = ""


def is_binary_mode(mode_val: Optional[str]) -> bool:
    """Return True if mode string represents binary mode."""
    if mode_val is None:
        return False
    return "b" in mode_val


def has_exemption(line: str) -> bool:
    """Check if the source line has an inline exemption comment."""
    return "# noqa: text-encoding" in line or "# pragma: no-encoding" in line


VALID_MODE_CHARS = set("rwax+btU")

NON_PATH_RECEIVERS = {
    "os", "tarfile", "zipfile", "gzip", "bz2", "lzma", "shutil",
    "zf", "tf", "archive", "zip_file", "tar_file",
    "client", "session", "app", "window", "driver", "browser", "page",
}


def is_valid_mode_string(s: str) -> bool:
    """Return True if s is a plausible Python file mode string."""
    if not s or len(s) > 5:
        return False
    if not all(c in VALID_MODE_CHARS for c in s):
        return False
    return any(c in "rwax" for c in s)


def is_none_literal(node: ast.AST) -> bool:
    """Return True if AST node represents a literal None."""
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if sys.version_info < (3, 8):
        name_const = getattr(ast, "NameConstant", None)
        if name_const and isinstance(node, name_const) and node.value is None:
            return True
    return False


def get_call_encoding_arg(node: ast.Call, pos_idx: Optional[int] = None) -> Optional[ast.AST]:
    """Return the AST expression passed for encoding (keyword or positional), if any."""
    for kw in node.keywords:
        if kw.arg == "encoding":
            return kw.value
    if pos_idx is not None and len(node.args) > pos_idx:
        return node.args[pos_idx]
    return None


def is_explicit_encoding_provided(node: ast.Call, pos_idx: Optional[int] = None) -> Tuple[bool, bool]:
    """Check if encoding is provided and whether it is None.

    Returns (has_encoding, is_explicit_none).
    has_encoding is True only if a non-None encoding is provided.
    is_explicit_none is True if encoding argument was explicitly provided as literal None.
    """
    enc_arg = get_call_encoding_arg(node, pos_idx)
    if enc_arg is None:
        return False, False
    if is_none_literal(enc_arg):
        return False, True
    return True, False


class TextIOVisitor(ast.NodeVisitor):
    """AST visitor that checks for text-mode I/O calls lacking explicit encoding."""

    def __init__(self, file_path: str, lines: List[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        self.calls_count = 0
        self.violations: List[Violation] = []

    def _line_text(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1]
        return ""

    def visit_Call(self, node: ast.Call) -> None:
        lineno = getattr(node, "lineno", 0)
        end_lineno = getattr(node, "end_lineno", lineno)
        col = getattr(node, "col_offset", 0)
        line_text = self._line_text(lineno)

        # Check for inline exemption across all lines spanning the call
        if any(has_exemption(self._line_text(l)) for l in range(lineno, end_lineno + 1)):
            self.generic_visit(node)
            return

        # 1. read_text: Path.read_text(encoding=None, errors=None)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "read_text":
            self.calls_count += 1
            has_enc, is_none = is_explicit_encoding_provided(node, pos_idx=0)
            if not has_enc:
                msg = (
                    "read_text() with explicit encoding=None (requires concrete encoding)"
                    if is_none
                    else "bare read_text() without explicit encoding"
                )
                self.violations.append(
                    Violation(
                        file_path=self.file_path,
                        line_number=lineno,
                        column_number=col,
                        call_kind="read_text",
                        message=msg,
                        line_content=line_text.strip(),
                        end_line_number=end_lineno,
                    )
                )

        # 2. write_text: Path.write_text(data, encoding=None, errors=None, newline=None)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "write_text":
            self.calls_count += 1
            has_enc, is_none = is_explicit_encoding_provided(node, pos_idx=1)
            if not has_enc:
                msg = (
                    "write_text() with explicit encoding=None (requires concrete encoding)"
                    if is_none
                    else "bare write_text() without explicit encoding"
                )
                self.violations.append(
                    Violation(
                        file_path=self.file_path,
                        line_number=lineno,
                        column_number=col,
                        call_kind="write_text",
                        message=msg,
                        line_content=line_text.strip(),
                        end_line_number=end_lineno,
                    )
                )

        # 3. open / io.open / Path.open
        elif (isinstance(node.func, ast.Name) and node.func.id == "open") or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            is_built_in_open = isinstance(node.func, ast.Name) and node.func.id == "open"
            is_io_open = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "io"
            )
            is_path_open = False

            if not is_built_in_open and not is_io_open:
                # receiver.open(...)
                # Exclude known non-Path receivers (os, tarfile, zipfile, zf, archive, etc.)
                receiver = node.func.value
                if isinstance(receiver, ast.Name):
                    rec_id = receiver.id.lower()
                    if rec_id in NON_PATH_RECEIVERS or rec_id.endswith(("_zip", "_tar", "_archive")):
                        self.generic_visit(node)
                        return
                # If first positional argument exists and is a string literal, it must be a valid mode string for Path.open
                if len(node.args) >= 1:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        if not is_valid_mode_string(first_arg.value):
                            # First argument is a filename or archive member, not a mode string (e.g. zf.open("file.txt"))
                            self.generic_visit(node)
                            return
                is_path_open = True

            mode_val: Optional[str] = None
            mode_pos_idx = 0 if is_path_open else 1
            enc_pos_idx = 2 if is_path_open else 3

            # Check positional mode argument
            if len(node.args) > mode_pos_idx and isinstance(node.args[mode_pos_idx], ast.Constant) and isinstance(node.args[mode_pos_idx].value, str):
                val = node.args[mode_pos_idx].value
                if is_valid_mode_string(val):
                    mode_val = val

            # Check keyword mode argument
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    mode_val = kw.value.value

            if not is_binary_mode(mode_val):
                self.calls_count += 1
                has_enc, is_none = is_explicit_encoding_provided(node, pos_idx=enc_pos_idx)
                if not has_enc:
                    kind = "path.open" if is_path_open else "open"
                    mode_desc = f"mode={mode_val!r}" if mode_val is not None else "default mode='r'"
                    if is_none:
                        msg = f"{kind}() in text mode ({mode_desc}) with explicit encoding=None"
                    else:
                        msg = f"bare {kind}() in text mode ({mode_desc}) without explicit encoding"
                    self.violations.append(
                        Violation(
                            file_path=self.file_path,
                            line_number=lineno,
                            column_number=col,
                            call_kind=kind,
                            message=msg,
                            line_content=line_text.strip(),
                            end_line_number=end_lineno,
                        )
                    )

        # 4. tempfile.NamedTemporaryFile / TemporaryFile
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ("NamedTemporaryFile", "TemporaryFile")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "tempfile"
        ) or (
            isinstance(node.func, ast.Name)
            and node.func.id in ("NamedTemporaryFile", "TemporaryFile")
        ):
            mode_val = None
            if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                mode_val = node.args[0].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    mode_val = kw.value.value

            # Default mode for tempfile is 'w+b' (binary). Only check if text mode is requested.
            if mode_val is not None and not is_binary_mode(mode_val):
                self.calls_count += 1
                has_enc, is_none = is_explicit_encoding_provided(node, pos_idx=2)
                if not has_enc:
                    func_name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                    if is_none:
                        msg = f"tempfile.{func_name}() in text mode ({mode_val!r}) with explicit encoding=None"
                    else:
                        msg = f"bare tempfile.{func_name}() in text mode ({mode_val!r}) without explicit encoding"
                    self.violations.append(
                        Violation(
                            file_path=self.file_path,
                            line_number=lineno,
                            column_number=col,
                            call_kind=f"tempfile.{func_name}",
                            message=msg,
                            line_content=line_text.strip(),
                            end_line_number=end_lineno,
                        )
                    )

        self.generic_visit(node)


def scan_file(path: Path) -> Tuple[int, int, List[Violation], Optional[str]]:
    """Scan a Python file for encoding violations.

    Returns (line_count, calls_count, violations, error_message).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return 0, 0, [], f"Could not read {path}: {exc}"

    lines = content.splitlines()
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as exc:
        return len(lines), 0, [], f"{path}:{exc.lineno}: SyntaxError: {exc.msg}"

    visitor = TextIOVisitor(str(path), lines)
    visitor.visit(tree)
    return len(lines), visitor.calls_count, visitor.violations, None


def tracked_python_files(root: Path) -> List[Path]:
    """Return every git-tracked ``.py`` file under ``root``, sorted, excluding vendor."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"ERROR: could not list tracked Python files under {root}: {exc}") from exc

    names = [name for name in proc.stdout.split("\0") if name]
    files: List[Path] = []
    for name in names:
        rel_p = Path(name)
        if "scripts/vendor/" in name or "vendor/" in name:
            continue
        if any(part in IGNORED_DIRS for part in rel_p.parts):
            continue
        files.append(root / name)
    return sorted(files)


def collect_tree_files(targets: List[Path], root: Path) -> List[Path]:
    """Collect Python files from given targets or default to tracked Python files."""
    if not targets or targets == [root]:
        return tracked_python_files(root)

    found: List[Path] = []
    for target in targets:
        if target.is_file() and target.suffix == ".py":
            found.append(target)
        elif target.is_dir():
            for r, dirs, fs in os.walk(target):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for f in fs:
                    if f.endswith(".py"):
                        p = Path(r) / f
                        if "vendor" not in p.parts:
                            found.append(p)
    return sorted(found)


def scan_tree(targets: List[Path], root: Path) -> ScanResult:
    """Scan whole Python files in the tree or specified paths."""
    files = collect_tree_files(targets, root)
    total_lines = 0
    total_calls = 0
    all_violations: List[Violation] = []
    errors: List[str] = []

    for path in files:
        lines_count, calls_count, violations, error = scan_file(path)
        total_lines += lines_count
        total_calls += calls_count
        if error:
            errors.append(error)
        all_violations.extend(violations)

    if not files:
        return ScanResult(
            files_count=0,
            lines_count=0,
            calls_count=0,
            violations=[],
            status="empty",
            message="No Python files found matching criteria.",
        )

    if errors:
        return ScanResult(
            files_count=len(files),
            lines_count=total_lines,
            calls_count=total_calls,
            violations=all_violations,
            status="error",
            message="\n".join(errors),
        )

    if all_violations:
        return ScanResult(
            files_count=len(files),
            lines_count=total_lines,
            calls_count=total_calls,
            violations=all_violations,
            status="violations",
        )

    return ScanResult(
        files_count=len(files),
        lines_count=total_lines,
        calls_count=total_calls,
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


def parse_diff_added_lines(diff_text: str) -> Dict[str, Set[int]]:
    """Parse unified diff text into a mapping of filename -> set of added line numbers."""
    added_lines: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    current_line_no = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            current_file = None
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in added_lines:
                added_lines[current_file] = set()
        elif line.startswith("@@ ") and current_file:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_line_no = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            added_lines[current_file].add(current_line_no)
            current_line_no += 1
        elif line.startswith("\\"):
            continue
        elif not line.startswith("-") and current_file:
            current_line_no += 1

    return added_lines


def get_untracked_python_files(repo_root: Path) -> List[Path]:
    """Get list of untracked Python files from git status."""
    proc = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"],
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
        rel_p = Path(rel)
        if any(part in IGNORED_DIRS for part in rel_p.parts) or "scripts/vendor/" in rel:
            continue
        p = repo_root / rel
        if p.is_file():
            untracked.append(p)
    return untracked


def scan_diff(repo_root: Path, base_ref: str) -> ScanResult:
    """Scan added lines in Python files relative to base_ref."""
    diff_proc = subprocess.run(
        ["git", "diff", "--unified=0", base_ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if diff_proc.returncode != 0:
        return ScanResult(
            files_count=0,
            lines_count=0,
            calls_count=0,
            violations=[],
            status="error",
            message=f"git diff failed: {diff_proc.stderr.strip()}",
        )

    file_added_lines = parse_diff_added_lines(diff_proc.stdout)
    untracked_files = get_untracked_python_files(repo_root)

    total_scanned_files: Set[str] = set()
    total_added_lines = 0
    total_calls = 0
    violations: List[Violation] = []
    errors: List[str] = []

    for rel_path, added_set in file_added_lines.items():
        if not rel_path.endswith(".py"):
            continue
        rel_p = Path(rel_path)
        if any(part in IGNORED_DIRS for part in rel_p.parts) or "scripts/vendor/" in rel_path:
            continue
        p = repo_root / rel_path

        total_scanned_files.add(rel_path)
        total_added_lines += len(added_set)
        lines_count, calls_count, file_violations, error = scan_file(p)
        total_calls += calls_count
        if error:
            errors.append(error)
        for v in file_violations:
            end_l = v.end_line_number or v.line_number
            if any(l in added_set for l in range(v.line_number, end_l + 1)):
                violations.append(v)

    for p in untracked_files:
        rel_path = str(p.relative_to(repo_root))
        total_scanned_files.add(rel_path)
        lines_count, calls_count, file_violations, error = scan_file(p)
        total_added_lines += lines_count
        total_calls += calls_count
        if error:
            errors.append(error)
        violations.extend(file_violations)

    if not total_scanned_files or total_added_lines == 0:
        return ScanResult(
            files_count=0,
            lines_count=0,
            calls_count=0,
            violations=[],
            status="empty",
            message=f"0 Python files and 0 added lines examined (empty diff against base '{base_ref}').",
        )

    if errors:
        return ScanResult(
            files_count=len(total_scanned_files),
            lines_count=total_added_lines,
            calls_count=total_calls,
            violations=violations,
            status="error",
            message="\n".join(errors),
        )

    if violations:
        return ScanResult(
            files_count=len(total_scanned_files),
            lines_count=total_added_lines,
            calls_count=total_calls,
            violations=violations,
            status="violations",
        )

    return ScanResult(
        files_count=len(total_scanned_files),
        lines_count=total_added_lines,
        calls_count=total_calls,
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
        help="Scan added lines relative to a base ref (working-tree aware)",
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help="Base git ref for diff mode (default: origin/main or main)",
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
        help="Quiet mode (only report errors/violations)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root (default: directory containing scripts/)",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root

    if args.diff:
        try:
            base_ref = resolve_base_ref(repo_root, args.base)
        except ValueError as exc:
            if args.as_json:
                print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
            else:
                print(f"error: {exc}", file=sys.stderr)
            return 2
        result = scan_diff(repo_root, base_ref)
    else:
        target_paths = args.paths if args.paths else [repo_root]
        result = scan_tree(target_paths, repo_root)

    if args.as_json:
        payload = {
            "status": result.status,
            "files_examined": result.files_count,
            "lines_examined": result.lines_count,
            "calls_inspected": result.calls_count,
            "violations_count": len(result.violations),
            "violations": [
                {
                    "file": v.file_path,
                    "line": v.line_number,
                    "column": v.column_number,
                    "kind": v.call_kind,
                    "message": v.message,
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
            print(
                f"{prefix}{result.message or 'No Python files or lines were examined.'}",
                file=sys.stderr if (args.diff or args.fail_if_empty) else sys.stdout,
            )
        elif result.status == "violations":
            print(
                f"error: Found {len(result.violations)} text I/O operation(s) missing explicit encoding across {result.files_count} file(s):",
                file=sys.stderr,
            )
            for v in result.violations:
                print(
                    f"  {v.file_path}:{v.line_number}:{v.column_number}: {v.message}",
                    file=sys.stderr,
                )
                print(f"      > {v.line_content}", file=sys.stderr)
        elif result.status == "clean":
            if not args.quiet:
                scope_label = "added line(s)" if args.diff else "line(s)"
                print(
                    f"ok: checked {result.files_count} file(s), {result.lines_count} {scope_label} ({result.calls_count} text I/O calls): explicit encoding verified."
                )

    if result.status == "error":
        return 2
    if result.status == "violations":
        return 1
    if result.status == "empty" and (args.diff or args.fail_if_empty):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
