"""Test the remind-treat-wording-as-draft hook.

Run:  python3 hooks/test-remind-treat-wording-as-draft.py hooks/remind-treat-wording-as-draft.py
"""
import json
import os
import subprocess
import sys

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]
if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")


def run(prompt=None, raw=None):
    stdin = raw if raw is not None else json.dumps({"prompt": prompt})
    p = subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    if '"decision"' in p.stdout or "block" in p.stdout.lower():
        sys.exit(f"FATAL: block-shaped output\n{p.stdout}")
    return "REMIND" if p.stdout.strip() else "silent"


REMIND = [
    "Tell the thread something like: no, that is not possible here.",
    "Reply with wording along the lines of 'we cannot do that'.",
    "Add a check for foo.py or similar so this does not recur.",
    "Use a hook, e.g. a UserPromptSubmit one, to enforce this rule.",
    "Maybe we should move the helper into the shared package first.",
    "The cap should be roughly ten files per pull request overall.",
]
SILENT = [
    "Please fix the failing test in foo.py and rerun the suite.",
    "ok maybe",
    "Here is the text:\n```\nsomething like this, e.g. that\n```\nplease summarize it now",
    "> something like this, or similar\nPlease summarize the quote above for me",
    "Explain what `something like` means in this changelog entry please.",
    "<system-reminder>maybe something like this, e.g. that or similar</system-reminder> run the tests again",
]
wrong = 0
for p in REMIND:
    v = run(p)
    wrong += v != "REMIND"
    print(f"  {v:<7} should remind: {p[:60]}")
for p in SILENT:
    v = run(p)
    wrong += v != "silent"
    print(f"  {v:<7} should be silent: {p[:60]!r}")
for desc, raw in [("empty stdin", ""), ("non-JSON", "not json"), ("list payload", "[1, 2]"),
                  ("non-string prompt", json.dumps({"prompt": 5}))]:
    v = run(raw=raw)
    wrong += v != "silent"
    print(f"  {v:<7} fails open and silent: {desc}")
print("FAIL" if wrong else "ok")
sys.exit(1 if wrong else 0)
