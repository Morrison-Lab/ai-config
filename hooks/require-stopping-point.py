#!/usr/bin/env python3
"""Stop-hook guard: require a stopping-point declaration in each final reply."""
import hashlib
import json
import os
import re
import sys
import tempfile

RX_LINE = re.compile(
    r"^(?:[-*]\s+|\d+\.\s+|#{1,6}\s+)?(?:\*\*)?Stopping Point(?:\*\*)?:\s*(?:Clean|Not (?:a )?clean\b)",
    re.IGNORECASE | re.MULTILINE,
)

FENCE_RX = re.compile(r"(`{3,}|~{3,}).*?\n.*?\n\1", re.DOTALL)
INLINE_CODE_RX = re.compile(r"`[^`\n]+`")


def has_stopping_point_declaration(text: str) -> bool:
    if not text:
        return False
    stripped = FENCE_RX.sub("", text)
    stripped = INLINE_CODE_RX.sub("", stripped)
    return bool(RX_LINE.search(stripped))


def last_text(path: str) -> str:
    last = ""
    try:
        for line in open(path, errors="ignore"):
            event = json.loads(line)
            if event.get("type") == "assistant":
                text = "".join(
                    block.get("text", "")
                    for block in (event.get("message") or {}).get("content", [])
                    if isinstance(block, dict)
                )
                if text.strip():
                    last = text
    except Exception:
        return ""
    return last


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = last_text(payload.get("transcript_path", ""))
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
