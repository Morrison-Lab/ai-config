#!/usr/bin/env python3
"""Tests for scripts/check-owed-mechanism.py (ai-config#5049).

Run: python3 scripts/test_check_owed_mechanism.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("com", HERE / "check-owed-mechanism.py")
com = importlib.util.module_from_spec(spec)
spec.loader.exec_module(com)

FAILS = []


def check(name, got, want):
    ok = got == want
    print(("  ok      " if ok else "  FAIL    ") + name)
    if not ok:
        print(f"          got {got!r}, want {want!r}")
        FAILS.append(name)


def flagged(text, changed=None):
    return bool(com.violations(text.splitlines(), changed))


CASES = [
    ("owed hook, no link, is flagged", "- A Stop hook is owed for announced work.", True),
    ("needed check, no link, is flagged", "- A check is needed for stale notes.", True),
    ("TODO hook is flagged", "- TODO: build the hook.", True),
    ("not yet filed check is flagged", "- The lint is not yet filed.", True),
    ("to be built mechanism is flagged", "- The guard is still to be built.", True),
    ("hash issue link passes", "- A Stop hook is owed (#5050).", False),
    ("repo-qualified link passes", "- A Stop hook is owed, Morrison-Lab/ai-config#5050.", False),
    ("issue URL passes", "- A hook is owed: https://github.com/Morrison-Lab/ai-config/issues/5050", False),
    ("link in a continuation line passes", "- A hook is owed\n  and tracked at #5050.", False),
    ("conditional instruction passes", "- When a rule needs a check, file its issue.", False),
    ("quoted wording passes", '- The word "owed" next to a hook is the trigger.', False),
    ("curly-quoted wording passes", "- The word " + chr(0x201C) + "owed" + chr(0x201D) + " beside a hook is the trigger.", False),
    ("code-span wording passes", "- Flag `owed` beside a hook.", False),
    ("negated need passes", "- No separate hook is needed.", False),
    ("not yet filed is not a negation", "- The check is not yet filed.", True),
    ("negated clause then owed clause is flagged", "- The old guard isn't needed, but a new check is owed.", True),
    ("owed clause then negated clause is flagged", "- A check is owed for this, although the old guard isn't needed.", True),
    ("negated need then owed check is flagged", "- No separate hook is needed for this, but a new check is owed for that.", True),
    ("negation with and, then owed, is flagged", "- The hook isn't needed for X, and a separate check is owed for Y.", True),
    ("owed but not filed is flagged", "- A lint is owed for this but not filed.", True),
    ("relative clause negation does not hide the debt", "- A hook that hasn't been written yet is owed.", True),
    ("earlier negated need does not hide the debt", "- A check that wasn't needed earlier is now owed.", True),
    ("a negator directly before the phrase negates it", "- No check owed.", False),
    ("negated owed phrase passes", "- The lint is not owed.", False),
    ("hyphenated not- adjective does not negate", "- A check for not-yet-released features is owed.", True),
    ("hyphenated not-fully adjective does not negate", "- A hook for the not-fully-tested path is owed.", True),
    ("conditional lead-in before the phrase passes", "- When a check is owed, file its issue.", False),
    ("conditional after the phrase is still a debt", "- A check is owed once the review lands.", True),
    ("before as a time word does not exempt", "- A check that wasn't needed before is now owed.", True),
    ("after as a time word does not exempt", "- A hook is owed, as discussed after the incident.", True),
    ("before later in the sentence does not exempt", "- A check is owed for this; it was raised before in review.", True),
    ("after before a new owed clause does not exempt", "- The guard was fine after the last patch, but a new check is owed.", True),
    ("still owed after a while does not exempt", "- A hook is still owed after all this time.", True),
    ("conditional in an earlier clause does not exempt", "- When reviewing PRs, remember that a hook is owed for the Stop check.", True),
    ("conditional in an earlier clause before and does not exempt", "- If you are curious, a lint is owed for the expiry path, and nobody has filed it.", True),
    ("conditional word inside a noun phrase does not exempt", "- A check for when the hook fails is owed.", True),
    ("if inside a noun phrase does not exempt", "- A hook for if the build breaks is owed.", True),
    ("whether inside a noun phrase does not exempt", "- A check for whether the API is live is owed.", True),
    ("once inside a noun phrase does not exempt", "- A check run once a day is owed.", True),
    ("negator inside a noun phrase does not exempt", "- A hook for cases with no fallback is owed.", True),
    ("negator then filler then owed passes", "- There is no separate hook owed.", False),
    ("only negated clauses pass", "- The hook isn't needed, and no check is needed either.", False),
    ("allow marker passes", "- A hook is owed. <!-- owed-mechanism: allow -->", False),
    ("owed with no mechanism word passes", "- The invoice is owed to the vendor.", False),
    ("mechanism word with no debt passes", "- The hook runs on Stop.", False),
]
for name, text, want in CASES:
    check(name, flagged(text), want)

# Diff mode: only a unit holding a changed line is checked.
two = "- A hook is owed.\n\n- A check is needed."
check("unchanged unit is not reflagged", [n for n, _ in com.violations(two.splitlines(), {3})], [3])
check("changed first unit is flagged", [n for n, _ in com.violations(two.splitlines(), {1})], [1])
check("no changed lines flags nothing", com.violations(two.splitlines(), set()), [])

# A table row is its own unit: adding a row must not reflag an older row.
table = ("| Hook | Rule |\n|---|---|\n"
         "| a.py | Arm a timer for owed actions; ship the hook now. |\n"
         "| b.py | Blocks a parked reply. |")
check("added table row does not reflag an older row", com.violations(table.splitlines(), {4}), [])
check("changed table row is still checked", [n for n, _ in com.violations(table.splitlines(), {3})], [3])
after = "| Hook | Rule |\n|---|---|\n| a.py | Tracked in #12. |\nA hook is owed for b.py."
check("a plain line after a row is its own unit",
      [n for n, _ in com.violations(after.splitlines(), {4})], [4])

# Negative control: the scan covers real files, so a zero cannot be an empty search.
check("covered files are found", len(com.covered_files(com.REPO)) > 0, True)

print(f"\n{len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)
