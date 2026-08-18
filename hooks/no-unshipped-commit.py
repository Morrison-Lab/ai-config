#!/usr/bin/env python3
"""Stop-hook guard: a successful commit must be pushed before reporting done."""
import hashlib
import json
import os
import re
import sys
import tempfile

COMMIT = re.compile(r"(?:^|[;&|]\s*)git\s+commit\b")
PUSH = re.compile(r"(?:^|[;&|]\s*)git\s+push\b")
CREATE = re.compile(r"(?:^|[;&|]\s*)gh\s+pr\s+create\b")


def pending_commit(path):
    pending = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("type") != "assistant":
                    continue
                for block in (record.get("message") or {}).get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in {"Bash", "bash", "run_command"}:
                        continue
                    command = str((block.get("input") or {}).get("command") or (block.get("input") or {}).get("cmd") or "")
                    if COMMIT.search(command):
                        pending = command
                    if pending and (PUSH.search(command) or CREATE.search(command)):
                        pending = None
    except Exception:
        return None
    return pending


def main():
    try:
        path = json.load(sys.stdin).get("transcript_path") or ""
    except Exception:
        return
    command = pending_commit(path)
    if not command:
        return
    key = hashlib.sha256((path + command).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-unshipped-commit-{key}")
    if os.path.exists(sentinel):
        return
    open(sentinel, "w").close()
    print(json.dumps({"decision": "block", "reason": "A commit was made without a later push or PR creation. Push the branch, open or verify its PR, then report status. The standing rule is executable work, not a handoff item."}))


if __name__ == "__main__":
    main()
