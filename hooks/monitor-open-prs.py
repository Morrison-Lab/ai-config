#!/usr/bin/env python3
"""Continuously poll every open PR authored by the authenticated GitHub user."""
import json
import os
import shutil
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


GH_PATH = shutil.which("gh")


def require_gh():
    if GH_PATH is None:
        sys.exit("FATAL: cannot resolve 'gh' on PATH; refusing to start a "
                 "monitor that can only error every poll")


def open_prs():
    result = subprocess.run(
        [GH_PATH, "search", "prs", "--author", "@me", "--state", "open", "--limit", "1000",
         "--json", "number,repository,title,updatedAt,url"],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


def poll_once(state):
    state.update({"kind": "all_open_prs", "pid": os.getpid(), "checked_at": time.time()})
    try:
        state["data"] = open_prs()
        state.pop("error", None)
        state["error_streak"] = 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        message = str(error)
        # The streak counts consecutive polls of the SAME error text, so a
        # text change starts a fresh streak and earns its own persistent
        # report downstream; state still holds the previous poll's error here.
        if "error" in state and state["error"] == message:
            state["error_streak"] = int(state.get("error_streak") or 0) + 1
        else:
            state["error_streak"] = 1
        state.pop("data", None)
        state["error"] = message
    write_state(state)
    return state


def monitor():
    while True:
        poll_once(read_state())
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
    require_gh()
    if sys.argv[1:] == ["--monitor"]:
        monitor()
    else:
        ensure()
