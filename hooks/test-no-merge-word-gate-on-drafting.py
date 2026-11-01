#!/usr/bin/env python3
"""Test the no-merge-word-gate-on-drafting guard (ai-config#4866).

The negative cases matter most: a sentence that gates the MERGE on the word is
correct and must pass.

Run: python3 hooks/test-no-merge-word-gate-on-drafting.py \
       hooks/no-merge-word-gate-on-drafting.py
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def clear_sentinels():
    """Sentinels outlive the process, so clear them to keep the suite repeatable."""
    for path in glob.glob(os.path.join(tempfile.gettempdir(), ".claude-mwc-gate-drafting-*")):
        try:
            os.unlink(path)
        except OSError:
            pass


def blocked(text):
    msg = {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        fh.write(json.dumps(msg) + "\n")
        path = fh.name
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True,
        text=True,
    ).stdout.strip()
    os.unlink(path)
    return bool(out) and json.loads(out).get("decision") == "block"


CASES_BLOCK = [
    # The measured instance.
    "Merged. The later PRs need a fresh mwc.",
    "The next PRs need a fresh mwc, so I am stopping here.",
    "I'll draft the remaining PRs once you type mwc.",
    "Waiting for your merge word before opening the next PR.",
    "**Stopping Point**: Not a clean stopping point: continuing the other labs is pending mwc.",
    # A merge named in an earlier clause does not excuse a later one.
    "After merging this one, the next PRs still need mwc.",
    "Merged the first PR, but drafting the next PR waits on mwc.",
    # The gate clause may lead and the gated work follow in another clause.
    "Still need mwc, so the next PRs stay undrafted.",
    "Waiting on mwc, the next PRs are paused.",
]

CASES_PASS = [
    # The merge is what the word gates.
    "I'll merge the next PRs after mwc.",
    "Each of the later PRs needs mwc before it merges.",
    "The merge needs your merge word.",
    # Negation.
    "Drafting the next PRs needs no merge word.",
    "The remaining PRs do not need mwc to be opened.",
    # No merge word at all.
    "The next PRs need a review first.",
    "Opened the next PR and pushed it.",
    # Code span.
    "The hook matches `the next PRs need a fresh mwc`.",
]


def main():
    clear_sentinels()
    failures = []
    for text in CASES_BLOCK:
        if not blocked(text):
            failures.append(("should block", text))
    for text in CASES_PASS:
        if blocked(text):
            failures.append(("should pass", text))
    for kind, text in failures:
        print(f"FAIL ({kind}): {text}")
    if failures:
        return 1
    print(f"ok: {len(CASES_BLOCK)} block cases, {len(CASES_PASS)} pass cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
