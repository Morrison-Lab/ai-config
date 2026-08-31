#!/usr/bin/env python3
"""Check that every test suite in scripts/ is gated in CI.

`.github/workflows/validate.yml` runs test suites under `scripts/`.
If a test suite is added to `scripts/test_*.py` but omitted from `validate.yml`,
it will never run in CI, leaving regressions unflagged (ai-config#2540).

This check discovers all `scripts/test_*.py` files and verifies that each
suite is executed on an active (uncommented) run line in `.github/workflows/validate.yml`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
DEFAULT_SCRIPTS_DIR = ROOT / "scripts"


def find_test_suites(scripts_dir: Path) -> list[Path]:
    """Return sorted list of test suite files matching scripts/test_*.py."""
    if not scripts_dir.is_dir():
        return []
    return sorted(scripts_dir.glob("test_*.py"))


def extract_active_run_commands(workflow_text: str) -> list[str]:
    """Extract all active (uncommented) command lines from run blocks in a workflow."""
    lines = workflow_text.splitlines()
    run_lines: list[str] = []
    in_multiline_run = False
    multiline_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if in_multiline_run:
            current_indent = len(line) - len(line.lstrip())
            if current_indent > multiline_indent:
                run_lines.append(stripped)
                continue
            in_multiline_run = False

        # Check for single line run: command
        match_single = re.match(r"^\s*(?:-\s+)?run:\s+(.*)$", line)
        if match_single:
            cmd = match_single.group(1).strip()
            if cmd in ("|", ">", "|-", ">-"):
                in_multiline_run = True
                multiline_indent = len(line) - len(line.lstrip())
            else:
                run_lines.append(cmd)

    return run_lines


def is_suite_executed(suite_name: str, run_commands: list[str]) -> bool:
    """Return True if suite_name is executed in any active run command."""
    pattern = re.compile(rf"\bpython3?\s+[^\n]*\b{re.escape(suite_name)}\b")
    for cmd in run_commands:
        # Ignore inline comments in commands if any
        cmd_code = cmd.split("#")[0].strip()
        if pattern.search(cmd_code):
            return True
    return False


def check_coverage(
    workflow_path: Path,
    scripts_dir: Path,
) -> tuple[list[str], list[str]]:
    """Compare discovered test suites against active execution in workflow.

    Returns (covered_names, missing_names).
    """
    if not workflow_path.is_file():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    workflow_text = workflow_path.read_text(encoding="utf-8")
    suites = find_test_suites(scripts_dir)
    if not suites:
        raise ValueError(f"No test suites found in {scripts_dir}")

    run_commands = extract_active_run_commands(workflow_text)

    covered: list[str] = []
    missing: list[str] = []

    for suite in suites:
        name = suite.name
        if is_suite_executed(name, run_commands):
            covered.append(name)
        else:
            missing.append(name)

    return covered, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workflow",
        "-w",
        type=Path,
        default=DEFAULT_WORKFLOW,
        help="Path to workflow file (default: .github/workflows/validate.yml)",
    )
    parser.add_argument(
        "--scripts-dir",
        "-s",
        type=Path,
        default=DEFAULT_SCRIPTS_DIR,
        help="Path to scripts directory (default: scripts/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of text",
    )
    args = parser.parse_args(argv)

    try:
        covered, missing = check_coverage(args.workflow, args.scripts_dir)
    except (FileNotFoundError, ValueError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2

    total = len(covered) + len(missing)

    if missing:
        if args.json:
            print(
                json.dumps(
                    {
                        "status": "missing_suites",
                        "total": total,
                        "covered_count": len(covered),
                        "missing_count": len(missing),
                        "missing": missing,
                        "covered": covered,
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"error: {len(missing)} of {total} test suite(s) in {args.scripts_dir} are not run in {args.workflow}:",
                file=sys.stderr,
            )
            for name in missing:
                print(f"  - {name}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "total": total,
                    "covered_count": len(covered),
                    "missing_count": 0,
                    "missing": [],
                    "covered": covered,
                },
                indent=2,
            )
        )
    else:
        print(
            f"ok: all {total} scripts/test_*.py test suites are gated in {args.workflow.name}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
