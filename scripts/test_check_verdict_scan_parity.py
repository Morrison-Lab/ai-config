#!/usr/bin/env python3
"""Smoke tests for scripts/check-verdict-scan-parity.py.

The instrument produces the evidence a change to the verdict scanner is
justified by, so it needs its own guard against rotting into one that always
reports zero -- which is the exact failure it was built to replace.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "parity", REPO / "scripts" / "check-verdict-scan-parity.py"
)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def main() -> int:
    print("Testing check-verdict-scan-parity.py...")

    bodies = list(parity.generated_bodies())
    check("generates a non-trivial corpus", len(bodies) > 1000)
    check("every generated body is a str", all(isinstance(b, str) for b in bodies))

    # is_widening encodes the direction that matters: accepting what the base
    # rejected. Getting this backwards would make the tool report zero forever.
    check("not-clean -> clean is a widening",
          parity.is_widening(("not-clean", False), ("clean", False)))
    check("a lost finding pattern is a widening",
          parity.is_widening(("clean", True), ("clean", False)))
    check("clean -> not-clean is NOT a widening",
          not parity.is_widening(("clean", False), ("not-clean", False)))
    check("no change is NOT a widening",
          not parity.is_widening(("clean", False), ("clean", False)))

    # Comparing a revision against itself must find nothing, and must still
    # report a live negative control -- a zero from a blind detector and a zero
    # from a genuinely unchanged candidate look identical without it.
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check-verdict-scan-parity.py"),
         "--base-rev", "HEAD", "--limit", "400"],
        cwd=REPO, capture_output=True, text=True,
    )
    out = result.stdout
    check("self-comparison reports no widening", "WIDENED" in out and (
        "WIDENED  (base rejected, candidate accepts) : 0" in out))
    check("self-comparison still discriminates", "DISCRIMINATES" in out)
    check("self-comparison exits 0", result.returncode == 0)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
