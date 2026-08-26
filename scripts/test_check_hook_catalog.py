#!/usr/bin/env python3
"""Regression tests for check-hook-catalog.py.

Every case runs the real script as a subprocess against a scratch repo, so the
control enters at the same entry point CI uses rather than at an internal
function that is already trusted.

The cases that matter most are the negative ones: a check nobody has watched
fail is a guess about what it covers. Each drift shape the script claims to
catch gets a case here that exits non-zero, and the "vacuous parse" pair covers
the way this particular check could silently pass forever -- a README whose
table shape changed would otherwise make every set comparison compare nothing.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "check-hook-catalog.py"
ROOT = Path(__file__).parent.parent

# Read KNOWN_UNREGISTERED from the script itself rather than restating it. A
# second hand-maintained copy goes stale the moment the allowlist changes --
# which ai-config#1505 exists to make happen -- and the fixtures below would
# then fail for a reason unrelated to whatever that change was.
#
# Only the FIXTURES derive from it. Every assertion keys on the script's own
# output strings, so this cannot become the case where a test's fixture and
# its expectation move together and a wrong constant satisfies both
# (`shared/principles/dont-incur-technical-debt.md`). The last case is
# anchored outside the constant entirely: it runs against the live repo.
_spec = importlib.util.spec_from_file_location("check_hook_catalog", SCRIPT)
_catalog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_catalog)
ALLOWLISTED = sorted(_catalog.KNOWN_UNREGISTERED)

passes = 0
failures = 0
skipped = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def skip(name, why):
    """Record a case that could not run, so a vacuous pass stays visible."""
    global skipped
    print(f"SKIP: {name} ({why})")
    skipped += 1


def hooks_json(entries):
    """entries: list of (script, event, matcher). Returns JSON text."""
    events = {}
    for script, event, matcher in entries:
        events.setdefault(event, {}).setdefault(matcher, []).append(script)
    groups = {}
    for event, by_matcher in events.items():
        out = []
        for matcher, scripts in by_matcher.items():
            group = {"hooks": [{"type": "command", "script": s} for s in scripts]}
            if matcher:
                group["matcher"] = matcher
            out.append(group)
        groups[event] = out
    import json
    return json.dumps({"hooks": groups}, indent=2)


def readme(rows, heading="## Enforcement hooks (`hooks/`)"):
    """rows: list of (script, event, matcher, rest). Returns README text."""
    body = [
        "# Title", "", "## Something else", "", "prose", "", heading, "",
        "| hook | event | enforces |", "|---|---|---|",
    ]
    for script, event, matcher, rest in rows:
        ev = f"`{event}`" + (f" ({matcher})" if matcher else "")
        body.append(f"| `{script}` | {ev} | {rest} |")
    body += ["", "trailing prose", "", "## After", "", "more"]
    return "\n".join(body) + "\n"


def make_repo(tmpdir, entries, rows, heading=None, allowlisted=None):
    root = Path(tmpdir)
    (root / "scripts").mkdir()
    (root / "hooks").mkdir()
    script_text = SCRIPT.read_text(encoding="utf-8")
    if allowlisted is not None:
        import re
        assert "KNOWN_UNREGISTERED = {" in script_text, (
            "check-hook-catalog.py shape changed; KNOWN_UNREGISTERED = { not found"
        )
        replacement = "KNOWN_UNREGISTERED = {\n" + "\n".join(f'    "{s}": 9999,' for s in allowlisted) + "\n}"
        script_text = re.sub(r"KNOWN_UNREGISTERED = \{[^}]*\}", replacement, script_text)
    (root / "scripts" / "check-hook-catalog.py").write_text(
        script_text, encoding="utf-8")
    (root / "hooks" / "hooks.json").write_text(
        hooks_json(entries), encoding="utf-8")
    kwargs = {"heading": heading} if heading else {}
    (root / "README.md").write_text(readme(rows, **kwargs), encoding="utf-8")
    return root


def run(root, issue_states="unfetchable"):
    """Run the copied check. Fixture tests default to unfetchable trackers
    so they never hit the network and never depend on live issue state.
    Pass issue_states=None to fetch live (the real-repo case).
    """
    env = os.environ.copy()
    if issue_states is None:
        env.pop("HOOK_CATALOG_ISSUE_STATES", None)
    elif isinstance(issue_states, str):
        env["HOOK_CATALOG_ISSUE_STATES"] = issue_states
    else:
        env["HOOK_CATALOG_ISSUE_STATES"] = json.dumps(issue_states)
    proc = subprocess.run(
        [sys.executable, str(Path(root) / "scripts" / "check-hook-catalog.py")],
        capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


# The allowlisted hooks in the live script, documented with the required marker.
# Every fixture starts from these so the allowlist checks are satisfied by default.
ALLOW_ROWS = [(s, "PreToolUse", "Bash", f"**not registered ([#{issue}](u))** --- would block")
              for s, issue in sorted(_catalog.KNOWN_UNREGISTERED.items())]


def case(name, entries, rows, want_fail, needle=None, heading=None,
         allowlisted=None, issue_states="unfetchable"):
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(td, entries, rows, heading, allowlisted)
        rc, out = run(root, issue_states=issue_states)
    ok = (rc != 0) if want_fail else (rc == 0)
    if ok and needle:
        ok = needle in out
    check(name, ok)
    if not ok:
        print(f"      rc={rc} needle={needle!r}\n{out}")


# --- the clean baseline: sets match, events match -------------------------
case("clean catalog passes",
     [("a.py", "Stop", ""), ("b.py", "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x"),
      ("b.py", "PreToolUse", "Bash", "blocks y")] + ALLOW_ROWS,
     want_fail=False)

# --- the two drift directions from ai-config#1206 -------------------------
case("registered but undocumented fails",
     [("a.py", "Stop", ""), ("b.py", "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="b.py is registered")

case("documented but unregistered fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"),
      ("c.py", "Stop", "", "blocks z")] + ALLOW_ROWS,
     want_fail=True, needle="never fires")

# --- the event/matcher direction, which a set comparison cannot see -------
case("event mismatch fails",
     [("a.py", "Stop", "")],
     [("a.py", "UserPromptSubmit", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="README says UserPromptSubmit")

case("matcher mismatch fails",
     [("a.py", "PreToolUse", "Bash")],
     [("a.py", "PreToolUse", "Agent", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="hooks.json binds PreToolUse (Bash)")

# --- allowlist hygiene, mirroring KNOWN_UNTESTED's reverse check ----------
# Always exercised by injecting a test allowlist, ensuring these checks run
# even when KNOWN_UNREGISTERED is empty in production.
test_allow = ["inert1.py", "inert2.py"]
test_allow_rows = [
    ("inert1.py", "PreToolUse", "Bash", "**not registered ([#9999](u))** --- would block"),
    ("inert2.py", "PreToolUse", "Agent", "**not registered ([#9999](u))** --- reminds")
]

case("allowlisted row without the marker fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"),
      ("inert1.py", "PreToolUse", "Bash", "describes an active guard"),
      test_allow_rows[1]],
     want_fail=True, needle="reads as an active guard", allowlisted=test_allow)

case("allowlisted hook that is now registered fails",
     [("a.py", "Stop", ""), ("inert1.py", "PreToolUse", "Bash")],
     [("a.py", "Stop", "", "blocks x"),
      ("inert1.py", "PreToolUse", "Bash", "**not registered ([#9999](u))** --- would block"),
      test_allow_rows[1]],
     want_fail=True, needle="drop it from KNOWN_UNREGISTERED", allowlisted=test_allow)

case("allowlisted hook with no README row fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x"), test_allow_rows[1]],
     want_fail=True, needle="has no README row", allowlisted=test_allow)

# --- closed-tracker gate (ai-config#2302) ---------------------------------
# Synthetic allowlist, so these run even after production KNOWN_UNREGISTERED
# empties. Injected states, so they never hit the network.
case("open tracker passes",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=False, allowlisted=test_allow, issue_states={"9999": "open"})

case("closed tracker fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=True, needle="which is closed",
     allowlisted=test_allow, issue_states={"9999": "closed"})

case("missing tracker fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=True, needle="which does not exist",
     allowlisted=test_allow, issue_states={"9999": "missing"})

case("unfetchable tracker skips rather than failing",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=False, needle="SKIP: could not fetch",
     allowlisted=test_allow, issue_states="unfetchable")

case("invalid HOOK_CATALOG_ISSUE_STATES JSON fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=True, needle="not valid JSON",
     allowlisted=test_allow, issue_states="{nope")

case("invalid injected tracker state fails",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=True, needle="invalid state",
     allowlisted=test_allow, issue_states={"9999": "wobbly"})

case("injected tracker states must be an object",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + test_allow_rows,
     want_fail=True, needle="must be a JSON object",
     allowlisted=test_allow, issue_states="[]")

# urllib 404/410 must return `missing`, not None. A live GET of issue 9999
# cannot lock that: both a 404-as-skip regression and a real offline miss
# print `SKIP: could not fetch` and would skip() to rc=0. Stub urlopen so
# the mapping cannot skip-pass.
def _http_error(code):
    return urllib.error.HTTPError(
        "https://api.github.com/repos/Morrison-Lab/ai-config/issues/1",
        code, "err", None, io.BytesIO(b""))


class _OpenBody:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fetch_with_urlopen(side_effect, extra_env=None):
    saved = {
        key: os.environ.get(key)
        for key in ("HOOK_CATALOG_ISSUE_STATES", "HOOK_CATALOG_REPO",
                    "GITHUB_REPOSITORY", "GITHUB_TOKEN", "GH_TOKEN")
    }
    os.environ.pop("HOOK_CATALOG_ISSUE_STATES", None)
    os.environ.pop("HOOK_CATALOG_REPO", None)
    os.environ.pop("GITHUB_REPOSITORY", None)
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("GH_TOKEN", None)
    if extra_env:
        os.environ.update(extra_env)
    try:
        with patch.object(_catalog.urllib.request, "urlopen",
                          side_effect=side_effect):
            return _catalog.fetch_issue_state(1)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


check("urllib 404 is missing, not skip",
      _fetch_with_urlopen(_http_error(404)) == "missing")
check("urllib 410 is missing, not skip",
      _fetch_with_urlopen(_http_error(410)) == "missing")
check("urllib 403 is unfetchable skip",
      _fetch_with_urlopen(_http_error(403)) is None)
check("urllib 200 open is open",
      _fetch_with_urlopen(lambda *a, **k: _OpenBody(b'{"state":"open"}'))
      == "open")
check("urllib 200 closed is closed",
      _fetch_with_urlopen(lambda *a, **k: _OpenBody(b'{"state":"closed"}'))
      == "closed")

seen_urls = []
seen_auth = []


def _auth_header(request):
    return request.headers.get("Authorization") or request.headers.get("authorization")


def _capture_open(request, timeout=None):
    seen_urls.append(request.full_url)
    seen_auth.append(_auth_header(request))
    return _OpenBody(b'{"state":"open"}')


_fetch_with_urlopen(_capture_open,
                    extra_env={"GITHUB_REPOSITORY": "some-fork/ai-config",
                               "GITHUB_TOKEN": "fork-token"})
check("fork GITHUB_REPOSITORY is not the issues host",
      seen_urls == [
          "https://api.github.com/repos/Morrison-Lab/ai-config/issues/1"
      ])
check("fork GITHUB_TOKEN is not sent to DEFAULT_REPO",
      seen_auth == [None])

seen_urls.clear()
seen_auth.clear()
_fetch_with_urlopen(_capture_open,
                    extra_env={"GITHUB_REPOSITORY": "Morrison-Lab/ai-config",
                               "GITHUB_TOKEN": "home-token"})
check("same-repo GITHUB_TOKEN is sent",
      seen_auth == ["Bearer home-token"])

seen_urls.clear()
seen_auth.clear()
_fetch_with_urlopen(_capture_open,
                    extra_env={"GITHUB_TOKEN": "local-token"})
check("local token is sent when GITHUB_REPOSITORY is unset",
      seen_auth == ["Bearer local-token"])

# --- fail-fast: a parse that finds nothing must not pass vacuously --------
case("missing section fails loudly",
     [("a.py", "Stop", "")],
     [("a.py", "Stop", "", "blocks x")] + ALLOW_ROWS,
     want_fail=True, needle="cannot run", heading="## Some Other Heading")

with tempfile.TemporaryDirectory() as td:
    root = make_repo(td, [("a.py", "Stop", "")], ALLOW_ROWS)
    # Strip every table row, leaving the section heading in place. The set
    # comparison would then compare against nothing and report clean.
    p = root / "README.md"
    kept = [ln for ln in p.read_text(encoding="utf-8").splitlines()
            if not ln.startswith("| `")]
    p.write_text("\n".join(kept) + "\n", encoding="utf-8")
    rc, out = run(root)
    check("empty table fails loudly rather than passing vacuously",
          rc != 0 and "parsed 0 hook rows" in out)

# --- the live corpus: a holding-constant regression guard -----------------
# Catalog shape is checked offline so a network SKIP cannot masquerade as a
# consistent catalog. Tracker freshness is a separate live fetch: a closed or
# missing production tracker fails; an offline miss is a visible skip(), not
# a PASS. Drop a leaked HOOK_CATALOG_ISSUE_STATES so the parent environment
# cannot skip the live fetch.
offline_env = os.environ.copy()
offline_env["HOOK_CATALOG_ISSUE_STATES"] = "unfetchable"
proc = subprocess.run([sys.executable, str(SCRIPT)],
                      capture_output=True, text=True, cwd=str(ROOT),
                      env=offline_env)
check("the real repo's catalog is consistent", proc.returncode == 0)
if proc.returncode != 0:
    print(proc.stdout + proc.stderr)

if ALLOWLISTED:
    live_env = os.environ.copy()
    live_env.pop("HOOK_CATALOG_ISSUE_STATES", None)
    proc = subprocess.run([sys.executable, str(SCRIPT)],
                          capture_output=True, text=True, cwd=str(ROOT),
                          env=live_env)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        check("the real repo's trackers are open", False)
        print(out)
    elif "SKIP: could not fetch" in out:
        skip("the real repo's trackers are open",
             "issue state could not be fetched")
    else:
        check("the real repo's trackers are open", True)
else:
    skip("the real repo's trackers are open",
         "KNOWN_UNREGISTERED is empty")

print(f"\n{passes} passed, {failures} failed, {skipped} skipped "
      f"({len(ALLOWLISTED)} hook(s) in KNOWN_UNREGISTERED)")
sys.exit(1 if failures else 0)
