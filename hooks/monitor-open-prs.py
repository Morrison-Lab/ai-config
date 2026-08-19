#!/usr/bin/env python3
"""Continuously poll every open PR authored by the authenticated GitHub user."""
import json
import os
import subprocess
import sys
import tempfile
import time

POLL_SECONDS = 120
STATE_PATH = os.path.join(tempfile.gettempdir(), "claude-pr-monitors", "all-open-prs.json")


def write_state(value):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    temporary = f"{STATE_PATH}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
    os.replace(temporary, STATE_PATH)


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def read_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as stream:
            return json.load(stream)
    except Exception:
        return {}


def open_prs():
    result = subprocess.run(
        ["gh", "search", "prs", "--author", "@me", "--state", "open", "--limit", "1000",
         "--json", "number,repository,title,updatedAt,url"],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


def monitor():
    while True:
        state = read_state()
        state.update({"kind": "all_open_prs", "pid": os.getpid(), "checked_at": time.time()})
        try:
            state["data"] = open_prs()
            state.pop("error", None)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            state.pop("data", None)
            state["error"] = str(error)
        write_state(state)
        time.sleep(POLL_SECONDS)


def ensure():
    if alive(read_state().get("pid")):
        return True
    try:
        process = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--monitor"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    state = read_state()
    state.update({"kind": "all_open_prs", "pid": process.pid, "started_at": time.time()})
    write_state(state)
    return True


if __name__ == "__main__":
    if sys.argv[1:] == ["--monitor"]:
        monitor()
    else:
        ensure()
