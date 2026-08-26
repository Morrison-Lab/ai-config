#!/usr/bin/env python3
"""Offline tests for check-harness-ignores.py."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-harness-ignores.py")
spec = importlib.util.spec_from_file_location("harness_ignores", SCRIPT)
hi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hi)

passes = failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def write_ignores(root: Path, extra_gitignore="", drop_cursor=False, omit_pattern=None):
    body = "\n".join(hi.REQUIRED_PATTERNS) + "\n"
    if omit_pattern:
        body = body.replace(omit_pattern + "\n", "")
    (root / ".gitignore").write_text(body + extra_gitignore, encoding="utf-8")
    (root / ".geminiignore").write_text(body, encoding="utf-8")
    cursor = root / ".cursorignore"
    if drop_cursor:
        cursor.unlink(missing_ok=True)
    else:
        cursor.write_text(body, encoding="utf-8")


with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    write_ignores(root)
    check("complete trio is clean", hi.audit(root) == [])

    write_ignores(root, omit_pattern=".worktrees/")
    check(
        "omitted residue pattern is named",
        hi.audit(root) == [
            ".gitignore: missing .worktrees/",
            ".cursorignore: missing .worktrees/",
            ".geminiignore: missing .worktrees/",
        ],
    )

    write_ignores(root, drop_cursor=True)
    check("missing ignore file is named", hi.audit(root) == ["missing file: .cursorignore"])

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(Path(__file__).resolve().parent.parent)],
        capture_output=True,
        text=True,
        check=False,
    )
    check("repo checkout currently satisfies the check", result.returncode == 0)
    check("repo run prints a non-vacuous count", "checked 3 ignore files" in result.stdout)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
