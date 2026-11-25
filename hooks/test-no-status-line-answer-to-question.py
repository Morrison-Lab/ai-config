#!/usr/bin/env python3
"""Tests for hooks/no-status-line-answer-to-question.py; optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-status-line-answer-to-question.py")
POST = "mcp__hearthbot__post_message"
# The founding wake (Claude app project thread, 2026-11-25), as hearthbot delivers it.
WHY_WAKE = ('<wake reason="mention"><message from="human" id="cmsg_x">'
            "why haven't you merged 2196?</message></wake>")
# The founding reply, verbatim.
BAD = "Running the clean check on gha#2196 now, then merging it under gha's standing grant."
GOOD = "I hadn't looked at it; another thread opened it. Running the clean check on gha#2196 now."


def user(text):
    return {"type": "user", "message": {"content": text}}


def posted(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": POST, "input": {"text": text}}]}}


def run(lines, text, tool=POST, env=None):
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "t.jsonl")
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines) + "\n")
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(
            {"tool_name": tool, "tool_input": {"text": text}, "transcript_path": tp}),
            capture_output=True, text=True, timeout=20, env={**os.environ, **(env or {})})
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else {}
    return out.get("permissionDecision") == "deny"


CASES = [
    ("the founding reply denies", [user(WHY_WAKE)], BAD, True, {}),
    ("an answer first passes", [user(WHY_WAKE)], GOOD, False, {}),
    ("a plain prompt question denies", [user("why haven't you merged 2196?")], BAD, True, {}),
    ("I'll denies", [user("did you push the fix?")], "I'll check the branch and report back.", True, {}),
    ("Let me denies", [user("what broke main?")], "Let me look at the failing run.", True, {}),
    ("a leading tag and bold gerund denies", [user("is gha#2196 merged?")],
     "**Checking** the PR state now.", True, {}),
    ("a question word with no question mark denies", [user("how did that get through review")],
     "Looking at the review history now.", True, {}),
    ("a gerund with an answer word passes", [user(WHY_WAKE)],
     "Nothing merged it because no thread owned it; checking now.", False, {}),
    ("a negation in the first sentence passes", [user("did you push the fix?")],
     "I'll be honest: I did not push it yet.", False, {}),
    ("a non-gerund -ing word passes", [user("what is pending?")],
     "Something in the review job; the check ran out of quota.", False, {}),
    ("a status line after the first sentence passes", [user(WHY_WAKE)],
     "It was never assigned to me.\nRunning the clean check now.", False, {}),
    ("a polite request passes", [user("can you push that?")], "Pushing now.", False, {}),
    ("a please request passes", [user("please rerun the check?")], "Rerunning it now.", False, {}),
    ("a non-question passes", [user("merge 2196")], BAD, False, {}),
    ("a later reply after the first passes", [user(WHY_WAKE), posted(GOOD)], BAD, False, {}),
    ("a later non-question clears it", [user(WHY_WAKE), user("merge it")], BAD, False, {}),
    ("a quoted question passes", [user("> why haven't you merged 2196?\n\nmerge it")], BAD, False, {}),
    ("a question in a code span passes", [user("run `why?` then merge")], BAD, False, {}),
    ("a wake with no human message passes",
     [user('<wake reason="ci"><message from="coordinator">why did CI fail?</message></wake>')],
     BAD, False, {}),
    ("another tool passes", [user(WHY_WAKE)], BAD, False, {"tool": "mcp__hearthbot__react"}),
    ("the override passes", [user(WHY_WAKE)], BAD, False,
     {"env": {"ALLOW_STATUS_FIRST_REPLY": "1"}}),
]


def main():
    failed = 0
    for name, lines, text, want, kw in CASES:
        got = run(lines, text, **kw)
        if got != want:
            failed += 1
            print(f"FAIL: {name}: denied={got}, want {want}")
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, timeout=20)
    if p.returncode != 0 or p.stdout.strip():
        failed += 1
        print("FAIL: bad input must fail open")
    total = len(CASES) + 1
    print(f"{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
