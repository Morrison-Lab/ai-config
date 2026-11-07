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
    ("code-span wording passes", "- Flag `owed` beside a hook.", False),
    ("negated need passes", "- No separate hook is needed.", False),
    ("not yet filed is not a negation", "- The check is not yet filed.", True),
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

# Negative control: the scan covers real files, so a zero cannot be an empty search.
check("covered files are found", len(com.covered_files(com.REPO)) > 0, True)

print(f"\n{len(FAILS)} failure(s)")
sys.exit(1 if FAILS else 0)
