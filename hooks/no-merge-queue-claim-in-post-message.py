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
transcript shows something was enqueued: a `enable_pr_auto_merge` call, a
`ccr/auto_merge` request, or `gh pr merge --auto`. The truthful report is that
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
ENQUEUED = re.compile(r"enable_pr_auto_merge|ccr/auto_merge|gh\s+pr\s+merge\b[^\n\"]{0,80}--auto", re.I)

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
    transcript = read_head(payload.get("transcript_path"))
    if THREAD_SESSION not in transcript[:200_000] or ENQUEUED.search(transcript):
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
