#!/usr/bin/env python3
"""Scan the repository for concrete, mechanical simplification opportunities.

This is the KISS review aid: instead of asking a human (or an agent) to eyeball
the tree for "things that look complicated", it reports duplication and
complexity that can be measured, with exact file:line locations.

Checks performed:

  duplicate-file   Two or more tracked files have byte-identical content.
  duplicate-block  A run of identical significant lines appears in 2+ places.
  long-function    A Python function/method exceeds the line budget.
  deep-nesting     Python control flow nests deeper than the budget.
  long-file        A text file exceeds the line budget.
  unparseable      A tracked .py file does not parse (reported, never ignored).

Nothing here rewrites code. It produces a work list.

Usage:
    python scripts/kiss_scan.py
    python scripts/kiss_scan.py --strict
    python scripts/kiss_scan.py --json
    python scripts/kiss_scan.py --paths scripts/foo.py scripts/bar.py

Exit codes:
    0  scan completed within the configured finding budget
    1  scan completed but the finding budget was exceeded
    2  the scan could not run (bad usage, not a git repo, undecodable file)
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_MIN_DUPLICATE_LINES = 8
DEFAULT_MAX_FUNCTION_LINES = 60
DEFAULT_MAX_NESTING = 5
DEFAULT_MAX_FILE_LINES = 800

# Only text formats we can reason about line-by-line.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".sh",
        ".bash",
        ".ps1",
        ".psm1",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".md",
        ".yml",
        ".yaml",
    }
)

# Directories whose contents are not ours to simplify.
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "vendor",
        "fixtures",
    }
)

HASH_COMMENT_SUFFIXES = frozenset({".py", ".sh", ".bash", ".ps1", ".psm1", ".yml", ".yaml"})
SLASH_COMMENT_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx"})

BLOCK_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


class ScanError(RuntimeError):
    """The scan cannot be completed. Always fatal, never downgraded to a warning."""


@dataclass(frozen=True)
class Location:
    path: str
    line: int

    def render(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    line: int
    message: str
    locations: tuple[Location, ...] = field(default_factory=tuple)

    @property
    def sort_key(self) -> tuple[str, str, int]:
        return (self.kind, self.path, self.line)


@dataclass(frozen=True)
class ScanConfig:
    min_duplicate_lines: int = DEFAULT_MIN_DUPLICATE_LINES
    max_function_lines: int = DEFAULT_MAX_FUNCTION_LINES
    max_nesting: int = DEFAULT_MAX_NESTING
    max_file_lines: int = DEFAULT_MAX_FILE_LINES

    def __post_init__(self) -> None:
        if self.min_duplicate_lines < 2:
            raise ScanError(
                f"--min-duplicate-lines must be >= 2, got {self.min_duplicate_lines}; "
                "a single shared line is not a duplication signal"
            )
        if self.max_function_lines < 1:
            raise ScanError(f"--max-function-lines must be >= 1, got {self.max_function_lines}")
        if self.max_nesting < 1:
            raise ScanError(f"--max-nesting must be >= 1, got {self.max_nesting}")
        if self.max_file_lines < 1:
            raise ScanError(f"--max-file-lines must be >= 1, got {self.max_file_lines}")


# --------------------------------------------------------------------------
# File discovery and loading
# --------------------------------------------------------------------------


def git_tracked_files(root: Path) -> list[Path]:
    """Return every file git tracks under *root*.

    Using git (rather than a raw walk) means .gitignore is honoured for free.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment dependent
        raise ScanError("git executable not found on PATH; kiss_scan requires git") from exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ScanError(f"`git ls-files` failed in {root}: {detail or 'no stderr output'}")

    names = proc.stdout.decode("utf-8").split("\0")
    # Tracked-but-deleted paths are a normal worktree state; there is nothing to read.
    return [root / name for name in names if name and (root / name).is_file()]


