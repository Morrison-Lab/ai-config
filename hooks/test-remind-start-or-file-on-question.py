"""Test the remind-start-or-file-on-question hook.

Run:  python3 hooks/test-remind-start-or-file-on-question.py hooks/remind-start-or-file-on-question.py
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
    "Should we move the helper into the shared package?",
    "how should we handle the stale freeze cache",
    "Is it worth adding a check for this?",
    "What do you think about splitting the page?",
    "Can we make the slide automatic",
    "What's the best way to test this hook?",
]
SILENT = [
    "Please fix the failing test in foo.py and rerun the suite.",
    "Add a reminder hook for this rule and open a PR.",
    "Here is the text:\n```\nshould we do it?\n```\nplease summarize it now",
    "> should we do it?\nSummarize the quote above for me",
    "Explain what `should we` means in this changelog entry.",
    "<system-reminder>how should we do this</system-reminder> run the tests again",
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
