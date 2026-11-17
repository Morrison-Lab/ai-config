#!/usr/bin/env python3
"""PreToolUse: a project thread must not say a PR is "in the merge queue" when nothing was enqueued.

ai-config#5754. On 2026-11-17 two owner threads (lds#2687, lds#2685) told Ezra a
content PR had "gone into the merge queue" when it was only waiting for his
`mwc` line, which reads as if GitHub auto-merge or a merge queue were on. A
project-memory note had recommended the phrase as a way past
no-merge-ask-in-post-message.py, so the hook that blocks one false-comfort
phrasing taught a second.

Scope: a thread session's user-visible tools (`mcp__hearthbot__post_message`,
`reply`, `update_message`, `edit_message`, `request_decision`). A thread session
is recognized as in no-merge-ask-in-post-message.py: its transcript says "You are
a Thread Session". The coordinator and other sessions are never blocked.

Blocks (deny) text that says "merge queue" (or "merge-queue") unless the
transcript shows something was enqueued: a `tool_use` block that calls
`enable_pr_auto_merge`, or one whose input (a Bash command) requests
`ccr/auto_merge` or runs `gh pr merge --auto`. Only `tool_use` blocks count, so
the hook's own denial text, a doc a thread read, or a tool listing naming the
tool cannot unlock it. The truthful report is that
the final head was sent on and it waits on a merge in the runner. A negated or
quoted mention is denied too, as in the sibling hook: the fix is one rewording.
`ALLOW_MERGE_QUEUE_CLAIM=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_MERGE_QUEUE_CLAIM"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")
THREAD_SESSION = "You are a Thread Session"
CLAIM = re.compile(r"\bmerge[\s-]+queue\b", re.I)
ENQUEUED_TOOL = re.compile(r"enable_pr_auto_merge$")
ENQUEUED_INPUT = re.compile(r"ccr/auto_merge|gh\s+pr\s+merge\b[^\n\"]{0,80}--auto", re.I)

REASON = (
    '[hook: no-merge-queue-claim-in-post-message] This post says "{phrase}", but nothing in this '
    "transcript enqueued a PR (no enable_pr_auto_merge, auto_merge request or "
    "`gh pr merge --auto`), so the phrase reads as if GitHub would merge it by itself "
    "(ai-config#5754, 2026-11-17: lds#2687 and lds#2685 both told Ezra this while the PR "
    "waited for his mwc line).\n"
    "Say what is true instead: the final head was sent on, and it waits on a merge in the "
    "runner. Set ALLOW_MERGE_QUEUE_CLAIM=1 only when a queue or auto-merge really exists."
)


def read_head(path, limit=3_000_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except (OSError, TypeError, ValueError):
        return ""


def tool_uses(node):
    """Yield every `tool_use` block nested anywhere in a parsed transcript line."""
    if isinstance(node, dict):
        if node.get("type") == "tool_use":
            yield node
        for value in node.values():
            yield from tool_uses(value)
    elif isinstance(node, list):
        for value in node:
            yield from tool_uses(value)


def enqueued(transcript: str) -> bool:
    """True when some tool_use block in the JSONL transcript enqueued a PR."""
    for line in transcript.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        for block in tool_uses(record):
            if ENQUEUED_TOOL.search(str(block.get("name") or "")):
                return True
            if ENQUEUED_INPUT.search(json.dumps(block.get("input"))):
                return True
    return False


def user_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    m = CLAIM.search(user_text(tool_input))
    if not m:
        return None
    path = payload.get("transcript_path")
    if THREAD_SESSION not in read_head(path, 200_000) or enqueued(read_head(path)):
        return None
    return REASON.format(phrase=" ".join(m.group(0).split()))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = denial(payload)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
