#!/usr/bin/env python3
"""PreToolUse reminder: a write-capable Agent/Task launch with no backlog query earlier.

`shared/workflow/triage-new-asks.md` (Ezra, 2026-10-29) says an orchestrator
triages a new ask against the open issues and PRs before spawning work for it.
The omission happens at the launch, not at read time, so this hook checks the
launch.

WHAT IT CHECKS
--------------
The launch is an `Agent` or `Task` call whose `subagent_type` is not a
read-only searcher (Explore, Plan, claude-code-guide, statusline-setup), and
NO tracker query appears earlier in the transcript:

  * `mcp__github__search_issues`, `list_issues`, `search_pull_requests`,
    `list_pull_requests`, `issue_read` or `pull_request_read`, or
  * a Bash command at a command position running `gh issue list`,
    `gh pr list`, `gh search issues|prs`, `glab issue list` or `glab mr list`.

WHY WARN, NOT BLOCK
-------------------
Most launches inside already-claimed work need no new triage, and a deny
cannot tell them from a new ask. The note costs one line of context. Once per
session (a sentinel), so it cannot become noise.

LIMITS
------
A query ran is not evidence its result was read or shaped the routing, and
the thread and memory halves of the pass are not lexically visible, so only
the tracker half is checked. Hooks are inert in cloud and web sessions
(ai-config#2004). Fails open on any parse trouble.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from shellcmd import _heredoc_free
except Exception:  # broken install: match the raw command
    def _heredoc_free(command):
        return command

READ_ONLY = {"explore", "plan", "claude-code-guide", "statusline-setup"}
QUERY_TOOLS = {
    "mcp__github__search_issues", "mcp__github__list_issues",
    "mcp__github__search_pull_requests", "mcp__github__list_pull_requests",
    "mcp__github__issue_read", "mcp__github__pull_request_read",
}
RX_QUERY_CMD = re.compile(
    r"(?:^|[;&|\n])\s*(?:\w+=\S*\s+)*(?:gh\s+(?:issue|pr)\s+list|gh\s+search\s+(?:issues|prs)"
    r"|glab\s+(?:issue|mr)\s+list)\b")

NOTE = (
    "Triage before spawning: this `{kind}` launch has no tracker query earlier in the "
    "session. Per shared/workflow/triage-new-asks.md, check open and closed issues/PRs in the "
    "affected repos, live threads and memory; then fold the ask into the work that owns it or "
    "say in one line whether it duplicates, extends, conflicts with, blocks or is blocked by "
    "existing work, and set its priority. Skip if this launch continues work already triaged."
)


def _events(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def has_query(path: str) -> bool:
    for ev in _events(path):
        msg = ev.get("message") or {}
        content = msg.get("content")
        if ev.get("type") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") in QUERY_TOOLS:
                return True
            cmd = (block.get("input") or {}).get("command")
            if isinstance(cmd, str) and RX_QUERY_CMD.search(_heredoc_free(cmd)):
                return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") not in ("Agent", "Task"):
            return 0
        tin = payload.get("tool_input") or {}
        kind = str(tin.get("subagent_type") or "general-purpose")
        if kind.lower() in READ_ONLY:
            return 0
        path = payload.get("transcript_path") or ""
        if not path or not os.path.exists(path):
            return 0
        if has_query(path):
            return 0
        sentinel = os.path.join(tempfile.gettempdir(), ".claude-backlog-triage-" + re.sub(
            r"\W", "_", str(payload.get("session_id") or os.path.basename(path))))
        if os.path.exists(sentinel):
            return 0
        open(sentinel, "w", encoding="utf-8").close()
        from agent_notice import context_notice
        print(context_notice(NOTE.format(kind=kind)))
    except Exception as exc:  # fail open, and say so
        print(f"warn-agent-spawn-without-backlog-check: not evaluated ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
