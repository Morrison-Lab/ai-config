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


USER = {"type": "user", "message": {"role": "user", "content": "cai: tell me why"}}
CHECK_BRIEF = ("Adversarially try to refute this claim: find a route that does not need Ezra "
               "to merge #6066 (another tool or API, a retry, a standing grant).")


def check_entries(brief=CHECK_BRIEF, failed=False, tool="Agent"):
    """An adversarial subagent launch and its result."""
    return [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_check", "name": tool, "input": {"prompt": brief}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_check", "is_error": failed,
             "content": "No route found."}]}},
    ]


# Claims that a step cannot be done (ai-config#6075). Run with an adversarial
# check in the transcript, so only the claim check decides.
CLAIM_CASES = [
    ("the 2026-11-22 relay", COORD, {"text": "The thread has no other way to commit."}, True),
    ("can't push, user-visible", POST, {"text": "I can't push the branch from here."}, True),
    ("unable to merge", POST, {"text": "I was unable to merge #12."}, True),
    ("commit claim names checks but not the API", POST,
     {"text": "I can't commit here. Checked: git push (403) and a retry (403)."}, True),
    ("commit claim with the API checked", POST,
     {"text": "I can't commit here. Checked: git push (403), a retry (403), and the GitHub API "
              "push_files tool (404, the repo is not in scope)."}, False),
    ("merge claim with checks", POST,
     {"text": "I can't merge #12: I tried the MCP merge (denied) and retried it once (denied)."}, False),
    ("permission, not impossibility", POST, {"text": "I can't merge #12 without your mwc."}, False),
    ("no step named", POST, {"text": "I can't find the old thread."}, False),
    ("quoted claim", POST, {"text": "The relay said \"no other way to commit\", which was wrong."}, False),
    ("can't find is not a claim", POST, {"text": "I can't find the merge commit in the log."}, False),
    ("can't reproduce is not a claim", POST, {"text": "I cannot reproduce the failure when I rerun."}, False),
    ("a gate that lifts", POST, {"text": "CI can't merge until checks pass."}, False),
    ("the route that worked", POST,
     {"text": "I couldn't push earlier, so I used the contents endpoint instead."}, False),
    ("won't work", POST, {"text": "Pushing won't work from this sandbox."}, True),
    ("no permission to push", POST, {"text": "The thread has no permission to push."}, True),
    ("relay to a thread", "mcp__hearthbot__message_thread",
     {"thread_id": "cmsg_x", "text": "You cannot push from that container."}, True),
]

# Claims that the user's input is needed (ai-config#6075), with and without
# an adversarial check this turn.
INPUT_CASES = [
    ("waiting on your approval, no check", POST, {"text": "This is waiting on your approval."}, None, True),
    ("waiting on your approval, checked", POST, {"text": "This is waiting on your approval."},
     check_entries(), False),
    ("relay of a needs-Ezra claim, no check", COORD, {"text": "lds#12 needs Ezra's sign-off."}, None, True),
    ("card, no check", DECIDE, {"question": "Which title do you prefer?",
                                "options": [{"label": "A", "consequence": "Uses A."},
                                            {"label": "B", "consequence": "Uses B."}]}, None, True),
    ("card, checked", DECIDE, {"question": "Which title do you prefer?",
                               "options": [{"label": "A", "consequence": "Uses A."},
                                           {"label": "B", "consequence": "Uses B."}]},
     check_entries(), False),
    ("check that failed", POST, {"text": "This needs your approval."}, check_entries(failed=True), True),
    ("brief that is not adversarial", POST, {"text": "This needs your approval."},
     check_entries(brief="Summarize the PR."), True),
    ("check in an earlier turn", POST, {"text": "This needs your approval."},
     check_entries() + [USER], True),
    ("on hold until you decide", POST, {"text": "This is on hold until you decide."}, None, True),
    ("Ezra has to approve", COORD, {"text": "Ezra has to approve before this goes on."}, None, True),
    ("needs a human", POST, {"text": "Blocked: needs a human."}, None, True),
    ("only the owner can", POST, {"text": "Only the owner can approve this."}, None, True),
    ("pending CI is not a claim", POST, {"text": "The deploy is pending CI."}, None, False),
    ("depends on a config file", POST, {"text": "The fix depends on the user's config file."}, None, False),
    ("no input needed", POST, {"text": "Merged #12; nothing needs your input."}, None, False),
    ("doesn't need you", POST, {"text": "The fix doesn't need you at all."}, None, False),
    ("plain report", POST, {"text": "Merged #12 and slid v3."}, None, False),
]


def run_with(tool, tool_input, entries) -> bool:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    path = transcript([USER] + entries) if entries is not None else ""
    if path:
        payload["transcript_path"] = path
    try:
        return denied(run(payload))
    finally:
        if path:
            os.unlink(path)


def main() -> int:
    failures = 0
    # The hand-off cases run with an adversarial check in the transcript, so the
    # input-claim check passes and only the hand-off check decides.
    for name, tool, tool_input, want in CASES + CLAIM_CASES:
        got = run_with(tool, tool_input, check_entries())
        if got != want:
            failures += 1
            print(f"FAIL {name}: denied={got}, want {want}")
    for name, tool, tool_input, entries, want in INPUT_CASES:
        got = run_with(tool, tool_input, entries)
        if got != want:
            failures += 1
            print(f"FAIL {name}: denied={got}, want {want}")

    card = {"question": "Can you press merge on #6066?",
            "options": [{"label": "Done", "consequence": "The thread goes on."},
                        {"label": "Leave it", "consequence": "It stays open."}]}
    user = USER
    explained = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": POST, "input": {"text": "Please press merge on #6066." + EXPLAINED}}]}}
    for name, entries, want in (
            ("card after explaining message this turn", [user] + check_entries() + [explained], False),
            ("card after explaining message last turn", check_entries() + [explained, user], True)):
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
        path = transcript([USER] + check_entries())
        try:
            clean = dict(stop, session_id="test-handoff-" + uuid.uuid4().hex, transcript_path=path,
                         last_assistant_message="Please press merge on #6066." + EXPLAINED)
            out = run(clean)
        finally:
            os.unlink(path)
        if out.strip() and json.loads(out).get("decision") == "block":
            failures += 1
            print(f"FAIL stop explained: {out!r}")

    if denied(run({"tool_name": POST, "tool_input": "not a dict"})) or run({"garbage": True}).strip():
        failures += 1
        print("FAIL malformed payload did not fail open")

    total = len(CASES) + len(CLAIM_CASES) + len(INPUT_CASES) + 6
    print(f"{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
