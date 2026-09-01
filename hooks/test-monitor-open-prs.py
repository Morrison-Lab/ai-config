#!/usr/bin/env python3
"""Regression test for monitor-open-prs.py."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

assert subject.POLL_SECONDS == 120
# The state file and "kind" keep their pre-GitLab names: a daemon started
# before GitLab support keeps writing this path, and the installer stops the
# pid recorded in it, so a rename would leave two daemons and two files.
assert subject.STATE_PATH.endswith("all-open-prs.json")
assert "all_open_prs" in subject.poll_once.__code__.co_consts
assert any(isinstance(c, (str, tuple, list)) and "--author" in c for c in subject.open_prs.__code__.co_consts)
# The command must run the absolutely-resolved GH_PATH; the literal "gh"
# reappearing in open_prs would be a revert of the #1953 fix. CPython folds
# a list display into a tuple inside co_consts, so nested consts are
# searched too -- a top-level-only check passes on the reverted code.
assert not any(
    value == "gh"
    for const in subject.open_prs.__code__.co_consts
    for value in (const if isinstance(const, (tuple, list)) else (const,)))
assert any(isinstance(c, (str, tuple, list)) and "created_by_me" in c for c in subject.host_merge_requests.__code__.co_consts)
assert "--hostname" in subject.host_merge_requests.__code__.co_consts
assert "--paginate" in subject.host_merge_requests.__code__.co_consts
assert "--all" in subject.glab_hosts.__code__.co_consts

# authenticated_hosts reads real `glab auth status --all` shape: a host line,
# then indented status lines, with the next instance's block starting on the
# very next line (status.go prints no separator). A failed instance between
# two working ones is not credited with a neighbour's login, a host may
# carry a port (glab api then refuses it, and that lands under the host's
# own error key below), and no login at all is an empty list, which
# glab_hosts turns into an error rather than a silent zero.
GLAB_STATUS = (
    "gitlab.com\n"
    "  \u2713 Logged in to gitlab.com as ezra (keyring)\n"
    "  \u2713 Git operations for gitlab.com configured to use https protocol.\n"
    "old.example.org\n"
    "  x old.example.org: API call failed: 401 Unauthorized\n"
    "gitlab.example.com:8443\n"
    "  \u2713 Logged in to gitlab.example.com:8443 as ezra (token)\n"
)
# A fully configured instance whose token expired, rendered line for line
# from status.go's format strings, plus glab's trailing summary. Its
# diagnosis is the FIRST status line, which is why ERROR_TAIL is sized to
# whole blocks: the tail of a no-host error must still carry that line.
GLAB_STATUS_FAILED_FULL = (
    "gitlab.example.com\n"
    "  x gitlab.example.com: API call failed: GET https://gitlab.example.com/api/v4/user: 401 {message: 401 Unauthorized}\n"
    "  \u2713 Git operations for gitlab.example.com configured to use https protocol.\n"
    "  \u2713 API calls for gitlab.example.com are made over https protocol.\n"
    "  \u2713 REST API Endpoint: https://gitlab.example.com/api/v4/\n"
    "  \u2713 GraphQL Endpoint: https://gitlab.example.com/api/graphql/\n"
    "  \u2713 Token found in operating system keyring: **************************\n"
    "\n"
    "x could not authenticate to one or more of the configured GitLab instances\n"
)
# The largest single-instance listing status.go produces: a 401 on a token
# taken from an environment variable, which adds three hint lines inside
# the block (status.go's env-token branch) and a three-line trailer before
# the summary. ERROR_TAIL must hold this whole rendering, or the tail drops
# the diagnosis on exactly the configuration that most needs it.
GLAB_STATUS_ENV_TOKEN_401 = (
    "gitlab.example.com\n"
    "  x gitlab.example.com: API call failed: GET https://gitlab.example.com/api/v4/user: 401 {message: 401 Unauthorized}\n"
    "    ! Token is from environment variable GITLAB_TOKEN. A wrapper may be injecting a different or expired token.\n"
    "    ! To investigate, run type glab: an alias such as 'op plugin run -- glab' means a wrapper (for example, a 1Password shell plugin) is injecting the token; a plain path rules that out.\n"
    "    ! To see the token value in use, run: env | grep -E 'GITLAB_TOKEN|GITLAB_ACCESS_TOKEN|OAUTH_TOKEN'\n"
    "  \u2713 Git operations for gitlab.example.com configured to use https protocol.\n"
    "  \u2713 API calls for gitlab.example.com are made over https protocol.\n"
    "  \u2713 REST API Endpoint: https://gitlab.example.com/api/v4/\n"
    "  \u2713 GraphQL Endpoint: https://gitlab.example.com/api/graphql/\n"
    "  \u2713 Token found in environment variable GITLAB_TOKEN: **************************\n"
    "\n"
    "! Token is from environment variable GITLAB_TOKEN. This takes precedence over tokens stored in config or keyring.\n"
    "  Run type glab to find the source: an alias such as 'op plugin run -- glab' means a wrapper (for example, a 1Password shell plugin) is injecting it, which is expected and needs no action.\n"
    "  A plain path means it is set in your environment (for example, a shell profile such as ~/.bashrc or ~/.zshrc, or a CI/CD variable); remove it there so glab uses your stored credentials.\n"
    "\n"
    "x could not authenticate to one or more of the configured GitLab instances\n"
)
assert 400 <= len(GLAB_STATUS_FAILED_FULL) <= 600, len(GLAB_STATUS_FAILED_FULL)
assert 1300 <= len(GLAB_STATUS_ENV_TOKEN_401) <= 1700, len(GLAB_STATUS_ENV_TOKEN_401)
assert len(GLAB_STATUS_ENV_TOKEN_401) + len(GLAB_STATUS_FAILED_FULL) <= subject.ERROR_TAIL
assert subject.authenticated_hosts(GLAB_STATUS) == ["gitlab.com", "gitlab.example.com:8443"]
assert subject.authenticated_hosts("gitlab.com\n  x gitlab.com: API call failed: 401\n") == []
assert subject.authenticated_hosts("") == []

# json_documents reads one page or several back to back, which is what
# `glab api --paginate` writes for a multi-page REST response.
assert subject.json_documents("[1, 2]") == [[1, 2]]
assert subject.json_documents("[1, 2]\n[3]\n") == [[1, 2], [3]]
# Real `glab api --paginate` writes the pages with NO separator (a bare
# io.Copy per page), so the boundary a line-based decoder cannot see is
# the one that matters.
assert subject.json_documents("[1, 2][3]") == [[1, 2], [3]]
assert subject.json_documents("") == []

# glab_hosts, host_merge_requests, and poll_once end to end against a stub
# glab: the hosts come from `auth status --all`, every host is queried with
# --paginate, pages are concatenated, and a host glab api refuses (the
# port-carrying one, as the real glab does) costs only its own entry. The
# stub records its argv so the flags are asserted rather than assumed.
import os
import stat
import tempfile
with tempfile.TemporaryDirectory() as d:
    argv_log = os.path.join(d, "argv.log")
    status_file = os.path.join(d, "status.txt")
    with open(status_file, "w", encoding="utf-8") as stream:
        stream.write(GLAB_STATUS)
    stub = os.path.join(d, "glab")
    with open(stub, "w", encoding="utf-8") as stream:
        stream.write(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"open({argv_log!r}, 'a').write(' '.join(sys.argv[1:]) + chr(10))\n"
            "if sys.argv[1:3] == ['auth', 'status']:\n"
            f"    text = open({status_file!r}, encoding='utf-8').read()\n"
            "    sys.stderr.write(text)\n"
            "    sys.exit(1 if ('Error:' in text or 'failed' in text) else 0)\n"
            "host = sys.argv[sys.argv.index('--hostname') + 1]\n"
            "if ':' in host:\n"
            "    sys.stderr.write('invalid hostname' + chr(10))\n"
            "    sys.exit(1)\n"
            "if host == 'noisy.example.org':\n"
            "    sys.stderr.write('HEAD-OF-STDERR ' + 'x' * 9000 + ' TAIL-OF-STDERR')\n"
            "    sys.exit(1)\n"
            "if host == 'gitlab.com':\n"
            "    sys.stdout.write('[{\"iid\": 1, \"description\": \"long\", \"user_notes_count\": 4}, {\"iid\": 2}][{\"iid\": 3}]')\n"
            "elif host == 'object.example.org':\n"
            "    sys.stdout.write('{\"message\": \"401 Unauthorized\"}')\n"
            "elif host == 'scalars.example.org':\n"
            "    sys.stdout.write('[1, 2]')\n"
            "else:\n"
            "    sys.stdout.write('[]')\n")
    os.chmod(stub, os.stat(stub).st_mode | stat.S_IEXEC)
    saved = (subject.GH_PATH, subject.GLAB_PATH, subject.STATE_PATH)
    try:
        subject.GH_PATH = None
        subject.GLAB_PATH = stub if os.name != "nt" else None
        subject.STATE_PATH = os.path.join(d, "state.json")
        if subject.GLAB_PATH is not None:
            # Real glab exits 1 when ANY instance fails, even beside a working
            # one (status.go; `--all` itself is v1.79.0 onward), so a mixed status is exit 1 and
            # still lists the working hosts -- the exit status is not read
            # when parsing, only carried into the no-host error.
            assert subject.glab_hosts() == (["gitlab.com", "gitlab.example.com:8443"], None)
            # Each merge request is projected to MERGE_REQUEST_FIELDS: the
            # volatile fields the stub carries (a description, a note
            # count) never reach the state file.
            def mr(iid):
                return {field: (iid if field == "iid" else None)
                        for field in subject.MERGE_REQUEST_FIELDS}
            assert subject.host_merge_requests("gitlab.com") == [mr(1), mr(2), mr(3)]
            state = subject.poll_once({})
            assert state["data"] == {"gitlab_merge_requests/gitlab.com": [mr(1), mr(2), mr(3)]}, state
            errors = json.loads(state["error"])
            assert list(errors) == ["gitlab_merge_requests/gitlab.example.com:8443"], errors
            refused = errors["gitlab_merge_requests/gitlab.example.com:8443"]
            assert "returned non-zero exit status 1" in refused and "invalid hostname" in refused, refused
            with open(argv_log, encoding="utf-8") as stream:
                calls = stream.read().splitlines()
            assert calls[0] == "auth status --all", calls
            assert calls[1].startswith("api --hostname gitlab.com --paginate "), calls
            # glab_hosts ran once more for poll_once, then one api call per host.
            assert calls[2] == "auth status --all", calls
            assert calls[3].startswith("api --hostname gitlab.com --paginate "), calls
            assert calls[4].startswith("api --hostname gitlab.example.com:8443 --paginate "), calls
            assert len(calls) == 5, calls
            # Both routes that keep a CLI's own output keep a bounded tail:
            # an oversized stderr on the api route ...
            saved_hosts = subject.glab_hosts
            try:
                subject.glab_hosts = lambda: (["noisy.example.org"], None)
                state = subject.poll_once({})
            finally:
                subject.glab_hosts = saved_hosts
            noisy = json.loads(state["error"])["gitlab_merge_requests/noisy.example.org"]
            assert noisy.endswith("TAIL-OF-STDERR") and "HEAD-OF-STDERR" not in noisy, noisy[:80]
            assert len(noisy.rsplit("status 1.: ", 1)[1]) == subject.ERROR_TAIL, len(noisy)
            # ... and an oversized status listing on the no-host route, whose
            # tail still carries a full failed block's first-line diagnosis.
            with open(status_file, "w", encoding="utf-8") as stream:
                stream.write("HEAD-OF-STATUS " + "y" * 9000 + "\n" + GLAB_STATUS_ENV_TOKEN_401)
            try:
                subject.glab_hosts()
                raise AssertionError("no authenticated hosts should raise")
            except OSError as error:
                text = str(error)
                assert "(exit 1)" in text and "API call failed" in text and "HEAD-OF-STATUS" not in text, text[:120]
                assert len(text.split("): ", 1)[1]) == subject.ERROR_TAIL, len(text)
            # A page that is not a JSON array is an error, never stored as
            # merge requests (an error object would flatten to its keys).
            try:
                subject.host_merge_requests("object.example.org")
                raise AssertionError("a non-array page should raise")
            except ValueError as error:
                assert "expected a JSON array page" in str(error)
            # ... and so is an array whose elements are not objects: a
            # ValueError lands under the host's error key, where an
            # AttributeError would have ended the daemon.
            try:
                subject.host_merge_requests("scalars.example.org")
                raise AssertionError("a page of non-objects should raise")
            except ValueError as error:
                assert "expected merge-request objects" in str(error)
            # No authenticated host is an error, never a silent empty list.
            with open(status_file, "w", encoding="utf-8") as stream:
                stream.write("gitlab.com\n  x gitlab.com: API call failed: 401\n")
            try:
                subject.glab_hosts()
                raise AssertionError("no authenticated hosts should raise")
            except OSError as error:
                assert "listed no authenticated host (exit 1)" in str(error), error
                assert "API call failed: 401" in str(error), error
            state = subject.poll_once({})
            assert state["data"] == {}
            assert list(json.loads(state["error"])) == ["gitlab_merge_requests"]
            # An invocation glab REFUSES (a glab older than v1.79.0 has no
            # `--all`) is not an authentication state: the error carries
            # glab's exit status and its own message.
            with open(status_file, "w", encoding="utf-8") as stream:
                stream.write("Error: unknown flag: --all\n")
            try:
                subject.glab_hosts()
                raise AssertionError("a refused status call should raise")
            except OSError as error:
                assert "(exit 1)" in str(error) and "unknown flag: --all" in str(error), error
        else:
            print("SKIP: stub-glab end-to-end block (needs a POSIX executable stub)")
    finally:
        subject.GH_PATH, subject.GLAB_PATH, subject.STATE_PATH = saved

# glab_hosts keeps the hosts that answered when `auth status --all` times
# out on a later instance: the partial output is parsed, not discarded, and
# the cut is reported so poll_once records it. The fixture carries BYTES,
# which is what subprocess.run attaches to TimeoutExpired under text=True on
# POSIX (measured on CPython 3.11; Windows attaches str) -- a str fixture
# would leave a real POSIX timeout's TypeError unseen.
real_run = subject.subprocess.run
glab_before_timeout_case = subject.GLAB_PATH
try:
    def timing_out(*args, **kwargs):
        raise subject.subprocess.TimeoutExpired(
            args[0], kwargs.get("timeout"), output=b"", stderr=GLAB_STATUS.encode())
    subject.subprocess.run = timing_out
    subject.GLAB_PATH = subject.GLAB_PATH or "glab"
    hosts, cut_short = subject.glab_hosts()
    assert hosts == ["gitlab.com", "gitlab.example.com:8443"]
    assert "timed out" in cut_short and "polled" in cut_short, cut_short

    # A timeout with no host answered is an error too, and it keeps the
    # partial output glab did write, exactly as the completed-run branch does.
    def timing_out_failed(*args, **kwargs):
        raise subject.subprocess.TimeoutExpired(
            args[0], kwargs.get("timeout"), output=b"", stderr=GLAB_STATUS_FAILED_FULL.encode())
    subject.subprocess.run = timing_out_failed
    try:
        subject.glab_hosts()
        raise AssertionError("a timeout with no host answered should raise")
    except OSError as error:
        assert "timed out" in str(error) and "API call failed" in str(error), error
finally:
    subject.subprocess.run = real_run
    subject.GLAB_PATH = glab_before_timeout_case

# Verify read_state / write_state roundtrip preserves reported fingerprint
with tempfile.TemporaryDirectory() as d:
    orig_path = subject.STATE_PATH
    subject.STATE_PATH = os.path.join(d, "test-prs.json")
    try:
        subject.write_state({"reported": "f1ng3rpr1nt", "prior": 123})
        s = subject.read_state()
        assert s.get("reported") == "f1ng3rpr1nt"
        s.update({"checked_at": 999})
        subject.write_state(s)
        subject.write_state({"data": [{"number": 1}], "reported": "f1ng3rpr1nt"})
        s = subject.read_state()
        assert s.get("data") == [{"number": 1}]
        s.pop("data", None)
        s["error"] = "Command failed"
        subject.write_state(s)
        assert subject.read_state().get("error") == "Command failed"
        assert "data" not in subject.read_state()
    finally:
        subject.STATE_PATH = orig_path

# require_cli fails fast instead of starting a monitor that can only error.
saved_gh = subject.GH_PATH
saved_glab = subject.GLAB_PATH
try:
    subject.GH_PATH = None
    subject.GLAB_PATH = None
    try:
        subject.require_cli()
        raise AssertionError("require_cli should exit when no CLI is resolvable")
    except SystemExit as exit_call:
        assert "gh" in str(exit_call.code)
finally:
    subject.GH_PATH = saved_gh
    subject.GLAB_PATH = saved_glab

# A GitHub failure must not suppress GitLab monitoring. Consecutive failures
# accumulate an error_streak; a full success resets it.
with tempfile.TemporaryDirectory() as d:
    orig_path = subject.STATE_PATH
    real_open_prs = subject.open_prs
    real_glab_hosts = subject.glab_hosts
    real_host_merge_requests = subject.host_merge_requests

    def failing():
        raise OSError("[Errno 2] No such file or directory: 'gh'")

    def working():
        return [{"number": 7}]

    def one_host():
        return ["gitlab.com"], None

    def working_gitlab(host):
        return [{"iid": 8}]

    # poll_once queries only the sources whose CLI resolves, so both paths
    # are pinned to a placeholder here: the queries themselves are stubbed.
    saved_paths = (subject.GH_PATH, subject.GLAB_PATH)
    try:
        subject.GH_PATH = subject.GH_PATH or "gh"
        subject.GLAB_PATH = subject.GLAB_PATH or "glab"
        subject.STATE_PATH = os.path.join(d, "streak.json")
        subject.open_prs = failing
        subject.glab_hosts = one_host
        subject.host_merge_requests = working_gitlab
        state = subject.poll_once({})
        assert "github_prs" not in state["data"]
        assert state["data"]["gitlab_merge_requests/gitlab.com"] == [{"iid": 8}]
        assert "github_prs" in state["error"]
        assert state["error_streak"] == 1
        state = subject.poll_once(state)
        assert state["error_streak"] == 2

        # A different error text restarts the streak: the streak counts
        # consecutive polls of the SAME error, so a new failure mode earns
        # its own persistent report downstream.
        def failing_differently():
            raise OSError("connection timed out")

        subject.open_prs = failing_differently
        state = subject.poll_once(state)
        assert "connection timed out" in state["error"]
        assert state["error_streak"] == 1
        state = subject.poll_once(state)
        assert state["error_streak"] == 2

        # Every source failing leaves "data" present but empty, with the
        # error naming every failed source. inject-pr-monitor-status.py's
        # fingerprint covers the error text beside the data, so a changed
        # error text under this constant empty data still surfaces.
        def no_hosts():
            raise OSError("glab auth status --all listed no authenticated host (exit 1): ")

        subject.glab_hosts = no_hosts
        state = subject.poll_once(state)
        assert state["data"] == {}
        assert "github_prs" in state["error"] and "gitlab_merge_requests" in state["error"]
        assert state["error_streak"] == 1

        # One GitLab host failing costs only its own entry: the other
        # host's merge requests are kept and the error names the host.
        def two_hosts():
            return ["gitlab.com", "down.example.org"], None

        def one_down(host):
            if host == "down.example.org":
                raise OSError("connection refused")
            return [{"iid": 8}]

        subject.open_prs = working
        subject.glab_hosts = two_hosts
        subject.host_merge_requests = one_down
        state = subject.poll_once(state)
        assert state["data"] == {
            "github_prs": [{"number": 7}],
            "gitlab_merge_requests/gitlab.com": [{"iid": 8}]
        }, state
        assert json.loads(state["error"]) == {"gitlab_merge_requests/down.example.org": "connection refused"}

        # A host list cut short by the auth-status timeout is an error
        # beside the hosts that did answer, never a clean poll.
        def cut_short():
            return ["gitlab.com"], "Command timed out after 120 seconds; hosts listed before the timeout were polled"

        subject.glab_hosts = cut_short
        subject.host_merge_requests = working_gitlab
        state = subject.poll_once(state)
        assert state["data"]["gitlab_merge_requests/gitlab.com"] == [{"iid": 8}]
        assert json.loads(state["error"]) == {
            "gitlab_merge_requests": "Command timed out after 120 seconds; hosts listed before the timeout were polled"}

        subject.glab_hosts = one_host
        subject.host_merge_requests = working_gitlab
        state = subject.poll_once(state)
        assert "error" not in state
        assert state["error_streak"] == 0
        assert state["data"] == {
            "github_prs": [{"number": 7}],
            "gitlab_merge_requests/gitlab.com": [{"iid": 8}]
        }

        # A source whose CLI is missing is not checked, and its key stays
        # absent: an empty list would assert "none open" about a source the
        # poll never asked. No error either -- the host simply lacks it.
        gh_before = subject.GH_PATH
        try:
            subject.GH_PATH = None
            state = subject.poll_once(state)
            assert state["data"] == {"gitlab_merge_requests/gitlab.com": [{"iid": 8}]}
            assert "error" not in state
            # Neither CLI is a refusal, never a "checked, none open" file.
            subject.GLAB_PATH = None
            try:
                subject.poll_once(state)
                raise AssertionError("no CLI at all should raise")
            except OSError as error:
                assert "nothing to poll" in str(error)
        finally:
            subject.GH_PATH = gh_before
    finally:
        subject.open_prs = real_open_prs
        subject.glab_hosts = real_glab_hosts
        subject.host_merge_requests = real_host_merge_requests
        subject.GH_PATH, subject.GLAB_PATH = saved_paths
        subject.STATE_PATH = orig_path

# alive() must be truthful on every platform: signal-0 does not track
# liveness on Windows (#2082), so the probe is OpenProcess there.
# Non-positive and garbage pids are refused before any probe -- signal 0
# to -1 would address a whole process group on POSIX.
for bad in (None, "abc", 0, -1, -999):
    assert subject.alive(bad) is False, f"alive({bad!r}) should be False"
assert subject.alive(os.getpid()) is True
assert subject.alive(2 ** 30) is False
if os.name == "nt":
    assert subject._alive_windows(os.getpid()) is True

print("PASS: GitHub and GitLab CLIs are resolved or refused at startup; "
      "failures accumulate an error streak that success resets")
