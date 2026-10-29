#!/usr/bin/env python3
"""Tests for hooks/warn-pr-without-thread-link.py (ai-config#4565).

Run: python3 hooks/test-warn-pr-without-thread-link.py [hooks/warn-pr-without-thread-link.py]
"""
import json
import os
import re
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-pr-without-thread-link.py")
REPLY = "mcp__hearthbot__reply"
POST = "mcp__hearthbot__post_message"
A = "https://github.com/Morrison-Lab/psw/pull/201"
B = "https://github.com/Morrison-Lab/psw/pull/202"
C = "https://github.com/Morrison-Lab/lds/pull/7"

# (name, tool, text, expected PRs named in the warning; None = silent)
CASES = [
    ("link, no thread", POST, f"[psw#201]({A}) is green.", ["Morrison-Lab/psw#201"]),
    ("bare URL, no thread", POST, f"Opened {A} today.", ["Morrison-Lab/psw#201"]),
    ("reply tool", REPLY, f"See {A}.", ["Morrison-Lab/psw#201"]),
    ("update_message", "mcp__hearthbot__update_message", f"See {A}.",
     ["Morrison-Lab/psw#201"]),
    ("in-app thread link", POST,
     f"[psw#201]({A}) is owned by [Drive down the backlog](#cmsg_01PWzn3MFaLU13).", None),
    ("thread URL outside the app", POST,
     f"[PR]({A}) and [thread](https://claude.ai/code/project/chan_x?thread=cmsg_01Pz).", None),
    ("thread anchor without parens is not a link", POST,
     f"{A} see #cmsg_01PWzn", ["Morrison-Lab/psw#201"]),
    ("no PR", POST, "Nothing to report.", None),
    ("issue URL is not a PR", POST, "https://github.com/o/r/issues/9 is open.", None),
    ("bare #N is out of scope", POST, "Fixed in #4224.", None),
    ("inline code", POST, f"The URL form is `{A}`.", None),
    ("fenced code", POST, f"```\n{A}\n```\nDone.", None),
    ("tilde fence", POST, f"~~~\n{A}\n~~~\nDone.", None),
    ("unclosed fence", POST, f"```\n{A}\nmore", None),
    ("other tool", "Bash", f"echo {A}", None),
    ("one thread link per list item", POST,
     f"- [a]({A}) -> [t1](#cmsg_01A)\n- [b]({B}) -> [t2](#cmsg_01B)", None),
    ("second item missing its thread", POST,
     f"- [a]({A}) -> [t1](#cmsg_01A)\n- [b]({B})", ["Morrison-Lab/psw#202"]),
    ("one link at the bottom covers only its own item", POST,
     f"- {A}\n- {B}\n- {C} -> [t](#cmsg_01C)",
     ["Morrison-Lab/psw#201", "Morrison-Lab/psw#202"]),
    ("paragraph with thread link in a later sentence", POST,
     f"I opened {A}. It belongs to [the backlog thread](#cmsg_01D).", None),
    ("separate paragraphs", POST,
     f"I opened {A}.\n\nThe thread is [here](#cmsg_01D).", ["Morrison-Lab/psw#201"]),
    ("numbered list", POST, f"1. {A}\n2. {B} [t](#cmsg_01E)", ["Morrison-Lab/psw#201"]),
    ("nested item's thread link covers the parent", POST,
     f"- {A} is the PR\n  - see [thread](#cmsg_01A)", None),
    ("nested numbered item", POST, f"1. {A}\n   1. [t](#cmsg_01A)", None),
    ("CRLF paragraphs", POST,
     f"I opened {A}.\r\n\r\nThe thread is [here](#cmsg_01D).", ["Morrison-Lab/psw#201"]),
    ("CRLF list items", POST, f"- {A}\r\n- {B} [t](#cmsg_01E)", ["Morrison-Lab/psw#201"]),
    ("code span cannot merge two items", POST,
     f"- {A} `code\n- more` [t](#cmsg_01A)", ["Morrison-Lab/psw#201"]),
    ("http scheme", POST, "See http://github.com/o/r/pull/7 now.", ["o/r#7"]),
    ("schemeless is not a mention", POST, "github.com/o/r/pull/7 is green.", None),
    ("ampersand thread param", POST,
     f"{A} [thread](https://claude.ai/code/project/c?x=1&thread=cmsg_01Pz)", None),
    ("PR URL with fragment", POST, f"{A}#issuecomment-1 is open.", ["Morrison-Lab/psw#201"]),
    ("PR URL with query", POST, f"{A}?x=1 is open.", ["Morrison-Lab/psw#201"]),
    ("same PR in two units, one unlinked", POST,
     f"- {A} [t](#cmsg_01A)\n- {A}", ["Morrison-Lab/psw#201"]),
    ("thread link in the same list item", POST,
     f"- done: {A}, thread [t](#cmsg_01A)", None),
    ("duplicate PR named once", POST, f"{A} and again {A}.", ["Morrison-Lab/psw#201"]),
    ("two repos", POST, f"{A} and {C}.",
     ["Morrison-Lab/psw#201", "Morrison-Lab/lds#7"]),
]


def run(tool, text):
    event = {"tool_name": tool, "tool_input": {"text": text}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def thread_note_cases():
    """In a thread session the note says never to link the thread itself (ai-config#4843)."""
    import tempfile
    url = "https://github.com/Morrison-Lab/lds/pull/1"
    failures = 0
    for log, want in (("You are a Thread Session. <thread ts=\"cmsg_01\">", "never link this thread"),
                      ("<wake>coordinator</wake>", "without linking the project thread")):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(log)
        event = {"tool_name": POST, "tool_input": {"text": f"See {url}."},
                 "transcript_path": f.name}
        proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                              capture_output=True, text=True)
        os.unlink(f.name)
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        if want not in ctx:
            failures += 1
            print(f"FAIL thread note for {log[:20]!r}: {ctx[:80]!r}")
    return failures


def main():
    failures = thread_note_cases()
    for name, tool, text, expected in CASES:
        code, out = run(tool, text)
        ok = code == 0
        if expected is None:
            ok = ok and out == ""
        else:
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
            named = re.findall(r"`([^`]+)`", ctx.split(" without linking", 1)[0])
            ok = ok and named == expected
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": REPLY, "tool_input": []}),
                json.dumps({"tool_name": REPLY, "tool_input": {"text": 5}})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    many = "\n".join(f"- https://github.com/o/r/pull/{n}" for n in range(1, 9))
    _, out = run(POST, many)
    if "3 more" not in out or "o/r#6" in out:
        failures += 1
        print("FAIL overflow count")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
