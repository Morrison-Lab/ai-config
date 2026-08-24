#!/usr/bin/env python3
"""Regression tests for rotate-claude-token.py.

Every test stubs the module's own `gh()`, so nothing here touches the network
or a real repo. The stub records what it was called with, which is what lets
the argv test below assert a property no observation of the script's output
could establish.
"""
import importlib.util
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "rct", Path(__file__).parent / "rotate-claude-token.py"
)
rct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rct)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def secrets_payload(*names_and_times):
    """What `gh api --paginate --jq '.secrets[]'` writes: one entry per line.

    NDJSON rather than a single object, because that is the shape the script
    actually reads. A fixture returning one object per call would pass just as
    happily against a bare `--paginate`, which this endpoint breaks on -- so
    it would pin the bug rather than catch it. See the pagination test below.
    """
    pairs = zip(names_and_times[::2], names_and_times[1::2])
    return "".join(
        json.dumps({"name": n, "updated_at": t}) + "\n" for n, t in pairs
    )


class FakeGh:
    """Stand-in for `rct.gh` that records calls and replays canned answers."""

    def __init__(self, answers=None, fail_for=None):
        self.answers = answers or {}
        self.fail_for = fail_for or set()
        self.calls = []

    def __call__(self, args, stdin=None):
        self.calls.append({"args": list(args), "stdin": stdin})
        for repo in self.fail_for:
            if any(repo in arg for arg in args):
                raise rct.GhError("HTTP 403: forbidden")
        if args[0] == "secret":
            return ""
        for key, value in self.answers.items():
            if any(key in arg for arg in args):
                return value
        return self.answers.get("*", secrets_payload())


def with_gh(fake):
    rct.gh = fake
    return fake


# --- secret_updated_at -------------------------------------------------

with_gh(
    FakeGh({"owner/has": secrets_payload("CLAUDE_CODE_OAUTH_TOKEN", "2026-07-28T00:00:00Z")})
)
check(
    "secret_updated_at returns the timestamp when the secret is present",
    rct.secret_updated_at("owner/has", "CLAUDE_CODE_OAUTH_TOKEN")
    == "2026-07-28T00:00:00Z",
)

with_gh(FakeGh({"owner/other": secrets_payload("CODECOV_TOKEN", "2026-01-01T00:00:00Z")}))
check(
    "secret_updated_at returns None when only unrelated secrets exist",
    rct.secret_updated_at("owner/other", "CLAUDE_CODE_OAUTH_TOKEN") is None,
)

# --- secret_updated_at over paginated output ---------------------------

# Why the `.secrets[]` projection is required rather than stylistic: this
# endpoint returns an object, so a bare `--paginate` emits one object per page
# and the concatenation is not valid JSON. Measured against the real API on
# Morrison-Lab/ai-config with `?per_page=1`, which forces two pages.
two_pages = (
    '{"total_count":2,"secrets":[{"name":"A","updated_at":"t1"}]}'
    '{"total_count":2,"secrets":[{"name":"B","updated_at":"t2"}]}'
)
try:
    json.loads(two_pages)
    concatenated_parses = True
except json.JSONDecodeError:
    concatenated_parses = False
check(
    "a bare --paginate on this endpoint yields output json.loads cannot read",
    not concatenated_parses,
)

fake = with_gh(
    FakeGh(
        {
            "owner/many": secrets_payload(
                "FIRST_PAGE_SECRET", "2026-01-01T00:00:00Z",
                "CLAUDE_CODE_OAUTH_TOKEN", "2026-07-30T00:00:00Z",
            )
        }
    )
)
check(
    "secret_updated_at finds a secret that falls beyond the first page",
    rct.secret_updated_at("owner/many", "CLAUDE_CODE_OAUTH_TOKEN")
    == "2026-07-30T00:00:00Z",
)
check(
    "secret_updated_at asks gh for the flattened .secrets[] projection",
    fake.calls[-1]["args"][-2:] == ["--jq", ".secrets[]"],
)

# --- find_targets ------------------------------------------------------

fake = with_gh(
    FakeGh(
        answers={
            "owner/has": secrets_payload("CLAUDE_CODE_OAUTH_TOKEN", "2026-07-28T00:00:00Z"),
            "owner/lacks": secrets_payload("CODECOV_TOKEN", "2026-01-01T00:00:00Z"),
        },
        fail_for={"owner/denied"},
    )
)
targets, errors = rct.find_targets(
    ["owner/has", "owner/lacks", "owner/denied"], "CLAUDE_CODE_OAUTH_TOKEN", 2
)
check(
    "find_targets selects only repos carrying the secret",
    [repo for repo, _ in targets] == ["owner/has"],
)
check(
    "find_targets reports an unreadable repo as an error, not a silent miss",
    [repo for repo, _ in errors] == ["owner/denied"],
)
check(
    "a repo merely lacking the secret is neither a target nor an error",
    all("owner/lacks" not in repo for repo, _ in targets + errors),
)

