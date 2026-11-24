#!/usr/bin/env python3
"""Tests for hooks/no-unfixed-preexisting-failure.py.

Run: python3 hooks/test-no-unfixed-preexisting-failure.py [hooks/no-unfixed-preexisting-failure.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-unfixed-preexisting-failure.py")
POST = "mcp__hearthbot__post_message"
BODY = "mcp__github__update_pull_request"
COMMENT = "mcp__github__add_issue_comment"

# (name, tool, field, text, should_deny)
CASES = [
    ("psw#703 shape", BODY, "body",
     "`lint-changed-files` fails because the runner cannot install curl. This PR changes no R code. "
     "See [job 1](https://github.com/o/r/actions/runs/1/job/2).", True),
    ("pre-existing note", POST, "text", "The lint check is red, but that failure is pre-existing.", True),
    ("not caused by this PR", COMMENT, "body", "The spellcheck job fails; it is not caused by this PR.", True),
    ("fails on main too", POST, "text", "lint-changed-files also fails on main, so it is not ours.", True),
    ("not this PR's", POST, "text", "That red check is not this PR's.", True),
    ("job link is not a fix", POST, "text",
     "The build error is pre-existing ([run](https://github.com/o/r/actions/runs/9)).", True),
    ("names the fix PR", POST, "text", "The lint failure is pre-existing; psw#707 fixes it and I merged main in.", False),
    ("links an issue", BODY, "body",
     "The check fails on main too; filed [o/r#12](https://github.com/o/r/issues/12) for it.", False),
    ("merged main in", POST, "text", "The curl lint failure was pre-existing, so I merged `main` into the branch.", False),
    ("pull link", COMMENT, "body",
     "Red check is not caused by this PR; fixed in https://github.com/o/r/pull/44.", False),
    ("no failure word", POST, "text", "The pre-existing paragraph stays as it was.", False),
    ("quoted", POST, "text", 'The hook denies text like "this failure is pre-existing".', False),
    ("code span", BODY, "body", "Matches `pre-existing` failures in replies.", False),
    ("blockquote", POST, "text", "> lint fails on main too\nThat was the old note.", False),
    ("fix in another paragraph does not count", POST, "text",
     "The lint failure is pre-existing.\n\nUnrelated: #5 merged.", True),
    ("issue body", "mcp__github__issue_write", "body", "The lint check fails; it is pre-existing.", True),
    ("unrelated tool", "mcp__github__get_file_contents", "path", "pre-existing failure", False),
]


def run(tool, field, text):
    payload = {"tool_name": tool, "tool_input": {field: text}}
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=10).stdout
    return '"deny"' in out


def main() -> int:
    bad = 0
    for name, tool, field, text, want in CASES:
        got = run(tool, field, text)
        if got != want:
            bad += 1
            print(f"FAIL {name}: want deny={want}, got {got}")
    for raw in ("", "not json", "[]"):
        out = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True,
                             text=True, timeout=10)
        if out.returncode or out.stdout.strip():
            bad += 1
            print(f"FAIL fail-open on {raw!r}")
    print(f"{len(CASES) + 3 - bad} of {len(CASES) + 3} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
