#!/usr/bin/env python3
"""PreToolUse: do not answer from memory when a source can be checked.

ai-config#4957. Ezra, 2026-11-04: "cai: never use memory when you can check."
In the lds thread "Consolidate overlapping linear regression labs" a reply named
the datasets ISL uses "from my memory of the book, not checked against the text"
and then asked Ezra where the book lives; the library at /mnt/project-files
holds it. Blocks (deny) a user-visible reply or relay tool call
(mcp__hearthbot__reply, post_message, update_message, edit_message,
message_coordinator, message_thread) whose text

  * says the answer comes from memory or recall ("from my memory", "as I
    recall", "if I remember correctly", "off the top of my head"), or that it
    was "not checked against" / "not verified against" a source; or
  * asks the user where a book, file, repo or other source lives, without
    saying where the agent already searched.

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
    r"\bfrom\s+(?:my\s+|the\s+)?(?:memory|recall|recollection)\b"
    r"|\b(?:my|a\s+vague)\s+(?:memory|recollection)\s+of\b"
    r"|\bas\s+I\s+(?:recall|remember)\b"
    r"|\bif\s+I\s+(?:recall|remember)\s+(?:correctly|right)\b"
    r"|\boff\s+the\s+top\s+of\s+my\s+head\b"
    r"|(?:\b(?:not|never|without)|n['\u2019]t)\s+(?:been\s+)?(?:checked|verified)\s+against\b"
    r"|\bunchecked\s+against\b",
    re.I)

# "not from memory" and the like say the author did check.
DISCLAIMED = re.compile(
    r"\b(?:not|never|rather\s+than|instead\s+of|no\s+longer|than)\s+(?:just\s+|only\s+)?from\s+(?:my\s+)?(?:memory|recall)\b",
    re.I)

WHERE_ASK = re.compile(
    r"\b(?:where\s+(?:does|do|is|are|can\s+I\s+find)|point\s+me\s+to|tell\s+me\s+where|which\s+(?:folder|repo|path)\s+(?:holds|has|contains))\b"
    r"[^.?\n]{0,60}\b(?:book|textbook|text|pdf|library|source|repo|file|folder|paper|docs?)\b",
    re.I)

SEARCHED = re.compile(
    r"\b(?:searched|looked\s+(?:in|through|at)|grepped|listed|found\s+no|did\s+not\s+find|didn['\u2019]t\s+find)\b",
    re.I)

REASON = (
    "[hook: no-answer-from-recall] This message {what}. "
    "Check the source first: search the project library (/mnt/project-files, and the books under Morrison-Lab/mlr), "
    "the attached repos, the docs or the API, read the passage, and restate the answer with what you read "
    "(file and page or line). Ask the user where a source lives only after naming the places you searched. "
    "shared/workflow/check-sources-over-recall.md; ai-config#4957."
)


def sentences(text: str):
    return re.split(r"(?<=[.!?])\s+|\n+", text)


def verdict(text: str):
    for sentence in sentences(text):
        if RECALL.search(sentence) and not DISCLAIMED.search(sentence):
            return "answers from memory or says it was not checked against a source"
    if WHERE_ASK.search(text) and not SEARCHED.search(text):
        return "asks the user where a source lives without naming where you searched"
    return None


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
    what = verdict(text)
    if what:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(what=what),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
