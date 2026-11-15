#!/usr/bin/env python3
"""Tests for hooks/no-unfenced-typed-line-ask.py (ai-config#5667).

Run: python3 hooks/test-no-unfenced-typed-line-ask.py [hooks/no-unfenced-typed-line-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-unfenced-typed-line-ask.py")
POST = "mcp__hearthbot__post_message"
EDIT = "mcp__hearthbot__edit_message"

FENCE = "```"

CASES = [
    ("mwc line in inline code", POST,
     {"text": "lds#2508 is clean. Type `mwc lds 2508 abc1234` in the runner thread."}, True),
    ("approve push line in quotes", POST,
     {"text": "The push was refused. Please type \"approve push of claude/x to Morrison-Lab/lds with ALLOW_LARGE_PR=1\" here."}, True),
    ("known line on its own plain line after an ask", POST,
     {"text": "Type this line in this thread:\napprove editing hooks/hooks.json in Morrison-Lab/ai-config to add the hook"}, True),
    ("retry line inline", EDIT, {"text": "To clear the guard, type `retry lds#2508`."}, True),
    ("merge anyway inline", POST, {"text": "If you want it regardless, reply with `merge anyway 2508`."}, True),
    ("generic typed line inline", POST,
     {"text": "Please type `go ahead with the Canvas upload` so the classifier sees it."}, True),
    ("mwc with bare PR number", POST, {"text": "Type `mwc 548` unless you disagree."}, True),
    ("fenced mwc line", POST,
     {"text": "lds#2508 is clean. Type this in the runner thread:\n\n" + FENCE + "\nmwc lds 2508 abc1234\n" + FENCE + "\n"}, False),
    ("fenced plus inline echo of the same line", POST,
     {"text": "Type `mwc lds 2508 abc1234` in the runner thread:\n\n" + FENCE + "text\nmwc lds 2508 abc1234\n" + FENCE}, False),
    ("plain mention runs past the fenced line", POST,
     {"text": "Type approve push of claude/x to Morrison-Lab/lds in this thread:\n" + FENCE
      + "\napprove push of claude/x to Morrison-Lab/lds\n" + FENCE}, False),
    ("tilde fence", POST, {"text": "Type this:\n~~~\nretry lds#2508\n~~~"}, False),
    ("fenced line but a second unfenced line", POST,
     {"text": "Type this:\n" + FENCE + "\nretry lds#2508\n" + FENCE + "\nThen type `mwc lds 2508 abc1234`."}, True),
    ("negated ask", POST, {"text": "No need to type `mwc` for this one: it merges under the infra grant."}, False),
    ("report of a typed line", POST,
     {"text": "You typed mwc lds 2508 abc1234 at 01:38Z, so the runner merged it."}, False),
    ("prose about bare mwc, no ask", POST, {"text": "A bare `mwc` covers every ready PR in the thread."}, False),
    ("status report", POST, {"text": "Pushed abc1234 and opened ai-config#5667. CI is running."}, False),
    ("known line, no ask at all", POST, {"text": "The runner merged lds#2508 on mwc lds 2508 abc1234."}, False),
    ("known line in a status sentence, ask elsewhere", POST,
     {"text": "Please type your answer in the quiz. mwc lds 2508 abc1234 is ready."}, False),
    ("fenced line plus a different status mention", POST,
     {"text": "Type this:\n" + FENCE + "\nmwc lds 2508 abc1234\n" + FENCE + "\nand mwc lds 2509 def5678 is queued."}, False),
    ("fragment in a fence covers nothing", POST,
     {"text": "Type `mwc lds 2508 abc1234`:\n" + FENCE + "\nmwc\n" + FENCE}, True),
    ("imperative say", POST, {"text": "Say mwc lds 2508 abc1234 to merge."}, True),
    ("imperative reply without with", POST, {"text": "Reply `approve editing hooks/hooks.json` here."}, True),
    ("curly-quoted line", POST, {"text": "Type \u201cgo ahead with the upload\u201d here."}, True),
    ("docs say is not an ask", POST, {"text": "The docs say `retry` is safe."}, False),
    # Runner reviews of daba5f9, 60d72bf and c1ddb9e (ai-config#5668): ordinary replies that ask for nothing to be typed.
    ("noun type with inline code", POST, {"text": "The return type of `getUser()` is `User`."}, False),
    ("reply with thoughts", POST, {"text": "Please reply with your thoughts on `module_a`."}, False),
    ("paste a log", POST, {"text": "Please paste the error log from `debug.log`."}, False),
    ("other inline token beside a fenced line", POST,
     {"text": "Please type the following command to update `package.json`:\n" + FENCE
      + "\napprove editing package.json\n" + FENCE}, False),
    ("four-backtick fence", POST, {"text": "Type this:\n````\nmwc lds 2508 abc1234\n````"}, False),
    ("trailing comma after a plain line", POST,
     {"text": "Please type approve push of claude/x to repo, then wait:\n" + FENCE
      + "\napprove push of claude/x to repo\n" + FENCE}, False),
    ("bare mwc ask", POST, {"text": "Please type mwc in the thread."}, True),
    ("bare retry ask", POST, {"text": "Please type retry #5668."}, True),
    ("noun type after and, mwc in prose", POST,
     {"text": "The mwc grant covers it, and type hints in `a.py` are fine."}, False),
    ("sentence-initial noun Type", POST, {"text": "Type `int` is expected by the validator."}, False),
    ("sentence-initial noun Type, other verb", POST, {"text": "Type `factor` encodes categories in R."}, False),
    ("could you type", POST, {"text": "Could you type `mwc lds 2508 abc1234` in the runner thread?"}, True),
    ("infinitive to send", POST, {"text": "We use a webhook to send `push` events to Slack."}, False),
    ("infinitive to reply with", POST, {"text": "Configured to reply with `pong` on ping."}, False),
    ("then enter a directory", POST, {"text": "Then enter `chapters/` and run the checker."}, False),
    ("inline bare mwc covered by a fenced full line", POST,
     {"text": "Please type `mwc` to merge:\n" + FENCE + "\nmwc lds 2508 abc1234\n" + FENCE}, False),
    ("merge anyway with repo#n", POST, {"text": "Please type merge anyway lds#2508 to force it."}, True),
    ("merge anyway with repo and n", POST, {"text": "Please type merge anyway lds 2508 to force it."}, True),
    ("bare mwc fenced", POST, {"text": "Please type this:\n" + FENCE + "\nmwc\n" + FENCE}, False),
    ("unrelated tool", "Bash", {"command": "echo 'Type `mwc lds 2508 abc1234`'"}, False),
    ("decision card not covered", "mcp__hearthbot__request_decision",
     {"question": "Type `mwc lds 2508`?", "options": []}, False),
]


def run(tool, tool_input, env=None):
    payload = {"tool_name": tool, "tool_input": tool_input}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, tool_input, deny in CASES:
        rc, out = run(tool, tool_input)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    env = dict(os.environ, ALLOW_UNFENCED_TYPED_LINE="1")
    rc, out = run(POST, {"text": "Type `mwc lds 2508 abc1234`."}, env)
    ok = rc == 0 and not out
    print(("  ok      " if ok else "  FAIL    ") + "override env var allows")
    fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 2
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