# Unparseable output must be attributed to its own repo. Before this was
# caught, a single bad response raised through the executor and killed the
# whole sweep, taking every other repo's result with it.
with_gh(
    FakeGh(
        answers={
            "owner/good": secrets_payload(
                "CLAUDE_CODE_OAUTH_TOKEN", "2026-07-28T00:00:00Z"
            ),
            "owner/garbled": "{not json at all\n",
        }
    )
)
targets, errors = rct.find_targets(
    ["owner/good", "owner/garbled"], "CLAUDE_CODE_OAUTH_TOKEN", 2
)
check(
    "unparseable output is reported against its repo, not raised through the sweep",
    [repo for repo, _ in errors] == ["owner/garbled"]
    and [repo for repo, _ in targets] == ["owner/good"],
)

# --- rotate ------------------------------------------------------------

fake = with_gh(
    FakeGh({"owner/repo": secrets_payload("TOK", "2026-07-31T09:00:00Z")})
)
check(
    "rotate returns the new timestamp when updated_at advances",
    rct.rotate("owner/repo", "TOK", "s3cret", "2026-07-28T00:00:00Z")
    == "2026-07-31T09:00:00Z",
)

# The security-critical property: a recorded secret value in argv would be
# visible to `ps` and land in shell history, so pin it rather than trust it.
set_calls = [c for c in fake.calls if c["args"][0] == "secret"]
check(
    "rotate sends the token on stdin",
    len(set_calls) == 1 and set_calls[0]["stdin"] == "s3cret",
)
check(
    "rotate never places the token in argv",
    all("s3cret" not in arg for call in fake.calls for arg in call["args"]),
)

# A write that silently no-ops must not pass for a rotation.
with_gh(FakeGh({"owner/repo": secrets_payload("TOK", "2026-07-28T00:00:00Z")}))
try:
    rct.rotate("owner/repo", "TOK", "s3cret", "2026-07-28T00:00:00Z")
    unchanged_raised = False
except rct.GhError:
    unchanged_raised = True
check("rotate raises when updated_at does not change", unchanged_raised)

with_gh(FakeGh({"owner/repo": secrets_payload("OTHER", "2026-07-28T00:00:00Z")}))
try:
    rct.rotate("owner/repo", "TOK", "s3cret", "2026-07-28T00:00:00Z")
    absent_raised = False
except rct.GhError:
    absent_raised = True
check("rotate raises when the secret is absent after the write", absent_raised)

# --- read_token --------------------------------------------------------

real_stdin = sys.stdin

sys.stdin = io.StringIO("  piped-token\n")
check(
    "read_token strips whitespace from a piped token",
    rct.read_token("SOME_UNSET_VAR_FOR_TESTS") == "piped-token",
)

sys.stdin = io.StringIO("   \n")
try:
    rct.read_token("SOME_UNSET_VAR_FOR_TESTS")
    empty_exited = False
except SystemExit:
    empty_exited = True
check("read_token exits rather than write an empty secret", empty_exited)

sys.stdin = io.StringIO("piped")
import os  # noqa: E402 -- deferred so the env var is set only for this case

os.environ["ROTATE_TEST_TOKEN"] = "from-env"
check(
    "read_token prefers the environment variable over stdin",
    rct.read_token("ROTATE_TEST_TOKEN") == "from-env",
)
del os.environ["ROTATE_TEST_TOKEN"]

sys.stdin = real_stdin

# --- admin_repos / collect_repos ---------------------------------------

with_gh(
    FakeGh(
        {
            "acme": json.dumps(
                [
                    {"nameWithOwner": "acme/admin", "viewerPermission": "ADMIN"},
                    {"nameWithOwner": "acme/write", "viewerPermission": "WRITE"},
                    {"nameWithOwner": "acme/none", "viewerPermission": None},
                ]
            )
        }
    )
)
check(
    "admin_repos keeps only ADMIN repos",
    rct.admin_repos("acme") == ["acme/admin"],
)


class Args:
    def __init__(self, repos=None, owners=None):
        self.repos = repos
        self.owners = owners


with_gh(FakeGh())
repos, owners = rct.collect_repos(Args(repos=["b/two", "a/one", "a/one"]))
check(
    "collect_repos dedupes and sorts an explicit --repos list",
    repos == ["a/one", "b/two"],
)
check("an explicit --repos list reports no swept owners", owners == [])


# --- discover_owners, and the default path through collect_repos -------

fake = with_gh(FakeGh({"/user/orgs": "acme\nwidgets\n", "/user": "octocat\n"}))
check(
    "discover_owners returns the authenticated login followed by its orgs",
    rct.discover_owners() == ["octocat", "acme", "widgets"],
)
check(
    "discover_owners paginates /user/orgs, so a 31st org is not dropped",
    any(
        "--paginate" in call["args"]
        for call in fake.calls
        if any("/user/orgs" in arg for arg in call["args"])
    ),
)

