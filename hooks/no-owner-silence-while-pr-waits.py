#!/usr/bin/env python3
"""Stop: an owner thread with a PR waiting must report to the coordinator hourly.

ai-config#5116. Coordinator hourly check, 2026-11-08 18:57Z: an owner thread had
posted nothing since 17:26Z while its PR (gha#1681) waited in the merge queue,
so the coordinator could not tell a queued thread from a stalled one.

Can a Stop hook read the timestamp? Yes. The Stop payload carries
`transcript_path`, and every transcript entry has an ISO `timestamp`, so the
time of the last `post_message` / `message_coordinator` / `message_thread`
tool_use is readable.

What it cannot read is whether the PR is still open: that is forge state, and a
hook does not call the forge. It uses the transcript as the proxy. The thread
counts as an owner with a PR waiting when a create or subscribe call succeeded
(the paired tool_result is not an error) and it has not resolved its thread
since (`set_thread_resolved`). A merged PR whose thread is still open therefore
blocks too, and the one reply that ends the silence also clears it.

Blocks the stop when the last report is an hour old (the thread's first entry
counts when it never reported). `agent_notice.stop_notice` blocks at most once
per turn and never while `stop_hook_active` is set, so it cannot wedge a
session. Fails OPEN on any parse trouble.
"""
import datetime
import json
import os
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from agent_notice import stop_notice
except Exception:
    sys.exit(0)

LIMIT_S = int(os.environ.get("OWNER_SILENCE_LIMIT_S", "3600"))
REPORT_TOOLS = {"mcp__hearthbot__post_message", "mcp__hearthbot__message_coordinator",
                "mcp__hearthbot__message_thread"}
PR_TOOLS = {"mcp__github__create_pull_request", "mcp__claude-code-remote__subscribe_pr_activity"}
RESOLVE = "mcp__hearthbot__set_thread_resolved"

REASON = (
    "[hook: no-owner-silence-while-pr-waits] You own a PR in this project thread and have "
    "reported nothing for {mins} minutes (last report {last}). The coordinator cannot tell a "
    "queued thread from a stalled one. Post one status now with post_message "
    "(PR, head, what it waits on), and while it waits pick up the next backlog item. "
    "Never merge main into a queued PR that is already clean. ai-config#5116."
)


def parse_ts(s):
    return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def now():
    override = os.environ.get("OWNER_SILENCE_NOW")
    return parse_ts(override) if override else datetime.datetime.now(datetime.timezone.utc)


def scan(path):
    """(first_ts, last_report_ts, owns_pr) from the transcript."""
    first = last = None
    owns = False
    pending = {}
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        ts = e.get("timestamp")
        if ts and first is None:
            first = ts
        msg = e.get("message")
        blocks = msg.get("content") if isinstance(msg, dict) else None
        for b in blocks if isinstance(blocks, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name = b.get("name")
                if name in REPORT_TOOLS and ts:
                    last = ts
                elif name in PR_TOOLS:
                    pending[b.get("id")] = name
                elif name == RESOLVE and (b.get("input") or {}).get("resolved", True):
                    owns = False
            elif b.get("type") == "tool_result":
                if pending.pop(b.get("tool_use_id"), None) and not b.get("is_error"):
                    owns = True
    return first, last, owns


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if payload.get("stop_hook_active") or not path or not os.path.isfile(path):
            return 0
        first, last, owns = scan(path)
        ref = last or first
        if not owns or not ref:
            return 0
        age = (now() - parse_ts(ref)).total_seconds()
        if age < LIMIT_S:
            return 0
        message = REASON.format(
            mins=int(age // 60), last=ref if last else "none since the thread began")
        print(stop_notice(payload, message, "no-owner-silence-while-pr-waits"))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
