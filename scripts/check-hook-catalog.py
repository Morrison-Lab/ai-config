#!/usr/bin/env python3
"""Assert README's hook catalog and `hooks/hooks.json` describe the same hooks.

`hooks/hooks.json` is what actually binds a hook to an event; README's
"Enforcement hooks" table is what a human reads to find out which guards exist.
Nothing kept the two in step, and they drifted apart in both directions
(ai-config#1206). The two directions fail differently, and the second is worse:

  registered but undocumented  -- the guard runs on every session while the
                                  catalog a reader consults says it does not
                                  exist.
  documented but unregistered  -- the README asserts an active guard that never
                                  fires. This is the failure mode the corpus
                                  already warns about at length: an unregistered
                                  guard and a guard with nothing to block look
                                  identical, because neither ever produces
                                  output. A README row is then positive evidence
                                  for something inert.

Per `shared/workflow/algorithmatize-checks.md`, "do these two sets match" is
decidable over data both files already carry, so it belongs in an instrument
rather than in anyone's periodic reading. The drift grew by one entry in the ten
days between #1206 being filed and being fixed, which is the argument for
gating it rather than only reconciling it once.

This checks five things:

  1. Every hook registered in `hooks.json` has a README row.
  2. Every hook with a README row is registered in `hooks.json`, unless it is in
     `KNOWN_UNREGISTERED` -- and an allowlisted hook's row must SAY it is not
     registered, so the table never reads as an active guard.
  3. For a hook in both, README's stated event and matcher match the binding.
  4. Every `KNOWN_UNREGISTERED` tracker is still open. A closed mapped issue is
     how a hook stays silently inert with a README row that still names a
     follow-up that will never happen (ai-config#1717 stayed allowlisted after
     it closed, until #2275 / #2294). Fail, do not warn.
  5. No script is bound twice for the same event and the same tool. `registered`
     folds several matcher groups for one script into a comma-joined string, so
     a hook bound once and a hook bound twice compare equal to the same README
     row -- the catalog was blind to a double binding by construction
     (ai-config#2535). A double binding runs the hook twice on one call, which
     is merely wasteful for a warn-only hook and is not benign for a blocking
     one.

Check 3 is what stops the table drifting in a way the set comparison cannot see:
a row can name every hook correctly and still tell a reader the wrong event.
Check 5 needs the harness's own matcher semantics, which `matcher_matches`
reimplements; see its docstring for the measurement that settles them.

When a tracker cannot be fetched (offline, timeout, or rate limit), this check
prints `SKIP` and does not fail. That skip is the documented offline path, not
a silent pass: the line is visible, and tests assert it. A 404/410 is not a
skip -- a missing tracker is the same class of defect as a closed one. Fixture
tests inject states via `HOOK_CATALOG_ISSUE_STATES` (a JSON object of
`{issue: state}`, or the token `unfetchable`) so those cases never hit the
network. A separate live case fetches; the urllib 404 path is locked with a
stub, not by a live GET that can skip.

Hard-gating rather than advisory. Unlike a file-length threshold, nothing here
is a judgment call -- the two sets either match or they do not.

Run: python3 scripts/check-hook-catalog.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
README = os.path.join(ROOT, "README.md")

# Hooks documented in README but deliberately NOT registered, each mapped to
# the issue tracking its activation. An explicit, reviewable list -- not a
# silent gap -- mirroring KNOWN_UNTESTED in scripts/test_hooks.py. This list
# should only ever shrink: registering a hook, or dropping its README row,
# means removing it from here.
KNOWN_UNREGISTERED = {}

# Public repo (measured 2026-08-26); unauthenticated GET works. A token is
# used only when it is scoped to this repo: a fork `push` sets
# GITHUB_REPOSITORY to the fork, and that GITHUB_TOKEN 404s an existing
# issue on Morrison-Lab/ai-config (GitHub REST troubleshooting, "404 Not
# Found for an existing resource", measured against the 2026-08-26 docs).
# Override the issues repo via HOOK_CATALOG_REPO only in tests; the host
# is always api.github.com.
DEFAULT_REPO = "Morrison-Lab/ai-config"
ISSUE_STATES_ENV = "HOOK_CATALOG_ISSUE_STATES"
UNFETCHABLE_TOKENS = frozenset({"", "unfetchable", "skip"})
VALID_ISSUE_STATES = frozenset({"open", "closed", "missing"})
GONE_HTTP = frozenset({404, 410})
API_TIMEOUT_SEC = 10

# The README row of an allowlisted hook must contain this, so the table states
# the hook is inert rather than describing it as an active guard.
UNREGISTERED_MARKER = "not registered"

# Heading that opens the catalog section, and the row shape inside it. Bounding
# the scan to one section keeps an unrelated table elsewhere in README from
# being read as hook rows.
SECTION_HEADING = "## Enforcement hooks"

# | `name.py` | `Event` (Matcher) | prose |   -- matcher is optional.
#
# The matcher cell accepts a backslash-escaped pipe (`Write\|Edit`), which is
# how a markdown cell has to carry an alternation matcher: a bare `|` would end
# the cell. `documented` unescapes it before comparing against hooks.json.
# A bare `|` is deliberately NOT accepted -- it would let the matcher group
# swallow a cell separator and silently reparse the row.
ROW = re.compile(
    r"^\|\s*`(?P<script>[A-Za-z0-9._-]+\.(?:py|sh))`\s*"
    r"\|\s*`(?P<event>[A-Za-z0-9_, ]+)`\s*"
    r"(?:\((?P<matcher>(?:[A-Za-z0-9_.*, -]|\\\|)+)\))?\s*"
    r"\|(?P<rest>.*)\|\s*$"
)

# How the harness decides whether a matcher applies to a tool call, measured
# 2026-09-03 against Claude Code v2.1.42's own matcher function in
# `cli.js`, and re-run against the extracted function under node:
#
#     if (!q || q === "*") return true;
#     if (/^[a-zA-Z0-9_|]+$/.test(q)) {
#       if (q.includes("|")) return q.split("|").map(y => y.trim()).includes(A);
#       return A === q;
#     }
#     try { return new RegExp(q).test(A) } catch { return false }
#
# So there are three branches, and the first two are NOT regex matching:
#
#   plain name        exact string equality. `Edit` does not match
#                     `NotebookEdit`, so three single-tool groups are three
#                     disjoint bindings rather than a triple invocation.
#   `A|B|C`           exact membership of the trimmed parts. An alternation is
#                     usable, not inert, and is one group rather than three.
#   anything else     an UNANCHORED JavaScript regex, which is why
#                     `mcp__github__.*` works and `mcp__github__*` does not.
#
# The fast-path class is `[A-Za-z0-9_|]`, narrower than the
# `[A-Za-z0-9_\- ,|]` that `memories/claude-code-hooks.md` recorded before
# this was measured: a matcher carrying `-`, a space, or a comma falls through
# to the regex branch.
PLAIN_MATCHER = re.compile(r"^[A-Za-z0-9_|]+$")

# A matcher that is absent, empty, or `*` applies to every tool.
CATCH_ALL = frozenset({"", "*"})


def matcher_matches(tool, matcher):
    """Whether `matcher` fires on a call to `tool`, per the semantics above.

    Python's `re` is not JavaScript's, so a matcher exercising a dialect
    difference could be read differently here than by the harness. Every
    matcher this repo binds is a plain name, an alternation, or a prefix plus
    `.*`, all of which mean the same thing in both dialects.
    """
    if matcher in CATCH_ALL:
        return True
    if PLAIN_MATCHER.match(matcher):
        if "|" in matcher:
            return tool in [part.strip() for part in matcher.split("|")]
        return tool == matcher
    try:
        return re.search(matcher, tool) is not None
    except re.error:
        return False


def matcher_names(matcher):
    """Tool names a matcher names literally; empty for a regex matcher.

    These are the only tool names available to compare two matchers against.
    The harness knows the full tool list and this check does not, so the
    vocabulary is built from what hooks.json itself spells out.
    """
    if matcher in CATCH_ALL or not PLAIN_MATCHER.match(matcher):
        return frozenset()
    return frozenset(
        part.strip() for part in matcher.split("|") if part.strip())


def overlapping_tools(first, second, vocabulary):
    """Tool names both matchers fire on, as a sorted list.

    Returns `["every tool"]` when either matcher is the catch-all, and names
    the shared matcher when two identical regex matchers match nothing in the
    vocabulary -- identical matchers overlap whatever they match.
    """
    if first in CATCH_ALL or second in CATCH_ALL:
        return ["every tool"]
    hits = sorted(tool for tool in vocabulary
                  if matcher_matches(tool, first)
                  and matcher_matches(tool, second))
    if not hits and first == second:
        return [f"whatever {first!r} matches"]
    return hits


def bindings():
    """[(script, event, matcher)] -- one tuple per binding, unmerged.

    `registered` folds a script's several matcher groups into one comma-joined
    string, which is what the README row is compared against and is exactly
    what makes a double binding invisible there. This keeps the groups apart so
    `check_double_bindings` can see them.
    """
    with open(HOOKS_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for event, groups in data["hooks"].items():
        for group in groups:
            matcher = group.get("matcher") or ""
            for entry in group.get("hooks", []):
                script = entry.get("script")
                if script:
                    out.append((script, event, matcher))
    return out


def registered(binds=None):
    """{script: (event, matcher)} for every hook bound in hooks/hooks.json."""
    out = {}
    for script, event, matcher in (bindings() if binds is None else binds):
        if script not in out:
            out[script] = (event, matcher)
            continue
        prev_event, prev_matcher = out[script]
        events = event if prev_event == event else f"{prev_event}, {event}"
        matchers = [m for m in (prev_matcher, matcher) if m]
        out[script] = (events, ", ".join(matchers))
    return out


def documented():
    """{script: (event, matcher, row_text)} for every row in README's catalog.

    Raises SystemExit if the section or its table cannot be found -- a parser
    that silently returns nothing would make every set comparison vacuously
    pass, which is the shape `shared/principles/fail-fast.md` warns about.
    """
    with open(README, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    start = next((i for i, ln in enumerate(lines)
                  if ln.startswith(SECTION_HEADING)), None)
    if start is None:
        sys.exit(f"FAIL: no {SECTION_HEADING!r} section in README.md; "
                 "this check cannot run")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))

    out = {}
    for ln in lines[start:end]:
        m = ROW.match(ln)
        if m:
            # A markdown cell carries an alternation matcher as `A\|B`; the
            # binding it is compared against spells it `A|B`.
            matcher = (m.group("matcher") or "").replace(r"\|", "|")
            out[m.group("script")] = (
                m.group("event"), matcher, m.group("rest"))
    if not out:
        sys.exit(f"FAIL: parsed 0 hook rows from README's {SECTION_HEADING!r} "
                 "section; the table shape changed and this check is blind")
    return out


def _injected_states():
    """Parse HOOK_CATALOG_ISSUE_STATES, or None to fetch live.

    A JSON object maps issue number -> `open`/`closed`/`missing`. The tokens
    `unfetchable` / `skip` / empty string mean every tracker is unfetchable
    (the documented offline path, and the fixture-test default). Invalid JSON
    fails the check rather than skipping: a malformed injection is a test bug,
    not an offline run.
    """
    raw = os.environ.get(ISSUE_STATES_ENV)
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped.lower() in UNFETCHABLE_TOKENS:
        return {}
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        sys.exit(f"FAIL: {ISSUE_STATES_ENV} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"FAIL: {ISSUE_STATES_ENV} must be a JSON object of "
                 f"issue-number -> state")
    out = {}
    for key, value in data.items():
        state = str(value).lower()
        if state not in VALID_ISSUE_STATES:
            sys.exit(f"FAIL: {ISSUE_STATES_ENV} has invalid state {value!r} "
                     f"for #{key}")
        out[str(key)] = state
    return out


def _token_for_default_repo():
    """Return a bearer token only when it is scoped to DEFAULT_REPO.

    GITHUB_TOKEN is installation-scoped to github.repository. A fork `push`
    sets GITHUB_REPOSITORY to the fork; attaching that token to a request
    for Morrison-Lab/ai-config 404s an existing issue. Treating that 404 as
    `missing` would fail the catalog on an open tracker. When
    GITHUB_REPOSITORY is unset (local pre-commit), a present token is used.

    A HOOK_CATALOG_REPO override redirects the request to another repo, so
    no token is attached then either -- this gate checks scope against
    DEFAULT_REPO only, and the token must not ride along to a repo the gate
    never examined.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return None
    override = os.environ.get("HOOK_CATALOG_REPO", "").strip()
    if override and override.lower() != DEFAULT_REPO.lower():
        return None
    here = os.environ.get("GITHUB_REPOSITORY", "")
    if here and here.lower() != DEFAULT_REPO.lower():
        return None
    return token


