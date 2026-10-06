#!/usr/bin/env python3
"""Stop-hook guard: warn when a stopping-point declaration is missing from a final reply.

Treats the last reply of a turn as a stopping point, including conversational
question-answering replies (#4308). Warns via systemMessage rather than blocking
when that reply omits an explicit statement of whether the session is done or not.
Handles streamed assistant chunk concatenation (#2500).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from fences import strip_code, strip_fences
except Exception:
    strip_code = strip_fences = None

try:
    from transcript_meta import is_skill_load_meta
except Exception as _exc:  # broken install: degrade, do not fail open silently
    print(f"require-stopping-point: cannot load scripts/lib/transcript_meta.py "
          f"({_exc}); a mid-turn skill load will wrongly reset the "
          f"accumulated reply",
          file=sys.stderr)

    def is_skill_load_meta(entry):  # noqa: D103 -- fail-open fallback
        return False

# In a project-thread session every user-visible sentence is the `text` input
# of an `mcp__hearthbot__reply` tool call, never an assistant text block.
# Measured on ai-config#3798/#3804: a reader that only walks `type == "text"` blocks
# is blind to the whole reply.
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)

RX_LINE = re.compile(
    r"^\s*(?:[-*]\s+|\d+\.\s+|#{1,6}\s+)?(?:\*\*)?Stopping Point:?(?:\*\*)?:?\s*(?:Clean\b|Not (?:a )?clean\b)",
    re.IGNORECASE,
)
RX_SESSION_STATUS = re.compile(
    r"\bsession\s+(?:is\s+)?(?:not\s+done|done|not\s+finished|finished|not\s+complete|complete|ongoing|in\s+progress)\b",
    re.IGNORECASE,
)
RX_SECTION_BREAK = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)")
RX_INDENTED_CODE = re.compile(r"^(?: {4,}|\t)(?![-*]\s+|\d+\.\s+)")
INLINE_CODE_RX = re.compile(r"`[^`\n]+`")


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


def has_stopping_point_declaration(text: str) -> bool:
    if not text:
        return False
    if strip_code is not None:
        stripped = strip_code(text, swallow_unclosed=False)
    elif strip_fences is not None:
        stripped = strip_fences(text, swallow_unclosed=False)
    else:
        stripped = text
    lines = stripped.splitlines()
    for i, line in enumerate(lines):
        if RX_INDENTED_CODE.match(line):
            continue
        line_no_inline = INLINE_CODE_RX.sub("", line)
        if RX_LINE.search(line_no_inline):
            combined_parts = [line_no_inline]
            for j in range(i + 1, min(len(lines), i + 6)):
                nxt = INLINE_CODE_RX.sub("", lines[j]).strip()
                if not nxt:
                    continue
                if RX_SECTION_BREAK.match(nxt) and not RX_LINE.search(nxt):
                    break
                combined_parts.append(nxt)
            combined = " ".join(combined_parts)
            if RX_SESSION_STATUS.search(combined):
                return True
    return False


def last_text(path: str) -> str:
    last_text_val = ""
    last_reply = ""
    saw_reply_tool = False
    curr_msg_id = None
    consecutive_assistant = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                etype = event.get("type") or event.get("role") or ""
                source = event.get("source") or ""
                if is_skill_load_meta(event):
                    # A loaded skill body arrives as a `type: "user"` entry
                    # with `isMeta: true` and a `sourceToolUseID`. It was
                    # never a real prompt, so it must not reset the
                    # accumulated reply the way a genuine new user turn does
                    # (ai-config#3860). `isMeta` alone is not this test: a
                    # scheduled check-in continuation also carries `isMeta:
                    # true` but no `sourceToolUseID`, and it IS a genuine
                    # new turn -- see scripts/lib/transcript_meta.py.
                    continue
                if (
                    etype == "user"
                    or etype == "USER_INPUT"
                    or source == "USER_EXPLICIT"
                ) and not event.get("isSidechain"):
                    blocks = (
                        (event.get("message") or {}).get("content")
                        or event.get("content")
                        or []
                    )
                    is_tool_result = (
                        event.get("type") == "tool_result"
                        or (
                            isinstance(blocks, list)
                            and any(
                                isinstance(b, dict) and b.get("type") == "tool_result"
                                for b in blocks
                            )
                        )
                    )
                    if not is_tool_result:
                        last_text_val = ""
                        last_reply = ""
                        saw_reply_tool = False
                    curr_msg_id = None
                    consecutive_assistant = False
                    continue
                if event.get("isSidechain"):
                    continue
                if event.get("type") == "assistant" or event.get("role") == "assistant":
                    blocks = (
                        (event.get("message") or {}).get("content")
                        or event.get("content")
                        or []
                    )
                    msg_id = (event.get("message") or {}).get("id") or event.get("id")
                    has_non_reply_tool = (
                        isinstance(blocks, list)
                        and any(
                            isinstance(b, dict)
                            and b.get("type") == "tool_use"
                            and not REPLY_TOOL_RX.search(b.get("name") or "")
                            for b in blocks
                        )
                    )
                    if isinstance(blocks, list):
                        text = "".join(
                            b.get("text", "")
                            for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        for b in blocks:
                            if (
                                isinstance(b, dict)
                                and b.get("type") == "tool_use"
                                and REPLY_TOOL_RX.search(b.get("name") or "")
                            ):
                                saw_reply_tool = True
                            payload = _reply_payload(b)
                            if payload.strip():
                                last_reply = payload
                    elif isinstance(blocks, str):
                        text = blocks
                    else:
                        text = ""

                    if has_non_reply_tool:
                        if text.strip():
                            last_text_val = text
                        consecutive_assistant = False
                        curr_msg_id = None
                    elif text:
                        is_same_message = (
                            (msg_id and curr_msg_id and msg_id == curr_msg_id)
                            or (
                                consecutive_assistant
                                and not msg_id
                                and not curr_msg_id
                                and last_text_val
                                and text.startswith(last_text_val)
                            )
                        )
                        if is_same_message:
                            if last_text_val and text.startswith(last_text_val):
                                last_text_val = text
                            else:
                                last_text_val += text
                        else:
                            last_text_val = text
                            consecutive_assistant = True
                            curr_msg_id = msg_id
                elif (
                    event.get("type") in {"PLANNER_RESPONSE", "GENERIC"}
                    or event.get("source") == "MODEL"
                ):
                    msg_id = (
                        (event.get("message") or {}).get("id")
                        or event.get("id")
                        or (str(event["step_index"]) if "step_index" in event else None)
                    )
                    has_tool_calls = bool(event.get("tool_calls"))
                    content = event.get("content")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                    else:
                        text = ""

                    if has_tool_calls:
                        if text.strip():
                            last_text_val = text
                        consecutive_assistant = False
                        curr_msg_id = None
                    elif text:
                        is_same_message = (
                            (msg_id and curr_msg_id and msg_id == curr_msg_id)
                            or (
                                consecutive_assistant
                                and not msg_id
                                and not curr_msg_id
                                and last_text_val
                                and text.startswith(last_text_val)
                            )
                        )
                        if is_same_message:
                            if last_text_val and text.startswith(last_text_val):
                                last_text_val = text
                            else:
                                last_text_val += text
                        else:
                            last_text_val = text
                            consecutive_assistant = True
                            curr_msg_id = msg_id
    except Exception:
        return ""
    chosen = last_reply if saw_reply_tool else last_text_val
    return chosen if chosen.strip() else ""


def _extract_from_blocks(blocks):
    """Extract assistant text from a list of blocks respecting reply-tool precedence."""
    last_text_parts = []
    last_reply = ""
    saw_reply_tool = False
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            txt = b.get("text") or ""
            if txt:
                last_text_parts.append(txt)
        if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
            saw_reply_tool = True
        payload = _reply_payload(b)
        if payload.strip():
            last_reply = payload
    last_text_val = "".join(last_text_parts)
    chosen = last_reply if saw_reply_tool else last_text_val
    return chosen if chosen.strip() else ""


def extract_text_from_payload(payload):
    """Extract last assistant text from payload transcript path or direct payload fields."""
    if not isinstance(payload, dict):
        return ""
    tpath = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
        or payload.get("history_file")
        or ""
    )
    if tpath:
        text = last_text(tpath)
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
            txt = val.get("text")
            if isinstance(txt, str) and txt.strip():
                return txt
        if isinstance(val, list):
            res = _extract_from_blocks(val)
            if res:
                return res
    return ""


def extract_turn_id(payload: dict) -> str:
    """Extract turn or prompt identifier from payload or transcript."""
    for key in (
        "prompt_id",
        "promptId",
        "turn_id",
        "turnId",
        "step_index",
        "stepIndex",
    ):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    tpath = (
        payload.get("transcript_path")
        or payload.get("transcriptPath")
        or payload.get("transcript")
        or payload.get("history_file")
        or ""
    )
    if tpath and os.path.exists(tpath):
        try:
            with open(tpath, "r", encoding="utf-8") as f:
                last_id = ""
                line_count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    line_count += 1
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(event, dict):
                        continue
                    ev_id = None
                    for k in (
                        "prompt_id",
                        "promptId",
                        "turn_id",
                        "turnId",
                        "step_index",
                        "stepIndex",
                    ):
                        val = event.get(k)
                        if val is not None and str(val).strip():
                            ev_id = str(val).strip()
                            break
                    if ev_id is None:
                        val = (event.get("message") or {}).get("id") or event.get("id")
                        if val is not None and str(val).strip():
                            ev_id = str(val).strip()
                    if ev_id is not None:
                        last_id = ev_id
                if last_id:
                    return last_id
                if line_count > 0:
                    return f"line_{line_count}"
        except Exception:
            pass
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # Harness-mode exception: automated non-interactive runs whose output is posted
    # somewhere by a harness are permitted to omit the declaration
    # (shared/workflow/flag-session-boundaries.md).
    if (
        payload.get("harness_mode")
        or payload.get("non_interactive")
        or payload.get("is_non_interactive")
        or os.environ.get("HARNESS_MODE") in {"1", "true", "True"}
        or os.environ.get("NON_INTERACTIVE") in {"1", "true", "True"}
        or os.environ.get("CLAUDE_NON_INTERACTIVE") in {"1", "true", "True"}
    ):
        return 0

    text = extract_text_from_payload(payload)
    if not text or has_stopping_point_declaration(text):
        return 0

    # Scope sentinel deduplication to current session and turn so identical replies
    # in later turns or other sessions are not silently suppressed.
    session_id = (
        payload.get("session_id")
        or payload.get("sessionId")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("SESSION_ID")
        or ""
    )
    turn_id = extract_turn_id(payload)
    key_src = f"{session_id}:{turn_id}:{text}"
    key = hashlib.sha256(key_src.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-stopping-point-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(
        json.dumps(
            {
                "systemMessage": (
                    "State whether the session is done or not using "
                    "`**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending` or "
                    "`**Stopping Point**: Not a clean stopping point / work remains queued: session not done; <details>` "
                    "before ending the turn."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
