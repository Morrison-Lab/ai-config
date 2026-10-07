#!/usr/bin/env python3
"""Regression tests for check-merge-commit-ci.py.

`evaluate()` is pure over a list of workflow-run dicts, so most cases run
offline. `main()` is exercised too, with `run_gh` monkeypatched, so the
exit codes (clean / not-clean / no-runs-yet / usage) are pinned end to end
and a future edit cannot quietly collapse the no-runs case into a clean
one -- the exact shape of the mds incident this script exists to catch:
an absent push-triggered run must never read as nothing to check.

The bad-SHA cases pin a second, adjacent shape: a typo'd, truncated, or
wrong-repo SHA must read as a usage error (exit 2), never as "no runs yet"
(exit 3) -- those two states are otherwise indistinguishable from the
`actions/runs?head_sha=` query alone, since both return an empty list.
"""
from __future__ import annotations

import importlib.util
import io
import json as _json
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

# Full 40-hex SHAs, since --sha now rejects anything shorter.
SHA_DEADBEEF = "deadbeef" * 5
SHA_CAFEF00D = "cafef00d" * 5
SHA_OTHER = "0123456789abcdef" * 2 + "01234567"
assert len(SHA_DEADBEEF) == 40 and len(SHA_CAFEF00D) == 40 and len(SHA_OTHER) == 40


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


def capture_evaluate(runs, repo=None):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        code = mod.evaluate(runs, repo=repo)
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
check(
    "a neutral conclusion is NOT clean (conservative default: neutral "
    "means neither pass nor fail, so it is not admitted for free)",
    code == mod.NOT_CLEAN_EXIT,
    out,
)

code, out = capture_evaluate([{**run("a"), "conclusion": "cancelled"}])
check(
    "a cancelled run is NOT clean (regression guard: cancelled is not in "
    "OK_CONCLUSIONS)",
    code == mod.NOT_CLEAN_EXIT,
    out,
)


def workflow_run(name, workflow_id, sha, conclusion, created_at, branch="main", status="completed"):
    return {
        "name": name,
        "workflow_id": workflow_id,
        "head_sha": sha,
        "head_branch": branch,
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "html_url": f"https://example.invalid/{name}/{sha}",
    }


# Case (a): a same-SHA re-run of the same workflow succeeded. Silent, per
# check-pr-fully-clean.py's identical handling (ai-config#2277) --
# mirrored here rather than reimplemented as an incompatible rule.
runs_same_sha_supersede = [
    workflow_run("Quarto Publish", 42, SHA_DEADBEEF, "cancelled", "2026-09-01T00:00:00Z"),
    workflow_run("Quarto Publish", 42, SHA_DEADBEEF, "success", "2026-09-01T00:05:00Z"),
]
code, out = capture_evaluate(runs_same_sha_supersede)
check(
    "case (a): a same-SHA success supersedes an earlier cancelled run "
    "of the same workflow -> clean",
    code == 0,
    out,
)

# The negative control: two DIFFERENT workflows (different workflow_id),
# even with the same name, must not cross-supersede each other.
runs_different_workflow_same_name = [
    workflow_run("build", 1, SHA_DEADBEEF, "cancelled", "2026-09-01T00:00:00Z"),
    workflow_run("build", 2, SHA_DEADBEEF, "success", "2026-09-01T00:05:00Z"),
]
code, out = capture_evaluate(runs_different_workflow_same_name)
check(
    "case (a) negative control: a same-named run from a DIFFERENT "
    "workflow_id does not supersede -> still not clean",
    code == mod.NOT_CLEAN_EXIT,
    out,
)

# Case (b): a later commit on the same branch superseded this one via a
# concurrency group, and its run succeeded. Requires `repo=` and a fake
# run_gh serving the per-workflow runs listing.
CANCELLED_RUN_B = workflow_run(
    "Quarto Publish", 42, SHA_DEADBEEF, "cancelled", "2026-09-01T00:00:00Z"
)
LATER_SUCCESS_RUN_B = workflow_run(
    "Quarto Publish", 42, SHA_CAFEF00D, "success", "2026-09-01T00:01:00Z"
)


