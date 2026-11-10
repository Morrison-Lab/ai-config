#!/usr/bin/env python3
"""PreToolUse deny: only the runner thread may start a Remote Control session.

ai-config#5090. Standing rule (Ezra, 2026-11-07): project threads never open
their own device run, and only the runner thread runs the fully-clean checker
and merges. On 2026-11-07 the ids owner thread tried to open its own Remote
Control session for that, then withdrew before anything ran. A deny is
decidable here (the tool name and the thread id are both exact), so this is a
deny and not a reminder.

A thread session knows its own id: the first wake in its transcript carries
`<thread ts="cmsg_...">`, and the transcript says "You are a Thread Session".
Any other session (the coordinator, a Claude Code session) has no own thread
and is never denied.

The runner threads are listed one id per line in hooks/rc-runner-threads.txt
(blank lines and `#` comments ignored); the env var RC_RUNNER_THREAD_IDS
(comma separated) adds more. Fails open on any parse trouble, including an
unreadable transcript.
"""
import json
import os
import re
import sys
from pathlib import Path

TOOL = "mcp__hearthbot__start_remote_control"
THREAD_TS = re.compile(r'<thread ts="(cmsg_\w+)"')
THREAD_SESSION = "You are a Thread Session"
ALLOWLIST = Path(__file__).with_name("rc-runner-threads.txt")

REASON = """\
[hook: no-rc-outside-runner] This thread (`{cmsg}`) is not the runner thread, \
so it may not start its own Remote Control session (ai-config#5090; Ezra, \
2026-11-07: threads never open their own device run, and only the runner \
merges).
Message the runner thread with `message_thread` (or the coordinator with \
`message_coordinator`), saying what to run on the device, and carry on with \
the work that needs no device."""


def own_thread_id(transcript_path):
    """The id of the thread this session works in, or None for any other session."""
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            head = f.read(200_000)
    except (OSError, TypeError, ValueError):
        return None
    if THREAD_SESSION not in head:
        return None
    m = THREAD_TS.search(head)
    return m.group(1) if m else None


def runner_ids():
    ids = set()
    try:
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                ids.add(line)
    except OSError:
        pass
    for part in os.environ.get("RC_RUNNER_THREAD_IDS", "").split(","):
        if part.strip():
            ids.add(part.strip())
    return ids


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != TOOL:
        return 0
    cmsg = own_thread_id(payload.get("transcript_path"))
    if not cmsg or cmsg in runner_ids():
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(cmsg=cmsg),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
