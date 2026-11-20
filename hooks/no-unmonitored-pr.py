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
SCHEDULE = re.compile(r"send_later|ScheduleWakeup|create_trigger|update_trigger|CronCreate|subscribe_pr_activity|^schedule\b", re.I)
# A closing reply that says the session is waiting on PR state (ai-config#4790).
# Each branch names the PR state and a future event, so a bare status word
# ("no pending items", "after CI passed") does not match; "not" and "no longer"
# before "waiting" negate it.
_PR_STATE = r"(?:CI|(?:the )?checks?|(?:the )?review|(?:the )?merge)"
_FUTURE = (r"(?:passes|pass|finishes|finish|completes|complete|is clean|comes back"
           r"|goes green|turns green|lands|is done|reports)")
WAITING = re.compile(
    r"(?<!not )(?<!no longer )\bwaiting (?:on|for) " + _PR_STATE
    + r"|\b" + _PR_STATE + r" (?:is|are) still (?:running|pending|in progress)"
    + r"|\b(?:once|when|after) " + _PR_STATE + r" " + _FUTURE + r"\b", re.I)
WAKE_REASON = (
    "This reply waits on PR state (CI, review or merge), but nothing recorded can "
    "re-invoke this session: the detached poller only records state for the next "
    "prompt (ai-config#4790). Arm a wake before ending the turn: send_later, "
    "ScheduleWakeup, a trigger routine, or subscribe_pr_activity.")
POLL_SECONDS = 120
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-pr-monitors")

try:
    _LIB = os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from pr_view import gh_pr_view
except Exception as _exc:  # broken install: no PR can be read
    print(f"no-unmonitored-pr: cannot load scripts/lib/pr_view.py ({_exc}); "
          "no PR state will be read", file=sys.stderr)
    gh_pr_view = None



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


def last_reply(path):
    """The text of the transcript's last assistant message, or ''."""
    text = ""
    for record in records(path):
        if record.get("type") != "assistant" and record.get("role") != "assistant":
            continue
        content = (record.get("message") or {}).get("content") or record.get("content") or []
        if isinstance(content, str):
            text = content
            continue
        parts = [block.get("text", "") for block in content
                 if isinstance(block, dict) and block.get("type") == "text"]
        if parts:
            text = "\n".join(parts)
    return text


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


READ_ATTEMPTS = 3


def read_state(path):
    """`(state, True)` for a readable or missing state file, `(None, False)`
    when it exists but stays unreadable after READ_ATTEMPTS tries.

    A live poller rewrites the file with `os.replace` every POLL_SECONDS, and
    on Windows a read that overlaps the replace can fail. Reading that as
    "no poller" spawned a duplicate each time, and the duplicates fed each
    other (ai-config#4009), so an unreadable file means "unknown" here."""
    for attempt in range(READ_ATTEMPTS):
        try:
            with open(path, encoding="utf-8") as stream:
                state = json.load(stream)
            return (state if isinstance(state, dict) else {}), True
        except FileNotFoundError:
            return {}, True
        except (OSError, ValueError):
            if attempt + 1 < READ_ATTEMPTS:
                time.sleep(0.05)
    return None, False


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
    os.replace(temporary, path)


def _alive_windows(pid):
    # memories/python.md: os.kill(pid, 0) on Windows maps to
    # GenerateConsoleCtrlEvent, where success does not track liveness, so
    # the probe goes through OpenProcess instead. A recycled pid whose new
    # process happened to exit with STILL_ACTIVE (259) reads as alive;
    # accepted, since a wrong True only delays one respawn cycle.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


MAX_CONSECUTIVE_ERRORS = 15
NO_WINDOW = ({"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
             if sys.platform == "win32" else {})


POLL_FIELDS = ["url", "state", "updatedAt", "reviewDecision", "statusCheckRollup", "reviews",
               "mergeable", "mergeStateStatus"]


def _run(*args, **kwargs):
    return subprocess.run(*args, **kwargs, **NO_WINDOW)


def pr_url(cwd):
    # `gh_pr_view` reads over REST where a cloud session refuses GraphQL
    # (ai-config#4733).
    if gh_pr_view is None:
        return ""
    data, _error = gh_pr_view(["url"], cwd=cwd, timeout=5, run=_run)
    return str((data or {}).get("url") or "").strip()


def start_monitor_for_url(url, cwd):
    if not url:
        return None
    path = monitor_path(url)
    state, readable = read_state(path)
    if readable and alive(state.get("pid")):
        return False
    if not readable and recently_written(path):
        return False  # a live poller may be mid-replace (ai-config#4009)
    try:
        process = subprocess.Popen([sys.executable, os.path.realpath(__file__), "--poll", url, path],
                                   cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True, **NO_WINDOW)
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


FRESH_SECONDS = 3 * POLL_SECONDS


def recently_written(path):
    """True when `path` was modified within FRESH_SECONDS. An unreadable
    file that old has no poller behind it, so it no longer blocks a spawn."""
    try:
        return time.time() - os.path.getmtime(path) < FRESH_SECONDS
    except OSError:
        return False


def other_poller(state):
    """True when `state` names a different, live poller that has written
    within FRESH_SECONDS, so this one should stand down."""
    pid = state.get("pid")
    if pid is None or str(pid) == str(os.getpid()) or not alive(pid):
        return False
    try:
        seen = max(float(state.get("checked_at") or 0), float(state.get("started_at") or 0))
    except (TypeError, ValueError):
        return False
    return time.time() - seen < FRESH_SECONDS


def poll(url, path):
    consecutive_errors = 0
    while True:
        state, readable = read_state(path)
        if readable and other_poller(state):
            return  # converge to one poller per URL (ai-config#4009)
        state = state if readable else {}
        state.update({"url": url, "pid": os.getpid(), "checked_at": time.time()})
        data, error = None, "scripts/lib/pr_view.py did not load"
        if gh_pr_view is not None:
            data, error = gh_pr_view(POLL_FIELDS, target=url, timeout=30, run=_run)
        if isinstance(data, dict):
            state["data"] = data
            state.pop("error", None)
            consecutive_errors = 0
        else:
            consecutive_errors += 1
            state.pop("data", None)
            state["error"] = str(error or "gh pr view answered something other than an object")
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

    # The loop above reads start_monitor_for_url's three results: True started a
    # poller, False means the PR's recorded poller is already alive (it stays
    # monitored), and None means none could start (all_monitored = False).
    # The poller is a record, not a wake: a reply that waits on PR state still
    # needs something that re-invokes the session. stop_hook_active means this
    # hook already blocked once this turn, so it does not block again.
    if ((any_started or all_monitored) and not payload.get("stop_hook_active")
            and WAITING.search(last_reply(transcript_path))):
        print(json.dumps({"decision": "block", "reason": WAKE_REASON}))
        return
    if any_started:
        print(json.dumps({"systemMessage": "No model scheduler was recorded, so a detached two-minute PR poller was started. It records GitHub state and injects changes on the next prompt; it cannot wake a terminated session."}))
        return
    if all_monitored:
        return
    print(json.dumps({"decision": "block", "reason": "A PR was opened without recurring monitoring. No local timer could be armed; call send_later, ScheduleWakeup, or a trigger routine before ending this turn."}))


if __name__ == "__main__":
    main()