def fetch_issue_state(number):
    """Return `open`, `closed`, or `missing`, or None when unfetchable.

    `missing` is HTTP 404/410: the tracker does not exist, which is the
    same class of defect as a closed issue. Network failures, timeouts, and
    rate limits return None so the caller can SKIP.
    """
    injected = _injected_states()
    if injected is not None:
        return injected.get(str(number))

    repo = os.environ.get("HOOK_CATALOG_REPO", "").strip() or DEFAULT_REPO
    url = f"https://api.github.com/repos/{repo}/issues/{int(number)}"
    headers = {
        "User-Agent": "ai-config-check-hook-catalog",
        "Accept": "application/vnd.github+json",
    }
    token = _token_for_default_repo()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SEC) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        code = getattr(exc, "code", None)
        try:
            exc.close()
        except OSError:
            pass
        if code in GONE_HTTP:
            return "missing"
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    state = str(payload.get("state", "")).lower()
    if state in ("open", "closed"):
        return state
    return None


def check_tracker_states():
    """Fail when an allowlisted hook's mapped issue is closed or missing.

    Returns the extra failure count. A fetch failure prints SKIP and does
    not count as a failure -- that skip is the documented offline path.
    HTTP 404/410 is not a fetch failure; it is a vanished tracker.
    """
    failures = 0
    for script, number in sorted(KNOWN_UNREGISTERED.items()):
        state = fetch_issue_state(number)
        if state is None:
            print(f"SKIP: could not fetch ai-config#{number} for {script}; "
                  "not failing the closed-tracker check (offline path; set "
                  f"{ISSUE_STATES_ENV} to inject a state)")
            continue
        if state == "open":
            continue
        if state == "closed":
            print(f"FAIL: {script} is in KNOWN_UNREGISTERED mapped to "
                  f"ai-config#{number}, which is closed, so a closed tracker "
                  "is keeping the hook silently inert; register the hook, "
                  "or retarget the allowlist at an open issue")
            failures += 1
            continue
        if state == "missing":
            print(f"FAIL: {script} is in KNOWN_UNREGISTERED mapped to "
                  f"ai-config#{number}, which does not exist, so a vanished "
                  "tracker is keeping the hook silently inert; register the "
                  "hook, or retarget the allowlist at an open issue")
            failures += 1
            continue
        print(f"FAIL: {script} is in KNOWN_UNREGISTERED mapped to "
              f"ai-config#{number} with unexpected state {state!r}")
        failures += 1
    return failures


