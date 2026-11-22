#!/usr/bin/env python3
"""Tests for hooks/handoff-ask-needs-why.py (ai-config#6068).

Run: python3 hooks/test-handoff-ask-needs-why.py [hooks/handoff-ask-needs-why.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "handoff-ask-needs-why.py")
POST = "mcp__hearthbot__post_message"
DECIDE = "mcp__hearthbot__request_decision"
COORD = "mcp__hearthbot__message_coordinator"

EXPLAINED = (
    " Why no other way works: the auto-mode classifier denied the merge call twice, and only you can "
    "press the button past it. What I tried: I retried the identical merge call, then the REST merge "
    "endpoint, and both were denied."
)

# (name, tool, tool_input, should_deny)
CASES = [
    ("the 2026-11-21 ask", POST, {"text": "Please press merge on ai-config#6066."}, True),
    ("you'll need to merge", POST, {"text": "The checks are green; you'll need to merge it."}, True),
    ("I need you to re-run", POST, {"text": "I need you to re-run the failed job."}, True),
    ("can you push", POST, {"text": "Can you push the branch from your laptop?"}, True),
    ("once you merge", POST, {"text": "I'll carry on once you merge #12."}, True),
    ("imperative press", POST, {"text": "Press the green Merge button on lds#3070."}, True),
    ("imperative merge it", POST, {"text": "CI passed.\nMerge it when you can."}, True),
    ("why only, no tried", POST, {"text": "Please press merge on #6066. There is no other way past the classifier."}, True),
    ("tried only, no why", POST, {"text": "Please press merge on #6066. I tried the merge call twice."}, True),
    ("both parts", POST, {"text": "Please press merge on #6066." + EXPLAINED}, False),
    ("both parts, short labels", POST, {"text": "Could you restart the runner? The only way in is your ssh key. "
                                                "Tried: the API restart (403) and a workflow dispatch (no runner)."}, False),
    ("report, past tense", POST, {"text": "Merged ai-config#6066 and slid v3."}, False),
    ("asking permission", POST, {"text": "May I run the restart script on cf463-01? Tap yes on the card."}, False),
    ("approval is the user's", POST, {"text": "Can you approve the plan on the card?"}, False),
    ("review is the user's", POST, {"text": "Please review the draft when you have a minute."}, False),
    ("negated", POST, {"text": "You don't need to merge anything; I merged it."}, False),
    ("no need", POST, {"text": "No need for you to restart the runner."}, False),
    ("secret exempt", POST, {"text": "Please add the token to the repo's secrets."}, False),
    ("sign-in exempt", POST, {"text": "Please sign in to GitHub again; the connector expired."}, False),
    ("user-only verbs", POST, {"text": "Could you pick an option and confirm the title?"}, False),
    ("would you like me to", POST, {"text": "Would you like me to merge it now?"}, False),
    ("not user-visible", COORD, {"text": "Please press merge on #6066."}, False),
    ("card hands off", DECIDE, {"question": "Can you press merge on #6066?",
                                "options": [{"label": "I merged it", "consequence": "The thread goes on."},
                                            {"label": "Leave it", "consequence": "It stays open."}]}, True),
    ("card label hands off", DECIDE, {"question": "How should #6066 land?",
                                      "options": [{"label": "You merge it", "consequence": "Please press merge on it."},
                                                  {"label": "Wait", "consequence": "Nothing moves."}]}, True),
    ("card with no hand-off", DECIDE, {"question": "Which title do you prefer?",
                                       "options": [{"label": "A", "consequence": "Uses A."},
                                                   {"label": "B", "consequence": "Uses B."}]}, False),
]


def run(payload: dict, env=None) -> str:
    result = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                            text=True, timeout=20, env=env)
    return result.stdout


def denied(out: str) -> bool:
    if not out.strip():
        return False
    data = json.loads(out)
    return data.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def transcript(entries) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    with handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return handle.name


def main() -> int:
    failures = 0
    for name, tool, tool_input, want in CASES:
        got = denied(run({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}))
        if got != want:
            failures += 1
            print(f"FAIL {name}: denied={got}, want {want}")

    card = {"question": "Can you press merge on #6066?",
            "options": [{"label": "Done", "consequence": "The thread goes on."},
                        {"label": "Leave it", "consequence": "It stays open."}]}
    user = {"type": "user", "message": {"role": "user", "content": "cai: tell me why"}}
    explained = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": POST, "input": {"text": "Please press merge on #6066." + EXPLAINED}}]}}
    for name, entries, want in (
            ("card after explaining message this turn", [user, explained], False),
            ("card after explaining message last turn", [explained, user], True)):
        path = transcript(entries)
        try:
            got = denied(run({"hook_event_name": "PreToolUse", "tool_name": DECIDE,
                              "tool_input": card, "transcript_path": path}))
        finally:
            os.unlink(path)
        if got != want:
            failures += 1
            print(f"FAIL {name}: denied={got}, want {want}")

    env = dict(os.environ, ALLOW_HANDOFF_WITHOUT_WHY="1")
    if denied(run({"tool_name": POST, "tool_input": {"text": "Please press merge on #6066."}}, env)):
        failures += 1
        print("FAIL override: still denied")

    with tempfile.TemporaryDirectory() as tmp:
        stop = {"hook_event_name": "Stop", "session_id": "test-handoff", "cwd": tmp,
                "last_assistant_message": "Please press merge on #6066."}
        out = run(stop)
        data = json.loads(out) if out.strip() else {}
        if data.get("decision") != "block" or "handoff-ask-needs-why" not in str(data.get("reason")):
            failures += 1
            print(f"FAIL stop hand-off: {out!r}")
        clean = dict(stop, session_id="test-handoff-2",
                     last_assistant_message="Please press merge on #6066." + EXPLAINED)
        out = run(clean)
        if out.strip() and json.loads(out).get("decision") == "block":
            failures += 1
            print(f"FAIL stop explained: {out!r}")

    if denied(run({"tool_name": POST, "tool_input": "not a dict"})) or run({"garbage": True}).strip():
        failures += 1
        print("FAIL malformed payload did not fail open")

    total = len(CASES) + 6
    print(f"{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
