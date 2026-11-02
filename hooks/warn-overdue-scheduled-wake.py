#!/usr/bin/env python3
"""UserPromptSubmit hook: warn when a one-time scheduled wake is overdue and unchecked.

THE GAP THIS FILLS (ai-config#4873)
-----------------------------------
A session arms a one-time scheduled task (`send_later`, or `create_trigger`
with a run time) and ends its turn, trusting it to wake the session.
On 2026-11-02 one such task (due 15:56Z) was never delivered: it stayed
`enabled` with no `last_run`, more than an hour overdue, while about thirty
other one-time tasks that day fired with 1 to 13 minutes of lag.
The session was connected and idle, so nothing ever told it the wake was lost.

A lost wake cannot announce itself, so the next turn that DOES run (a person
typing, a PR event, another session's message) is the only place to notice.
This hook runs at the start of every prompt, finds scheduled tasks this
session created that are more than OVERDUE_MINUTES past due, and, unless
the session has since checked them, adds one line telling it to call
`get_trigger`.

WHAT COUNTS AS CHECKED
----------------------
Any later `get_trigger` / `update_trigger` / `delete_trigger` / `fire_trigger`
call naming the id, any later `list_triggers` call, or a scheduled
continuation (a `promptSource: "sdk"` meta entry, see
scripts/lib/transcript_meta.py) after the due time, which shows the
dispatcher delivered something to this session.

Warn-only: the injected line never blocks.
Each task is reported at most once per session.
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

OVERDUE_MINUTES = 15
CHECK_TOOLS = ("get_trigger", "update_trigger", "delete_trigger", "fire_trigger")
LIST_TOOL = "list_triggers"
RX_SEND_LATER = re.compile(r'"fire_at"\s*:\s*"([^"]+)".*?"trigger_id"\s*:\s*"(trig_\w+)"', re.S)
RX_SEND_LATER_REV = re.compile(r'"trigger_id"\s*:\s*"(trig_\w+)".*?"fire_at"\s*:\s*"([^"]+)"', re.S)
RX_CREATED = re.compile(r'"id"\s*:\s*"(trig_\w+)".*?"run_once_at"\s*:\s*"([^"]+)"', re.S)


def parse_time(text):
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def blocks(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


def scan(path):
    """Return (armed, checks, deliveries): armed maps id -> due time;
    checks is a list of (time, id or None); deliveries is a list of times."""
    armed, checks, deliveries = {}, [], []
    with open(path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            when = parse_time(record.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)
            if record.get("isMeta") and record.get("promptSource") == "sdk":
                deliveries.append(when)
            for block in blocks(record):
                if block.get("type") == "tool_result":
                    text = result_text(block)
                    found = []
                    match = RX_SEND_LATER.search(text)
                    if match:
                        found.append((match.group(2), match.group(1)))
                    match = RX_SEND_LATER_REV.search(text)
                    if match:
                        found.append((match.group(1), match.group(2)))
                    match = RX_CREATED.search(text)
                    if match:
                        found.append((match.group(1), match.group(2)))
                    for trigger_id, due in found:
                        due_time = parse_time(due)
                        if due_time:
                            armed[trigger_id] = due_time
                elif block.get("type") == "tool_use":
                    name = str(block.get("name", ""))
                    if name.endswith(LIST_TOOL):
                        checks.append((when, None))
                    elif name.endswith(CHECK_TOOLS):
                        checks.append((when, (block.get("input") or {}).get("trigger_id")))
    return armed, checks, deliveries


def overdue(armed, checks, deliveries, now):
    out = []
    for trigger_id, due in sorted(armed.items(), key=lambda item: item[1]):
        if now - due < timedelta(minutes=OVERDUE_MINUTES):
            continue
        checked = any(when > due and target in (None, trigger_id) for when, target in checks)
        delivered = any(when > due for when in deliveries)
        if not checked and not delivered:
            out.append((trigger_id, due))
    return out


def already_reported(session_id, trigger_id):
    marker = os.path.join(tempfile.gettempdir(), f"overdue-wake-{session_id}-{trigger_id}")
    if os.path.exists(marker):
        return True
    try:
        open(marker, "w").close()
    except OSError:
        pass
    return False


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        session_id = str(payload.get("session_id") or "nosession")
        if not path or not os.path.exists(path):
            return
        armed, checks, deliveries = scan(path)
        now = parse_time(os.environ.get("OVERDUE_WAKE_NOW")) or datetime.now(timezone.utc)
        late = [(i, d) for i, d in overdue(armed, checks, deliveries, now)
                if not already_reported(session_id, i)]
    except (OSError, ValueError):
        return
    if not late:
        return
    items = "; ".join(f"{i} (due {d:%H:%M}Z)" for i, d in late)
    message = (
        f"Scheduled wake overdue and unchecked: {items}. A one-time task can be skipped by the "
        "dispatcher with no error (ai-config#4873). Call get_trigger now: if it is still enabled "
        "with no last_run, the wake is late or lost, so do that check now rather than waiting on it."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "additionalContext": message}}))


if __name__ == "__main__":
    main()
