#!/usr/bin/env python3
"""Regression tests for scripts/test_hooks.py.

Test case #1 is the incident that prompted the timeout: a suite that never
terminates used to stall the whole sweep with no FAIL line (ai-config#2098,
Windows 11, 2026-08-23). The runner must report FAIL on expiry rather than
wait forever, and must continue to the next suite.

Test case #4b/#4c cover that a suite's own kill-then-drain also has a
bounded deadline: CPython's subprocess.run() retries communicate() with NO
timeout after killing a timed-out process on Windows, which can hang again
if a descendant inherited the pipe handle -- reverting the runner's own
drain bound must FAIL, not hang.

The other required hardening from that issue -- verdict() spawning
sys.executable rather than a bare python3, which is a suspect for the same
hang and guarantees a real interpreter either way -- is pinned as a source
check against hooks/test-no-clobbering-push.py (case #5), and generalized
(case #5b) to a corpus-wide scan: no hooks/test-*.py may invoke its subject
via a bare "python3", since the same suspect mechanism (ai-config#2098)
applies to every one of them, not just this one file.

Run: python3 scripts/test_test_hooks.py
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "test_hooks.py"
ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("test_hooks_under_test", SCRIPT)
th = importlib.util.module_from_spec(spec)
spec.loader.exec_module(th)

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


HANG = """\
import time
print("started", flush=True)
time.sleep(30)
print("should-not-reach")
"""

OK = """\
print("1/1 ok")
"""

BOOM = """\
import sys
print("boom")
sys.exit(2)
"""


def _write_pair(hooks: Path, stem: str, test_body: str) -> tuple[str, str]:
    test_path = hooks / f"test-{stem}.py"
    subject = hooks / f"{stem}.py"
    test_path.write_text(test_body, encoding="utf-8")
    subject.write_text("pass\n", encoding="utf-8")
    return str(test_path), str(subject)


def _capture(fn):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = fn()
    return result, out.getvalue(), err.getvalue()


# --- 1. The incident: a hung suite must FAIL, not stall -------------------

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    hang_test, hang_subj = _write_pair(hooks, "hang", HANG)
    rc, stdout, stderr = _capture(
        lambda: th.run_one_suite(hang_test, hang_subj, timeout=1))
    check("hung suite returns failure", rc == 1, f"rc={rc}")
    check("hung suite FAIL line names timeout",
          "FAIL:" in stdout and "timed out after 1s" in stdout,
          repr(stdout))
    check("hung suite names the test on FAIL",
          os.path.basename(hang_test) in stdout, repr(stdout))


# --- 2. A hang must not prevent later suites from running -----------------

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    _write_pair(hooks, "hang", HANG)
    _write_pair(hooks, "ok", OK)
    old = th.HOOKS
    th.HOOKS = str(hooks)
    try:
        (counts, stdout, stderr) = _capture(
            lambda: th.run_suites(timeout=1))
    finally:
        th.HOOKS = old
    suite_failures, n_suites = counts
    check("sweep still examines both suites after a hang",
          n_suites == 2, f"n={n_suites} out={stdout!r}")
    check("sweep counts the hung suite as a failure",
          suite_failures == 1, f"failures={suite_failures}")
    check("later suite still runs after a hang",
          "PASS:" in stdout and "test-ok.py" in stdout, repr(stdout))


# --- 3. Timeout does not swallow a real pass or a real fail ---------------

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    ok_test, ok_subj = _write_pair(hooks, "ok", OK)
    boom_test, boom_subj = _write_pair(hooks, "boom", BOOM)
    rc, stdout, _ = _capture(
        lambda: th.run_one_suite(ok_test, ok_subj, timeout=10))
    check("fast pass still PASSes under a timeout",
          rc == 0 and "PASS:" in stdout, repr(stdout))
    rc, stdout, _ = _capture(
        lambda: th.run_one_suite(boom_test, boom_subj, timeout=10))
    check("fast fail still FAILs with exit code, not timeout",
          rc == 1 and "(exit 2)" in stdout and "timed out" not in stdout,
          repr(stdout))


# --- 4. HOOK_TEST_SUITE_TIMEOUT parsing ----------------------------------

with patch.dict(os.environ):
    os.environ.pop("HOOK_TEST_SUITE_TIMEOUT", None)
    check("default timeout is 900s", th.suite_timeout_s() == 900)

with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "12"}):
    check("env override is honored", th.suite_timeout_s() == 12)

with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": ""}):
    check("empty env keeps the default", th.suite_timeout_s() == 900)

try:
    with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "nope"}):
        th.suite_timeout_s()
    check("invalid env is fatal", False)
except SystemExit as exc:
    check("invalid env is fatal", "not a number" in str(exc), str(exc))

try:
    with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "0"}):
        th.suite_timeout_s()
    check("non-positive env is fatal", False)
except SystemExit as exc:
    check("non-positive env is fatal",
          "positive finite number" in str(exc), str(exc))

for raw in ("nan", "inf", "-inf"):
    try:
        with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": raw}):
            th.suite_timeout_s()
        check(f"{raw} env is fatal", False)
    except SystemExit as exc:
        check(f"{raw} env is fatal",
              "positive finite number" in str(exc), str(exc))

# A genuinely finite, positive value can still crash the underlying
# subprocess wait rather than FAIL one suite -- ai-config#2098 review
# finding #3, measured directly above MAX_SUITE_TIMEOUT_S's own docstring.
with patch.dict(os.environ, {
        "HOOK_TEST_SUITE_TIMEOUT": str(th.MAX_SUITE_TIMEOUT_S)}):
    check("the maximum itself is accepted",
          th.suite_timeout_s() == th.MAX_SUITE_TIMEOUT_S)

try:
    with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "1000000000"}):
        th.suite_timeout_s()
    check("a value that would overflow the subprocess wait is fatal", False)
except SystemExit as exc:
    check("a value that would overflow the subprocess wait is fatal",
          "exceeds the" in str(exc), str(exc))

check("timeout label drops trailing .0", th._timeout_label(600) == "600")
check("timeout label keeps a fraction", th._timeout_label(0.5) == "0.5")
check("captured None decodes to empty", th._decode_captured(None) == "")
check("captured bytes decode", th._decode_captured(b"hi") == "hi")


# --- 4b. Production run_suites() applies suite_timeout_s() ----------------
# Hang checks pass an explicit timeout=; env checks call suite_timeout_s()
# in isolation. Neither exercises main()'s path: run_suites() with
# timeout=None. Deleting that coalesce leaves communicate(timeout=None).

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    _write_pair(hooks, "ok", OK)
    old = th.HOOKS
    th.HOOKS = str(hooks)
    try:
        with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "12"}):
            with patch.object(th.subprocess, "Popen") as mock_popen:
                mock_proc = mock_popen.return_value
                mock_proc.communicate.return_value = ("ok\n", "")
                mock_proc.returncode = 0
                _capture(lambda: th.run_suites())
                timeouts = [
                    call.kwargs.get("timeout")
                    for call in mock_proc.communicate.call_args_list
                ]
    finally:
        th.HOOKS = old
check("production run_suites() applies suite_timeout_s()",
      timeouts == [12], repr(timeouts))


# --- 4c. A descendant that inherits the pipe must not defeat the deadline -
# ai-config#2098 review finding #1: CPython's own subprocess.run() retries
# communicate() with NO timeout after killing a timed-out process on
# Windows -- and that retry can hang forever if a descendant process
# inherited the pipe write handle, since kill() only kills the direct
# child. run_one_suite() must bound that retry itself (DRAIN_TIMEOUT_S)
# rather than trusting subprocess.run()'s own internal handling.
#
# Reproduced here on Linux with the general shape rather than the
# Windows-specific mechanism: a grandchild that inherits the pipe and
# outlives the killed direct child defeats EOF-based reads identically on
# any platform.

HANG_WITH_DESCENDANT = """\
import subprocess, sys, time
# A detached grandchild that inherits our stdout/stderr pipe and outlives
# us -- killing THIS process does not close ITS pipe handle.
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
print("started", flush=True)
time.sleep(30)
"""

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    desc_test, desc_subj = _write_pair(
        hooks, "descendant", HANG_WITH_DESCENDANT)
    old_drain = th.DRAIN_TIMEOUT_S
    th.DRAIN_TIMEOUT_S = 0.5
    try:
        rc, stdout, stderr = _capture(
            lambda: th.run_one_suite(desc_test, desc_subj, timeout=1))
    finally:
        th.DRAIN_TIMEOUT_S = old_drain
check("a descendant holding the pipe still returns failure", rc == 1,
      f"rc={rc}")
check("a descendant holding the pipe reports output unavailable "
      "rather than hanging",
      "output unavailable" in stdout, repr(stdout))


# --- 5. verdict() spawn uses this interpreter, not a bare python3 ---------

src = (ROOT / "hooks" / "test-no-clobbering-push.py").read_text(encoding="utf-8")
start = src.index("def verdict(")
end = src.index("\ndef ", start + 1)
body = src[start:end]
check("verdict() spawns sys.executable",
      "[sys.executable, hook_path]" in body, body)
check("verdict() does not spawn a bare python3",
      '["python3", hook_path]' not in body, body)


# --- 5b. No hooks/test-*.py invokes its hook via a bare "python3" ---------
# Generalizes check #5: a bare "python3" (ai-config#2098's unverified but
# unretired suspect for a Windows hang, and in any case a real gap for
# whatever "python3" does or doesn't resolve to on a given machine's PATH)
# applies to every hooks/test-*.py that spawns its subject, not just
# test-no-clobbering-push.py -- review finding #2 named several others
# still doing it.
BARE_PYTHON3_INVOCATION = re.compile(r'\[\s*["\']python3["\']\s*,')
offenders = [
    test_file.name
    for test_file in sorted((ROOT / "hooks").glob("test-*.py"))
    if BARE_PYTHON3_INVOCATION.search(test_file.read_text(encoding="utf-8"))
]
check('no hooks/test-*.py spawns its hook via a bare "python3"',
      not offenders, repr(offenders))


# --- 6. Coverage allowlist branches and the two-subject FAIL (#1080) ------
# KNOWN_UNTESTED is empty in production, so both of check_coverage()'s
# allowlist branches would otherwise run only when a hook regresses; inject a
# test allowlist so they are exercised every run.

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    (hooks / "untested.py").write_text("pass\n", encoding="utf-8")
    _write_pair(hooks, "ok", OK)
    old_hooks, old_allow = th.HOOKS, th.KNOWN_UNTESTED
    th.HOOKS = str(hooks)
    try:
        th.KNOWN_UNTESTED = {"untested.py"}
        (cov, stdout, _) = _capture(th.check_coverage)
        check("an allowlisted hook without a test is a NOTE, not a failure",
              cov[0] == 0 and "NOTE: untested.py has no test" in stdout, repr(stdout))
        th.KNOWN_UNTESTED = set()
        (cov, stdout, _) = _capture(th.check_coverage)
        check("an unlisted hook without a test fails",
              cov[0] == 1 and "FAIL: hooks/untested.py has no test" in stdout, repr(stdout))
        th.KNOWN_UNTESTED = {"ok.py"}
        (cov, stdout, _) = _capture(th.check_coverage)
        # untested.py is still unlisted here, so that failure counts too.
        check("a stale allowlist entry that now has a test fails",
              cov[0] == 2 and "drop it from KNOWN_UNTESTED" in stdout, repr(stdout))
    finally:
        th.HOOKS, th.KNOWN_UNTESTED = old_hooks, old_allow

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    _write_pair(hooks, "twin", OK)
    (hooks / "twin.sh").write_text("exit 0\n", encoding="utf-8")
    old_hooks = th.HOOKS
    th.HOOKS = str(hooks)
    try:
        (counts, stdout, _) = _capture(lambda: th.run_suites(timeout=5))
    finally:
        th.HOOKS = old_hooks
    check("a stem with both .py and .sh subjects is one failure",
          counts == (1, 1), repr(counts))
    check("the two-subject FAIL names both subjects",
          "has two subjects" in stdout and "twin.py" in stdout and "twin.sh" in stdout, repr(stdout))
    check("the ambiguous suite is not invoked",
          "RUN:" not in stdout and "PASS:" not in stdout, repr(stdout))

with tempfile.TemporaryDirectory(prefix="hook-runner-") as tmp:
    hooks = Path(tmp)
    (hooks / "test-shell.py").write_text(OK, encoding="utf-8")
    (hooks / "shell.sh").write_text("exit 0\n", encoding="utf-8")
    old_hooks = th.HOOKS
    th.HOOKS = str(hooks)
    try:
        (counts, stdout, _) = _capture(lambda: th.run_suites(timeout=5))
    finally:
        th.HOOKS = old_hooks
    check("a .sh-only subject resolves and its suite runs",
          counts == (0, 1) and "PASS:" in stdout, repr((counts, stdout)))


print(f"\n{passes}/{passes + failures} checks passed")
sys.exit(1 if failures else 0)
