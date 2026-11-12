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
    ("one of", POST, "ai-config isn't one of this thread's repos.", True),
    ("session repo scope", POST, "I can't search mlr because it isn't in this session's repo scope.", True),
    ("curly apostrophe", POST, "mlr isn\u2019t in this thread\u2019s repositories.", True),
    ("not attached", POST, "The repo is not attached to this session.", True),
    ("outside scope", POST, "That repository is outside this session's scope.", True),
    ("not available in", POST, "psw is not available in this thread's repos.", True),
    ("is not part of", POST, "gha is not part of the session's repos, so I stopped.", True),
    ("repos attached to", POST, "ai-config is not in the repos attached to this thread.", True),
    ("my repos", POST, "ai-config isn't in my repos.", True),
    ("don't have X in", POST, "I don't have ai-config in this thread.", True),
    ("attached here", POST, "ai-config isn't attached here, so I can't edit it.", True),
    ("doesn't have access", COORD, "This thread doesn't have access to ai-config.", True),
    ("checked out", POST, "ai-config isn't checked out in this session.", True),
    ("repos don't include", POST, "The thread's repos don't include ai-config.", True),
    ("can't reach", POST, "I can't reach ai-config from this thread.", True),
    ("lab repo name", POST, "mlr isn't in this thread, so I stopped.", True),
    ("unrelated failure word", POST, "The CI failed, and ai-config isn't in this thread's repos.", True),
    ("second sentence", POST, "CI is green. ai-config isn't in this thread's repos.", True),
    ("newline split", POST, "Done.\nai-config isn't in this thread's repos", True),
    ("thread tool", "mcp__hearthbot__message_thread", "ai-config isn't in this session's repos.", True),
    ("isn't added to", POST, "The repo isn't added to this thread, so please file an issue.", True),
    ("has no checkout", COORD, "This session has no ai-config checkout, so route it as an issue.", True),
    ("can't push", POST, "I can't push to ai-config from this session.", True),
    ("hyphenated word", POST, "The merge-ready PR isn't in this thread yet.", False),
    ("tool not installed", POST, "pre-commit isn't installed in this session.", False),
    ("bug in thread's repo", POST, "The bug is not in this thread's repo, it is in lds-site.", False),
    ("repos' lockfile", POST, "The cached build isn't in my repos' lockfile.", False),
    ("don't see", POST, "I don't see ai-config in this thread's repos.", True),
    ("there is no repo", POST, "There is no ai-config repo in this thread.", True),
    ("repos folder", POST, "Tests aren't in this session's repos folder.", False),
    ("has no changes", POST, "We have no gha changes in this thread.", False),
    ("no network access", POST, "This session has no access to the network.", False),
    ("thread scope of", POST, "That change is outside this thread's scope of work.", False),
    ("added a note", POST, "I added a note that ai-config isn't in this thread's repos.", True),
    ("attached adjective", POST, "The attached patch failed, and ai-config isn't in this thread's repos.", True),
    ("a repo object", POST, "I don't have access to a repo in this thread.", True),
    ("file path", POST, "scripts/check.py isn't in this thread.", False),
    # Passes.
    ("tried and refused", POST, "add_repo refused ai-config, so it is not in this session's repos.", False),
    ("attach failed", POST, "The attach failed with a 403, so ai-config is not in this thread's repos.", False),
    ("attached report", POST, "I attached ai-config to this thread and opened a PR.", False),
    ("added after", POST, "I added mlr after it wasn't in this thread's repos.", False),
    ("no repo word", POST, "That file isn't in this thread.", False),
    ("ordinary negation", POST, "The PR is not merged yet, and this thread is waiting.", False),
    ("other tool", "Bash", "ai-config isn't in this thread's repos.", False),
]


def decision_denied():
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": "mcp__hearthbot__request_decision", "tool_input": {
        "question": "File it where?",
        "options": [{"label": "Ask coordinator",
                     "consequence": "ai-config isn't in this thread's repos."}]}}) is not None


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
        print("FAIL request_decision option")
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
