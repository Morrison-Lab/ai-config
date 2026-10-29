#!/usr/bin/env python3
"""PreToolUse: do not ask the user to start or run Remote Control.

Ezra, 2026-10-15: "you can launch sessions on that machine without me; stop
forgetting." Ezra, 2026-10-29 14:54 and 14:55 UTC, after the coordinator asked him to
start Remote Control on cf463-02: "you can run remote control yourself" and "you
should have known that". The standing permission is recorded in
shared/workflow/fetch-untrusted-files.md (ai-config#4516) and
shared/workflow/lab-operating-rules.md.

Blocks (deny) an outgoing message that asks the user to start, run, launch or
open Remote Control or `claude remote-control`: the hearthbot reply tools
(post_message, message_thread, message_coordinator, edit_message and the
older reply tools; field `text`) and the forge comment tools (field `body`). The
denial points at `start_remote_control`, which the agent calls itself on
cf463-02 and the XPS. A sentence that denies the ask ("never ask you to start
Remote Control", "no need to start it yourself") is not an ask. Fails open on
parse trouble.
"""
import json
import re
import sys

TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|message_thread|message_coordinator)$"
    r"|^mcp__github__(?:add_issue_comment|update_issue_comment|add_reply_to_pull_request_comment"
    r"|add_comment_to_pending_review|pull_request_review_write|create_pull_request|update_pull_request|issue_write)$")

SENTENCE_BREAK = re.compile(
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\betc\.)(?<=[.!?])\s+|\n+", re.I)

RC = r"(?:remote[- ]control|(?-i:\bRC\b))"
VERB = r"(?:start|starting|run|running|launch|launching|open|opening|spin up|kick off|enable|turn on|bring up)"
FILL = r"[^.!?\n]{0,60}?"

ASKS = (
    # "please start RC", "can you run Remote Control", "you need to launch claude remote-control"
    re.compile(
        r"\b(?:please|can you|could you|would you|will you|you(?:'ll| will)? need to|you have to|you must|"
        r"you can|you could|you should|(?:I )?need you to|(?:I )?want you to|I(?:'d| would) like you to|"
        r"ask(?:ing)? you to|have you|if you (?:can|could|would)|once you|when you)\s+" + VERB + r"\b"
        + FILL + RC, re.I),
    # sentence-opening imperative: "Start Remote Control on cf463-02."
    re.compile(r"(?:^|[.!?\n:]\s*)" + VERB + r"\b" + FILL + RC, re.I),
    # passive: "Remote Control needs to be started on the Mac"
    re.compile(RC + FILL + r"\b(?:needs?|has|have|must|should) (?:to )?be (?:started|launched|run|opened|enabled)\b"
               + FILL + r"\b(?:by you|on (?:your|the) |from (?:your|the) )", re.I),
    # "on your machine, start RC" and "from your terminal run claude remote-control"
    re.compile(r"\b(?:on|from|in) (?:your|the) (?:machine|laptop|Mac|box|terminal|computer|XPS)\b" + FILL + VERB + r"\b" + FILL + RC, re.I),
)

NEGATION = re.compile(
    r"\b(?:never|won't|will not|don't|do not|doesn't|not (?:ask|need)|no need|without asking|"
    r"without you|instead of asking|rather than asking|yourself|already (?:started|running))\b", re.I)

REASON = (
    "[hook: no-ask-to-start-rc] This message asks the user to start or run Remote Control. "
    "Ezra's standing permission (2026-10-15; again 2026-10-29: \"you can run remote control yourself\") "
    "lets you start it yourself on cf463-02 or the XPS. Call mcp__hearthbot__start_remote_control "
    "(its card is the only approval), brief the session, and report in the past tense. "
    "Ask only for a permission prompt the box itself raises, or when cf463-02 needs sudo. "
    "shared/workflow/fetch-untrusted-files.md; shared/workflow/lab-operating-rules.md."
)


def asked(text: str) -> bool:
    for sentence in SENTENCE_BREAK.split(text):
        if NEGATION.search(sentence):
            continue
        if any(p.search(sentence) for p in ASKS):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    for field in ("text", "body"):
        text = tool_input.get(field)
        if isinstance(text, str) and asked(text):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            }))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
