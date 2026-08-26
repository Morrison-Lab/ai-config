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

# Unique negatives: restore one false claim. Forbidden needles are
# file-wide, so a sibling bullet must fail the same way as an in-bullet
# restore.
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
    "old heading restored as a sibling bullet",
    live_text + "\nWriting any explicit step-level `if:` REPLACES success().\n",
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

# Unique negatives: drop one required phrase from the bullet, keep the
# rest. Replacements are scoped to the recommendation / retraction, not
# every success() && in the file (gha#350's sibling copy must not satisfy
# the Keep writing needle).
case_exits(
    "retraction sentence removed",
    live_text.replace("older claim that *any* explicit step", "older claim that a step"),
    1,
    "older claim that *any* explicit step",
)
keep = "Keep writing `success() &&`"
keep_gone = live_text.replace(keep, "Keep writing success() and")
check("Keep writing success() && removal actually applied", keep not in keep_gone)
check(
    "gha#350 sibling success() && still present after Keep writing removal",
    "success() &&" in keep_gone,
)
case_exits(
    "recommended Keep writing success() && removed",
    keep_gone,
    1,
    "Keep writing `success() &&`",
)
docs = "GitHub auto-applies `success()` when the condition has no such function"
docs_gone = live_text.replace(docs, "GitHub applies success() when prior steps passed")
check("docs auto-applies sentence removal actually applied", docs not in docs_gone)
check(
    "Jules wrap auto-applies still present after docs sentence removal",
    "GitHub auto-applies" in docs_gone,
)
case_exits(
    "docs auto-applies sentence removed",
    docs_gone,
    1,
    "GitHub auto-applies `success()` when the condition has no such function",
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
