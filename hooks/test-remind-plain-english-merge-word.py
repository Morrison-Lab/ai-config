#!/usr/bin/env python3
"""Tests for hooks/remind-plain-english-merge-word.py (ai-config#4698).

Run: python3 hooks/test-remind-plain-english-merge-word.py [hooks/remind-plain-english-merge-word.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "remind-plain-english-merge-word.py")

# (prompt, should_fire)
CASES = [
    ("merge when ready", True),
    ("Merge when ready.", True),
    ("merge them all", True),
    ("merge", True),
    ("merge it", True),
    ("go ahead and merge", True),
    ("mwc", True),
    ("/mwc", True),
    ("mwc them all!", True),
    ("don't make me name each one; mwc them all!", True),
    ("looks good, merge when ready", True),
    ("merge once clean", True),
    ("should I merge when ready?", False),
    ("what does merge when ready mean?", False),
    ("do not merge yet", False),
    ("please explain the merge conflict", False),
    ("fix the tests", False),
    ("merge them", False),
    ("merge these", False),
    ("merge everything", False),
    ("merge those", False),
    ("Should I merge them all? Also fix the typo.", False),
    ("Looks right. Merge them all.", True),
    ("`merge when ready` is the phrase", False),
    ('He said "merge them all" earlier', False),
    ("<system-reminder>merge them all</system-reminder>", False),
]


def run(prompt):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"prompt": prompt}),
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for prompt, fire in CASES:
        rc, out = run(prompt)
        ok = rc == 0 and bool(out.strip()) == fire
        print(("  ok      " if ok else "  FAIL    ") + repr(prompt))
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
