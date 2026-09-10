#!/usr/bin/env python3
"""Check that Antigravity hook commands can actually launch.

A hook command that fails to launch is invisible from both ends: Antigravity
skips a hook whose subprocess dies (see `memories/antigravity.md`, "Fail-open
on a hook subprocess timeout or crash is intentional"), and a headless `agy`
run then reports success and prints a work summary listing files it never
wrote. Nothing is red, and `git status` staying clean is the only tell
(ai-config#3091).

So the launch has to be checked ahead of the run. Two files are in scope:

  plugins/ai-config/hooks.json
      The canonical manifest. Checked for the escaped-quote form and for
      staying in the portable POSIX shape that `scripts/render-agy-hooks.py`
      renders per platform. Failing this exits 1: it is a defect in the repo.

  ~/.gemini/config/plugins/ai-config/hooks.json
      The installed copy, checked with `--installed`. On Windows this also
      refuses any double quote, since the launcher re-escapes one on the way
      to `cmd.exe`. It also checks that the program each command names
      resolves on this machine, which the canonical file cannot be checked
      for since its interpreter is resolved at install time. Absent unless
      bootstrap.sh has run, so its absence is reported and is not a failure.

Usage:
    python3 scripts/check-agy-hook-commands.py
    python3 scripts/check-agy-hook-commands.py --installed
    python3 scripts/check-agy-hook-commands.py --installed --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import agy_hooks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_MANIFEST = ROOT / "plugins" / "ai-config" / "hooks.json"


def load_manifest(path: Path) -> dict:
    """Read one hook manifest, raising rather than returning a partial result."""
    return json.loads(path.read_text(encoding="utf-8"))


def check_manifest(
    manifest: dict,
    canonical: bool,
    check_program: bool = False,
    windows: bool | None = None,
) -> list[str]:
    """Return one message per defective command, empty when the manifest is sound."""
    if windows is None:
        windows = agy_hooks.is_windows()
    findings: list[str] = []
    for where, command in agy_hooks.iter_commands(manifest):
        if canonical:
            problems = agy_hooks.canonical_problems(command)
        elif windows:
            problems = agy_hooks.windows_problems(command)
        else:
            problems = agy_hooks.command_problems(command)
        if check_program and not problems and not agy_hooks.program_resolves(command):
            program = agy_hooks.program_token(command)
            problems.append(
                f"names a program that does not resolve on this machine: {program!r}"
            )
        for problem in problems:
            findings.append(f"{where}: {problem}\n    command: {command}")
    return findings


def check_file(path: Path, canonical: bool, check_program: bool = False) -> dict:
    """Check one manifest file and return a report dict."""
    if not path.is_file():
        return {"path": str(path), "present": False, "findings": [], "commands": 0}
    try:
        manifest = load_manifest(path)
    except Exception as exc:
        return {
            "path": str(path),
            "present": True,
            "findings": [f"is not valid JSON: {exc}"],
            "commands": 0,
        }
    return {
        "path": str(path),
        "present": True,
        "findings": check_manifest(manifest, canonical, check_program),
        "commands": len(list(agy_hooks.iter_commands(manifest))),
    }


def installed_manifest_path() -> Path:
    """Return the staged manifest path bootstrap.sh writes."""
    return Path(os.path.expanduser(agy_hooks.STAGED_MANIFEST))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--installed",
        action="store_true",
        help="also check the staged copy under ~/.gemini/config",
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args(argv)

    reports = [check_file(CANONICAL_MANIFEST, canonical=True)]
    if args.installed:
        reports.append(check_file(installed_manifest_path(), canonical=False, check_program=True))

    failed = any(report["findings"] for report in reports)

    if args.json:
        print(json.dumps({"ok": not failed, "reports": reports}, indent=2))
        return 1 if failed else 0

    for report in reports:
        if not report["present"]:
            print(f"SKIP {report['path']} (not present)")
            continue
        if report["findings"]:
            print(f"FAIL {report['path']}")
            for finding in report["findings"]:
                print(f"  {finding}")
        else:
            print(f"OK   {report['path']} ({report['commands']} command(s))")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