def is_scannable(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    return not any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def load_file(path: Path) -> list[str]:
    """Read *path* as UTF-8 text. A decode failure is fatal, not skipped."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ScanError(
            f"{path} has a scannable extension but is not valid UTF-8 text "
            f"({exc.reason}); exclude it or fix the file"
        ) from exc
    except OSError as exc:
        raise ScanError(f"cannot read {path}: {exc}") from exc
    return text.splitlines()


def display_path(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return path.as_posix()
    return relative.as_posix()


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def significant_lines(path: Path, lines: Sequence[str]) -> list[tuple[int, str]]:
    """Return (1-based line number, normalised text) for lines that carry meaning.

    Blank lines and whole-line comments are dropped so that reformatting noise
    does not hide genuine copy-paste.
    """
    suffix = path.suffix.lower()
    comment_markers: list[str] = []
    if suffix in HASH_COMMENT_SUFFIXES:
        comment_markers.append("#")
    if suffix in SLASH_COMMENT_SUFFIXES:
        comment_markers.append("//")

    result: list[tuple[int, str]] = []
    for offset, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        if any(stripped.startswith(marker) for marker in comment_markers):
            continue
        result.append((offset, stripped))
    return result


def check_duplicate_files(
    contents: dict[Path, list[str]], root: Path
) -> list[Finding]:
    by_digest: dict[str, list[Path]] = {}
    for path in contents:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_digest.setdefault(digest, []).append(path)

    findings: list[Finding] = []
    for paths in by_digest.values():
        if len(paths) < 2:
            continue
        ordered = sorted(paths, key=lambda p: display_path(p, root))
        locations = tuple(Location(display_path(p, root), 1) for p in ordered)
        others = ", ".join(loc.path for loc in locations[1:])
        findings.append(
            Finding(
                kind="duplicate-file",
                path=locations[0].path,
                line=1,
                message=f"byte-identical to {others}; keep one and reference it",
                locations=locations,
            )
        )
    return findings


def check_duplicate_blocks(
    contents: dict[Path, list[str]], root: Path, min_lines: int
) -> list[Finding]:
    """Report runs of >= *min_lines* identical significant lines seen 2+ times."""
    significant: dict[Path, list[tuple[int, str]]] = {
        path: significant_lines(path, lines) for path, lines in contents.items()
    }

    windows: dict[tuple[str, ...], list[tuple[Path, int]]] = {}
    for path in sorted(significant, key=lambda p: display_path(p, root)):
        sig = significant[path]
        for start in range(len(sig) - min_lines + 1):
            key = tuple(text for _, text in sig[start : start + min_lines])
            windows.setdefault(key, []).append((path, start))

    findings: list[Finding] = []
    covered: set[tuple[Path, int]] = set()

    # Stable order: earliest first occurrence wins, so overlapping shifted
    # windows collapse into the single report that starts the duplicated run.
    def order(item: tuple[tuple[str, ...], list[tuple[Path, int]]]) -> tuple[str, int]:
        path, start = item[1][0]
        return (display_path(path, root), start)

    for _, occurrences in sorted(windows.items(), key=order):
        if len(occurrences) < 2:
            continue
        if all((path, start) in covered for path, start in occurrences):
            continue
        for path, start in occurrences:
            for offset in range(min_lines):
                covered.add((path, start + offset))

        locations = tuple(
            Location(display_path(path, root), significant[path][start][0])
            for path, start in occurrences
        )
        others = ", ".join(loc.render() for loc in locations[1:])
        findings.append(
            Finding(
                kind="duplicate-block",
                path=locations[0].path,
                line=locations[0].line,
                message=(
                    f"{min_lines} identical significant lines also at {others}; "
                    "extract a shared helper"
                ),
                locations=locations,
            )
        )
    return findings


def _parse_python(path: Path, lines: Sequence[str], root: Path) -> ast.Module | Finding:
    source = "\n".join(lines)
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return Finding(
            kind="unparseable",
            path=display_path(path, root),
            line=exc.lineno or 1,
            message=f"python file does not parse: {exc.msg}",
        )


def check_long_functions(
    tree: ast.Module, path_label: str, max_lines: int
) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:  # pragma: no cover - always set on supported Pythons
            continue
        length = end - node.lineno + 1
        if length > max_lines:
            findings.append(
                Finding(
                    kind="long-function",
                    path=path_label,
                    line=node.lineno,
                    message=(
                        f"{node.name}() spans {length} lines "
                        f"(budget {max_lines}); split it"
                    ),
                )
            )
    return findings


def _deepest_blocks(node: ast.AST, depth: int, limit: int) -> list[tuple[int, int]]:
    """Collect (line, depth) for every block statement nested deeper than *limit*."""
    found: list[tuple[int, int]] = []
    is_if = isinstance(node, ast.If)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, BLOCK_NODES):
            # `elif` is a nested If in the AST but flat to a reader.
            is_elif = is_if and isinstance(child, ast.If) and len(node.orelse) == 1 and child in node.orelse
            child_depth = depth if is_elif else depth + 1
            if child_depth > limit:
                found.append((child.lineno, child_depth))
            found.extend(_deepest_blocks(child, child_depth, limit))
        else:
            found.extend(_deepest_blocks(child, depth, limit))
    return found


def check_deep_nesting(tree: ast.Module, path_label: str, limit: int) -> list[Finding]:
    over_budget = _deepest_blocks(tree, 0, limit)
    if not over_budget:
        return []
    # One report per file, pointing at the worst offender.
    line, depth = min(over_budget, key=lambda item: (-item[1], item[0]))
    return [
        Finding(
            kind="deep-nesting",
            path=path_label,
            line=line,
            message=(
                f"control flow nests {depth} levels deep (budget {limit}); "
                "use early returns or a helper"
            ),
        )
    ]


def check_long_files(
    contents: dict[Path, list[str]], root: Path, max_lines: int
) -> list[Finding]:
    findings: list[Finding] = []
    for path, lines in contents.items():
        if len(lines) > max_lines:
            findings.append(
                Finding(
                    kind="long-file",
                    path=display_path(path, root),
                    line=1,
                    message=f"{len(lines)} lines (budget {max_lines}); consider splitting",
                )
            )
    return findings


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def scan_paths(
    paths: Iterable[Path], config: ScanConfig, root: Path
) -> list[Finding]:
    """Run every check over *paths*. Raises ScanError if nothing is scannable."""
    selected = sorted({p for p in paths if is_scannable(p)})
    if not selected:
        raise ScanError(
            f"no scannable files found under {root} "
            f"(extensions checked: {', '.join(sorted(TEXT_SUFFIXES))})"
        )

    contents = {path: load_file(path) for path in selected}

    findings: list[Finding] = []
    findings.extend(check_duplicate_files(contents, root))
    findings.extend(check_duplicate_blocks(contents, root, config.min_duplicate_lines))
    findings.extend(check_long_files(contents, root, config.max_file_lines))

    for path, lines in contents.items():
        if path.suffix.lower() != ".py":
            continue
        label = display_path(path, root)
        parsed = _parse_python(path, lines, root)
        if isinstance(parsed, Finding):
            findings.append(parsed)
            continue
        findings.extend(check_long_functions(parsed, label, config.max_function_lines))
        findings.extend(check_deep_nesting(parsed, label, config.max_nesting))

    return sorted(findings, key=lambda f: f.sort_key)


def render_text(findings: Sequence[Finding], files_scanned: int) -> str:
    if not findings:
        return f"KISS scan: no simplification opportunities across {files_scanned} files."

    noun = "opportunity" if len(findings) == 1 else "opportunities"
    lines = [f"KISS scan: {len(findings)} simplification {noun} across {files_scanned} files.", ""]

    current_kind = None
    for finding in findings:
        if finding.kind != current_kind:
            current_kind = finding.kind
            count = sum(1 for f in findings if f.kind == current_kind)
            lines.append(f"{current_kind} ({count})")
        lines.append(f"  {finding.path}:{finding.line}  {finding.message}")
    return "\n".join(lines)


def render_json(findings: Sequence[Finding], files_scanned: int) -> str:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    payload = {
        "files_scanned": files_scanned,
        "total": len(findings),
        "counts": counts,
        "findings": [asdict(finding) for finding in findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kiss_scan",
        description="Report measurable simplification opportunities (duplication, size, nesting).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root used for discovery and for relative display paths",
    )
    parser.add_argument(
        "--paths",
        type=Path,
        nargs="+",
        help="scan these files instead of every git-tracked file",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--min-duplicate-lines",
        type=int,
        default=DEFAULT_MIN_DUPLICATE_LINES,
        help=f"identical-line run length that counts as duplication (default {DEFAULT_MIN_DUPLICATE_LINES})",
    )
    parser.add_argument(
        "--max-function-lines",
        type=int,
        default=DEFAULT_MAX_FUNCTION_LINES,
        help=f"python function line budget (default {DEFAULT_MAX_FUNCTION_LINES})",
    )
    parser.add_argument(
        "--max-nesting",
        type=int,
        default=DEFAULT_MAX_NESTING,
        help=f"python block nesting budget (default {DEFAULT_MAX_NESTING})",
    )
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=DEFAULT_MAX_FILE_LINES,
        help=f"file line budget (default {DEFAULT_MAX_FILE_LINES})",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=None,
        help="exit 1 if the finding count exceeds this budget",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="shorthand for --max-findings 0",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.strict and args.max_findings is not None:
            raise ScanError("--strict and --max-findings are mutually exclusive; pass only one")
        budget = 0 if args.strict else args.max_findings

        config = ScanConfig(
            min_duplicate_lines=args.min_duplicate_lines,
            max_function_lines=args.max_function_lines,
            max_nesting=args.max_nesting,
            max_file_lines=args.max_file_lines,
        )

        root: Path = args.root
        if not root.is_dir():
            raise ScanError(f"--root {root} is not a directory")

        candidates = args.paths if args.paths else git_tracked_files(root)
        if args.paths:
            missing = [p for p in candidates if not p.is_file()]
            if missing:
                raise ScanError(
                    "these --paths do not exist: " + ", ".join(p.as_posix() for p in missing)
                )

        findings = scan_paths(candidates, config, root)
        scanned = len([p for p in candidates if is_scannable(p)])
    except ScanError as exc:
        print(f"kiss_scan: {exc}", file=sys.stderr)
        return 2

    output = render_json(findings, scanned) if args.json else render_text(findings, scanned)
    print(output)

    if budget is not None and len(findings) > budget:
        print(
            f"kiss_scan: {len(findings)} findings exceeds budget of {budget}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
