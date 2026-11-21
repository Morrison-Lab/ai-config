#!/usr/bin/env python3
"""Tests for hooks/no-stale-pin-macro-excuse.py; optional arg: hook path."""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-stale-pin-macro-excuse.py")
POST = "mcp__hearthbot__post_message"
BS = chr(92)
EXCUSE = f"I kept {BS}tp{{X}} {BS}vx raw because the repo's latex-macros pin predates {BS}ccprod."


def run(tool, tool_input, env=None):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
                       capture_output=True, text=True, timeout=20, env={**os.environ, **(env or {})})
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)["hookSpecificOutput"] if p.stdout.strip() else {}
    return out.get("permissionDecision") == "deny"


CASES = [
    ("the excuse in a reply denies", POST, {"text": EXCUSE}, True, {}),
    ("plain wording denies", POST,
     {"text": "The pinned macros copy does not have the macro yet, so the expression stays as it is."}, True, {}),
    ("a PR body denies", "mcp__github__create_pull_request",
     {"title": "t", "body": "Left the raw form for now: the submodule is missing the macro."}, True, {}),
    ("a gh pr body denies", "Bash",
     {"command": f"gh pr create --title t --body {json.dumps(EXCUSE)}"}, True, {}),
    ("a commit message denies", "Bash",
     {"command": "git commit -m 'Keep raw transpose until the macros pin includes it; pin lacks the macro'"},
     True, {}),
    ("a bumped pin passes", POST,
     {"text": f"The pin lacked {BS}ccprod, so I bumped it and used the macro instead."}, False, {}),
    ("the rule itself passes", POST,
     {"text": "Never skip a macro because the pinned copy lacks it."}, False, {}),
    ("a pin note without a skip passes", POST,
     {"text": "The latex-macros pin predates macros#317."}, False, {}),
    ("a macro note without the pin passes", POST,
     {"text": "The macro is missing, so I opened a macros PR."}, False, {}),
    ("an unrelated tool passes", "Read", {"file_path": "x"}, False, {}),
    ("an unrelated Bash passes", "Bash", {"command": "echo hi"}, False, {}),
    ("the override passes", POST, {"text": EXCUSE}, False, {"env": {"ALLOW_STALE_PIN_MACRO": "1"}}),
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
