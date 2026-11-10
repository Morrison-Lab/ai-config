#!/usr/bin/env python3
"""Tests for hooks/no-mwc-ask-for-infra-pr.py (ai-config#5097).

Run: python3 hooks/test-no-mwc-ask-for-infra-pr.py
"""
import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-mwc-ask-for-infra-pr.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny); the fetch is disabled, so only repo-level infra is decided here.
CASES = [
    ("gha PR waiting on mwc", POST, "Needs your mwc: Morrison-Lab/gha#1628 is clean.", True),
    ("short ref macros", POST, "Type mwc to merge macros#349.", True),
    ("ai-config url", POST, "mwc for https://github.com/Morrison-Lab/ai-config/pull/5097 please.", True),
    ("grant for one PR, ask for another", POST, "gha#1628 merges under the infra grant already. mwc needed for macros#99 too.", True),
    ("comma-joined grant and ask", POST, "Needs mwc for macros#99, though gha#1628 merges under the infra grant already.", True),
    ("one grant covers a list", POST, "Both macros#99 and gha#1628 merge under the infra grant, no mwc needed for either.", False),
    ("d-morrison macros", POST, "Needs mwc: d-morrison/macros#12.", True),
    ("grant stated", POST, "gha#1628 merges under the infra grant, no mwc needed.", False),
    ("content repo", POST, "Type mwc to merge lds#2063.", False),
    ("no mwc word", POST, "gha#1628 is clean.", False),
    ("no PR ref", POST, "Type mwc when ready.", False),
    ("other owner", POST, "mwc for someone/gha#1.", False),
    ("unrelated tool", "Bash", "mwc gha#1628", False),
    ("no text", POST, None, False),
]


def run(tool, text, stdin=None):
    payload = {"tool_name": tool, "tool_input": {"text": text} if text is not None else {}}
    env = dict(os.environ, NO_MWC_INFRA_HOOK_DISABLE_FETCH="1")
    p = subprocess.run([sys.executable, HOOK], input=stdin or json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, text, deny in CASES:
        rc, out = run(tool, text)
        ok = rc == 0 and ('"permissionDecision": "deny"' in out) == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    rc, out = run(POST, None, stdin="not json")
    ok = rc == 0 and not out
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
