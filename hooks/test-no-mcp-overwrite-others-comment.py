#!/usr/bin/env python3
"""Tests for hooks/no-mcp-overwrite-others-comment.py.

Run: python3 hooks/test-no-mcp-overwrite-others-comment.py
"""
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location(
    "hook", os.path.join(HERE, "no-mcp-overwrite-others-comment.py"))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

TOOL = hook.TOOL
ARGS = {"owner": "o", "repo": "r", "comment_id": 7, "body": "x"}


def payload(tool=TOOL, args=ARGS):
    return {"tool_name": tool, "tool_input": args}


def denied(look, **kw):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial(payload(**kw), look=look) is not None


# (name, lookup result, should_deny)
CASES = [
    ("other login's comment", ("claude[bot]", "d-morrison"), True),
    ("own comment", ("d-morrison", "d-morrison"), False),
    ("login case differs", ("D-Morrison", "d-morrison"), False),
    ("author lookup failed fails open", (None, "d-morrison"), False),
    ("own login lookup failed fails open", ("claude[bot]", None), False),
]


def main() -> int:
    bad = 0
    for name, result, want in CASES:
        ok = denied(lambda *a, r=result: r) == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)

    def check(name, ok):
        nonlocal bad
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)

    other = lambda *a: ("claude[bot]", "d-morrison")  # noqa: E731
    check("other tool ignored", not denied(other, tool="mcp__github__add_issue_comment"))
    check("camelCase id accepted",
          denied(other, args={"owner": "o", "repo": "r", "commentId": 7}))
    check("missing id ignored", not denied(other, args={"owner": "o", "repo": "r"}))
    check("non-dict input ignored", not denied(other, args="x"))
    os.environ[hook.OVERRIDE] = "1"
    check("override clears it", hook.denial(payload(), look=other) is None)
    os.environ.pop(hook.OVERRIDE)
    r = subprocess.run([sys.executable, os.path.join(HERE, "no-mcp-overwrite-others-comment.py")],
                       input="not json", capture_output=True, text=True)
    check("bad stdin exits 0 silently", r.returncode == 0 and not r.stdout)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
