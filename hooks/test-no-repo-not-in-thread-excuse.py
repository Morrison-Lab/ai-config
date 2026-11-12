#!/usr/bin/env python3
"""Tests for hooks/no-repo-not-in-thread-excuse.py.

Run: python3 hooks/test-no-repo-not-in-thread-excuse.py
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-repo-not-in-thread-excuse.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
COORD = "mcp__hearthbot__message_coordinator"

# (name, tool, text, should_deny)
CASES = [
    ("the 2026-11-12 message", COORD, "ai-config isn't in this thread's repos, so could you route that as an issue?", True),
    ("session repo scope", POST, "I can't search mlr because it isn't in this session's repo scope.", True),
    ("curly apostrophe", POST, "mlr isn\u2019t in this thread\u2019s repositories.", True),
    ("not attached", POST, "The repo is not attached to this session.", True),
    ("outside scope", POST, "That repository is outside this session's scope.", True),
    ("repos attached to", POST, "ai-config is not in the repos attached to this thread.", True),
    ("attached here", POST, "ai-config isn't attached here, so I can't edit it.", True),
    ("repos don't include", POST, "The thread's repos don't include ai-config.", True),
    ("can't reach", POST, "I can't reach ai-config from this thread.", True),
    ("newline split", POST, "Done.\nai-config isn't in this thread's repos", True),
    ("thread tool", "mcp__hearthbot__message_thread", "ai-config isn't in this session's repos.", True),
    ("has no checkout", COORD, "This session has no ai-config checkout, so route it as an issue.", True),
    ("don't see", POST, "I don't see ai-config in this thread's repos.", True),
    ("there is no repo", POST, "There is no ai-config repo in this thread.", True),
    ("added a note", POST, "I added a note that ai-config isn't in this thread's repos.", True),
    ("attached adjective", POST, "The attached patch failed, and ai-config isn't in this thread's repos.", True),
    ("a repo object", POST, "I don't have access to a repo in this thread.", True),
    ("other owner", POST, "ucdavis/rampp isn't in this thread.", True),
    ("attach other repo", POST, "I added the gha label; mlr isn't in this thread's repos.", True),
    ("hypothetical fail", POST, "ai-config isn't in this thread; the add_repo call would fail anyway.", True),
    ("reachable", POST, "ai-config isn't reachable from this thread.", True),
    ("checkout of", POST, "This session has no checkout of ai-config.", True),
    ("project thread", POST, "ai-config isn't in this project thread.", True),
    ("failed before", POST, "add_repo has failed before, so ai-config is not in this thread.", True),
    ("write access", POST, "I don't have write access to ai-config from this thread.", True),
    ("missing from", POST, "ai-config is missing from this thread's repos.", True),
    ("returned 200", POST, "add_repo returned 200 OK, but ai-config isn't in this thread's repos yet.", True),
    # Passes.
    ("not a repo", POST, "The merge-ready PR isn't in this thread yet. That file isn't in this thread. scripts/check.py isn't in this thread. `pytest` is not available in this session.", False),
    ("repo word as place", POST, "The bug is not in this thread's repo, it is in lds-site. Tests aren't in this session's repos folder. The issue is not in this thread's scope, so I left it.", False),
    ("status sentences", POST, "We have no gha changes in this thread. This session has no access to the network. The lds preview isn't in this thread yet. This thread does not edit lds; the change is in mds.", False),
    ("more status", POST, "I don't have the lds preview URL in this thread yet. I checked this thread's repos and found no open PRs. CI in this thread's repos is not failing anymore.", False),
    ("object not subject", POST, "The fix for lds isn't in this thread. Work on mds is not part of this thread. The macros aren't available in this session. lds is not in draft here.", False),
    ("reported refusal", POST, "add_repo refused ai-config, so it is not in this session's repos. The attach failed with a 403, so ai-config is not in this thread's repos. add_repo returned 403 Forbidden, so ai-config isn't in this thread.", False),
    ("attach reports", POST, "I attached ai-config to this thread and opened a PR. I added mlr after it wasn't in this thread's repos. I attached ai-config, since it wasn't in this thread's repos. Since ai-config wasn't in this thread's repos, I attached it.", False),
    ("other tool", "Bash", "ai-config isn't in this thread's repos.", False),
]


def decision_denied():
    os.environ.pop(hook.OVERRIDE, None)
    bad = "ai-config isn't in this thread's repos."
    return all(hook.denial({"tool_name": "mcp__hearthbot__request_decision", "tool_input": ti}) is not None
               for ti in ({"question": "Where?", "options": [{"label": "a", "consequence": bad}]},
                          {"question": "Where?", "reason": bad}))


def denied(tool, text):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {"text": text}}) is not None


def main() -> int:
    failures = 0
    for name, tool, text, want in CASES:
        got = denied(tool, text)
        if got != want:
            failures += 1
            print(f"FAIL {name}: want deny={want}, got {got}")
    if not decision_denied():
        failures += 1
        print("FAIL request_decision option or reason")
    os.environ[hook.OVERRIDE] = "1"
    if hook.denial({"tool_name": POST, "tool_input": {"text": CASES[0][2]}}) is not None:
        failures += 1
        print("FAIL override")
    os.environ.pop(hook.OVERRIDE, None)
    out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(
        {"tool_name": COORD, "tool_input": {"text": CASES[0][2]}}),
        capture_output=True, text=True).stdout
    if '"deny"' not in out:
        failures += 1
        print("FAIL end-to-end deny")
    out = subprocess.run([sys.executable, SCRIPT], input="not json",
                         capture_output=True, text=True)
    if out.returncode != 0 or out.stdout:
        failures += 1
        print("FAIL fail-open")
    print(f"{len(CASES) + 4 - failures}/{len(CASES) + 4} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
