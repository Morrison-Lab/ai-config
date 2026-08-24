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
IS_WINDOWS = os.name == "nt"


def write_state(value):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    temporary = f"{STATE_PATH}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
    os.replace(temporary, STATE_PATH)


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
    # Non-positive pids are refused before any platform probe: signal 0 to
    # -1 would address an entire process group on POSIX rather than one pid.
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if IS_WINDOWS:
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
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
