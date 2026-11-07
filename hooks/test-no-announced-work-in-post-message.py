#!/usr/bin/env python3
"""Test no-announced-work-in-post-message.py (ai-config#5053).

Every case runs this hook alone: the Stop hook is never invoked, which is the
point of a layer that must work with the others off.

Run: python3 hooks/test-no-announced-work-in-post-message.py \
       hooks/no-announced-work-in-post-message.py
"""
import json
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
POST = "mcp__hearthbot__post_message"


def tool(name, **inp):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
    }


def checklist(text):
    return tool("mcp__hearthbot__update_progress_checklist", text=text)


OPEN = "Work\n\n✓ first\n○ second"
DONE = "Work\n\n✓ first\n✓ second"


def decision(messages, text, tool_name=POST):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        for m in messages:
            fh.write(json.dumps(m) + "\n")
        path = fh.name
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(
            {"tool_name": tool_name, "tool_input": {"text": text}, "transcript_path": path}
        ),
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not out:
        return "allow"
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


CASES = [
    # (name, transcript, text, tool, expected)
    ("announce with open step", [checklist(OPEN)], "Merged the first PR.\n\nNext I'm opening the first workflow PR.", POST, "deny"),
    ("I'm now with open step", [checklist(OPEN)], "I'm now opening the follow-up PR.", POST, "deny"),
    ("announce, all steps done", [checklist(DONE)], "Next I'm opening the first workflow PR.", POST, "allow"),
    ("announce, no checklist", [], "Next I'm opening the first workflow PR.", POST, "allow"),
    ("blocker named", [checklist(OPEN)], "Next I'll open the PR, but I'm blocked on the repo grant.", POST, "allow"),
    ("conditional", [checklist(OPEN)], "Next I'll open the PR once the review lands.", POST, "allow"),
    ("past tense", [checklist(OPEN)], "Opened the PR and filed the issue.", POST, "allow"),
    ("other tool", [checklist(OPEN)], "Next I'm opening the first workflow PR.", "Bash", "allow"),
    ("reply tool", [checklist(OPEN)], "Next I'm opening the first workflow PR.", "mcp__hearthbot__reply", "deny"),
    ("update_message tool", [checklist(OPEN)], "Next I'm opening the first workflow PR.", "mcp__hearthbot__update_message", "deny"),
    ("in-progress glyph is not unstarted", [checklist("Work\n\n✓ first\n✱ second")], "Next I'm opening the first workflow PR.", POST, "allow"),
    ("latest checklist wins", [checklist(OPEN), checklist(DONE)], "Next I'm opening the PR.", POST, "allow"),
]


def main():
    failures = 0
    for name, transcript, text, tool_name, want in CASES:
        got = decision(transcript, text, tool_name)
        if got != want:
            failures += 1
            print(f"FAIL {name}: want {want}, got {got}")
        else:
            print(f"PASS {name}")
    # Fails open on unreadable input.
    out = subprocess.run(
        [sys.executable, HOOK], input="not json", capture_output=True, text=True
    )
    if out.stdout.strip() or out.returncode != 0:
        failures += 1
        print("FAIL fail-open on bad input")
    else:
        print("PASS fail-open on bad input")
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
