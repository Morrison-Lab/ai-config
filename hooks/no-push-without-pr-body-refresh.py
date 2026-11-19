#!/usr/bin/env python3
"""Stop hook: a turn that pushes must refresh the PR's title and body after it.

THE GAP THIS FILLS (ai-config#5871)
-----------------------------------
On 2026-11-19 agy returned NOT CLEAN on lds#2879 because the PR body named
only two of the three memory entries in its diff: a later push added the
third, and the body was never updated.
ardi.md's round checklist already asks for every touched PR description to be
re-read, but that rule is consulted when a round starts and broken at push
time, so this hook fires at the end of the turn that pushed.

WHAT IT CHECKS
--------------
In the current turn (the records after the last real user prompt), if the
last PUSH (`git push`, or the MCP `push_files`, `create_or_update_file` and
`delete_file` tools) has no later PR-body WRITE (`update_pull_request` with a
title or body, `create_pull_request`, `gh pr edit` with `--title`, `--body`
or `--body-file`, `gh pr create`, or a `gh api` PATCH on `pulls/N`), the stop
is blocked once with the rule.

Why it blocks once instead of refusing: whether the body already covers the
whole diff is a judgment the transcript cannot settle (a push that answers a
review nit often leaves the body accurate), so the reply may say the body
still covers the diff and stop.
Blocks at most once per turn (agent_notice.stop_notice) and fails open on any
parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "scripts", "lib")
if os.path.isdir(_LIB):
    sys.path.insert(0, os.path.realpath(_LIB))
from agent_notice import stop_notice  # noqa: E402

PUSH_TOOLS = ("push_files", "create_or_update_file", "delete_file")
RX_PUSH_CMD = re.compile(r"(?:^|[;&|(]\s*|\s)git(?:\s+-C\s+\S+)?\s+push\b")
RX_BODY_CMD = re.compile(
    r"\bgh\s+pr\s+create\b"
    r"|\bgh\s+pr\s+edit\b[^;&|]*?(?:--title|--body|--body-file|\s-t\s|\s-b\s|\s-F\s)"
    r"|\bgh\s+api\b(?=[^;&|]*(?:-X\s*PATCH|--method\s+PATCH))[^;&|]*\bpulls/\d+(?![/\w])")


def blocks(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def is_real_prompt(record):
    if record.get("type") != "user" or record.get("isMeta"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    return any(b.get("type") == "text" for b in blocks(record))


def classify(block):
    """Return 'push', 'body' or None for one tool_use block."""
    name = str(block.get("name", ""))
    inputs = block.get("input") or {}
    command = str(inputs.get("command", "")) if name == "Bash" else ""
    if name.endswith(PUSH_TOOLS) or (command and RX_PUSH_CMD.search(command)):
        return "push"
    if name.endswith("create_pull_request"):
        return "body"
    if name.endswith("update_pull_request") and (inputs.get("body") or inputs.get("title")):
        return "body"
    if command and RX_BODY_CMD.search(command):
        return "body"
    return None


def unrefreshed_push(path):
    events = []
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if is_real_prompt(record):
                events = []
                continue
            for block in blocks(record):
                if block.get("type") == "tool_use":
                    kind = classify(block)
                    if kind:
                        events.append(kind)
    last_push = max((i for i, kind in enumerate(events) if kind == "push"), default=None)
    return last_push is not None and "body" not in events[last_push + 1:]


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if not path or not os.path.exists(path) or not unrefreshed_push(path):
            return 0
    except (OSError, ValueError):
        return 0
    print(stop_notice(
        payload,
        "This turn pushed and did not update a PR title or body afterwards. "
        "After a push to an open PR, update its title and body in the same turn so they "
        "cover the whole diff: re-read the diff against the body, and list every file, "
        "entry or change it now holds (ai-config#5871; lds#2879 drew a NOT CLEAN review "
        "because its body named two of three entries). If the body already covers the "
        "whole diff, or the push opened no PR yet, say so in one line and stop.",
        "no-push-without-pr-body-refresh"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
