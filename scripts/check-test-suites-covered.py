#!/usr/bin/env python3
"""Check that every test suite in scripts/ is gated in CI.

`.github/workflows/validate.yml` runs test suites under `scripts/`.
If a test suite is added to `scripts/test_*.py` but omitted from `validate.yml`,
it will never run in CI, leaving regressions unflagged (ai-config#2540).

This check discovers all `scripts/test_*.py` files and verifies that each
suite is referenced in `.github/workflows/validate.yml`.
"""
from __future__ import annotations

import argparse
import json
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


def check_coverage(
    workflow_path: Path,
    scripts_dir: Path,
) -> tuple[list[str], list[str]]:
    """Compare discovered test suites against workflow content.

    Returns (covered_names, missing_names).
    """
    if not workflow_path.is_file():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    workflow_text = workflow_path.read_text(encoding="utf-8")
    suites = find_test_suites(scripts_dir)
    if not suites:
        raise ValueError(f"No test suites found in {scripts_dir}")

    covered: list[str] = []
    missing: list[str] = []

    for suite in suites:
        name = suite.name
        # Match test suite file name in workflow text
        if name in workflow_text:
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
    except FileNotFoundError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
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
