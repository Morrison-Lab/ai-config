#!/usr/bin/env python3
"""Tests for hooks/no-cai-reply-without-routing.py; optional arg: hook path."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-cai-reply-without-routing.py")
POST = "mcp__hearthbot__post_message"
# The founding wake (mlg thread, 2026-11-24), as a hearthbot wake reaches the transcript.
CAI_WAKE = ('<wake reason="mention"><message from="human" id="cmsg_x">&lt;!-- reply 1 --&gt;\n'
            "&gt; LaTeX is too old for the exam template.\n\n"
            "cai: never make excuses like this; install the software you need</message></wake>")
BAD = "On it. I'm installing a current TeX Live from CTAN now, then I'll render both student PDFs."
GOOD = "Installing TeX now, and adding a deny hook to ai-config for this rule; its PR comes this turn."


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
    ("the founding reply denies", [user(CAI_WAKE)], BAD, True, {}),
    ("a reply naming the hook passes", [user(CAI_WAKE)], GOOD, False, {}),
    ("a Mechanism line passes", [user(CAI_WAKE)],
     "Installing TeX now.\nMechanism: https://github.com/Morrison-Lab/ai-config/pull/1", False, {}),
    ("a later reply after a routed one passes", [user(CAI_WAKE), posted(GOOD)], BAD, False, {}),
    ("a second unrouted reply still denies", [user(CAI_WAKE), posted(BAD)], BAD, True, {}),
    ("a plain user message passes", [user("render both PDFs please")], BAD, False, {}),
    ("a later non-cai message clears it", [user(CAI_WAKE), user("yes what?")], BAD, False, {}),
    ("a quoted cai passes", [user("> cai: something someone said\n\nwhat do you think?")], BAD, False, {}),
    ("ca: counts too", [user("ca: always link the rendered page")], BAD, True, {}),
    ("another tool passes", [user(CAI_WAKE)], BAD, False, {"tool": "mcp__hearthbot__react"}),
    ("the override passes", [user(CAI_WAKE)], BAD, False,
     {"env": {"ALLOW_CAI_REPLY_WITHOUT_ROUTING": "1"}}),
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
