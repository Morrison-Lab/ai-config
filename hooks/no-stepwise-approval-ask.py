#!/usr/bin/env python3
"""PreToolUse: do not ask the user to approve each step of a job already asked for.

ai-config#4726; shared/workflow/lab-operating-rules.md. Ezra, 2026-10-25: "stop
making me give so many manual orders". An ask for a deliverable (for example
"post the key") authorizes its whole follow-through, including re-uploads and
replacements of the same item. Only merges and irreversible student-facing
changes need his word, and `mwc` is that word.

Blocks (deny) a user-visible reply tool call (mcp__hearthbot__reply,
post_message, update_message, edit_message) whose text

  * asks the user to type an approval word (yes, approve, confirm, proceed,
    continue, okay, allow) so that a step can go ahead; or
  * asks whether to do the follow-through of a deliverable (re-upload,
    replace, repost, resend) instead of doing it.

The denial points at the substitute: do the step, report it in the past tense,
and make any real approval ask one line that covers the whole remaining job.
Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

APPROVAL = r"(?:yes|approve[ds]?|approval|confirm(?:ed)?|proceed|continue|ok(?:ay)?|allow(?:ed)?)"
FOLLOW = r"(?:re-?upload|re-?post|re-?send|replac(?:e|ing)|overwrit(?:e|ing)|re-?publish|re-?run)"

ASKS = (
    ("a typed approval word to continue a step", re.compile(
        r"\b(?:type|say|reply(?:\s+with)?|answer(?:\s+with)?|respond(?:\s+with)?|send)\b"
        r"\s+[`'\"*]*" + APPROVAL + r"\b[`'\"*]*"
        r"[^.\n]{0,60}\b(?:to|and\s+I(?:'ll|\s+will)|so\s+(?:I|that))\b",
        re.I)),
    ("a question whether to do a deliverable's follow-through", re.compile(
        r"\b(?:shall\s+I|should\s+I|do\s+you\s+want\s+me\s+to|want\s+me\s+to|"
        r"would\s+you\s+like\s+me\s+to|may\s+I|can\s+I)\s+"
        + FOLLOW + r"\b",
        re.I)),
)

REASON = (
    "[hook: no-stepwise-approval-ask] This message asks the user to approve each step: {what}. "
    "An ask for a deliverable authorizes its whole follow-through, including re-uploads and "
    "replacements of the same item. Do the step and report it in the past tense. If a real "
    "approval is needed (a merge, or an irreversible student-facing change), ask once, in one "
    "line that covers the entire remaining job; for a merge ask for plain `mwc`. "
    "shared/workflow/lab-operating-rules.md; ai-config#4726."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    for what, pattern in ASKS:
        if pattern.search(text):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(what=what),
                }
            }))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
