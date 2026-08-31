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
SCHEDULE = re.compile(r"send_later|ScheduleWakeup|create_trigger|update_trigger|CronCreate|^schedule\b", re.I)
POLL_SECONDS = 120
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")



def unwrap_command(cmd):
    if not isinstance(cmd, str):
        return ""
    if cmd.startswith('"'):
        try:
            return json.loads(cmd)
        except Exception:
            # Handle truncated JSON strings by unescaping manually
            cmd = cmd[1:]
            if cmd.endswith('"'):
                cmd = cmd[:-1]
            return cmd.replace('\\n', '\n').replace('\\"', '"')
    return cmd

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
        blobs = []
        if record.get("type") == "assistant" or record.get("role") == "assistant":
            for block in (record.get("message") or {}).get("content") or record.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    blobs.append(block.get("name", "") + " " + json.dumps(block.get("input") or {}))
        if record.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or record.get("source") == "MODEL" or "tool_calls" in record:
            for block in (record.get("tool_calls") or []):
                if isinstance(block, dict):
                    name = block.get("name") or (block.get("function") or {}).get("name") or ""
                    args = block.get("args") or block.get("input") or (block.get("function") or {}).get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {"command": args}
                    if not isinstance(args, dict):
                        args = {}
                    cmd = args.get("CommandLine") or args.get("command") or args.get("cmd") or ""
                    cmd = unwrap_command(cmd)
                    blobs.append(name + " " + json.dumps({**args, "command": cmd}))
        for blob in blobs:
            if OPEN.search(blob):
                opened, armed = True, False
            if opened and SCHEDULE.search(blob):
                armed = True
    return opened and not armed


PR_URL = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+")


def monitor_path(url):
    return os.path.join(STATE_DIR, hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")


def extract_pr_urls(path):
    """Extract PR URLs strictly produced by gh pr create / create_pull_request tool calls."""
    urls = []
    pending_tool_ids = set()
    pending_open = False

    for record in records(path):
        content_items = []
        if isinstance(record.get("content"), list):
            content_items.extend(record.get("content"))

        if isinstance((record.get("message") or {}).get("content"), list):
            content_items.extend(record["message"]["content"])
        elif isinstance(record.get("message"), list):
            content_items.extend(record["message"])

        # Antigravity tool calls
        if record.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or record.get("source") == "MODEL" or "tool_calls" in record:
            for tc in record.get("tool_calls") or []:
                if isinstance(tc, dict):
                    blob = (tc.get("name") or "") + " " + json.dumps(tc.get("args") or tc.get("input") or {})
                    if OPEN.search(blob):
                        pending_open = True
                        for match in PR_URL.finditer(blob):
                            u = match.group(0)
                            if u not in urls:
                                urls.append(u)

        # Antigravity tool result or generic output text
        if pending_open and (record.get("source") in {"MODEL", "SYSTEM"} or record.get("type") in {"GENERIC", "USER_INPUT"}):
            raw_content = record.get("content")
            if isinstance(raw_content, str):
                for match in PR_URL.finditer(raw_content):
                    u = match.group(0)
                    if u not in urls:
                        urls.append(u)
                if not record.get("tool_calls"):
                    pending_open = False

        for block in content_items:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use":
                blob = block.get("name", "") + " " + json.dumps(block.get("input") or {})
                if OPEN.search(blob):
                    tool_id = block.get("id")
                    if tool_id:
                        pending_tool_ids.add(tool_id)
                    else:
                        pending_open = True
                    for match in PR_URL.finditer(blob):
                        u = match.group(0)
                        if u not in urls:
                            urls.append(u)
            elif btype == "tool_result":
                tool_id = block.get("tool_use_id")
                if (tool_id and tool_id in pending_tool_ids) or pending_open:
                    for match in PR_URL.finditer(json.dumps(block)):
                        u = match.group(0)
                        if u not in urls:
                            urls.append(u)
                    if tool_id:
                        pending_tool_ids.discard(tool_id)
                    pending_open = False
    return urls


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


def start_monitor_for_url(url, cwd):
    if not url:
        return None
    path = monitor_path(url)
    if alive(read_json(path).get("pid")):
        return False
    try:
        process = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--poll", url, path],
                                   cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
    except OSError:
        return None
    write_json(path, {"url": url, "pid": process.pid, "started_at": time.time()})
    return True


def start_monitor(cwd):
    if not shutil.which("gh"):
        return None
    url = pr_url(cwd)
    if not url:
        return None
    return start_monitor_for_url(url, cwd)


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
    transcript_path = payload.get("transcript_path") or ""
    if not pending(transcript_path):
        return
    cwd = payload.get("cwd") or os.getcwd()
    if not shutil.which("gh"):
        print(json.dumps({"decision": "block", "reason": "A PR was opened without recurring monitoring. No local timer could be armed; call send_later, ScheduleWakeup, or a trigger routine before ending this turn."}))
        return

    urls = extract_pr_urls(transcript_path)
    if not urls:
        url = pr_url(cwd)
        if url:
            urls = [url]

    if not urls:
        print(json.dumps({"decision": "block", "reason": "A PR was opened without recurring monitoring. No local timer could be armed; call send_later, ScheduleWakeup, or a trigger routine before ending this turn."}))
        return

    any_started = False
    all_monitored = True
    for url in urls:
        status = start_monitor_for_url(url, cwd)
        if status is True:
            any_started = True
        elif status is False:
            pass
        else:
            all_monitored = False

    if any_started:
        print(json.dumps({"systemMessage": "No model scheduler was recorded, so a detached two-minute PR poller was started. It records GitHub state and injects changes on the next prompt; it cannot wake a terminated session."}))
        return
    if all_monitored:
        return
    print(json.dumps({"decision": "block", "reason": "A PR was opened without recurring monitoring. No local timer could be armed; call send_later, ScheduleWakeup, or a trigger routine before ending this turn."}))


if __name__ == "__main__":
    main()
