#!/usr/bin/env python3
"""PreToolUse: do not ask the user for hand work the agent can do itself.

ai-config#4698; shared/workflow/lab-operating-rules.md. Ezra, 2026-10-23:
"don't make me intervene manually to prompt threads to \"go\" if there's any
other way", and no merge buttons or manual steps. Blocks (deny) a user-visible
reply tool call (mcp__hearthbot__reply, post_message, update_message,
edit_message) whose text asks the user to

  * type "go" (or similar) into a Remote Control / RC session;
  * click or press a Merge button, or merge a PR themselves;
  * paste, append, or hand-add text into a file or settings (Ezra, 2026-10-26:
    "never ask me to paste anything into a file; always give me a script-based
    command to run that does it for me").

The denial points at the substitute: start a fresh session on an already
approved environment with the brief as its opening task, retry a denied step
once, for merges ask for the plain `mwc` word, and for a file edit write an
idempotent script and give one command that runs it. Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

ASKS = (
    ("a manual 'go' in a Remote Control session", re.compile(
        r"\b(?:type|say|send|reply|enter|answer)\s+(?:with\s+)?[`'\"*]*go\b[`'\"*]*[^.\n]{0,60}"
        r"\b(?:remote control|RC|session|device)\b"
        r"|\b(?:remote control|RC)\b[^.\n]{0,80}\b(?:type|say|send|reply|enter)\b[^.\n]{0,40}[`'\"*]\bgo\b",
        re.I)),
    ("a merge button or manual merge", re.compile(
        r"\b(?:click|press|hit|tap)\b[^.\n]{0,30}\bmerge\b[^.\n]{0,20}\bbutton\b"
        r"|\bmerge (?:it|them|the PRs?) (?:yourself|manually|by hand)\b",
        re.I)),
    ("a paste or hand-edit of a file", re.compile(
        r"(?:^|[.!?\n:]\s*|\b(?:please|you can|you could|can you|could you|just)\s+)"
        r"(?:paste|append|insert|add|put|copy)\b(?:[^.\n]|\.(?=\S)){0,80}\b(?:into|to|in|onto)\b"
        r"(?:[^.\n]|\.(?=\S)){0,60}(?:\bfile\b|settings|config|\.json\b|\.ya?ml\b|\.toml\b|~/)",
        re.I)),
)

REASON = (
    "[hook: no-manual-step-ask] This message asks the user for hand work: {what}. "
    "Do it another way. For a Remote Control session, start a fresh one on an "
    "already approved environment with the brief as its opening task (no 'go' to type). "
    "For a merge, ask for plain `mwc`. For a file edit, write an idempotent script, test it, and give one command that runs it (no pasting). For a denied step, retry once unchanged. "
    "shared/workflow/lab-operating-rules.md; ai-config#4698."
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
