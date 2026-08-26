#!/usr/bin/env python3
"""Unique-negative tests for check-github-actions-step-if.py.

The live memory is the known-clean control. Each finding has its own
otherwise-valid fixture so deleting that finder turns the matching test
red. A check that has never been watched fail is a guess.

False-claim fixtures inject into the step-if bullet, not the file tail:
required phrases also occur later in the same file, and a tail append is
outside the section the checker scans.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-github-actions-step-if.py"
ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "memories" / "github-actions.md"
SECTION_START = "- **An `if:` that names a status-check function"

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


def insert_in_section(text: str, extra: str) -> str:
    i = text.find(SECTION_START)
    if i < 0:
        raise AssertionError("section heading missing from live fixture")
    nl = text.find("\n", i)
    return text[: nl + 1] + extra + text[nl + 1 :]


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
check("live memory has one step-if heading", live_text.count(SECTION_START) == 1)
check(
    "live memory still names the retracted any-explicit claim as false",
    "older claim that *any* explicit step" in live_text,
)
check(
    "retraction does not match the false-heading needle",
    "Writing any explicit step-level" not in live_text,
)

# Unique negatives: restore one false claim INSIDE the bullet.
case_exits(
    "old heading restored in the bullet",
    insert_in_section(
        live_text,
        "Writing any explicit step-level `if:` REPLACES success().\n",
    ),
    1,
    "Writing any explicit step-level",
)
case_exits(
    "old silently-discards body restored in the bullet",
    insert_in_section(
        live_text,
        "Adding an if: silently discards that default.\n",
    ),
    1,
    "silently discards that",
)
case_exits(
    "old own-if Don't restored in the bullet",
    insert_in_section(
        live_text,
        "Don't skip steps that carry their own `if:`.\n",
    ),
    1,
    "steps that carry their own",
)

# Section-scoping control: the same false heading after the file must not
# trip the checker. Whole-file search is the defect this replaces.
case_exits(
    "false heading outside the step-if bullet is ignored",
    live_text + "\nWriting any explicit step-level `if:` REPLACES success().\n",
    0,
)

# Unique negatives: drop one required phrase, keep the rest.
case_exits(
    "retraction sentence removed",
    live_text.replace("older claim that *any* explicit step", "older claim that a step"),
    1,
    "older claim that *any* explicit step",
)
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

# Deleting the #2307 writeup heading is not a clean pass: later copies of
# auto-applies / success() && in the Jules wrap Do must not satisfy the gate.
gutted = live_text.replace(SECTION_START, "- **A step if: that names a status function")
check("writeup heading removal actually applied", SECTION_START not in gutted)
case_exits(
    "step-if bullet heading removed",
    gutted,
    1,
    "missing step-if bullet",
)

# Empty file is not a clean pass: the bullet is gone.
case_exits("empty file is not clean", "", 1, "missing step-if bullet")

# Missing file is a usage error, not a clean pass.
missing_code, missing_out = run_check(ROOT / "no-such-github-actions.md")
check("missing file exits 2", missing_code == 2, missing_out)
check("missing file names the path", "missing file:" in missing_out, missing_out)

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
