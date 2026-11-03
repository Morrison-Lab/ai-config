#!/usr/bin/env python3
"""Test the prose-relationship guard.

Run: python3 hooks/test-flag-prose-relationship-without-link.py hooks/flag-prose-relationship-without-link.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def human(text="go"):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def call(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def pr(body):
    return call("mcp__github__create_pull_request", title="t", body=body)


def sh(cmd):
    return call("Bash", command=cmd)


LINK = call("mcp__github__sub_issue_write", issue_number=1, sub_issue_id=2)
CASES = [
    ([human(), pr("Blocked by #12")], True, "prose blocked-by with no link blocks"),
    ([human(), pr("Stacked on #12")], True, "stacked on blocks"),
    ([human(), pr("Part of Morrison-Lab/lds#5")], True, "cross-repo part of blocks"),
    ([human(), sh("gh issue create --body 'Depends on #3'")], True, "gh issue create prose blocks"),
    ([human(), pr("Blocked by #12"), sh("gh issue edit 9 --add-blocked-by 12")], False, "later gh flag discharges"),
    ([human(), pr("Part of #5"), sh("gh api -X POST repos/o/r/issues/5/sub_issues -f sub_issue_id=7")], False, "later sub_issues call discharges"),
    ([human(), pr("Blocked by #12"), call("Bash", command="gh api repos/o/r/issues/9/dependencies/blocked_by -f issue_id=1")], False, "later REST dependency call discharges"),
    ([human(), pr("Blocked by #12"), LINK], False, "later sub_issue_write discharges"),
    ([human(), LINK, pr("Blocked by #12")], True, "link BEFORE the prose write does not discharge"),
    ([human(), call("mcp__github__issue_write", method="create", body="Part of #5", parent_issue_number=5)], False, "parent_issue_number in same call passes"),
    ([human(), pr("Closes #12")], False, "closing keyword is not a cue"),
    ([human(), pr("The rule: write `Blocked by #12` as a relationship.")], False, "quoted in a code span passes"),
    ([human(), pr("Fixes the bug.")], False, "no cue passes"),
    ([human(), pr("See #12 for background.")], False, "bare reference passes"),
    ([human(), pr("Blocked by #12"), human("next"), pr("Fixes the bug.")], False, "earlier turn is ignored"),
    ([human(), call("mcp__github__add_issue_comment", body="Blocked by #12")], False, "comment is not an issue/PR body"),
]


def run(events):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(e) for e in events))
        payload = {"transcript_path": path, "session_id": "s", "stop_hook_active": False}
        env = dict(os.environ, TMPDIR=d)
        out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env)
        return '"decision": "block"' in out.stdout


fail = 0
for events, expect, label in CASES:
    got = run(events)
    if got != expect:
        fail += 1
        print(f"FAIL {label}: expected block={expect}, got {got}")
print(f"{len(CASES) - fail}/{len(CASES)} passed")
sys.exit(1 if fail else 0)
