#!/usr/bin/env python3
"""Tests for hooks/no-bare-for-now-limit.py (ai-config#5160).

Run: python3 hooks/test-no-bare-for-now-limit.py
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-bare-for-now-limit.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
DECIDE = "mcp__hearthbot__request_decision"

# (name, text, should_deny)
CASES = [
    ("used up for now", "Quota is used up for now.", True),
    ("paused for now", "The runner is paused for now.", True),
    ("unavailable for now", "Review is unavailable for now.", True),
    ("exhausted, later sentence has time", "Quota is exhausted for now. It resets at 00:00 UTC.", True),
    ("pst reset", "Quota is used up for now; back at 4 pm PST.", False),
    ("duration same sentence", "Quota is used up for now, about 2 hours.", False),
    ("reset in sentence", "Quota is used up for now and resets 2026-11-10T00:00Z.", False),
    ("until", "The runner is paused for now until 23:00 UTC.", False),
    ("no limit word", "I will leave that for now.", False),
    ("no for now", "Quota is exhausted.", False),
    ("empty", "", False),
]


def denied(text, tool=POST, **extra):
    os.environ.pop(hook.OVERRIDE, None)
    tool_input = {"text": text} if tool != DECIDE else extra
    return hook.denial({"tool_name": tool, "tool_input": tool_input}) is not None


def main() -> int:
    bad = 0

    def check(name, ok):
        nonlocal bad
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)

    for name, text, want in CASES:
        check(name, denied(text) == want)
    check("other tool ignored", not denied("Quota used up for now.", tool="mcp__github__add_issue_comment"))
    check("request_decision option denied",
          denied("", tool=DECIDE, question="Next?",
                 options=[{"label": "Wait", "consequence": "Runner is paused for now."}]))
    check("request_decision clean allowed",
          not denied("", tool=DECIDE, question="Pick?",
                     options=[{"label": "A", "consequence": "Use A."}]))
    os.environ[hook.OVERRIDE] = "1"
    check("override clears it",
          hook.denial({"tool_name": POST, "tool_input": {"text": "Quota used up for now."}}) is None)
    os.environ.pop(hook.OVERRIDE)
    r = subprocess.run([sys.executable, SCRIPT], input="not json", capture_output=True, text=True)
    check("bad stdin exits 0 silently", r.returncode == 0 and not r.stdout)
    payload = json.dumps({"tool_name": POST, "tool_input": {"text": "Quota used up for now."}})
    r = subprocess.run([sys.executable, SCRIPT], input=payload, capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != hook.OVERRIDE})
    check("subprocess denies", '"permissionDecision": "deny"' in r.stdout)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
