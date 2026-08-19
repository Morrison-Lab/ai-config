#!/usr/bin/env python3
"""Block a status-only reply after CI identifies a missing hook test.

This is intentionally narrow. CI's exact missing-test diagnostic names both
the hook and the test file, making the repair mechanically decidable. A status
request does not turn that in-scope repair into a report-only task.
"""
import json
import os
import re
import sys

MISSING = re.compile(r"FAIL:\s+hooks/[^\s]+\.py has no test \((test-[^)]+\.py)\)")


def scan(path):
    required = set()
    repaired = set()
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                blocks = (record.get("message") or {}).get("content") or []
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        text = json.dumps(block.get("content") or block.get("text") or "")
                        required.update(MISSING.findall(text))
                    if block.get("type") != "tool_use":
                        continue
                    payload = block.get("input") or {}
                    blob = json.dumps(payload)
                    if block.get("name") in {"Write", "Edit", "NotebookEdit"}:
                        blob = str(payload.get("file_path") or "")
                    for name in required:
                        if name in blob:
                            repaired.add(name)
    except Exception:
        return set()
    return required - repaired


def main():
    try:
        missing = scan(json.load(sys.stdin).get("transcript_path") or "")
    except Exception:
        return
    if missing:
        names = ", ".join(sorted(missing))
        print(json.dumps({"decision": "block", "reason": (
            f"CI supplied a concrete missing-hook-test repair ({names}); add "
            "that test and run it before reporting status. A known in-scope "
            "CI repair is work to do, not status to relay.")}))


if __name__ == "__main__":
    main()
