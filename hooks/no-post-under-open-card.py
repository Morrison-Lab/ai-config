#!/usr/bin/env python3
"""PreToolUse: nothing may be posted under a decision card that is still waiting for an answer.

Ezra, 2026-11-19: "sometimes a card moves while I'm clicking and I click the
wrong choice; can we avoid that?" and "or maybe if you want to post something
after a card, delete the card and repost it last?" A thread had posted an
annotation-gate card and then a message under it; the card shifted as he
tapped, and he picked the option he did not mean.

The app's layout is not ours to change, so the fix is on the posting side:
while a card is open, it must stay the last thing in the thread. This hook
denies a thread-visible post (`mcp__hearthbot__post_message`, `reply`,
`update_message`, `edit_message`, `update_progress_checklist`, `post_widget`,
`request_decision`) when the session's transcript holds an open card. The fix
it names is Ezra's: withdraw the card with `close_decision` (no `chose`), make
the post, then post the card again with `request_decision` as the last call.

A card is open when a `request_decision` tool_use got a tool_result naming its
`message_id` (`cmsg_...`), and nothing has closed it since: no
`close_decision` tool_use with that `message_id`, and no record the assistant
did not write saying `decision_id=<that id>` (the platform's decision-chosen
wake). Only a request_decision tool_use and its own tool_result open a card,
so text that merely quotes an id cannot.

A deny, not a reminder, because the failing shape is decidable from the
transcript (ai-config#4741). `edit_message` is included because an edit can
change a message's height above the card too. `ALLOW_POST_UNDER_CARD=1`
overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_POST_UNDER_CARD"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|"
    r"update_progress_checklist|post_widget|request_decision)$")
REQUEST = re.compile(r"^mcp__hearthbot__request_decision$")
CLOSE = re.compile(r"^mcp__hearthbot__close_decision$")
MESSAGE_ID = re.compile(r'"message_id"\s*:\s*"(cmsg_[A-Za-z0-9]+)"')
CHOSEN = re.compile(r"decision_id=(cmsg_[A-Za-z0-9]+)")

REASON = (
    "[hook: no-post-under-open-card] A decision card ({card}) is still waiting for an answer, "
    "and this call would put something under it. Cards move when anything is posted after "
    "them, and Ezra has tapped the wrong option because of it (2026-11-19).\n"
    "Keep the card last: withdraw it with mcp__hearthbot__close_decision (message_id "
    "{card}, no `chose`), make this post, then post the card again with "
    "mcp__hearthbot__request_decision as the turn's last thread-visible call. "
    "ALLOW_POST_UNDER_CARD=1 overrides."
)


def read_text(path, limit=20_000_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except (OSError, TypeError, ValueError):
        return ""


def blocks(node):
    """Yield every dict with a `type` key nested anywhere in a parsed transcript line."""
    if isinstance(node, dict):
        if "type" in node:
            yield node
        for value in node.values():
            yield from blocks(value)
    elif isinstance(node, list):
        for value in node:
            yield from blocks(value)


def result_text(block) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(c.get("text") or "") for c in content if isinstance(c, dict))
    return ""


def open_cards(transcript: str):
    """Return the ids of cards opened by request_decision and not closed since, in order."""
    request_ids = set()
    opened = []
    closed = set()
    for line in transcript.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        for block in blocks(record):
            kind = block.get("type")
            if kind == "tool_use":
                name = str(block.get("name") or "")
                if REQUEST.search(name):
                    request_ids.add(block.get("id"))
                elif CLOSE.search(name):
                    card = (block.get("input") or {}).get("message_id")
                    if isinstance(card, str):
                        closed.add(card)
            elif kind == "tool_result":
                if block.get("tool_use_id") in request_ids and not block.get("is_error"):
                    m = MESSAGE_ID.search(result_text(block))
                    if m:
                        opened.append(m.group(1))
        # The decision-chosen wake reaches the transcript as a queue-operation
        # or attachment record, or as a user message (measured 2026-11-19 on a
        # real thread transcript). Any record not written by the assistant may
        # close a card; a tool result that quotes the id can too, which errs
        # toward allowing the post (fail open), never toward a false block.
        if not (isinstance(record, dict) and record.get("type") == "assistant"):
            closed.update(CHOSEN.findall(line))
    return [c for c in opened if c not in closed]


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    still_open = open_cards(read_text(payload.get("transcript_path")))
    if not still_open:
        return None
    return REASON.format(card=still_open[-1])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    try:
        reason = denial(payload)
    except Exception:  # fail open: a hook bug must never block a reply
        return 0
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
