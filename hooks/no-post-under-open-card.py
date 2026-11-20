#!/usr/bin/env python3
"""PreToolUse: deny a thread-visible post while a decision card waits for an answer.

Ezra, 2026-11-19: "sometimes a card moves while I'm clicking and I click the
wrong choice" and "if you want to post something after a card, delete the card
and repost it last". Denies post_message, reply, update_message, edit_message
(an edit changes height too), update_progress_checklist, post_widget and
request_decision while the transcript holds an open card, and names Ezra's
fix: close_decision, post, then request_decision last.

Open: a request_decision tool_use whose own tool_result names its message_id.
Closed: a close_decision with that id; a `decision_id=<id>` in any record the
assistant did not write (the tap wake, or a tool result quoting one, which errs
toward allowing); or a later wake with a typed message from the person.
A deny because the state is decidable (ai-config#4741). Writer layer:
shared/workflow/lab-operating-rules.md; reviewer layer: adversarial-reviewer.md.
ALLOW_POST_UNDER_CARD=1 overrides. Fails open on parse trouble.
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
# A wake carrying the person's own typed message: <message ... from="human" trust="principal">.
# Raw transcript lines hold it JSON-escaped, so the quotes may carry a backslash.
HUMAN = re.compile(r'from=\\?"human\\?"[^>]*trust=\\?"principal\\?"')

REASON = (
    "[hook: no-post-under-open-card] Decision card {card} is still waiting for an answer, and this "
    "call would put something under it, so the card moves under Ezra's tap (2026-11-19).\n"
    "Keep the card last: mcp__hearthbot__close_decision (message_id {card}, no `chose`), make this post, "
    "then mcp__hearthbot__request_decision again as the turn's last thread-visible call. "
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
    if isinstance(content, list):
        return "\n".join(str(c.get("text") or "") for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


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
        # The tap wake can be any non-assistant record type (measured 2026-11-19).
        if not (isinstance(record, dict) and record.get("type") == "assistant"):
            closed.update(CHOSEN.findall(line))
            if HUMAN.search(line):  # a typed answer, or a message past the card
                closed.update(opened)
    return [c for c in opened if c not in closed]


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict) \
            or not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    still_open = open_cards(read_text(payload.get("transcript_path")))
    return REASON.format(card=still_open[-1]) if still_open else None


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
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