def _show(matcher):
    """A matcher as it reads in a message; an absent one has no name."""
    return repr(matcher) if matcher else "(no matcher)"


def check_double_bindings(binds):
    """Fail when one script is bound twice for the same event and tool.

    The harness collects every matcher group whose matcher fires on the call
    and runs all of their commands, so a script named in two firing groups runs
    twice on one call. `registered` cannot see that: it folds the groups into
    one comma-joined matcher, so a hook bound once and a hook bound twice both
    compare equal to the same README row (ai-config#2535).

    Returns (failure count, pairs examined). The second number is the negative
    control: a detector that examined nothing reports the same zero failures as
    a clean catalog, and only the count tells them apart.
    """
    vocabulary = {name for _, _, matcher in binds
                  for name in matcher_names(matcher)}
    by_key = {}
    for script, event, matcher in binds:
        by_key.setdefault((script, event), []).append(matcher)

    failures = 0
    examined = 0
    for (script, event), matchers in sorted(by_key.items()):
        for i, first in enumerate(matchers):
            for second in matchers[i + 1:]:
                examined += 1
                shared = overlapping_tools(first, second, vocabulary)
                if not shared:
                    continue
                print(f"FAIL: {script} is bound to {event} in two matcher "
                      f"groups, {_show(first)} and {_show(second)}, which "
                      f"both fire on {', '.join(shared)}; the hook then runs "
                      "twice on one call. Merge the groups, or narrow one "
                      "matcher so they are disjoint")
                failures += 1
    return failures, examined


