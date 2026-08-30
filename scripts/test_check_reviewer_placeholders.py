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


def fires(line, tmp_path, name="sample.md"):
    f = tmp_path / name
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
        # Quoting is the likeliest real spelling of a two-word value.
        (f'--reviewer "{PHRASE}"', "a QUOTED --reviewer flag"),
        (f"--add-reviewer '{PHRASE}'", "a single-quoted --add-reviewer flag"),
        (f"--reviewer={PHRASE}", "an =-joined --reviewer flag"),
        (f"gh pr create -r {PHRASE}", "a -r reviewer flag"),
        (f'-f reviewers[]="{PHRASE}"', "a quoted reviewers[]= field"),
        (f'"reviewers": ["{PHRASE}"]', "a JSON reviewers array"),
        (f"reviewers:\n  - {PHRASE}", "a YAML reviewers list item"),
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

    # --- a value position WRAPPED ACROSS A LINE BREAK must still fire.
    #     This is verbatim the shape the published workflow.qmd carried, and a
    #     per-line scan could not see it.
    hit, _ = fires(f"escalate to a human reviewer (`gh pr edit <N> --add-reviewer\n{PHRASE}`) rather than looping.", tmp)
    check("fires on a value wrapped across a line break", hit)

    # --- .qmd is scanned: the published site copy is the surface a new user
    #     reads, and it was invisible while SUFFIXES omitted this extension.
    hit, _ = fires(f"--add-reviewer {PHRASE}", tmp, name="page.qmd")
    check("a .qmd file IS scanned", hit)
    hit, _ = fires(f"--add-reviewer {PHRASE}", tmp, name="rule.mdc")
    check("a .mdc file IS scanned", hit)

    # --- the population is reported, so a zero has a denominator ---
    f = tmp / "clean.md"
    f.write_text("nothing here\n", encoding="utf-8")
    findings, examined = gate.scan([f])
    check("reports how many files it examined", examined == 1 and not findings)

    # --- an empty population is exit 2, not a clean pass. A gate that
    #     examined nothing reports clean and is indistinguishable from one
    #     that passed, which the module docstring claims and the git-error
    #     handler alone did not deliver.
    real_tracked = gate.tracked_files
    gate.tracked_files = lambda: []
    try:
        rc = gate.main()
    finally:
        gate.tracked_files = real_tracked
    check("examining zero files exits 2, not 0", rc == 2)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
