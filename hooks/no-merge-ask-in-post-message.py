#!/usr/bin/env python3
"""PreToolUse: a project thread must not ask the user for a merge or `mwc`.

ai-config#5155. Ezra's rule (2026-11-09): owner threads never ask him for a
merge or an `mwc`. The coordinator puts a PR on his merge line once the agy
review and the fully-clean checker have passed, and a thread's job ends at
reporting the final head to the coordinator. On 2026-11-07 a thread told him it
would ask for `mwc` and was corrected twice (ai-config#5058).

Scope: a thread session's user-visible tools, `mcp__hearthbot__post_message`
and `request_decision` (also `reply`, `update_message`, `edit_message`). The
coordinator and every other session are never blocked, because the coordinator
is the one that asks. A thread session is recognized as in
no-self-thread-link.py: its transcript says "You are a Thread Session".

Blocks (deny) text, a question or an option that asks the user to merge, to
give `mwc`, or for permission to merge. Inline code is NOT ignored, since the
ask usually sits in a code span. A past-tense report ("the coordinator has it
on the merge line") is allowed. `ALLOW_MERGE_ASK=1` overrides. Fails open on
any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_MERGE_ASK"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")
THREAD_SESSION = "You are a Thread Session"

_VERB = (r"(?:say|type|write|reply|respond|send|post|give|grant|issue|need|needs|"
         r"needed|want|wants|require|requires|awaiting|await|waiting\s+(?:for|on)|"
         r"ask(?:ing)?(?:\s+\w+)?\s+for|request(?:ing)?)")
ASKS = [
    re.compile(rf"\b{_VERB}\b[^.\n?!]{{0,40}}?\bmwc\b", re.I),
    re.compile(r"\bmwc\b[^.\n]{0,20}\b(?:please|needed|required|from you|from ezra)\b", re.I),
    re.compile(r"\b(?:can|could|may|should|shall)\s+i\s+merge\b", re.I),
    re.compile(r"\b(?:want|would you like)\s+me\s+to\s+merge\b", re.I),
    re.compile(r"\b(?:ok|okay|fine|good)\s+to\s+merge\s*\?", re.I),
    re.compile(r"\b(?:permission|approval|go-ahead|ok|okay)\s+(?:to|for)\s+(?:the\s+)?merge\b", re.I),
    re.compile(r"\bplease\s+merge\b", re.I),
    re.compile(
        r"\b(?:awaiting|waiting\s+(?:for|on)|needs?)\s+(?:your|ezra'?s?)\s+"
        r"(?:merge|approval|ok|okay|go-ahead)\b", re.I),
    re.compile(r"\b(?:waiting|awaiting)\s+(?:for\s+)?(?:you|ezra)\s+to\s+merge\b", re.I),
]

# There is deliberately no negation check. A negated mention ("I am not asking for
# mwc") is denied too: the fix is one rewording, whereas every negation heuristic
# tried (a fixed window, a clause split) let a real ask through behind a hedge
# ("Not sure, but can I merge") or a connector ("... and please merge").

REASON = (
    '[hook: no-merge-ask-in-post-message] This post asks the user for a merge or `mwc` '
    '("{phrase}"). Owner threads never ask Ezra for either (ai-config#5155, 2026-11-09): '
    "the coordinator puts a PR on his merge line after the agy review and the fully-clean "
    "checker pass.\n"
    "Send the PR link and its final head SHA to the coordinator with message_coordinator "
    "instead, and tell the user in the past tense that the coordinator has it. "
    "Set ALLOW_MERGE_ASK=1 only when the user asked this thread to ask."
)


def is_thread_session(transcript_path) -> bool:
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            return THREAD_SESSION in f.read(200_000)
    except (OSError, TypeError, ValueError):
        return False


def user_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def merge_ask(text: str):
    """The first phrase that asks for a merge or mwc, or None."""
    for pattern in ASKS:
        m = pattern.search(text)
        if m:
            return " ".join(m.group(0).split())
    return None


def denial(payload: dict):
    if os.environ.get(OVERRIDE):
        return None
    if not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    phrase = merge_ask(user_text(tool_input))
    if not phrase or not is_thread_session(payload.get("transcript_path")):
        return None
    return REASON.format(phrase=phrase)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = denial(payload)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