def fake_gh_branch_runs(page_runs):
    def fake_gh(args):
        if args[:2] == ["api", "repos/acme/widgets/actions/workflows/42/runs"]:
            return "\n".join(_json.dumps(r) for r in page_runs)
        raise AssertionError(f"unexpected gh call: {args}")

    return fake_gh


original_run_gh = mod.run_gh
mod.run_gh = fake_gh_branch_runs([LATER_SUCCESS_RUN_B])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "case (b): a later commit's success on the same branch supersedes -> "
    "clean, WITH an explicit note (never silent)",
    code == 0,
    out,
)
check(
    "case (b) note names the superseding SHA",
    SHA_CAFEF00D[:8] in out and "superseded" in out,
    out,
)

# Case (b) negative control: no later success exists (only an OLDER success,
# or none at all) -> stays not clean, and no note is fabricated.
mod.run_gh = fake_gh_branch_runs([])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "case (b) negative control: no later success -> still not clean",
    code == mod.NOT_CLEAN_EXIT,
    out,
)
check("no fabricated superseded note when none exists", "superseded" not in out, out)

OLDER_SUCCESS_RUN_B = workflow_run(
    "Quarto Publish", 42, SHA_OTHER, "success", "2026-08-31T00:00:00Z"
)
mod.run_gh = fake_gh_branch_runs([OLDER_SUCCESS_RUN_B])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "case (b) negative control: a success OLDER than the cancelled run "
    "does not count as superseding -> still not clean",
    code == mod.NOT_CLEAN_EXIT,
    out,
)

# Load-bearing case: cancelled X, then a FAILED run Z, then a successful
# run Y, in that chronological order. The next-COMPLETED-run rule must
# stop at Z, the first completed run after X, and never skip past it to
# reach Y just because Y is a success. A success-only query would have
# reported X "superseded by Y (success)" with Z's failure invisible --
# exactly the gap the bot review caught.
FAILED_RUN_Z = workflow_run(
    "Quarto Publish", 42, SHA_OTHER, "failure", "2026-09-01T00:02:00Z"
)
SUCCESS_RUN_Y = workflow_run(
    "Quarto Publish",
    42,
    "1111111111111111111111111111111111111a",
    "success",
    "2026-09-01T00:03:00Z",
)
mod.run_gh = fake_gh_branch_runs([SUCCESS_RUN_Y, FAILED_RUN_Z])  # order-independent
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "cancelled X, failed Z, successful Y: X is NOT clean (Z, not Y, is "
    "the next completed run)",
    code == mod.NOT_CLEAN_EXIT,
    out,
)
check(
    "the report names Z (the intervening failure), not Y",
    SHA_OTHER[:8] in out and "failure" in out,
    out,
)
check(
    "the report does NOT claim X was superseded-clean by Y",
    "superseded by" not in out,
    out,
)

# Chain of cancellations: cancelled X, then a second cancelled run W (a
# still-newer push superseded W in turn), then a successful run Y. The
# walk must skip past W -- a cancelled run answers nothing about the
# branch state -- and land on Y.
CANCELLED_RUN_W = workflow_run(
    "Quarto Publish", 42, FAILED_RUN_Z["head_sha"], "cancelled", "2026-09-01T00:02:00Z"
)
mod.run_gh = fake_gh_branch_runs([CANCELLED_RUN_W, SUCCESS_RUN_Y])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "cancelled X, cancelled W, successful Y: X is clean with a note "
    "(the walk skips past W to reach Y)",
    code == 0,
    out,
)
check(
    "the note names Y, not W",
    SUCCESS_RUN_Y["head_sha"][:8] in out and "superseded" in out,
    out,
)

