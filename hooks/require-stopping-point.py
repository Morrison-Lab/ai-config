#!/usr/bin/env python3
"""Stop-hook guard: require a stopping-point declaration in each final reply."""
import hashlib
import json
import os
import re
import sys
import tempfile

RX = re.compile(r"\*\*Stopping Point\*\*:\s*(?:Clean|Not clean)", re.I)


def last_text(path):
    last = ""
    try:
        for line in open(path, errors="ignore"):
            event = json.loads(line)
            if event.get("type") == "assistant":
                text = "".join(block.get("text", "") for block in (event.get("message") or {}).get("content", []) if isinstance(block, dict))
                if text.strip():
                    last = text
    except Exception:
        return ""
    return last


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = last_text(payload.get("transcript_path", ""))
    if not text or RX.search(text):
        return 0
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-stopping-point-{key}")
    if os.path.exists(sentinel):
        return 0
    open(sentinel, "w").close()
    print(json.dumps({"decision": "block", "reason": "State `**Stopping Point**: Clean stopping point reached` or `**Stopping Point**: Not clean — <remaining work>` before ending the turn."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
