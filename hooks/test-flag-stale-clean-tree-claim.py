#!/usr/bin/env python3
"""Test the flag-stale-clean-tree-claim guard.

Run: python3 hooks/test-flag-stale-clean-tree-claim.py hooks/flag-stale-clean-tree-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def bash_tool(command):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


def ag_cmd(command):
    return {
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "tool_calls": [{"name": "run_command", "args": {"CommandLine": command}}],
    }


def say_claude(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def say_ag(text):
    return {
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "content": text,
    }


CASES = [
    # True positives
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            say_claude("Audit complete.\n\n**Stopping Point**: Clean stopping point"),
        ],
        True,
        "`git checkout <ref> -- <path>` before clean stopping point declaration warns",
    ),
    (
        [
            bash_tool("git restore --source origin/main scripts/"),
            say_claude("Restored scripts. Working tree clean, ready to wrap up."),
        ],
        True,
        "`git restore` before 'working tree clean' warns",
    ),
    (
        [
            bash_tool("git stash pop"),
            say_claude("Stash applied.\n\nNothing to commit, clean stopping point."),
        ],
        True,
        "`git stash pop` before clean stopping point warns",
    ),
    (
        [
            bash_tool("git apply patch.diff"),
            say_claude("Applied patch. Clean working tree."),
        ],
        True,
        "`git apply` before 'clean working tree' warns",
    ),
    (
        [
            bash_tool("git checkout origin/main file.txt"),
            say_claude("Updated file. Clean stop."),
        ],
        True,
        "Positional `git checkout <ref> <file>` before 'clean stop' warns",
    ),
    (
        [
            bash_tool("git cherry-pick -n abc1234"),
            say_claude("Cherry-picked change. No uncommitted changes."),
        ],
        True,
        "`git cherry-pick -n` before 'no uncommitted changes' warns",
    ),
    (
        [
            ag_cmd("git checkout -q origin/main -- website/"),
            say_ag("Sync complete. **Stopping Point**: Clean stopping point."),
        ],
        True,
        "Antigravity transcript format with path checkout warns",
    ),
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            bash_tool("git status"),
            bash_tool("git checkout -q origin/main -- tools/"),
            say_claude("All done. Clean stopping point."),
        ],
        True,
        "Intervening git status does not clear a LATER path-writing command",
    ),

    # True negatives
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            bash_tool("git status"),
            say_claude("Checked status. **Stopping Point**: Clean stopping point."),
        ],
        False,
        "`git status` run after path checkout satisfies the guard",
    ),
    (
        [
            bash_tool("git restore file.txt"),
            bash_tool("git diff"),
            say_claude("Checked diff. Working tree clean."),
        ],
        False,
        "`git diff` run after `git restore` satisfies the guard",
    ),
    (
        [
            bash_tool("pytest tests/"),
            say_claude("Tests pass. **Stopping Point**: Clean stopping point."),
        ],
        False,
        "No path-writing git command ran, clean stopping point stays silent",
    ),
    (
        [
            bash_tool("git checkout feat/some-branch"),
            say_claude("Switched branch. Working tree clean."),
        ],
        False,
        "Normal branch checkout does not trigger path-writing warning",
    ),
    (
        [
            bash_tool("git checkout -b feat/new-feature"),
            say_claude("Created branch. Clean stopping point."),
        ],
        False,
        "Branch creation `checkout -b` does not trigger warning",
    ),
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            say_claude("**Stopping Point**: Not a clean stopping point / work remains queued."),
        ],
        False,
        "Negated stopping point ('Not a clean stopping point') does not warn",
    ),
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            say_claude("Working tree is not clean; 1 file staged for review."),
        ],
        False,
        "Negated working tree claim ('working tree is not clean') does not warn",
    ),
    (
        [
            bash_tool("git checkout -q origin/main -- website/"),
            say_claude("The rule says to write `clean stopping point` in recaps."),
        ],
        False,
        "Backtick-quoted phrase in prose does not trigger clean assertion",
    ),
]


def run_case(events, should_warn):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
        for ev in events:
            tf.write(json.dumps(ev) + "\n")
        tpath = tf.name

    try:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": tpath}),
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert proc.returncode == 0, f"Hook crashed with code {proc.returncode}: {proc.stderr}"
        out = proc.stdout.strip()
        warned = False
        if out:
            data = json.loads(out)
            warned = bool(data.get("systemMessage"))
        return warned == should_warn, warned
    finally:
        if os.path.exists(tpath):
            os.remove(tpath)


def main():
    passed = 0
    failed = 0
    for events, expected, description in CASES:
        ok, warned = run_case(events, expected)
        if ok:
            passed += 1
            print(f"PASS: {description}")
        else:
            failed += 1
            print(f"FAIL: {description} (expected warn={expected}, got warn={warned})")

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
