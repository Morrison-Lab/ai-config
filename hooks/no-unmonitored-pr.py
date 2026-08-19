#!/usr/bin/env python3
"""Arm a detached PR poller when an opened PR has no model scheduler.

Hooks cannot call Claude's scheduler. This fallback observes a PR every two
minutes and the companion UserPromptSubmit hook reports changed state next
prompt. It cannot wake a model session that has ended.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

OPEN = re.compile(r"\bgh\s+pr\s+create\b|create_pull_request", re.I)
SCHEDULE = re.compile(r"send_later|ScheduleWakeup|create_trigger|update_trigger|CronCreate", re.I)
POLL_SECONDS = 120
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")


def records(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def pending(path):
    opened = armed = False
    for record in records(path):
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            blob = block.get("name", "") + " " + json.dumps(block.get("input") or {})
            if OPEN.search(blob):
                opened, armed = True, False
            if opened and SCHEDULE.search(blob):
                armed = True
    return opened and not armed


def monitor_path(url):
    return os.path.join(STATE_DIR, hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")


def cwd_monitor_path(cwd):
    return os.path.join(STATE_DIR, "cwd-" + hashlib.sha256(os.path.abspath(cwd).encode()).hexdigest()[:16] + ".json")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except Exception:
        return {}


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
    os.replace(temporary, path)


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


MAX_CONSECUTIVE_ERRORS = 15


def pr_url(cwd):
    try:
        result = subprocess.run(["gh", "pr", "view", "--json", "url", "--jq", ".url"],
                                cwd=cwd, capture_output=True, text=True,
                                timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def start_monitor(cwd):
    if not shutil.which("gh"):
        return None
    cwd_state = cwd_monitor_path(cwd)
    if alive(read_json(cwd_state).get("pid")):
        return False
    url = pr_url(cwd)
    if not url:
        return None
    path = monitor_path(url)
    if alive(read_json(path).get("pid")):
        write_json(cwd_state, {"url": url, "pid": read_json(path).get("pid"), "path": path})
        return False
    try:
        process = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--poll", url, path],
                                   cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
    except OSError:
        return None
    write_json(path, {"url": url, "pid": process.pid, "started_at": time.time()})
    write_json(cwd_state, {"url": url, "pid": process.pid, "path": path})
    return True


def poll(url, path):
    consecutive_errors = 0
    while True:
        state = read_json(path)
        state.update({"url": url, "pid": os.getpid(), "checked_at": time.time()})
        try:
            result = subprocess.run(["gh", "pr", "view", url, "--json",
                                     "url,state,updatedAt,reviewDecision,statusCheckRollup,reviews"],
                                    capture_output=True, text=True, timeout=30, check=True)
            state["data"] = json.loads(result.stdout)
            state.pop("error", None)
            consecutive_errors = 0
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            consecutive_errors += 1
            state.pop("data", None)
            state["error"] = str(error)
        write_json(path, state)
        if state.get("data", {}).get("state") in {"MERGED", "CLOSED"}:
            return
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            return
        time.sleep(POLL_SECONDS)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--poll":
        poll(sys.argv[2], sys.argv[3])
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not pending(payload.get("transcript_path") or ""):
        return
    status = start_monitor(payload.get("cwd") or os.getcwd())
    if status is True:
        print(json.dumps({"systemMessage": "No model scheduler was recorded, so a detached two-minute PR poller was started. It records GitHub state and injects changes on the next prompt; it cannot wake a terminated session."}))
        return
    elif status is False:
        return
    print(json.dumps({"decision": "block", "reason": "A PR was opened without recurring monitoring. No local timer could be armed; call send_later, ScheduleWakeup, or a trigger routine before ending this turn."}))


if __name__ == "__main__":
    main()
