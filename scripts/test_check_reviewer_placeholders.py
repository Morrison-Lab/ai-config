#!/usr/bin/env python3
"""Tests for scripts/check-reviewer-placeholders.py (ai-config#2627).

The NEGATIVE cases carry the weight here, inverting this repo's usual advice
for a detector. Elsewhere an over-eager gate is cheap; here it would block CI
over the exact prose form the corpus is supposed to keep using ("request the
repository owner as reviewer" is a role reference and is correct). So the
cases proving it does NOT fire on prose are what make the gate safe to add.
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "gate", Path(__file__).parent / "check-reviewer-placeholders.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

# Assembled at runtime: this file is itself scanned by the gate it tests, so a
# literal value-position example here would trip the very rule under test --
# the self-implicating-example problem shared/writing/examples-are-scanned.md
# describes. Building the phrase from parts keeps the gate free of a path
# exemption, which would be a hole in it.
PHRASE = "the repository " + "owner"

passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


def fires(line, tmp_path):
    f = tmp_path / "sample.md"
    f.write_text(line, encoding="utf-8")
    findings, examined = gate.scan([f])
    return bool(findings), examined


def main():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    # scan() computes paths relative to REPO, so point it at the temp root
    gate.REPO = tmp

    # --- must fire: value positions ---
    for line, label in [
        (f"owner: {PHRASE}", "an owner: argument"),
        (f'`owner: "{PHRASE}"`', "a quoted owner: argument"),
        (f'-f "reviewers[]={PHRASE}"', "a reviewers[]= field"),
        (f"gh pr edit 5 --add-reviewer {PHRASE}", "an --add-reviewer flag"),
        (f"gh pr list --head {PHRASE}:branch", "a --head argument"),
        (f'"login": "{PHRASE}"', "a login value"),
        (f'reviewers=["{PHRASE}"],', "a reviewers=[...] literal"),
    ]:
        hit, _ = fires(line, tmp)
        check(f"fires on {label}", hit)

    # --- must NOT fire: the prose the corpus should keep ---
    for line, label in [
        (f"request `{PHRASE}` as reviewer (`request-pr-review`)",
         "a backticked role reference"),
        (f"Apply the same standards {PHRASE}'s priorities imply.",
         "a possessive role reference"),
        (f"If `Author` is `{PHRASE}` (self-authored): `Ready for self-merge`.",
         "a role reference in a conditional"),
        (f"| [#101](url) | `{PHRASE}` | Ready |",
         "a role reference in a table cell"),
        ("owner: <owner>", "an angle-bracket placeholder"),
        ('reviewers=["<reviewer>"],', "a placeholder in a reviewers literal"),
        ('-f "reviewers[]=<reviewer>"', "a placeholder in a reviewers[] field"),
    ]:
        hit, _ = fires(line, tmp)
        check(f"does NOT fire on {label}", not hit)

    # --- the population is reported, so a zero has a denominator ---
    f = tmp / "clean.md"
    f.write_text("nothing here\n", encoding="utf-8")
    findings, examined = gate.scan([f])
    check("reports how many files it examined", examined == 1 and not findings)

    # --- a file type outside the set is skipped rather than silently scanned ---
    f2 = tmp / "thing.txt"
    f2.write_text(f"owner: {PHRASE}\n", encoding="utf-8")
    findings, examined = gate.scan([f2])
    check("a .txt file is outside the scanned set", examined == 0 and not findings)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
