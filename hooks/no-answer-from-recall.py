#!/usr/bin/env python3
"""PreToolUse: do not answer from memory when a source can be checked.

ai-config#4957. Ezra, 2026-11-04: "cai: never use memory when you can check."
In the lds thread "Consolidate overlapping linear regression labs" a reply named
the datasets ISL uses "from my memory of the book, not checked against the text"
and then asked Ezra where the book lives; the library at /mnt/project-files
holds it. Blocks (deny) a user-visible reply or relay tool call
(mcp__hearthbot__reply, post_message, update_message, edit_message,
message_coordinator, message_thread) whose text says the answer comes from
memory or recall ("from my memory", "as I recall", "if I remember correctly",
"off the top of my head").

Only first-person recall hedges are matched, because each reads as an admission
and almost never as ordinary English. Wider patterns over-matched ordinary prose
in five review rounds: "from the memory of", "not checked against <noun>" (every
noun list either denied status updates or missed real sources), and asking where
a book lives (#4959). A lexical hook cannot decide those.

A hook cannot tell whether a source exists, so the denial sends the author back
to check (library, attached repos, docs, the API) and to restate the answer
with the source it read. A sentence that disclaims recall ("not from memory",
"rather than from recall") is exempt. Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|message_coordinator|message_thread)$")

RECALL = re.compile(
    r"\bfrom\s+(?:my\s+)?(?:memory|recall|recollection)\b(?!\s+(?:card|stick|buffer|bank|usage|leak|address))"
    r"|\b(?:my|a\s+vague)\s+(?:memory|recollection)\s+of\b"
    r"|\bas\s+I\s+(?:recall|remember)\b(?!\s+you)"
    r"|\bif\s+I\s+(?:recall|remember)\s+(?:correctly|right)\b"
    r"|\boff\s+the\s+top\s+of\s+my\s+head\b",
    re.I)

# "not from memory" and the like say the author did check.
DISCLAIMED = re.compile(
    r"\b(?:not|never|rather\s+than|instead\s+of|no\s+longer|than)\s+(?:just\s+|only\s+)?from\s+(?:my\s+)?(?:memory|recall)\b",
    re.I)

REASON = (
    "[hook: no-answer-from-recall] This message answers from memory or recall. "
    "Check the source first: search the project library (/mnt/project-files, and the books under Morrison-Lab/mlr), "
    "the attached repos, the docs or the API, read the passage, and restate the answer with what you read "
    "(file and page or line). Ask the user where a source lives only after naming the places you searched. "
    "shared/workflow/check-sources-over-recall.md; ai-config#4957."
)


def sentences(text: str):
    return re.split(r"(?<=[.!?])\s+|\n+", text)


def recalls(text: str) -> bool:
    return any(RECALL.search(s) and not DISCLAIMED.search(s) for s in sentences(text))


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
    if isinstance(text, str) and recalls(text):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
