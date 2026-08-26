#!/usr/bin/env python3
"""Run every hook's own test suite, and flag any hook that lacks one.

The hooks in `hooks/` each can ship a `test-<name>.py` beside a `<name>.py`,
but those tests ran nowhere: `.pre-commit-config.yaml` and `validate.yml`
invoke `scripts/test_*.py` by name and never reach into `hooks/`. So a guard
could regress -- start blocking a message it should pass, stop catching the
case it exists for -- and no check would notice. That is the gap
ai-config#1065's "algorithmatize whenever possible" points at, one level up:
the instruments that enforce the corpus's rules were themselves unverified.

This runner does two things:

  1. Runs each `hooks/test-*.py` against its subject `hooks/<name>.py` (the
     convention every hook test already uses, taking the subject as argv[1]).
  2. Checks coverage in the OTHER direction -- enumerates every hook and
     confirms it has a test. A one-directional test->subject walk cannot see a
     hook that ships NO test at all, so "N/N suites passed" would read as full
     coverage while an untested hook -- including a blocking `Stop` hook, the
     highest-stakes kind -- sat invisible (ai-config#1075 review).

`KNOWN_UNTESTED` records the hooks that currently ship without a test as an
explicit, reviewable debt; adding a NEW hook without a test fails this check.
Tracked in ai-config#1080 -- write those tests, then empty the allowlist.

A hung suite used to stall the whole sweep with no timeout and nothing on
stdout (ai-config#2098, observed on Windows). Each suite now has a deadline;
expiry prints FAIL and the runner continues. Override with
HOOK_TEST_SUITE_TIMEOUT (seconds).

Run: python3 scripts/test_hooks.py
"""
import glob
import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")

# Per-suite deadline. Measured 2026-08-26 on a Linux cloud runner: the
# slowest suite (test-no-clobbering-push: 32 scratch git repos plus 17
# mutation rounds) finished in 178s. 600s is about 3x that, so a slow
# Windows box has headroom, while the hang that never terminated across
# 120s and 420s kills (ai-config#2098) still FAILs instead of stalling
# the sweep. Override with HOOK_TEST_SUITE_TIMEOUT.
DEFAULT_SUITE_TIMEOUT_S = 600

# Hooks that ship without a test today. An explicit, reviewable list -- not a
# silent gap. A new hook is expected to bring its test; this list should only
# ever shrink. See ai-config#1080.
KNOWN_UNTESTED = {"inject-local-time.sh"}


def suite_timeout_s():
    """Seconds a single hooks/test-*.py may run before the runner FAILs it."""
    raw = os.environ.get("HOOK_TEST_SUITE_TIMEOUT")
    if raw is None or raw == "":
        return DEFAULT_SUITE_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        sys.exit(f"FATAL: HOOK_TEST_SUITE_TIMEOUT={raw!r} is not a number")
    # nan and inf both pass `value <= 0` (nan comparisons are false;
    # inf is positive). On Python 3.12.3 (measured 2026-08-26),
    # subprocess.run(timeout=nan) raises ValueError immediately and
    # timeout=inf raises OverflowError; either would abort the whole
    # sweep with no per-suite FAIL. timeout=-inf expires immediately
    # as TimeoutExpired. Rejecting all three names the bad env var
    # instead of crashing, and does not treat -inf as a zero-second
    # deadline.
    if not math.isfinite(value) or value <= 0:
        sys.exit(
            f"FATAL: HOOK_TEST_SUITE_TIMEOUT={raw!r} must be a positive "
            "finite number")
    return value


def _timeout_label(timeout):
    """Render a timeout for the FAIL line without a trailing .0."""
    if timeout == int(timeout):
        return str(int(timeout))
    return str(timeout)


def _decode_captured(blob):
    """TimeoutExpired.stdout/stderr may be str, bytes, or None."""
    if blob is None:
        return ""
    if isinstance(blob, bytes):
        return blob.decode("utf-8", errors="replace")
    return blob


def test_for(subject_basename):
    """The test filename a subject is expected to ship: test-<stem>.py."""
    stem = os.path.splitext(subject_basename)[0]
    return f"test-{stem}.py"


def subjects():
    """Every hook script (not a test, not the manifest)."""
    out = []
    for path in sorted(glob.glob(os.path.join(HOOKS, "*.py"))
                       + glob.glob(os.path.join(HOOKS, "*.sh"))):
        name = os.path.basename(path)
        if name.startswith("test-"):
            continue
        out.append(name)
    return out


def run_one_suite(test_path, subject, timeout):
    """Run one suite against its subject. Returns 0 on pass, 1 on fail."""
    rel_test = os.path.relpath(test_path, ROOT)
    print(f"RUN: {rel_test}", flush=True)
    try:
        proc = subprocess.run(
            [sys.executable, test_path, subject],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        print(f"FAIL: {rel_test} (timed out after {_timeout_label(timeout)}s)")
        sys.stdout.write(_decode_captured(exc.stdout))
        sys.stderr.write(_decode_captured(exc.stderr))
        return 1
    tail = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
    if proc.returncode == 0:
        print(f"PASS: {rel_test} -- {tail}")
        return 0
    print(f"FAIL: {rel_test} (exit {proc.returncode})")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return 1


def run_suites(timeout=None):
    """Run each hooks/test-*.py against its subject. Returns failure count."""
    if timeout is None:
        timeout = suite_timeout_s()
    failures = 0
    tests = sorted(glob.glob(os.path.join(HOOKS, "test-*.py")))
    for test_path in tests:
        subject = os.path.join(HOOKS, os.path.basename(test_path)[len("test-"):])
        rel_test = os.path.relpath(test_path, ROOT)
        rel_subj = os.path.relpath(subject, ROOT)
        if not os.path.isfile(subject):
            print(f"FAIL: {rel_test} has no subject at {rel_subj}")
            failures += 1
            continue
        failures += run_one_suite(test_path, subject, timeout)
    return failures, len(tests)


def check_coverage():
    """Confirm every hook has a test, allowing only KNOWN_UNTESTED. Returns
    (failure count, tested count, total count)."""
    failures = 0
    subs = subjects()
    tested = 0
    for name in subs:
        has_test = os.path.isfile(os.path.join(HOOKS, test_for(name)))
        if has_test:
            tested += 1
        elif name in KNOWN_UNTESTED:
            print(f"NOTE: {name} has no test (known debt, ai-config#1080)")
        else:
            print(f"FAIL: hooks/{name} has no test ({test_for(name)}); "
                  "add one or add it to KNOWN_UNTESTED with a tracking issue")
            failures += 1
    # A name in KNOWN_UNTESTED that has since gained a test should be removed
    # from the list, so the debt cannot silently linger as satisfied.
    for name in sorted(KNOWN_UNTESTED):
        if os.path.isfile(os.path.join(HOOKS, test_for(name))):
            print(f"FAIL: {name} now has a test; drop it from KNOWN_UNTESTED")
            failures += 1
    return failures, tested, len(subs)


def main() -> int:
    suite_failures, n_suites = run_suites()
    if n_suites == 0:
        print("no hooks/test-*.py found -- nothing to run")
        return 1
    cov_failures, tested, total = check_coverage()

    print(f"\n{n_suites - suite_failures}/{n_suites} hook test suites passed; "
          f"{tested}/{total} hooks have a test "
          f"({len(KNOWN_UNTESTED)} known untested)")
    return 1 if (suite_failures or cov_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
