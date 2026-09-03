#!/usr/bin/env python3
r"""Fail on an invalid escape sequence in any Python string literal (ai-config#3114).

A backslash sequence Python does not recognize --- `\s`, `\d`, `\w` and
friends --- inside a non-raw string literal is an *invalid escape sequence*.
It is deprecated and on a path to a hard `SyntaxError`.

This corpus is unusually exposed to the defect for a structural reason rather
than a careless one: its Python modules quote regex source in their prose.  A
docstring explaining why a pattern is written a certain way naturally contains
the pattern, and the moment that pattern carries a `\s` the docstring is an
invalid escape.  The rule and the thing it describes are the same characters,
which is the self-implicating-example shape
`shared/writing/examples-are-scanned.md` already names for prose checkers.
This module's own docstring is raw for exactly that reason.

Two constraints shape the implementation:

* **Key on the warning MESSAGE, not its category.**  Python 3.11 raises
  `DeprecationWarning`, which is silent by default;  3.12 and later raise
  `SyntaxWarning`, which prints on every cold-cache import.  Asserting on the
  category inherits that split and would pass vacuously on one of them.
* **Report the denominator.**  A zero from a detector that never ran is
  indistinguishable from a clean tree, so the summary states how many files
  were examined alongside how many were flagged, and an empty search space is
  itself a failure.  The first attempt at this scan reported zero across the
  whole tree while a hand-confirmed hit sat in it, because it compiled to
  `/dev/null`, every compile raised, and a bare `except: continue` swallowed
  all of them.  Nothing here swallows a compile failure: a file that does not
  parse is reported and fails the run.

Usage:

    python3 scripts/check-python-escapes.py            # every tracked .py file
    python3 scripts/check-python-escapes.py PATH ...   # given files/directories

Exit 0 when every examined file is clean, 1 otherwise --- a finding, a file
that does not compile, or an empty search space.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The interpreter's own wording for this diagnostic.  It is stable across the
# DeprecationWarning/SyntaxWarning split described in the module docstring,
# which is why the scan keys on it rather than on the warning category.
INVALID_ESCAPE_MARKER = "invalid escape sequence"


def tracked_python_files(root: Path) -> list[Path]:
    """Return every git-tracked ``.py`` file under ``root``, sorted."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        # Fail loudly rather than returning an empty list: an unusable file
        # listing must never be mistaken for a tree with nothing in it.
        raise SystemExit(
            f"ERROR: could not list tracked Python files under {root}: {exc}"
        ) from exc
    names = [name for name in proc.stdout.split("\0") if name]
    return sorted(root / name for name in names)


def collect_files(paths: list[str], root: Path) -> list[Path]:
    """Resolve CLI arguments to a file list, defaulting to the tracked tree."""
    if not paths:
        return tracked_python_files(root)
    resolved: list[Path] = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_dir():
            resolved.extend(sorted(candidate.rglob("*.py")))
        else:
            resolved.append(candidate)
    return resolved


def scan_file(path: Path) -> tuple[list[str], str | None]:
    """Compile one file with warnings visible.

    Returns ``(findings, error)``, where ``findings`` are formatted
    ``path:line: message`` strings for every invalid escape sequence and
    ``error`` is set when the file could not be compiled at all.
    """
    try:
        source = path.read_bytes()
    except OSError as exc:
        return [], f"{path}: could not be read: {exc}"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            return [], f"{path}:{exc.lineno}: does not compile: {exc.msg}"
        except ValueError as exc:
            return [], f"{path}: does not compile: {exc}"

    findings = [
        f"{path}:{entry.lineno}: {entry.message}"
        for entry in caught
        if INVALID_ESCAPE_MARKER in str(entry.message)
    ]
    return findings, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "invalid escape sequence check").strip().splitlines()[0]
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="files or directories to scan (default: every tracked .py file)",
    )
    args = parser.parse_args(argv)

    files = collect_files(args.paths, ROOT)

    findings: list[str] = []
    errors: list[str] = []
    flagged_files = 0
    for path in files:
        file_findings, error = scan_file(path)
        if error is not None:
            errors.append(error)
        if file_findings:
            flagged_files += 1
            findings.extend(file_findings)

    for line in errors:
        print(line)
    for line in findings:
        print(line)

    print(
        f"Examined {len(files)} Python files; "
        f"{flagged_files} carried an invalid escape sequence."
    )

    if not files:
        print(
            "ERROR: no Python files examined --- the search space was empty, "
            "so a clean verdict would be vacuous."
        )
        return 1
    if errors:
        print(f"ERROR: {len(errors)} file(s) could not be compiled.")
        return 1
    if findings:
        print(
            "ERROR: use a raw string literal (r'...') for a pattern, or double "
            "the backslash, so the literal says what it means."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