# Load-bearing case, from the re-review: cancelled X, then an IN-PROGRESS
# run Z, then a successful run Y. The walk must stop at Z -- the first
# non-cancelled run -- rather than skip an unfinished run to reach a later
# success. Z's own conclusion is None while in progress, so this also
# guards against a bare `next_run.get("conclusion") == "success"` read
# quietly passing on missing data.
IN_PROGRESS_RUN_Z = {
    **workflow_run(
        "Quarto Publish", 42, SHA_OTHER, None, "2026-09-01T00:02:00Z"
    ),
    "status": "in_progress",
}
assert IN_PROGRESS_RUN_Z["conclusion"] is None
mod.run_gh = fake_gh_branch_runs([SUCCESS_RUN_Y, IN_PROGRESS_RUN_Z])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "cancelled X, in-progress Z, successful Y: X is NOT clean -- Z is "
    "unresolved, so X cannot be read as superseded-clean via Y",
    code == mod.NOT_CLEAN_EXIT,
    out,
)
check(
    "the report names Z as still in progress",
    SHA_OTHER[:8] in out and "in_progress" in out,
    out,
)
check(
    "the report does NOT claim X was superseded-clean via Y",
    "superseded by" not in out,
    out,
)

# A "skipped" successor counts exactly as OK_CONCLUSIONS says it does --
# consistent with every other run this script reads, not held to a
# stricter bar just because it is the successor in case (b).
SKIPPED_RUN_Y = workflow_run(
    "Quarto Publish", 42, SUCCESS_RUN_Y["head_sha"], "skipped", "2026-09-01T00:03:00Z"
)
mod.run_gh = fake_gh_branch_runs([SKIPPED_RUN_Y])
try:
    code, out = capture_evaluate([CANCELLED_RUN_B], repo="acme/widgets")
finally:
    mod.run_gh = original_run_gh
check(
    "cancelled X, successor Y concludes 'skipped': X is clean with a note "
    "(skipped is in OK_CONCLUSIONS, same as everywhere else in this script)",
    code == 0,
    out,
)
check(
    "the note names the skipped conclusion explicitly",
    "skipped" in out and "superseded" in out,
    out,
)

# Without `repo=`, case (b) is never attempted -- offline callers get the
# conservative (not-clean) answer rather than a network call they did not
# ask for.
code, out = capture_evaluate([CANCELLED_RUN_B])
check(
    "case (b) is skipped entirely when repo= is omitted (no gh call, "
    "conservative not-clean)",
    code == mod.NOT_CLEAN_EXIT,
    out,
)

# The negative control this test suite would be worst without: OK_CONCLUSIONS
# must not silently grow to include every value naively encountered. Assert
# the exact set, so a future edit that widens it here shows up as a diff on
# this exact assertion rather than a passing test that quietly reports
# more things clean than mds#19 intended. `neutral` is deliberately excluded
# (see the docstring/comment on OK_CONCLUSIONS itself) -- this pins that
# exclusion, not just the two members that remain.
check(
    "OK_CONCLUSIONS is exactly success/skipped (neutral excluded on purpose)",
    mod.OK_CONCLUSIONS == {"success", "skipped"},
    repr(mod.OK_CONCLUSIONS),
)

# --- resolve_sha(): SHA validation, offline (run_gh monkeypatched) ---------


def with_fake_run_gh(fake, thunk):
    original = mod.run_gh
    mod.run_gh = fake
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                result = thunk()
                code = 0
            except SystemExit as exc:
                result = None
                code = exc.code
    finally:
        mod.run_gh = original
    return code, result, buf.getvalue()


def gh_never_called(args):
    raise AssertionError(f"gh should not have been called: {args}")


code, _, out = with_fake_run_gh(
    gh_never_called, lambda: mod.resolve_sha("acme/widgets", "cafef00d")
)
check(
    "a short/abbreviated SHA is rejected before any gh call (exit 2)",
    code == mod.USAGE_EXIT,
    out,
)
check(
    "the short-SHA message names the 40-character requirement",
    "40-character" in out,
    out,
)

code, _, out = with_fake_run_gh(
    gh_never_called, lambda: mod.resolve_sha("acme/widgets", "not-hex-at-all-zzzzzz")
)
check(
    "a non-hex --sha is rejected before any gh call (exit 2)",
    code == mod.USAGE_EXIT,
    out,
)


