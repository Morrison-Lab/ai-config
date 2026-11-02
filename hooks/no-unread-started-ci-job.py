#!/usr/bin/env python3
"""Stop hook: a turn that starts a CI job must read its result before it ends.

THE GAP THIS FILLS (ai-config#4873)
-----------------------------------
On 2026-11-02 a session re-ran a failed CI job, then ended its turn with a
scheduled check as the only follow-up, and wrote "From now on I'll read a
short job's result in the same turn that starts it".
That promise had no mechanism behind it, and the scheduled check was then
delivered 69 minutes late.
A job that takes a few minutes is cheaper to read in the same turn than to
wake for.

WHAT IT CHECKS
--------------
In the current turn (the records after the last real user prompt), if the
last call that STARTED a job (`actions_run_trigger`, `gh run rerun`,
`gh workflow run`) has no later call that READS a run (`actions_get`,
`actions_list`, `get_job_logs`, `get_check_run`, `pull_request_read`,
`gh run view|watch|list`, or a `gh api` call on `actions/runs` or
`check-runs`), the stop is blocked once with a note.
A scheduling call (`send_later`, `ScheduleWakeup`, a trigger) does NOT count as
a read: it is the substitute this hook exists to question.

The note allows the legitimate case: a job longer than about five minutes may
end the turn if the reply names the wake that will re-invoke the session.
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

START_TOOLS = ("actions_run_trigger",)
READ_TOOLS = ("actions_get", "actions_list", "get_job_logs", "get_check_run", "pull_request_read")
RX_START_CMD = re.compile(r"\bgh\s+(?:run\s+rerun|workflow\s+run)\b")
RX_READ_CMD = re.compile(r"\bgh\s+run\s+(?:view|watch|list)\b|\bgh\s+api\b[^|;&]*(?:actions/runs|check-runs)")


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
    """Return 'start', 'read' or None for one tool_use block."""
    name = str(block.get("name", ""))
    command = str((block.get("input") or {}).get("command", "")) if name == "Bash" else ""
    if name.endswith(START_TOOLS) or (command and RX_START_CMD.search(command)):
        return "start"
    if name.endswith(READ_TOOLS) or (command and RX_READ_CMD.search(command)):
        return "read"
    return None


def unread_start(path):
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
    last_start = max((i for i, kind in enumerate(events) if kind == "start"), default=None)
    return last_start is not None and "read" not in events[last_start + 1:]


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if not path or not os.path.exists(path) or not unread_start(path):
            return 0
    except (OSError, ValueError):
        return 0
    print(stop_notice(
        payload,
        "This turn started a CI job (a rerun or a workflow run) and ended without reading it. "
        "A job that takes under about 5 minutes should be read in the same turn that starts it: "
        "read its check runs or logs now, and do not rely on a scheduled check, which can be "
        "delivered an hour late (ai-config#4873). If the job really runs longer, say so and "
        "name the wake or background wait that will re-invoke this session.",
        "no-unread-started-ci-job"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
