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
counts as an owner with a PR waiting when it has created or subscribed to a PR
and has not resolved its thread since (`set_thread_resolved`). A merged PR whose
thread is still open therefore blocks too, and the one reply that ends the
silence also clears it.

Blocks the stop when the last report is an hour old (the thread's first entry
counts when it never reported). Fires at most once per user turn, so it cannot
wedge a session. Fails OPEN on any parse trouble.
"""
import datetime
import json
import os
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

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
    """(first_ts, last_report_ts, owns_pr, turn_key) from the transcript."""
    from transcript_meta import is_real_user_turn
    first = last = turn = None
    owns = False
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        ts = e.get("timestamp")
        if ts and first is None:
            first = ts
        if is_real_user_turn(e):
            turn = ts or turn
        msg = e.get("message")
        blocks = msg.get("content") if isinstance(msg, dict) else None
        for b in blocks if isinstance(blocks, list) else []:
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            name = b.get("name")
            if name in REPORT_TOOLS and ts:
                last = ts
            elif name in PR_TOOLS:
                owns = True
            elif name == RESOLVE and (b.get("input") or {}).get("resolved", True):
                owns = False
    return first, last, owns, turn


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if payload.get("stop_hook_active") or not path or not os.path.isfile(path):
            return 0
        first, last, owns, turn = scan(path)
        ref = last or first
        if not owns or not ref:
            return 0
        age = (now() - parse_ts(ref)).total_seconds()
        if age < LIMIT_S:
            return 0
        marker = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".owner-silence")
        key = str(turn)
        if os.path.isfile(marker) and open(marker, encoding="utf-8").read() == key:
            return 0
        with open(marker, "w", encoding="utf-8") as f:
            f.write(key)
        print(json.dumps({"decision": "block", "reason": REASON.format(
            mins=int(age // 60), last=ref if last else "none since the thread began")}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
