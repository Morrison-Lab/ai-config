#!/usr/bin/env python3
"""Continuously poll open GitHub PRs and GitLab merge requests authored by the user."""
import functools
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
# beside a second one, with both files surfaced whenever either changes.
# Nothing reads "kind". The file holds GitLab merge requests too; see
# poll_once().
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
# The backreference ties the status line to the host line above it, so a
# failed instance listed between two working ones is not credited with its
# neighbour's login. A host may carry a port: `glab auth login` accepts one,
# so it can appear here, while `glab api --hostname` refuses any host with a
# ':' (gitlab-org/cli internal/glinstance/host.go, HostnameValidator). It is
# matched anyway, so that refusal -- exit status plus glab's own
# `invalid hostname` -- lands in state["error"] under the host's key rather
# than the host silently going unpolled.
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


def glab_hosts():
    """(hosts, cut_short): hosts glab is logged in to, and None or text saying the list was cut short.

    An error when the status lists no logged-in host, carrying glab's exit
    status and its own message, since the two causes differ: no login at
    all, or an invocation glab refused (a glab older than v1.79.0 has no
    `--all`, an unreadable config). `--all` covers every
    authenticated instance. Without it glab checks only the instance implied
    by the cwd's git remote or GITLAB_HOST when that is not gitlab.com -- and
    this daemon inherits the cwd of whichever session spawned it, so the
    polled host set would depend on where the session happened to start.
    """
    cut_short = None
    exit_status = None
    try:
        result = subprocess.run(
            [GLAB_PATH, "auth", "status", "--all"],
            capture_output=True, text=True, timeout=POLL_SECONDS)
        output = (result.stdout or "") + (result.stderr or "")
        exit_status = result.returncode
    except subprocess.TimeoutExpired as error:
        # glab gives each instance its own 30 s, so one unreachable instance
        # can exhaust the budget after the reachable ones already answered.
        # The partial output names those, and they are polled rather than
        # lost with the timeout -- but the cut is reported back, since a
        # slow logged-in instance absent from that output is otherwise
        # indistinguishable from one never logged in to.
        output = _captured_text(error.stdout) + _captured_text(error.stderr)
        if not authenticated_hosts(output):
            raise
        cut_short = f"{error}; hosts listed before the timeout were polled"
    hosts = authenticated_hosts(output)
    if not hosts:
        raise OSError(
            f"glab auth status --all listed no authenticated host "
            f"(exit {exit_status}): {output.strip()[-300:]}")
    return hosts, cut_short


def _captured_text(captured):
    # On POSIX subprocess.run attaches BYTES to TimeoutExpired even under
    # text=True (measured on CPython 3.11; its Windows branch attaches str
    # via communicate()), so the decode is what keeps a real timeout from
    # raising TypeError out of the poll and killing the daemon.
    if captured is None:
        return ""
    return captured.decode(errors="replace") if isinstance(captured, bytes) else captured


def host_merge_requests(host):
    """Every open merge request the user authored on one GitLab host."""
    response = subprocess.run(
        [
            GLAB_PATH, "api", "--hostname", host, "--paginate",
            "merge_requests?scope=created_by_me&state=opened&per_page=100"
        ],
        capture_output=True, text=True, timeout=60, check=True)
    merge_requests = []
    for page in json_documents(response.stdout):
        # A page is a JSON array of merge requests. glab exits non-zero on
        # an API error, so an error object should never reach this point,
        # and extending with one would silently store its key strings as
        # merge requests.
        if not isinstance(page, list):
            raise ValueError(
                f"expected a JSON array page from glab api, got {type(page).__name__}")
        merge_requests.extend(page)
    return merge_requests


def poll_once(state):
    state.update({"kind": "all_open_prs", "pid": os.getpid(), "checked_at": time.time()})
    # Every source that answered lands under "data", every one that failed
    # under "error" (a JSON object keyed by source), so one failing does not
    # hide another's results; "data" is {} when every source failed. Each
    # GitLab host is its own source ("gitlab_merge_requests/<host>"), so a
    # host that is down, or one glab api refuses, costs only its own entry.
    # A source whose CLI is missing is left out rather than reported as an
    # empty list: an absent key means "not checked", an empty list means
    # "checked, none open", and the state file must not blur the two.
    data = {}
    errors = {}
    caught = (OSError, ValueError, subprocess.SubprocessError)

    def run(name, query):
        try:
            data[name] = query()
        except subprocess.CalledProcessError as error:
            # The exit status alone names no cause; the CLI's stderr does
            # (`invalid hostname`, an auth failure), so it rides along.
            stderr = (error.stderr or "").strip()
            errors[name] = f"{error}: {stderr}" if stderr else str(error)
        except caught as error:
            errors[name] = str(error)

    if GH_PATH is None and GLAB_PATH is None:
        # require_cli() refuses to start the daemon in this state; a poll
        # reaching here anyway must not write a "checked, none open" file.
        raise OSError("cannot resolve 'gh' or 'glab' on PATH; nothing to poll")
    if GH_PATH is not None:
        run("github_prs", open_prs)
    if GLAB_PATH is not None:
        try:
            hosts, cut_short = glab_hosts()
        except caught as error:
            errors["gitlab_merge_requests"] = str(error)
        else:
            if cut_short:
                errors["gitlab_merge_requests"] = cut_short
            for host in hosts:
                run(f"gitlab_merge_requests/{host}",
                    functools.partial(host_merge_requests, host))

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
