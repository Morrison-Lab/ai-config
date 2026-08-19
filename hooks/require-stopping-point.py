#!/usr/bin/env python3
"""Stop-hook guard: require a stopping-point declaration in each final reply."""
import hashlib
import json
import os
import re
import sys
import tempfile

FENCE_LINE_RX = re.compile(r"^\s*([`~]{3,})(?:[a-zA-Z0-9_-]+)?\s*$")
RX_LINE = re.compile(
    r"^\s*(?:[-*]\s+|\d+\.\s+|#{1,6}\s+)?(?:\*\*)?Stopping Point:?(?:\*\*)?:?\s*(?:Clean\b|Not (?:a )?clean\b)",
    re.IGNORECASE,
)
INLINE_CODE_RX = re.compile(r"`[^`\n]+`")


def has_stopping_point_declaration(text: str) -> bool:
    if not text:
        return False
    lines = text.splitlines()
    fence_indices = [idx for idx, line in enumerate(lines) if FENCE_LINE_RX.match(line)]

    def get_code_line_indices(fences):
        code_lines = set()
        for i in range(0, len(fences) - 1, 2):
            for l in range(fences[i], fences[i + 1] + 1):
                code_lines.add(l)
        return code_lines

    candidate_code_sets = []
    if len(fence_indices) % 2 == 0:
        candidate_code_sets.append(get_code_line_indices(fence_indices))
    else:
        candidate_code_sets.append(get_code_line_indices(fence_indices[1:]))
        candidate_code_sets.append(get_code_line_indices(fence_indices[:-1]))

    for idx, line in enumerate(lines):
        stripped = INLINE_CODE_RX.sub("", line)
        if RX_LINE.search(stripped):
            for code_set in candidate_code_sets:
                if idx not in code_set:
                    return True
    return False


def last_text(path: str) -> str:
    last = ""
    try:
        f = open(path, errors="ignore")
    except Exception:
        return ""
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") == "assistant":
                text = "".join(
                    block.get("text", "")
                    for block in (event.get("message") or {}).get("content", [])
                    if isinstance(block, dict)
                )
                if text.strip():
                    last = text
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