def check(reg, doc):
    """Compare the two catalogs. Returns the failure count."""
    failures = 0

    for script in sorted(set(reg) - set(doc)):
        event, matcher = reg[script]
        where = f"{event}" + (f" ({matcher})" if matcher else "")
        print(f"FAIL: hooks/{script} is registered ({where}) but has no README "
              "row; add one to the Enforcement hooks table")
        failures += 1

    for script in sorted(set(doc) - set(reg)):
        if script in KNOWN_UNREGISTERED:
            if UNREGISTERED_MARKER in doc[script][2]:
                print(f"NOTE: {script} is documented but not registered "
                      f"(known, ai-config#{KNOWN_UNREGISTERED[script]})")
            else:
                print(f"FAIL: {script} is in KNOWN_UNREGISTERED but its README "
                      f"row does not say {UNREGISTERED_MARKER!r}, so the table "
                      "reads as an active guard")
                failures += 1
        else:
            print(f"FAIL: hooks/{script} has a README row but is not "
                  "registered in hooks/hooks.json, so it never fires; "
                  "register it, or add it to KNOWN_UNREGISTERED with a "
                  "tracking issue")
            failures += 1

    # An allowlisted hook that has since been registered should leave the list,
    # so the debt cannot linger as silently satisfied.
    for script in sorted(KNOWN_UNREGISTERED):
        if script in reg:
            print(f"FAIL: {script} is now registered; drop it from "
                  "KNOWN_UNREGISTERED")
            failures += 1
        elif script not in doc:
            print(f"FAIL: {script} is in KNOWN_UNREGISTERED but has no README "
                  "row; drop it from the allowlist")
            failures += 1

    for script in sorted(set(reg) & set(doc)):
        want_event, want_matcher = reg[script]
        got_event, got_matcher, _ = doc[script]
        if (want_event, want_matcher) != (got_event, got_matcher):
            def fmt(e, m):
                return e + (f" ({m})" if m else "")
            print(f"FAIL: {script} README says {fmt(got_event, got_matcher)} "
                  f"but hooks.json binds {fmt(want_event, want_matcher)}")
            failures += 1

    return failures


def main() -> int:
    binds = bindings()
    reg = registered(binds)
    doc = documented()
    failures = check(reg, doc)
    double_failures, examined = check_double_bindings(binds)
    failures += double_failures
    failures += check_tracker_states()

    print(f"\n{len(reg)} hooks registered in hooks.json; {len(doc)} documented "
          f"in README ({len(KNOWN_UNREGISTERED)} known unregistered); "
          f"{len(set(reg) & set(doc))} compared for event and matcher; "
          f"{examined} matcher pair(s) compared for a double binding")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
