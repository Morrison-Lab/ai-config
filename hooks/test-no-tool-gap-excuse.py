#!/usr/bin/env python3
"""Tests for hooks/no-tool-gap-excuse.py; optional arg: hook path."""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-tool-gap-excuse.py")
POST = "mcp__hearthbot__post_message"
# The founding reply (mlg thread, 2026-11-24).
EXCUSE = ("I couldn't build the PDFs here because this container's LaTeX is too old "
          "for the exam template.")


def run(tool, tool_input, env=None):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
                       capture_output=True, text=True, timeout=20, env={**os.environ, **(env or {})})
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else {}
    return out.get("permissionDecision") == "deny"


CASES = [
    ("the founding excuse in a reply denies", POST, {"text": EXCUSE}, True, {}),
    ("a missing tool in a reply denies", POST,
     {"text": "I haven't rendered the page, and `typos` isn't installed in this session."}, True, {}),
    ("a PR body denies", "mcp__github__create_pull_request",
     {"title": "t", "body": "The PDF could not be built: tinytex is not installed here."}, True, {}),
    ("an issue comment denies", "mcp__github__add_issue_comment",
     {"body": "Skipped the lint because the lintr package is missing."}, True, {}),
    ("a gh pr body denies", "Bash",
     {"command": f"gh pr create --title t --body {json.dumps(EXCUSE)}"}, True, {}),
    ("an outdated version denies", POST,
     {"text": "I couldn't render it, since the Quarto version here is outdated."}, True, {}),
    ("an install in the next sentence passes", POST,
     {"text": "I couldn't build the PDFs because LaTeX was too old. I installed TinyTeX and rebuilt both."},
     False, {}),
    ("a plain result passes", POST, {"text": "Both PDFs build and every page has room to write."}, False, {}),
    ("a missing config key passes", POST,
     {"text": "I couldn't finish the migration because a config key was missing from the YAML file."},
     False, {}),
    ("an unrelated tool passes", "Read", {"file_path": "x"}, False, {}),
    ("an unrelated Bash passes", "Bash", {"command": "echo hi"}, False, {}),
    ("the override passes", POST, {"text": EXCUSE}, False, {"env": {"ALLOW_TOOL_GAP_EXCUSE": "1"}}),
]


def main():
    failed = 0
    for name, tool, tool_input, want, kw in CASES:
        got = run(tool, tool_input, **kw)
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
