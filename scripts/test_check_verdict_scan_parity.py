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
    check("generates a non-trivial corpus for fast tier", len(bodies) > 1000)
    check("every generated body is a str", all(isinstance(b, str) for b in bodies))

    exhaustive_count = sum(1 for _ in parity.generated_bodies(exhaustive=True))
    check("exhaustive tier is larger than fast tier", exhaustive_count > len(bodies))

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

    # Comparing a revision against ITSELF must find nothing, and must still
    # report a live negative control -- a zero from a blind detector and a zero
    # from a genuinely unchanged candidate look identical without it.
    #
    # --candidate-rev is passed explicitly rather than defaulting to the working
    # tree: with uncommitted changes present, "--base-rev HEAD" alone compares
    # HEAD against the working tree, which is a real diff and not a self-check.
    # That is exactly how this assertion failed when it was first written.
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check-verdict-scan-parity.py"),
         "--base-rev", "HEAD", "--candidate-rev", "HEAD", "--limit", "400"],
        cwd=REPO, capture_output=True, text=True,
    )
    out = result.stdout
    check("self-comparison reports no widening", "WIDENED" in out and (
        "WIDENED  (base rejected, candidate accepts) : 0" in out))
    check("self-comparison still discriminates", "DISCRIMINATES" in out)
    check("self-comparison exits 0", result.returncode == 0)

    # widening_is_on_axis is the function that produces the "0 off axis"
    # headline, and the suite would pass unchanged if it were `return True`.
    # These pin both answers so it cannot rot into one.
    import importlib.util as _ilu
    sys.path.insert(0, str(REPO / "scripts" / "lib"))
    # The working tree, not origin/main: a shallow or single-branch CI checkout
    # has no origin/main, and this assertion does not need one.
    spec_new = _ilu.spec_from_file_location(
        "smoke_new", REPO / "scripts" / "check-pr-fully-clean.py"
    )
    new_mod = _ilu.module_from_spec(spec_new)
    spec_new.loader.exec_module(new_mod)

    BT = chr(96)
    off_axis_body = (
        "## Verdict\n"
        f"The previously-blocking defect in {BT}{BT}scripts/a.py{BT}{BT} "
        "is still there; nothing fixed.\n"
    )
    on_axis_body = (
        "## Verdict: Ready for merge\n\n"
        f"The phrase {BT}{BT}a {BT}x{BT} Needs more work{BT}{BT} is quoted.\n"
    )
    check(
        "widening_is_on_axis says False when the filter suppressed nothing",
        not parity.widening_is_on_axis(new_mod, off_axis_body),
    )
    check(
        "widening_is_on_axis says True for a phrase suppressed from a span",
        parity.widening_is_on_axis(new_mod, on_axis_body),
    )

    # Reach assertion tests (Issue #2769 / Pattern 32):
    # A sampling instrument cannot silently pass with 0 coverage on any generator arm.
    import argparse
    import json
    import tempfile

    # 1. assert_arm_reach passes when all arm counts are positive
    try:
        parity.assert_arm_reach({"prose": 10, "payload": 5})
        check("assert_arm_reach passes for non-zero counts", True)
    except Exception as exc:
        check(f"assert_arm_reach failed unexpectedly: {exc}", False)

    # 2. assert_arm_reach raises ReachAssertionError on zero count
    try:
        parity.assert_arm_reach({"prose": 10, "payload": 0})
        check("assert_arm_reach fails on zero-count arm", False)
    except parity.ReachAssertionError as exc:
        check("assert_arm_reach raises ReachAssertionError on 0 count", "payload" in str(exc))

    # 3. assert_arm_reach reports all failing arms when multiple have 0
    try:
        parity.assert_arm_reach({"prose": 0, "payload": 0})
        check("assert_arm_reach fails on multiple zero arms", False)
    except parity.ReachAssertionError as exc:
        check("assert_arm_reach identifies all zero arms",
              "prose" in str(exc) and "payload" in str(exc))

    # 4. build_corpus validates reach across default arms
    corpus, arm_counts = parity.build_corpus(
        argparse.Namespace(corpus=[], exhaustive=False, limit=50)
    )
    check("build_corpus yields non-empty corpus", len(corpus) > 0)
    check("build_corpus tracks prose arm count", arm_counts.get("prose") == 50)
    check("build_corpus tracks payload arm count", arm_counts.get("payload") == 57)

    # 5. build_corpus raises when custom generator arm produces 0 items
    try:
        parity.build_corpus(
            argparse.Namespace(corpus=[]),
            generator_arms={"mock_empty_arm": lambda _a: []},
        )
        check("build_corpus rejects empty generator arm", False)
    except parity.ReachAssertionError as exc:
        check("build_corpus raises ReachAssertionError for empty generator arm",
              "mock_empty_arm" in str(exc))

    # 6. build_corpus raises when --corpus points to an empty record list
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp_f:
        json.dump([], tmp_f)
        tmp_path = tmp_f.name
    try:
        parity.build_corpus(
            argparse.Namespace(corpus=[tmp_path], exhaustive=False, limit=10)
        )
        check("build_corpus rejects empty corpus file", False)
    except parity.ReachAssertionError as exc:
        check("build_corpus raises ReachAssertionError for empty corpus file",
              "real" in str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 7. CLI execution with empty corpus file exits non-zero with reach error
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp_f:
        json.dump([], tmp_f)
        tmp_path = tmp_f.name
    try:
        cli_res = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "check-verdict-scan-parity.py"),
             "--corpus", tmp_path, "--base-rev", "HEAD", "--candidate-rev", "HEAD", "--limit", "10"],
            cwd=REPO, capture_output=True, text=True,
        )
        check("CLI exits 1 on reach assertion failure", cli_res.returncode == 1)
        check("CLI reports reach assertion error message in stderr",
              "reach assertion failed" in cli_res.stderr.lower())
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
