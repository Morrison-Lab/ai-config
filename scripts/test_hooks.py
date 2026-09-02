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
ai-config#1080 wrote the last of those tests, so the allowlist is empty; it
stays so a new untested hook is a failure, not a NOTE.

A hung suite used to stall the whole sweep with no timeout and nothing on
stdout (ai-config#2098, observed on Windows). Each suite now has a deadline;
expiry prints FAIL and the runner continues. Override with
HOOK_TEST_SUITE_TIMEOUT (seconds). Killing the suite on expiry is not
itself enough on Windows: `subprocess.run()`'s own retry-after-kill can
hang again if a descendant process inherited a pipe handle, so this runner
does its own bounded drain instead (see DRAIN_TIMEOUT_S).

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
# mutation rounds) finished in 178s. 900s is about 5x that, so a slow
# Windows box has headroom past the 420s kill of the hang that never
# produced output (ai-config#2098) while still FAILing an infinite
# stall. Override with HOOK_TEST_SUITE_TIMEOUT.
DEFAULT_SUITE_TIMEOUT_S = 900

# The largest HOOK_TEST_SUITE_TIMEOUT this runner accepts. A genuinely
# finite, positive value can still crash the sweep: Popen.communicate()'s
# poll()-based selector (selectors.PollSelector -- CPython's subprocess
# module deliberately avoids epoll/kqueue here, per its own comment about
# not spending an extra file descriptor) converts the timeout to
# milliseconds as a C int, so a value above roughly INT_MAX ms
# (~2147483s, ~24.9 days) raises OverflowError -- measured directly
# through the real path (Linux, Python 3.11.15, 2026-08-26:
# `Popen(...).communicate(timeout=1e9)` raises "timeout is too large")
# and reported independently on Python 3.12.3 for
# HOOK_TEST_SUITE_TIMEOUT=1000000000. Windows uses blocking reads on
# child threads instead of a selector, so the exact boundary there is
# unmeasured; the cap stays far below every candidate boundary. That exception is not caught
# anywhere a per-suite FAIL could absorb it, so it aborts the whole sweep
# exactly like the nan/inf cases below. One day is far more than any suite
# should ever need and stays safely under that boundary on every platform
# this runner targets.
MAX_SUITE_TIMEOUT_S = 86400

# Hooks that ship without a test: an explicit, reviewable allowlist rather
# than a silent gap. Empty since ai-config#1080 wrote the last missing test;
# the set stays so a new hook without a test fails this check, and an entry
# added here must cite its tracking issue.
KNOWN_UNTESTED: set = set()


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
    # inf is positive). On POSIX Python 3.12.3 (Linux, measured
    # 2026-08-26), subprocess.run(timeout=nan) raises ValueError
    # immediately and timeout=inf raises OverflowError, even for an
    # instant child; either would abort the whole sweep with no
    # per-suite FAIL. timeout=-inf raises TimeoutExpired immediately.
    # Rejecting all three names the bad env var instead of crashing,
    # and does not treat -inf as a zero-second deadline.
    if not math.isfinite(value) or value <= 0:
        sys.exit(
            f"FATAL: HOOK_TEST_SUITE_TIMEOUT={raw!r} must be a positive "
            "finite number")
    if value > MAX_SUITE_TIMEOUT_S:
        sys.exit(
            f"FATAL: HOOK_TEST_SUITE_TIMEOUT={raw!r} exceeds the "
            f"{MAX_SUITE_TIMEOUT_S}s maximum (a larger value can overflow "
            "the underlying subprocess wait and crash the whole sweep "
            "instead of FAILing one suite)")
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


# After killing a timed-out suite, how long to wait for its output to drain
# before giving up on capturing it. subprocess.run()'s OWN TimeoutExpired
# handling calls communicate() a second time with NO timeout on Windows, to
# collect output for the exception -- see CPython's subprocess.py: "Windows
# accumulates the output in a single blocking read() call run on child
# threads ... communicate() after kill() is required to collect that". kill()
# only kills the direct child; a descendant that inherited the pipe write
# handle (e.g. a git helper a suite spawned) can keep that pipe open past the
# child's death, so the unbounded second communicate() never sees EOF and the
# whole sweep hangs again -- past the deadline this runner exists to enforce.
# Doing our own bounded retry, and giving up on the output rather than
# waiting forever, is what keeps the per-suite deadline a real deadline.
DRAIN_TIMEOUT_S = 5


def run_one_suite(test_path, subject, timeout):
    """Run one suite against its subject. Returns 0 on pass, 1 on fail."""
    rel_test = os.path.relpath(test_path, ROOT)
    print(f"RUN: {rel_test}", flush=True)
    # PYTHONWARNINGS, not a `-W` flag: most hooks/test-*.py invoke their
    # subject hook as a SEPARATE subprocess (subprocess.run([sys.executable,
    # HOOK], ...)), and a `-W` flag given to this outer interpreter is not
    # inherited by a child `python` process it launches -- only environment
    # variables propagate that way. An earlier version of this fix used `-W`
    # and was caught in review: 36 of 46 suites spawn the subject as a
    # subprocess, and a SyntaxWarning injected into one of them (verified
    # empirically) still passed cleanly under the `-W`-only form.
    env = dict(os.environ, PYTHONWARNINGS="error::SyntaxWarning")
    env.pop("ANTIGRAVITY_AGENT", None)
    proc = subprocess.Popen(
        [sys.executable, test_path, subject],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=DRAIN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            stdout = stderr = None
            proc.stdout.close()
            proc.stderr.close()
        print(f"FAIL: {rel_test} (timed out after {_timeout_label(timeout)}s)")
        sys.stdout.write(_decode_captured(stdout))
        sys.stderr.write(_decode_captured(stderr))
        if stdout is None and stderr is None:
            # Known trade-off: only the direct child was killed above, so
            # a descendant that inherited the pipe survives as an orphan
            # until it exits on its own. Killing the whole process group
            # (start_new_session=True) would close that, at the cost of
            # changing signal semantics for every well-behaved suite.
            print("(output unavailable: a descendant process still held the "
                  "pipe after the suite was killed)")
        return 1
    tail = (stdout.strip().splitlines() or ["(no output)"])[-1]
    if proc.returncode == 0:
        print(f"PASS: {rel_test} -- {tail}")
        return 0
    print(f"FAIL: {rel_test} (exit {proc.returncode})")
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return 1


def rel_test_for(test_path):
    return os.path.relpath(test_path, ROOT)


def run_suites(timeout=None):
    """Run each hooks/test-*.py against its subject. Returns failure count."""
    if timeout is None:
        timeout = suite_timeout_s()
    failures = 0
    tests = sorted(glob.glob(os.path.join(HOOKS, "test-*.py")))
    for test_path in tests:
        # A subject may be a .py or a .sh hook (inject-local-time.sh, #1080);
        # try the test's own extension first, then the shell spelling.
        stem = os.path.basename(test_path)[len("test-"):-len(".py")]
        candidates = [os.path.join(HOOKS, stem + ext) for ext in (".py", ".sh")]
        present = [c for c in candidates if os.path.isfile(c)]
        if len(present) > 1:
            # Two subjects for one suite is ambiguous; picking one silently
            # would test the wrong file with no signal (fail-fast).
            print(f"FAIL: {rel_test_for(test_path)} has two subjects: "
                  + ", ".join(os.path.relpath(c, ROOT) for c in present))
            failures += 1
            continue
        subject = present[0] if present else candidates[0]
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
            print(f"NOTE: {name} has no test (known debt; track it in an issue)")
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