def fake_gh_commit_resolves_to(expected_sha):
    def fake_gh(args):
        if args[:2] == ["api", f"repos/acme/widgets/commits/{expected_sha}"]:
            return expected_sha + "\n"
        raise AssertionError(f"unexpected gh call: {args}")

    return fake_gh


code, result, out = with_fake_run_gh(
    fake_gh_commit_resolves_to(SHA_DEADBEEF),
    lambda: mod.resolve_sha("acme/widgets", SHA_DEADBEEF),
)
check(
    "a full 40-hex SHA that resolves is accepted and returned unchanged",
    code == 0 and result == SHA_DEADBEEF,
    out,
)


def fake_gh_commit_404(args):
    # run_gh() itself dies with USAGE_EXIT on a non-zero `gh api` exit; a
    # 404 is modeled here by having the fake raise the same SystemExit
    # run_gh would raise, so this test exercises resolve_sha()'s CALLER
    # contract rather than reimplementing run_gh's own subprocess handling.
    print("gh api ... failed: 404 Not Found", file=sys.stderr)
    raise SystemExit(mod.USAGE_EXIT)


code, _, out = with_fake_run_gh(
    fake_gh_commit_404, lambda: mod.resolve_sha("acme/widgets", SHA_CAFEF00D)
)
check(
    "a well-formed but nonexistent SHA (404 from the commits endpoint) "
    "exits 2, never 3 -- it must never read the same as 'no runs yet'",
    code == mod.USAGE_EXIT,
    out,
)


def fake_gh_commit_mismatch(args):
    # Pathological: the API answers 200 but with a SHA that does not match
    # what was asked for. resolve_sha() must refuse to guess rather than
    # silently substituting the returned value.
    return SHA_OTHER + "\n"


code, _, out = with_fake_run_gh(
    fake_gh_commit_mismatch, lambda: mod.resolve_sha("acme/widgets", SHA_CAFEF00D)
)
check(
    "a commits-endpoint response that does not echo the requested SHA is "
    "refused rather than substituted (exit 2)",
    code == mod.USAGE_EXIT,
    out,
)

# --- main(): end-to-end with run_gh monkeypatched ---------------------------


def with_fake_gh(fake, argv):
    original = mod.run_gh
    mod.run_gh = fake
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                code = mod.main(argv)
            except SystemExit as exc:
                # die() raises SystemExit(USAGE_EXIT) directly, rather than
                # returning it, for the cases resolve_repo/resolve_sha hit
                # before main() has anything to return -- so a usage exit
                # has to be caught here too, not just read as a return value.
                code = exc.code
    finally:
        mod.run_gh = original
    return code, buf.getvalue()


def fake_gh_factory(sha_runs_json, sha=SHA_DEADBEEF):
    def fake_gh(args):
        if args[:2] == ["repo", "view"]:
            return "acme/widgets\n"
        if args[:2] == ["api", "repos/acme/widgets/commits/HEAD"]:
            return sha + "\n"
        if args[:2] == ["api", f"repos/acme/widgets/commits/{sha}"]:
            return sha + "\n"
        if "actions/runs" in args[1]:
            return sha_runs_json
        raise AssertionError(f"unexpected gh call: {args}")

    return fake_gh


code, out = with_fake_gh(
    fake_gh_factory(_json.dumps(run("publish"))),
    [],
)
check("main(): resolves repo/sha and reports clean end to end", code == 0, out)
check("main(): names the SHA it checked", SHA_DEADBEEF in out, out)

code, out = with_fake_gh(fake_gh_factory(""), [])
check(
    "main(): no runs on the resolved SHA still exits 3, not 0 "
    "(this is the mds incident's exact shape)",
    code == mod.NO_RUNS_EXIT,
    out,
)

code, out = with_fake_gh(
    fake_gh_factory(
        _json.dumps({**run("publish"), "conclusion": "failure"}),
        sha=SHA_CAFEF00D,
    ),
    ["--sha", SHA_CAFEF00D],
)
check("main(): explicit --sha is used instead of resolving HEAD", code == mod.NOT_CLEAN_EXIT, out)
check("main(): explicit --sha appears in the checked-SHA line", SHA_CAFEF00D in out, out)

