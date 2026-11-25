#!/usr/bin/env python3
"""Tests for hooks/no-ask-to-slide-tag.py (ai-config#6052).

Run: python3 hooks/test-no-ask-to-slide-tag.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-ask-to-slide-tag.py")
POST = "mcp__hearthbot__post_message"
COORD = "mcp__hearthbot__message_coordinator"
DECIDE = "mcp__hearthbot__request_decision"

# (name, tool, tool_input, should_deny)
CASES = [
    ("want me to slide", POST, {"text": "gha#2160 merged. Want me to slide v3?"}, True),
    ("type slide v3", POST, {"text": "Type `slide v3` when you are ready."}, True),
    ("needs your go-ahead", POST, {"text": "The v3 slide needs your go-ahead."}, True),
    ("runner thread slides", COORD, {"text": "Merged gha#2160; the runner thread slides v3."}, True),
    ("leave the slide", COORD, {"text": "I am leaving the tag slide to you."}, True),
    ("waiting on Ezra", POST, {"text": "Holding the slide of v3, waiting on Ezra."}, True),
    ("decision card", DECIDE, {"question": "Slide v3 to main now?",
                               "options": [{"label": "Slide v3", "consequence": "If you agree, v3 moves."},
                                           {"label": "Wait", "consequence": "Nothing moves."}]}, True),
    ("shall I dispatch", POST, {"text": "Shall I dispatch slide-major-tag for gha?"}, True),
    ("give the order", POST, {"text": "v3 is ready to slide once you give the order."}, True),
    ("your order", POST, {"text": "The v3 slide waits only for your order."}, True),
    ("when you say", COORD, {"text": "I will slide v3 when you say so."}, True),
    ("done without asking", POST, {"text": "Slid v3 to abc1234 without asking, per the standing rule."}, False),
    ("report", POST, {"text": "Slid v3 from 1111111 to 2222222; it carries gha#2160."}, False),
    ("gate hold", POST, {"text": "Holding the v3 slide until the review on gha#2160 returns clean."}, False),
    ("gate failure", POST, {"text": "The v3 slide failed: a check run on main's tip is cancelled, re-running it."}, False),
    ("ask in another clause", POST, {"text": "The deck needs your approval; slide v3 done."}, False),
    ("card names slide in a label only", DECIDE, {"question": "What next for gha?",
                                                  "options": [{"label": "Slide v3", "consequence": "The tag moves."},
                                                              {"label": "Stop", "consequence": "Nothing moves."}]}, True),
    ("deck slides", POST, {"text": "Want me to add slides to the deck?"}, False),
    ("no slide word", POST, {"text": "Want me to merge gha#2160?"}, False),
    ("other tool", "Bash", {"command": "echo want me to slide v3"}, False),
    ("empty", POST, {}, False),
]


def run(tool, tool_input, stdin=None):
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    p = subprocess.run([sys.executable, HOOK], input=stdin or payload,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout


def denied(stdout):
    if not stdout.strip():
        return False
    out = json.loads(stdout)
    return out["hookSpecificOutput"]["permissionDecision"] == "deny"


def main():
    failures = 0
    for name, tool, tool_input, want in CASES:
        code, stdout = run(tool, tool_input)
        got = denied(stdout)
        if code != 0 or got != want:
            failures += 1
            print(f"FAIL {name}: exit {code}, denied={got}, want {want}")
    code, stdout = run(POST, {}, stdin="not json")
    if code != 0 or stdout.strip():
        failures += 1
        print("FAIL malformed input should fail open")
    print(f"{len(CASES) + 1 - failures}/{len(CASES) + 1} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
