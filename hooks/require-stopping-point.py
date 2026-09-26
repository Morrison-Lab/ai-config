#!/usr/bin/env python3
"""Stop-hook guard: require a stopping-point declaration in each final reply."""
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
    for line in stripped.splitlines():
        if RX_INDENTED_CODE.match(line):
            continue
        line_no_inline = INLINE_CODE_RX.sub("", line)
        if RX_LINE.search(line_no_inline):
            return True
    return False


def last_text(path: str) -> str:
    last_text_val = ""
    last_reply = ""
    saw_reply_tool = False
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
                    continue
                if event.get("isSidechain"):
                    continue
                if event.get("type") == "assistant" or event.get("role") == "assistant":
                    blocks = (
                        (event.get("message") or {}).get("content")
                        or event.get("content")
                        or []
                    )
                    if isinstance(blocks, list):
                        text = "".join(
                            b.get("text", "")
                            for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if text.strip():
                            last_text_val = text
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
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text_val = blocks
                elif (
                    event.get("type") in {"PLANNER_RESPONSE", "GENERIC"}
                    or event.get("source") == "MODEL"
                ):
                    content = event.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text_val = content
                    elif isinstance(content, list):
                        text = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if text.strip():
                            last_text_val = text
    except Exception:
        return ""
    chosen = last_reply if saw_reply_tool else last_text_val
    return chosen if chosen.strip() else ""


def _extract_from_blocks(blocks):
    """Extract assistant text from a list of blocks respecting reply-tool precedence."""
    last_text_val = ""
    last_reply = ""
    saw_reply_tool = False
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            txt = b.get("text") or ""
            if txt.strip():
                last_text_val = txt
        if b.get("type") == "tool_use" and REPLY_TOOL_RX.search(b.get("name") or ""):
            saw_reply_tool = True
        payload = _reply_payload(b)
        if payload.strip():
            last_reply = payload
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = extract_text_from_payload(payload)
    if not text or has_stopping_point_declaration(text):
        return 0
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-stopping-point-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "State `**Stopping Point**: Clean stopping point reached` or "
                    "`**Stopping Point**: Not a clean stopping point / work remains queued: <details>` "
                    "before ending the turn."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
