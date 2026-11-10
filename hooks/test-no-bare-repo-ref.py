#!/usr/bin/env python3
"""Tests for hooks/no-bare-repo-ref.py (ai-config#5164).

Run: python3 hooks/test-no-bare-repo-ref.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location("hook", os.path.join(HERE, "no-bare-repo-ref.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"

# (name, text, should_deny)
CASES = [
    ("bare repo#N", "psw#542 is on the line.", True),
    ("bare owner/repo#N", "See Morrison-Lab/psw#542 now.", True),
    ("bare mid-sentence", "Merged lds#2243 and then pds#386.", True),
    ("linked", "[psw#542](https://github.com/Morrison-Lab/psw/pull/542) is on the line.", False),
    ("code span", "The token `psw#542` is a mention.", False),
    ("fenced", "```\npsw#542\n```", False),
    ("inside a URL", "https://github.com/Morrison-Lab/psw/issues/542", False),
    ("one linked one bare", "[psw#542](https://github.com/Morrison-Lab/psw/pull/542) and mcs#113", True),
    ("bare number only", "Fixed #542 yesterday.", False),
    ("thread link", "[thread](#cmsg_014QLd5)", False),
    ("empty", "", False),
]


def denied(text, tool=POST):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {"text": text}}) is not None


def main() -> int:
    wrong = 0
    for name, text, want in CASES:
        got = denied(text)
        ok = got == want
        wrong += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}   {name}")
    if denied("psw#542", tool="Bash"):
        wrong += 1
        print("  FAIL   non-reply tool is ignored")
    os.environ[hook.OVERRIDE] = "1"
    if hook.denial({"tool_name": POST, "tool_input": {"text": "psw#542"}}):
        wrong += 1
        print("  FAIL   override allows")
    os.environ.pop(hook.OVERRIDE)
    if hook.denial("not a dict") is not None:
        wrong += 1
        print("  FAIL   malformed payload fails open")
    print(f"\n{'all passed' if not wrong else 'FAILED'}: {wrong} wrong")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
