#!/usr/bin/env python3
"""Stop-hook guard: catch a reply that is nothing but a placeholder.

`CLAUDE.md`'s "Always produce a reply --- never end a turn silently" bans the
exact string `No response requested.` in a Do/Don't pair, with a case record
naming ai-config#1568. The rule was loaded and the lapse happened anyway,
three times in one session on 2026-08-17 -- each time on resuming after a
context-window summary, which is a fourth trigger that section does not name:
the summary reads like a report, so the work it describes feels already
reported.

Per `shared/principles/deterministic-tools.md`, the third occurrence is a
tool. The condition is lexically decidable over one artifact, so it should not
cost model reasoning at all.

WHOLE-MESSAGE anchoring, not substring. This corpus discusses the banned
string constantly -- this docstring does -- so a substring matcher would block
every reply that quotes the rule it enforces.

The line the patterns draw is between a claim about the REQUEST and a claim
about the WORK:

  blocked  "No response requested."   -- says nothing about what happened
  allowed  "Nothing to report."       -- says the work produced no change,
                                         which `CLAUDE.md` explicitly REQUIRES
                                         of a no-change background tick

Fires once per distinct message (sentinel keyed by content hash) so a block
cannot loop. Fails OPEN: a guard that wedges the session costs more than the
lapse it prevents.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Each pattern is matched against the WHOLE stripped message, never searched
# for inside it. Kept deliberately small: per algorithmatize-checks' "Limits",
# an instrument with a mushy threshold misfires and trains everyone to ignore
# it, and every entry here has to be a phrase that reports nothing about the
# work. "Done.", "No change.", and "Nothing to report." are therefore absent
# on purpose -- each of those reports an outcome.
PLACEHOLDERS = [
    r"no (response|reply|answer|output|message)( is| was)?"
    r" (requested|required|needed|expected)",
    r"n/?a",
    r"acknowledged",
    r"nothing further",
]
RX = re.compile(r"(?:%s)[.!]*" % "|".join(PLACEHOLDERS), re.I)

# Emphasis and brackets a placeholder is commonly dressed in. Stripped before
# matching so `*No response requested.*` and `(no reply needed)` are caught.
DRESSING = " \t\r\n*_`()[]\"'"


# In a project-thread session every user-visible sentence is the `text` input
# of an `mcp__hearthbot__reply` tool call, never an assistant text block.
# Measured on ai-config#3798: a reader that only walks `type == "text"` blocks
# is blind to the whole reply.
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _reply_payload(block):
    """The user-visible text of a reply-tool call, or '' for any other block."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if not REPLY_TOOL_RX.search(block.get("name") or ""):
        return ""
    inp = block.get("input")
    if not isinstance(inp, dict):
        return ""
    txt = inp.get("text")
    return txt if isinstance(txt, str) else ""


def last_assistant_text(path):
    if not path or not os.path.exists(path):
        return ""
    last_text = ""
    last_reply = ""
    saw_reply_tool = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if m.get("type") in {"assistant", "assistant_response"} or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        txt = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last_text = txt
                        for b in blocks:
                            if isinstance(b, dict) and b.get(
                                "type"
                            ) == "tool_use" and REPLY_TOOL_RX.search(
                                b.get("name") or ""
                            ):
                                saw_reply_tool = True
                            payload = _reply_payload(b)
                            if payload.strip():
                                last_reply = payload
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text = blocks
                elif m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
                    elif isinstance(content, list):
                        txt = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if txt.strip():
                            last_text = txt
    except Exception:
        return ""
    chosen = last_reply if saw_reply_tool else last_text
    return chosen if chosen.strip() else ""


def is_placeholder(text):
    """True when the whole message is a contentless placeholder."""
    stripped = text.strip(DRESSING)
    if not stripped:
        return False
    return RX.fullmatch(stripped) is not None


def _extract_from_blocks(blocks):
    """Extract assistant text from a list of blocks respecting reply-tool precedence."""
    last_text = ""
    last_reply = ""
    saw_reply_tool = False
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            txt = b.get("text") or ""
            if txt.strip():
                last_text = txt
        if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
            saw_reply_tool = True
        payload = _reply_payload(b)
        if payload.strip():
            last_reply = payload
    chosen = last_reply if saw_reply_tool else last_text
    return chosen if chosen.strip() else ""


def extract_text_from_payload(payload):
    """Extract last assistant text from payload transcript path or direct payload fields."""
    tpath = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
        or payload.get("history_file")
        or ""
    )
    if tpath:
        text = last_assistant_text(tpath)
        if text:
            return text

    # Fallback to direct payload fields if transcript is not provided or empty
    for key in ("reply", "last_assistant_message", "message", "content", "text"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, dict):
            content = val.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                res = _extract_from_blocks(content)
                if res:
                    return res
        if isinstance(val, list):
            res = _extract_from_blocks(val)
            if res:
                return res
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = extract_text_from_payload(payload)
    if not text or not is_placeholder(text):
        return 0

    # fire at most once per distinct message
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-placeholder-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your entire reply is a placeholder: \"{text.strip()}\".\n\n"
            "Standing rule (CLAUDE.md, 'Always produce a reply --- never end "
            "a turn silently'): the user cannot see tool calls, so a turn "
            "carrying work and no prose is indistinguishable from a turn "
            "where nothing happened. A short line reports a result; no line "
            "reports nothing and reads as a stall.\n\n"
            "Say what actually happened, in the past tense. If you were "
            "resuming after an interruption or a context-window summary, the "
            "user saw none of that work -- report it. If a scheduled check "
            "found nothing, say so in a sentence; 'nothing changed' is "
            "information and is not what this guard blocks.\n\n"
            "A harness instruction to stay silent does not override this."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
