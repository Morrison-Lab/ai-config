#!/usr/bin/env python3
"""Tests for hooks/no-merge-ask-in-post-message.py (ai-config#5155).

Run: python3 hooks/test-no-merge-ask-in-post-message.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-merge-ask-in-post-message.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
DECIDE = "mcp__hearthbot__request_decision"


def transcript(thread: bool) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write("You are a Thread Session.\n" if thread else "You are the coordinator.\n")
    f.close()
    return f.name


THREAD = transcript(True)
OTHER = transcript(False)


def denied(text, tool=POST, tpath=THREAD, **extra):
    os.environ.pop(hook.OVERRIDE, None)
    tool_input = {"text": text} if tool != DECIDE else extra
    return hook.denial({"tool_name": tool, "tool_input": tool_input,
                        "transcript_path": tpath}) is not None


# (name, text, should_deny)
CASES = [
    ("say mwc", "Say `mwc` and I will merge it.", True),
    ("need mwc", "I need your mwc for PR 12.", True),
    ("awaiting mwc", "Awaiting Ezra's mwc.", True),
    ("ask for mwc", "I will ask Ezra for mwc.", True),
    ("can I merge", "Can I merge #12?", True),
    ("okay to merge", "Is it okay to merge?", True),
    ("permission to merge", "Need permission to merge this.", True),
    ("please merge", "Please merge the PR.", True),
    ("waiting on your merge", "Waiting on your merge.", True),
    ("waiting for you to merge", "Waiting for you to merge it.", True),
    ("coordinator has it", "The coordinator has it on the merge line.", False),
    ("merge main", "I merged main into the branch.", False),
    ("ready to merge state", "The head is clean and ready to merge.", False),
    ("past tense report", "I sent the final head to the coordinator.", False),
    ("mwc noun, no ask", "mwc is the merge word.", False),
    ("passive ask", "Your mwc is needed for this PR.", True),
    ("passive ask short", "mwc is needed here.", True),
    ("passive ask vocative", "Ezra, mwc is needed for #12.", True),
    ("passive required", "An mwc is required.", True),
    ("no mwc needed denied too (reword)", "No mwc needed here.", True),
    ("hedge does not shield", "Not sure, but can I merge this one?", True),
    ("hedge no rush", "No rush, but please merge when you can.", True),
    ("hedge n't", "I'm not confident, but want me to merge this?", True),
    ("connector does not shield", "I don't like this and want me to merge this?", True),
    ("connector so", "There is no issue so please merge when ready.", True),
    ("connector though", "No concerns though want me to merge this?", True),
    ("negated mention is denied too (reword)", "I am not asking for mwc.", True),
    ("empty", "", False),
]


def main() -> int:
    bad = 0

    def check(name, ok):
        nonlocal bad
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)

    for name, text, want in CASES:
        check(name, denied(text) == want)
    check("coordinator session never blocked",
          not denied("Say `mwc` now.", tpath=OTHER))
    check("missing transcript fails open",
          not denied("Say `mwc` now.", tpath="/nonexistent/x.jsonl"))
    check("other tool ignored", not denied("Say `mwc` now.", tool="mcp__github__add_issue_comment"))
    check("request_decision question denied",
          denied("", tool=DECIDE, question="Can I merge #12?", options=[]))
    check("request_decision option denied",
          denied("", tool=DECIDE, question="Next?",
                 options=[{"label": "Wait", "consequence": "Waiting for your mwc."}]))
    check("request_decision clean allowed",
          not denied("", tool=DECIDE, question="Pick a name?",
                     options=[{"label": "A", "consequence": "Use A."}]))
    os.environ[hook.OVERRIDE] = "1"
    check("override clears it",
          hook.denial({"tool_name": POST, "tool_input": {"text": "Say mwc."},
                       "transcript_path": THREAD}) is None)
    os.environ.pop(hook.OVERRIDE)
    r = subprocess.run([sys.executable, SCRIPT], input="not json",
                       capture_output=True, text=True)
    check("bad stdin exits 0 silently", r.returncode == 0 and not r.stdout)
    payload = json.dumps({"tool_name": POST, "tool_input": {"text": "Say `mwc`."},
                          "transcript_path": THREAD})
    r = subprocess.run([sys.executable, SCRIPT], input=payload,
                       capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != hook.OVERRIDE})
    check("subprocess denies", '"permissionDecision": "deny"' in r.stdout)
    for p in (THREAD, OTHER):
        os.unlink(p)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
