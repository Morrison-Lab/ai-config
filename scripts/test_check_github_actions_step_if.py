#!/usr/bin/env python3
"""Unique-negative tests for check-github-actions-step-if.py.

The live memory is the known-clean control. Each finding has its own
otherwise-valid fixture so deleting that finder turns the matching test
red. A check that has never been watched fail is a guess.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-github-actions-step-if.py"
ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "memories" / "github-actions.md"

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def run_check(memory: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(memory)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


def write_fixture(tmpdir: str, body: str) -> Path:
    path = Path(tmpdir) / "github-actions.md"
    path.write_text(body, encoding="utf-8")
    return path


def case_exits(
    name: str,
    body: str,
    expect: int,
    needle: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_fixture(tmpdir, body)
        code, output = run_check(path)
    check(f"{name}: exit {expect}", code == expect, f"got {code}\n{output}")
    if needle is not None:
        check(f"{name}: mentions {needle!r}", needle in output, output)


# Live file must pass through the same entry point CI will run.
check("live memory exists", LIVE.is_file())
live_code, live_out = run_check(LIVE)
check("live memory is clean", live_code == 0, live_out)
check(
    "live run reports its denominator",
    "Examined 6 invariants" in live_out,
    live_out,
)

live_text = LIVE.read_text(encoding="utf-8")
check(
    "live memory still names the retracted any-explicit claim as false",
    "older claim that *any* explicit step" in live_text,
)
check(
    "retraction does not match the false-heading needle",
    "Writing any explicit step-level" not in live_text,
)

# Unique negatives: restore one false claim, keep the rest of the live file.
case_exits(
    "old heading restored",
    live_text + "\nWriting any explicit step-level `if:` REPLACES success().\n",
    1,
    "Writing any explicit step-level",
)
case_exits(
    "old silently-discards body restored",
    live_text + "\nAdding an if: silently discards that default.\n",
    1,
    "silently discards that",
)
case_exits(
    "old own-if Don't restored",
    live_text + "\nDon't skip steps that carry their own `if:`.\n",
    1,
    "steps that carry their own",
)

# Unique negatives: drop one required phrase, keep the rest.
case_exits(
    "recommended success() && removed",
    live_text.replace("success() &&", "success() and"),
    1,
    "success() &&",
)
check(
    "success() && removal actually applied",
    "success() &&" not in live_text.replace("success() &&", "success() and"),
)
case_exits(
    "auto-applies claim removed",
    live_text.replace("auto-applies", "applies"),
    1,
    "auto-applies",
)
case_exits(
    "status-check function wording removed",
    live_text.replace("status-check function", "status function"),
    1,
    "status-check function",
)

# Empty file is not a clean pass: required phrases are gone.
case_exits("empty file is not clean", "", 1, "success() &&")

# Missing file is a usage error, not a clean pass.
missing_code, missing_out = run_check(ROOT / "no-such-github-actions.md")
check("missing file exits 2", missing_code == 2, missing_out)
check("missing file names the path", "missing file:" in missing_out, missing_out)

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
