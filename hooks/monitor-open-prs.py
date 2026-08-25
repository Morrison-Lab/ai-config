#!/usr/bin/env python3
"""Continuously poll every open PR authored by the authenticated GitHub user."""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

POLL_SECONDS = 120
STATE_PATH = os.path.join(tempfile.gettempdir(), "claude-pr-monitors", "all-open-prs.json")
TEMP_SUFFIX = ".tmp"
IS_WINDOWS = os.name == "nt"


def temp_path_for(pid):
    return f"{STATE_PATH}.{pid}{TEMP_SUFFIX}"


def write_state(value):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    temporary = temp_path_for(os.getpid())
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
    os.replace(temporary, STATE_PATH)


def _temp_pid(path):
    # Only `<state>.<int>.tmp` is claimed as ours. Anything else sharing the
    # directory belongs to another writer and is left untouched, so a sweep
    # can never widen into a general "delete stray files here".
    name = os.path.basename(path)
    prefix = f"{os.path.basename(STATE_PATH)}."
    if not name.startswith(prefix) or not name.endswith(TEMP_SUFFIX):
        return None
    middle = name[len(prefix):-len(TEMP_SUFFIX)]
    try:
        return int(middle)
    except ValueError:
        return None


def sweep_orphan_temp_files(max_age_seconds=POLL_SECONDS):
    """Unlink `<state>.<pid>.tmp` leftovers older than one poll interval.

    write_state() is a create-then-replace pair, so a daemon killed between
    the two steps -- by stop_stale_daemon(), an installer re-run, or logoff --
    strands its temporary file with nothing to collect it. The age gate is
    what makes removal safe without any locking: a live writer holds its
    temporary file for the duration of one json.dump(), so anything whose
    mtime predates a full poll interval is provably abandoned.
    """
    removed = 0
    for path in glob.glob(f"{glob.escape(STATE_PATH)}.*{TEMP_SUFFIX}"):
        pid = _temp_pid(path)
        if pid is None or pid == os.getpid():
            # A temporary file bearing our own pid can only be a write this
            # process is executing right now; the sweep never owns it.
            continue
        try:
            age = time.time() - os.stat(path).st_mtime
        except FileNotFoundError:
            continue
        except OSError as error:
            print(f"WARN: monitor-open-prs: cannot stat {path}: {error}", file=sys.stderr)
            continue
        if age <= max_age_seconds:
            continue
        try:
            os.unlink(path)
            removed += 1
        except FileNotFoundError:
            # Another sweeper won the race; the file is gone either way.
            continue
        except OSError as error:
            # Reported, not swallowed: a locked or unwritable leftover must
            # not take down the poll loop that this sweep is a side errand of.
            print(f"WARN: monitor-open-prs: cannot unlink orphaned state file "
                  f"{path}: {error}", file=sys.stderr)
    return removed


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
    # Swept after the replace, so this process holds no temporary file of its
    # own. A gh failure still reaches here on purpose: leftovers should drain
    # even while polls are erroring, since that is when restarts cluster.
    sweep_orphan_temp_files()
    return state


def monitor():
    while True:
        poll_once(read_state())
        time.sleep(POLL_SECONDS)


def ensure():
    if alive(read_state().get("pid")):
        # A live daemon sweeps on its own schedule; do not duplicate the work
        # on every hook invocation.
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
    # Respawn is exactly the event that strands temporary files, and the
    # daemon that just died could not clean up after itself.
    sweep_orphan_temp_files()
    return True


if __name__ == "__main__":
    require_gh()
    if sys.argv[1:] == ["--monitor"]:
        monitor()
    else:
        ensure()
