#!/usr/bin/env python3
"""Tests for hooks/handoff-ask-needs-why.py (ai-config#6068).

Run: python3 hooks/test-handoff-ask-needs-why.py [hooks/handoff-ask-needs-why.py]
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

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
    ("over to you", POST, {"text": "Over to you to merge #12."}, True),
    ("needs you to press", POST, {"text": "This needs you to press merge."}, True),
    ("it's on you", POST, {"text": "I can't merge it, so it's on you."}, True),
    ("your click", POST, {"text": "Needs your click on Merge."}, True),
    ("yourself", POST, {"text": "Go ahead and merge #12 yourself."}, True),
    ("would you mind", POST, {"text": "Would you mind merging #12?"}, True),
    ("kindly", POST, {"text": "Kindly merge #12."}, True),
    ("I'd like you to", POST, {"text": "I'd like you to merge #12."}, True),
    ("go ahead and", POST, {"text": "Please go ahead and merge it."}, True),
    ("approve and merge", POST, {"text": "Please approve and merge #12."}, True),
    ("force-push", POST, {"text": "Please force-push the branch."}, True),
    ("squash and merge", POST, {"text": "Please squash and merge."}, True),
    ("you can merge", POST, {"text": "You can merge #12 now."}, True),
    ("when you've merged", POST, {"text": "Let me know when you've merged #12."}, True),
    ("negation earlier in the sentence", POST, {"text": "I never saw this block before, so please merge #12."}, True),
    ("card option is the agent's own step", DECIDE, {"question": "Land #12 now?",
                                                     "options": [{"label": "Merge it", "consequence": "I merge #12 under your mwc."},
                                                                 {"label": "Push it", "consequence": "I push the fix first."}]}, False),
    ("plan line", POST, {"text": "Plan: merge #12 after CI."}, False),
    ("next line", POST, {"text": "Done. Next up:\nPush it to the branch."}, False),
    ("update me", POST, {"text": "Please update me when CI finishes."}, False),
    ("stop by", POST, {"text": "Can you stop by the thread later?"}, False),
    ("start with", POST, {"text": "Please start with option A."}, False),
    ("apply by Friday", POST, {"text": "You must apply by Friday."}, False),
    ("press coverage", POST, {"text": "Press coverage: the merge button was added."}, False),
    ("quoted request", POST, {"text": "The reviewer wrote \"please merge this\" on the PR."}, False),
    ("blockquote", POST, {"text": "> Please re-run the job\nThat was the bot's comment; I re-ran it."}, False),
    ("fenced code", POST, {"text": "The bot posted:\n```\nPlease merge #12\n```\nI merged it."}, False),
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
        stop = {"hook_event_name": "Stop", "session_id": "test-handoff-" + uuid.uuid4().hex, "cwd": tmp,
                "last_assistant_message": "Please press merge on #6066."}
        out = run(stop)
        data = json.loads(out) if out.strip() else {}
        if data.get("decision") != "block" or "handoff-ask-needs-why" not in str(data.get("reason")):
            failures += 1
            print(f"FAIL stop hand-off: {out!r}")
        clean = dict(stop, session_id="test-handoff-" + uuid.uuid4().hex,
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