with_gh(
    FakeGh(
        {
            "/user/orgs": "acme\n",
            "/user": "octocat\n",
            "acme": json.dumps(
                [{"nameWithOwner": "acme/one", "viewerPermission": "ADMIN"}]
            ),
            "octocat": json.dumps(
                [
                    {"nameWithOwner": "octocat/two", "viewerPermission": "ADMIN"},
                    {"nameWithOwner": "octocat/ro", "viewerPermission": "READ"},
                ]
            ),
        }
    )
)
repos, owners = rct.collect_repos(Args())
check(
    "collect_repos falls back to discover_owners when neither flag is given",
    repos == ["acme/one", "octocat/two"] and owners == ["octocat", "acme"],
)

# The Windows cp1252 decode guards in `gh()`. Pinned HERE rather than only in
# the sibling suites, because `test_pr_sweep.py` makes the argument itself: a
# pin in another file proves nothing about this one. This script's stdout is not
# realistically exposed (every call reads ASCII-only GitHub identifiers), but
# its stderr is -- a `gh` failure can surface a non-ASCII OS error string on a
# non-English Windows install -- and the guards must behave the same either way.
from unittest.mock import patch  # noqa: E402

# A PRISTINE copy of the module. `with_gh` above replaces `rct.gh` globally and
# never restores it, which is fine for every test wanting a stubbed `gh` and
# fatal for these, which test `gh` itself.
#
# A one-line alternative exists and was rejected for a reason worth stating,
# since it is the cheaper option: capturing `_real_gh = rct.gh` right after the
# `exec_module` above would work and needs no second module. A second instance
# is used because it also isolates `GhError` and any future module-level state
# these cases touch, so a stub installed later cannot reach them.
#
# THE TRAP that buys: `rct_real.GhError is not rct.GhError`. They are distinct
# classes from distinct module objects, so `except rct.GhError` around a
# `rct_real` call silently fails to catch. Every case below uses `rct_real` on
# both sides. Note also that `patch.object(rct_real.subprocess, ...)` is NOT
# scoped by the second module -- both instances share `sys.modules['subprocess']`
# -- so those patches are global for their `with` block.
_spec_real = importlib.util.spec_from_file_location(
    "rct_real", Path(__file__).parent / "rotate-claude-token.py"
)
rct_real = importlib.util.module_from_spec(_spec_real)
_spec_real.loader.exec_module(rct_real)


class _NoneStdout:
    returncode = 0
    stdout = None
    stderr = ""


with patch.object(rct_real.subprocess, "run", lambda *a, **kw: _NoneStdout()):
    try:
        rct_real.gh(["api", "/user"])
        outcome = "returned normally"
    except SystemExit as exc:
        outcome = f"SystemExit:{exc}"
    except AttributeError:
        outcome = "AttributeError"
check(
    "gh() exits on None stdout rather than returning it to a caller that will .strip() it",
    outcome.startswith("SystemExit:") and "environment failure" in outcome,
)


class _NoneStderr:
    returncode = 1
    stdout = ""
    stderr = None


with patch.object(rct_real.subprocess, "run", lambda *a, **kw: _NoneStderr()):
    try:
        rct_real.gh(["api", "/user"])
        outcome = "returned normally"
    except SystemExit as exc:
        outcome = f"SystemExit:{exc}"
    except rct_real.GhError:
        outcome = "GhError"
    except AttributeError:
        outcome = "AttributeError"
check(
    "gh() exits on a failed call whose stderr could not be decoded",
    outcome.startswith("SystemExit:"),
)


class _RealStderr:
    returncode = 1
    stdout = ""
    stderr = "gh: Not Found (HTTP 404)\n"


with patch.object(rct_real.subprocess, "run", lambda *a, **kw: _RealStderr()):
    try:
        rct_real.gh(["api", "/user"])
        outcome = "returned normally"
    except SystemExit:
        outcome = "SystemExit"
    except rct_real.GhError as exc:
        outcome = f"GhError:{exc}"
check(
    "negative control: a readable-stderr failure still raises GhError, not SystemExit",
    outcome.startswith("GhError:") and "404" in outcome,
)

recorded = {}


class _Ok:
    returncode = 0
    stdout = "octocat\n"
    stderr = ""


def _rec(cmd, **kwargs):
    recorded.update(kwargs)
    return _Ok()


with patch.object(rct_real.subprocess, "run", _rec):
    rct_real.gh(["api", "/user", "--jq", ".login"])
check("gh() decodes subprocess output as UTF-8 explicitly",
      recorded.get("encoding") == "utf-8")

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
