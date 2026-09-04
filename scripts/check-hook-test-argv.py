#!/usr/bin/env python3
"""Report hook test suites whose PATH shim never inspects its own argv.

A hook test can stub an external command, assert the hook's decision, and
constrain nothing about *what the hook actually asked*. The suite is green and
mutations to the query survive: swapping `headRefName` for `baseRefName`, or
dropping `--base` from a list query, changes no assertion when the shim returns
the same fixture whatever it is handed (ai-config#2447, ai-config#2458).

The condition is decidable from the test file alone, with no judgment about
coverage: a suite that writes an executable stub and never reads `sys.argv`
(or `$@`, `$1`, `$*` in a shell stub) inside it cannot constrain the query.

Advisory rather than hard-gating, unlike `check-hook-output-shape.py`. A shim
that legitimately needs no argv exists --- a stub whose only job is to be
present on PATH, or one whose single fixture answers the hook's single call ---
so a finding here is a prompt to read the suite, not a proven defect. Pass
`--strict` to exit non-zero on any finding.

Run: python3 scripts/check-hook-test-argv.py
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOOKS_DIR = ROOT / "hooks"

SUCCESS_EXIT = 0
FINDING_EXIT = 1
USAGE_EXIT = 2

# Markers that a stub reads the arguments it was called with. `sys.argv` covers
# a Python stub; the shell forms cover a `#!/bin/sh` one. A bare `argv` is
# deliberately NOT a marker: a suite that logs to a path it named `argv_log`
# would match it without the stub ever reading an argument, and a stub that
# binds `args = sys.argv[1:]` first carries `sys.argv` anyway.
ARGV_MARKERS = ("sys.argv", "$@", "$1", "$2", "$*")

# A shebang inside a test file is not by itself a stub: diff-hunk fixtures carry
# `#!/bin/bash` as ordinary content. A stub is a shebang the file writes out, in a
# suite that also marks something executable; this marker is the coarse pre-filter.
INSTALL_MARKERS = ("chmod",)

# A hook is a Python script or a shell script; both take a `test-<name>.py` suite.
SUBJECT_SUFFIXES = (".py", ".sh")


def _shebang_constants(tree: ast.AST) -> list[ast.AST]:
    """Return every string-literal node whose text opens with a shebang."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.lstrip().startswith("#!"):
                found.append(node)
    return found


def stub_statements(source: str) -> tuple[list[str], str | None]:
    """Return the source text of each statement that embeds a stub program.

    The unit is the INNERMOST statement enclosing a shebang literal, and both
    halves of that choice are load-bearing. A statement rather than a lone
    literal, because a stub is routinely built from an f-string or from
    adjacent literals: the shebang lands in one constant and `"$@"` in the
    next, so a per-constant scan reads the second half as a separate program
    and misses the argv marker. The innermost one rather than any enclosing
    one, because an outer `with` block holding both a blind stub and unrelated
    code that happens to mention `sys.argv` would otherwise read as clean.

    A shebang the file never writes out is fixture content rather than a stub,
    so the statement must either call a write itself or bind a name that a
    simple write statement elsewhere in the file mentions.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        return [], f"could not be parsed as Python ({err})"

    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    written = _written_names(tree, source)
    segments = []
    for literal in _shebang_constants(tree):
        node: ast.AST | None = literal
        while node is not None and not isinstance(node, ast.stmt):
            node = parents.get(id(node))
        if node is None:
            continue
        segment = ast.get_source_segment(source, node)
        if not segment:
            continue
        if "write" not in segment and not (_bound_names(node) & written):
            continue
        segments.append(segment)
    return segments, None


def _written_names(tree: ast.AST, source: str) -> set[str]:
    """Names mentioned by a simple statement whose text calls a write.

    Compound statements are skipped, so an enclosing block does not mark
    every name inside it as written.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or hasattr(node, "body"):
            continue
        segment = ast.get_source_segment(source, node) or ""
        if "write" not in segment:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                names.add(sub.id)
    return names


def _bound_names(node: ast.AST) -> set[str]:
    """Names this statement assigns to."""
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return {t.id for t in targets if isinstance(t, ast.Name)}


def stub_label(segment: str) -> str:
    """A short identifying slice of a stub statement: its first line."""
    first = segment.strip().splitlines()[0].strip()
    return first if len(first) <= 60 else first[:57] + "..."


def inspects_argv(segment: str) -> bool:
    """True when the statement's text reads the arguments the stub was given."""
    return any(marker in segment for marker in ARGV_MARKERS)


def subject_exists(hooks_dir: Path, test_path: Path) -> bool:
    """True when the suite has a hook beside it to test.

    The extension is not assumed: `inject-local-time` is a shell hook, so a
    `.py`-only lookup drops its suite from the sweep silently.
    """
    stem = test_path.stem[len("test-"):]
    return any((hooks_dir / f"{stem}{ext}").is_file() for ext in SUBJECT_SUFFIXES)


def check_test_file(path: Path) -> tuple[list[str], str | None, int]:
    """Return (findings, parse_error, stub count) for one hook test suite.

    Each stub is judged on its own text, so an argv-aware shim does not clear
    a blind one installed beside it.
    """
    source = path.read_text(encoding="utf-8")
    if not any(marker in source for marker in INSTALL_MARKERS):
        return [], None, 0

    stub_segments, parse_err = stub_statements(source)
    if parse_err:
        return [], f"{path.name} {parse_err}", 0

    findings = [
        f"{path.name}: the stub at `{stub_label(seg)}` never reads its own argv. "
        "A stub returning one fixture whatever it is asked leaves the hook's "
        "query unconstrained, so a mutated query ships green."
        for seg in stub_segments
        if not inspects_argv(seg)
    ]
    return findings, None, len(stub_segments)


def collect_findings(hooks_dir: Path) -> tuple[list[str], list[str], int, int]:
    """Return (findings, parse_errors, suites examined, stubs installed).

    The stub count is the negative control. Zero findings over zero stubs is
    indistinguishable from a detector that never ran, so both numbers are
    reported rather than only the one that fired.
    """
    findings: list[str] = []
    errors: list[str] = []
    examined = 0
    stubs = 0

    for test_path in sorted(hooks_dir.glob("test-*.py")):
        if not subject_exists(hooks_dir, test_path):
            continue
        examined += 1
        file_findings, error, stub_count = check_test_file(test_path)
        stubs += stub_count
        if error:
            errors.append(error)
        findings.extend(file_findings)

    return findings, errors, examined, stubs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        default=DEFAULT_HOOKS_DIR,
        help="directory holding hooks and their test suites (default: hooks/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any suite is flagged (default: advisory, exits 0)",
    )
    args = parser.parse_args()

    hooks_dir = args.hooks_dir
    if not hooks_dir.is_dir():
        print(f"FAIL: no hooks directory at {hooks_dir}")
        return USAGE_EXIT

    findings, errors, examined, stubs = collect_findings(hooks_dir)
    if not examined:
        print(f"FAIL: no hook test suites found in {hooks_dir}")
        return USAGE_EXIT

    for error in errors:
        print(f"FAIL: {error}")

    for finding in findings:
        print(f"FINDING: {finding}")

    print(
        f"\nExamined {examined} hook test suite(s) "
        f"holding {stubs} executable stub(s): "
        f"{len(findings)} ignore argv, {len(errors)} unparseable."
    )

    if errors:
        return FINDING_EXIT
    if findings and args.strict:
        return FINDING_EXIT
    return SUCCESS_EXIT


if __name__ == "__main__":
    sys.exit(main())
