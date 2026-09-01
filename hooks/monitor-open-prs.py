#!/usr/bin/env python3
"""Continuously poll open GitHub PRs and GitLab merge requests authored by the user."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

POLL_SECONDS = 120
# The file and the "kind" marker keep their pre-GitLab names on purpose. A
# daemon started before the GitLab support landed keeps writing this path
# every poll, ensure() reads the pid from it, and scripts/install-pr-monitor.py
# stops the pid recorded in it -- renaming it would leave that daemon running
# beside a second one, with both files surfaced on every prompt. Nothing reads
# "kind". The file holds GitLab merge requests too; see poll_once().
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
GLAB_PATH = shutil.which("glab")


def require_cli():
    if GH_PATH is None and GLAB_PATH is None:
        sys.exit("FATAL: cannot resolve 'gh' or 'glab' on PATH; refusing to "
                 "start a monitor that can only error every poll")


def open_prs():
    result = subprocess.run(
        [GH_PATH, "search", "prs", "--author", "@me", "--state", "open", "--limit", "1000",
         "--json", "number,repository,title,updatedAt,url"],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


# One `glab auth status` block per instance: a host line, then indented
# status lines, of which a successful login reads `Logged in to <host> as`.
# The host may carry a port. The backreference ties the status line to the
# host line above it, so a failed instance listed between two working ones
# is not credited with its neighbour's login.
GLAB_LOGGED_IN_RE = re.compile(
    r"^([A-Za-z0-9.-]+(?::[0-9]+)?)\n\s+.*Logged in to \1 as ",
    re.MULTILINE)


def authenticated_hosts(auth_status_output):
    """Hosts `glab auth status --all` reports a working login for, in order."""
    return GLAB_LOGGED_IN_RE.findall(auth_status_output)


def json_documents(text):
    """Every JSON document in `text`, in order.

    `glab api --paginate` writes each page's body to stdout in turn, so a
    multi-page REST response is several JSON arrays back to back rather than
    one; a single page is one array. Decoding document by document reads both.
    """
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return documents
        document, position = decoder.raw_decode(text, position)
        documents.append(document)


def open_merge_requests():
    # `--all` covers every authenticated instance. Without it glab checks
    # only the instance implied by the cwd's git remote or GITLAB_HOST when
    # that is not gitlab.com -- and this daemon inherits the cwd of whichever
    # session spawned it, so the polled host set would depend on where the
    # session happened to start.
    result = subprocess.run(
        [GLAB_PATH, "auth", "status", "--all"],
        capture_output=True, text=True, timeout=30)
    hosts = authenticated_hosts(result.stdout + result.stderr)
    if not hosts:
        raise OSError("glab has no authenticated hosts")
    merge_requests = []
    for host in hosts:
        response = subprocess.run(
            [
                GLAB_PATH, "api", "--hostname", host, "--paginate",
                "merge_requests?scope=created_by_me&state=opened&per_page=100"
            ],
            capture_output=True, text=True, timeout=60, check=True)
        for page in json_documents(response.stdout):
            merge_requests.extend(page)
    return merge_requests


def available_sources():
    """The sources this host can query, keyed by their state["data"] entry.

    A source whose CLI is missing is left out rather than reported as an
    empty list: an absent key means "not checked", an empty list means
    "checked, none open", and the state file must not blur the two.
    """
    sources = {}
    if GH_PATH is not None:
        sources["github_prs"] = open_prs
    if GLAB_PATH is not None:
        sources["gitlab_merge_requests"] = open_merge_requests
    return sources


def poll_once(state):
    state.update({"kind": "all_open_prs", "pid": os.getpid(), "checked_at": time.time()})
    # Every source that answered lands under "data", every one that failed
    # under "error" (a JSON object keyed by source), so one CLI failing does
    # not hide the other's results; "data" is {} when every source failed.
    data = {}
    errors = {}
    for name, query in available_sources().items():
        try:
            data[name] = query()
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            errors[name] = str(error)

    state["data"] = data
    if not errors:
        state.pop("error", None)
        state["error_streak"] = 0
    else:
        message = json.dumps(errors, sort_keys=True)
        # The streak counts consecutive polls of the SAME error text, so a
        # text change starts a fresh streak and earns its own persistent
        # report downstream; state still holds the previous poll's error here.
        if "error" in state and state["error"] == message:
            state["error_streak"] = int(state.get("error_streak") or 0) + 1
        else:
            state["error_streak"] = 1
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
    require_cli()
    if sys.argv[1:] == ["--monitor"]:
        monitor()
    else:
        ensure()
