#!/usr/bin/env python3
"""Regression tests for check-merge-commit-ci.py.

`evaluate()` is pure over a list of workflow-run dicts, so most cases run
offline. `main()` is exercised too, with `run_gh` monkeypatched, so the
three exit codes (clean / not-clean / no-runs-yet) are pinned end to end
and a future edit cannot quietly collapse the no-runs case into a clean
one -- the exact shape of the mds incident this script exists to catch:
an absent push-triggered run must never read as nothing to check.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "check_merge_commit_ci", Path(__file__).parent / "check-merge-commit-ci.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def run(name: str) -> dict:
    return {
        "name": name,
        "status": "completed",
        "conclusion": "success",
        "html_url": f"https://example.invalid/{name}",
    }


def capture_evaluate(runs):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        code = mod.evaluate(runs)
    return code, buf.getvalue()


# --- evaluate(): pure cases -------------------------------------------------

code, out = capture_evaluate([])
check("no runs -> exit 3 (ambiguous, not clean)", code == mod.NO_RUNS_EXIT, out)
check("no-runs output says NOT a clean verdict", "NOT a clean verdict" in out, out)

code, out = capture_evaluate([run("a"), run("b")])
check("all success -> exit 0", code == 0, out)
check("clean output names every run", "a" in out and "b" in out, out)

code, out = capture_evaluate(
    [run("a"), {**run("b"), "conclusion": "failure"}]
)
check("one failure among successes -> exit 1", code == mod.NOT_CLEAN_EXIT, out)
check("failure output names the failing run", "b" in out and "failure" in out, out)

code, out = capture_evaluate([{**run("a"), "status": "in_progress", "conclusion": None}])
check("in-progress run -> exit 1, not exit 0", code == mod.NOT_CLEAN_EXIT, out)
check("in-progress output says not yet completed", "not yet completed" in out, out)

code, out = capture_evaluate([{**run("a"), "conclusion": "skipped"}])
check("a deliberately skipped run alone is still clean", code == 0, out)

code, out = capture_evaluate([{**run("a"), "conclusion": "neutral"}])
check("a neutral conclusion alone is still clean", code == 0, out)

code, out = capture_evaluate([{**run("a"), "conclusion": "cancelled"}])
check(
    "a cancelled run is NOT clean (regression guard: cancelled is not in "
    "OK_CONCLUSIONS)",
    code == mod.NOT_CLEAN_EXIT,
    out,
)

# The negative control this test suite would be worst without: OK_CONCLUSIONS
# must not silently grow to include every value naively encountered. Assert
# the exact set, so a future edit that widens it here shows up as a diff on
# this exact assertion rather than a passing test that quietly reports
# more things clean than mds#19 intended.
check(
    "OK_CONCLUSIONS is exactly success/skipped/neutral",
    mod.OK_CONCLUSIONS == {"success", "skipped", "neutral"},
    repr(mod.OK_CONCLUSIONS),
)

# --- main(): end-to-end with run_gh monkeypatched ---------------------------


def with_fake_gh(fake, argv):
    original = mod.run_gh
    mod.run_gh = fake
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            code = mod.main(argv)
    finally:
        mod.run_gh = original
    return code, buf.getvalue()


def fake_gh_factory(sha_runs_json):
    def fake_gh(args):
        if args[:2] == ["repo", "view"]:
            return "acme/widgets\n"
        if args[:2] == ["api", "repos/acme/widgets/commits/HEAD"]:
            return "deadbeef\n"
        if "actions/runs" in args[1]:
            return sha_runs_json
        raise AssertionError(f"unexpected gh call: {args}")

    return fake_gh


import json as _json

code, out = with_fake_gh(
    fake_gh_factory(_json.dumps([{"workflow_runs": [run("publish")]}])),
    [],
)
check("main(): resolves repo/sha and reports clean end to end", code == 0, out)
check("main(): names the SHA it checked", "deadbeef" in out, out)

code, out = with_fake_gh(fake_gh_factory(_json.dumps([{"workflow_runs": []}])), [])
check(
    "main(): no runs on the resolved SHA still exits 3, not 0 "
    "(this is the mds incident's exact shape)",
    code == mod.NO_RUNS_EXIT,
    out,
)

code, out = with_fake_gh(
    fake_gh_factory(
        _json.dumps(
            [{"workflow_runs": [{**run("publish"), "conclusion": "failure"}]}]
        )
    ),
    ["--sha", "cafef00d"],
)
check("main(): explicit --sha is used instead of resolving HEAD", code == mod.NOT_CLEAN_EXIT, out)
check("main(): explicit --sha appears in the checked-SHA line", "cafef00d" in out, out)

# --sha short-circuits resolve_sha's own gh call: prove it by making that
# path raise if reached at all.


def fake_gh_no_head_lookup(args):
    if args[:2] == ["repo", "view"]:
        return "acme/widgets\n"
    if args[:2] == ["api", "repos/acme/widgets/commits/HEAD"]:
        raise AssertionError("resolve_sha called gh for HEAD despite --sha")
    if "actions/runs" in args[1]:
        return _json.dumps([{"workflow_runs": [run("publish")]}])
    raise AssertionError(f"unexpected gh call: {args}")


code, out = with_fake_gh(fake_gh_no_head_lookup, ["--sha", "cafef00d"])
check("main(): --sha skips the HEAD-resolution gh call entirely", code == 0, out)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