# --sha short-circuits resolve_sha's own HEAD lookup: prove it by making that
# path raise if reached at all. The commits/<sha> validation call still
# happens -- that is the point of the fix -- so it is stubbed here instead.


def fake_gh_no_head_lookup(args):
    if args[:2] == ["repo", "view"]:
        return "acme/widgets\n"
    if args[:2] == ["api", "repos/acme/widgets/commits/HEAD"]:
        raise AssertionError("resolve_sha called gh for HEAD despite --sha")
    if args[:2] == ["api", f"repos/acme/widgets/commits/{SHA_CAFEF00D}"]:
        return SHA_CAFEF00D + "\n"
    if "actions/runs" in args[1]:
        return _json.dumps(run("publish"))
    raise AssertionError(f"unexpected gh call: {args}")


code, out = with_fake_gh(fake_gh_no_head_lookup, ["--sha", SHA_CAFEF00D])
check("main(): --sha skips the HEAD-resolution gh call entirely", code == 0, out)

# End-to-end: a short/abbreviated --sha never reaches the runs query at all,
# and exits 2 rather than reading as "no runs found" (3).
code, out = with_fake_gh(fake_gh_no_head_lookup, ["--sha", "cafef00d"])
check(
    "main(): a short --sha exits 2 (usage), never 3 (no-runs)",
    code == mod.USAGE_EXIT,
    out,
)

# --- parse_runs() tests ----------------------------------------------------

check("parse_runs: empty string returns empty list", mod.parse_runs("") == [])
check("parse_runs: whitespace returns empty list", mod.parse_runs("   \n\t  ") == [])

single_ndjson = _json.dumps(run("a"))
check(
    "parse_runs: single NDJSON line",
    mod.parse_runs(single_ndjson) == [run("a")],
)

multiple_ndjson = _json.dumps(run("a")) + "\n" + _json.dumps(run("b"))
check(
    "parse_runs: multiple NDJSON lines",
    mod.parse_runs(multiple_ndjson) == [run("a"), run("b")],
)
# --- fetch_runs & find_next_branch_run pagination and flag tests -----------

recorded_args = []


def fake_gh_recorder(output):
    def fake(args):
        recorded_args.append(args)
        return output

    return fake


# fetch_runs with --jq .workflow_runs[] across multiple NDJSON lines
recorded_args.clear()
mod.run_gh = fake_gh_recorder(multiple_ndjson)
try:
    fetched = mod.fetch_runs("acme/widgets", SHA_DEADBEEF)
finally:
    mod.run_gh = original_run_gh

check(
    "fetch_runs: --slurp is NOT passed to gh api",
    "--slurp" not in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "fetch_runs: --paginate IS passed to gh api",
    "--paginate" in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "fetch_runs: --jq .workflow_runs[] IS passed to gh api",
    "--jq" in recorded_args[0] and ".workflow_runs[]" in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "fetch_runs: runs are parsed across NDJSON lines",
    [r["name"] for r in fetched] == ["a", "b"],
    str(fetched),
)

# find_next_branch_run with --jq .workflow_runs[] across multiple NDJSON lines
recorded_args.clear()
line1 = _json.dumps(FAILED_RUN_Z)
line2 = _json.dumps(SUCCESS_RUN_Y)
mod.run_gh = fake_gh_recorder(line1 + "\n" + line2)
try:
    next_found = mod.find_next_branch_run("acme/widgets", CANCELLED_RUN_B)
finally:
    mod.run_gh = original_run_gh

check(
    "find_next_branch_run: --slurp is NOT passed to gh api",
    "--slurp" not in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "find_next_branch_run: --paginate IS passed to gh api",
    "--paginate" in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "find_next_branch_run: --jq .workflow_runs[] IS passed to gh api",
    "--jq" in recorded_args[0] and ".workflow_runs[]" in recorded_args[0],
    str(recorded_args[0]),
)
check(
    "find_next_branch_run: finds candidate across NDJSON lines",
    next_found == FAILED_RUN_Z,
    str(next_found),
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
