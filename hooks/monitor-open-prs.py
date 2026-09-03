#!/usr/bin/env python3
"""Continuously poll the open GitHub PRs and GitLab merge requests in the user's scope."""
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
# How much of a CLI's own output an error entry keeps. The entry reaches the
# next prompt through inject-pr-monitor-status.py, so it is bounded. It is
# the TAIL, because glab's `could not authenticate to one or more ...`
# summary comes last -- but each instance's diagnosis (`API call failed`,
# `could not read the token`) is the FIRST status line of its block, so the
# bound has to hold whole blocks rather than line endings. Rendered from
# status.go's own format strings, a fully configured instance's block is
# about 480 characters. The longest branch -- a 401 on an
# environment-variable token -- adds at least three hint lines to the block
# (a fourth when the host is configured for OAuth) and a three-line trailer
# before the summary, for about 1450, and optional `Subfolder:` and
# `SSH Host:` lines can take one block past 1700. 4000 holds that with room
# for a second default block; test-monitor-open-prs.py pins the env-token
# rendering and a default block to fit together. A `glab api` or `gh`
# diagnosis is one line.
ERROR_TAIL = 4000

# The fields of a merge request kept in the state file, the counterpart of
# the `--json` list open_prs() asks gh for. The rest of the object is
# volatile (`user_notes_count`, `detailed_merge_status`, ...) and would
# change the fingerprint -- and re-inject every description into the next
# prompt -- on every poll.
MERGE_REQUEST_FIELDS = ("iid", "references", "title", "updated_at", "web_url")
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


def gh_search_prs(*qualifiers):
    """One `gh search prs` arm, as a list of PR objects."""
    result = subprocess.run(
        [GH_PATH, "search", "prs", "--state", "open", "--limit", "1000",
         "--json", "number,repository,title,updatedAt,url", *qualifiers],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


def gh_owners():
    """The user's own login, then every organization login they belong to.

    Derived per poll rather than written down, so a new organization is
    covered without editing this file. An empty result is an error: it
    would silently turn the workflow-bot arm below into a search of
    nothing, which is indistinguishable from that arm finding nothing.

    `user/orgs` lists the memberships the token can see, so a token
    without `read:org` reports only public ones and narrows that arm
    accordingly. A missing organization there is the first thing to check
    when a workflow-bot PR goes unreconciled.
    """
    owners = []
    for arguments in (["api", "user", "--jq", ".login"],
                      ["api", "--paginate", "user/orgs", "--jq", ".[].login"]):
        result = subprocess.run([GH_PATH, *arguments],
                                capture_output=True, text=True, timeout=60, check=True)
        owners.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    if not owners:
        raise OSError("gh api resolved no owner to scope the workflow-bot PR search to")
    return owners


def open_prs():
    """Every open GitHub PR a search can place in the user's scope.

    memories/reviewing-prs.md states that scope as four arms: the user
    opened the PR, is assigned to it, named it in the request, or the
    repository's own workflow bot (the `github-actions` app) opened it.
    Polling `--author @me` alone covered the first arm only, so a PR
    assigned to the user, or a `bump-submodule.yml` PR the user is
    driving, was never reconciled (ai-config#2919). The named-in-request
    arm is a property of a conversation rather than of a PR, so no query
    can carry it.

    The two `@me` arms are self-scoping. The workflow-bot arm is not:
    unqualified, `--author app/github-actions` searches every open
    workflow-bot PR on GitHub, so it is bounded by `--owner` to the
    owners the user actually works under.

    A failure of any arm --- the owner lookup included --- propagates, so
    the whole `github_prs` source records an error. Keeping the arms that
    answered would write a partial population under a key that asserts a
    complete one, which is the distinction poll_once() draws between an
    absent key and an empty list.
    """
    owner_flags = []
    for owner in gh_owners():
        owner_flags += ["--owner", owner]
    arms = [("--author", "@me"),
            ("--assignee", "@me"),
            ("--author", "app/github-actions", *owner_flags)]
    found = {}
    for arm in arms:
        pull_requests = gh_search_prs(*arm)
        # `gh search prs --json` writes an array of objects. Anything else
        # is refused rather than stored: poll_once() catches ValueError
        # into the source's error entry, where the AttributeError a
        # non-object would raise below would instead end the daemon.
        if not isinstance(pull_requests, list):
            raise ValueError(
                f"expected a JSON array from gh search prs, got {type(pull_requests).__name__}")
        for pull_request in pull_requests:
            if not isinstance(pull_request, dict):
                raise ValueError(
                    f"expected PR objects from gh search prs, got {type(pull_request).__name__}")
            # A PR can match more than one arm (the user opened it and was
            # then assigned to it), so the arms are unioned on the PR's
            # url rather than concatenated.
            key = pull_request.get("url") or json.dumps(pull_request, sort_keys=True)
            found[key] = pull_request
    # Sorted, because inject-pr-monitor-status.py fingerprints this list:
    # three searches concatenated in gh's own result order would reorder
    # between polls and re-inject an unchanged population.
    return [found[key] for key in sorted(found)]


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
    status and its own message. The message is what names the cause -- no
    login at all, or an invocation glab refused (a glab older than v1.79.0
    has no `--all`, an unreadable config) -- since glab exits 1 for either,
    and also for a working instance listed beside a failed one, which is
    why the status is never consulted when parsing. `--all` covers every
    authenticated instance. Without it glab checks only the instance implied
    by the cwd's git remote or GITLAB_HOST when that is not gitlab.com -- and
    this daemon inherits the cwd of whichever session spawned it, so the
    polled host set would depend on where the session happened to start.
    """
    cut_short = None
    try:
        result = subprocess.run(
            [GLAB_PATH, "auth", "status", "--all"],
            capture_output=True, text=True, timeout=POLL_SECONDS)
        output = (result.stdout or "") + (result.stderr or "")
        none_listed = f"(exit {result.returncode})"
    except subprocess.TimeoutExpired as error:
        # glab gives each instance its own 30 s, so one unreachable instance
        # can exhaust the budget after the reachable ones already answered.
        # The partial output names those, and they are polled rather than
        # lost with the timeout -- but the cut is reported back, since a
        # slow logged-in instance absent from that output is otherwise
        # indistinguishable from one never logged in to.
        output = _captured_text(error.stdout) + _captured_text(error.stderr)
        none_listed = f"({error}; nothing listed before the timeout)"
        cut_short = f"{error}; hosts listed before the timeout were polled"
    hosts = authenticated_hosts(output)
    if not hosts:
        raise OSError(
            f"glab auth status --all listed no authenticated host "
            f"{none_listed}: {output.strip()[-ERROR_TAIL:]}")
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
        for item in page:
            if not isinstance(item, dict):
                raise ValueError(
                    f"expected merge-request objects from glab api, got {type(item).__name__}")
            merge_requests.append({field: item.get(field) for field in MERGE_REQUEST_FIELDS})
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
            stderr = (error.stderr or "").strip()[-ERROR_TAIL:]
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
