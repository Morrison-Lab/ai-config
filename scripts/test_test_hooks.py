#!/usr/bin/env python3
"""Regression tests for scripts/test_hooks.py.

Test case #1 is the incident that prompted the timeout: a suite that never
terminates used to stall the whole sweep with no FAIL line (ai-config#2098,
Windows 11, 2026-08-23). The runner must report FAIL on expiry rather than
wait forever, and must continue to the next suite.

The other required hardening from that issue -- verdict() spawning
sys.executable rather than a bare python3 -- is pinned as a source check
against hooks/test-no-clobbering-push.py.

Run: python3 scripts/test_test_hooks.py
"""
from __future__ import annotations

import importlib.util
import io
import os
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

check("default timeout is 600s", th.suite_timeout_s() == 600)

with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": "12"}):
    check("env override is honored", th.suite_timeout_s() == 12)

with patch.dict(os.environ, {"HOOK_TEST_SUITE_TIMEOUT": ""}):
    check("empty env keeps the default", th.suite_timeout_s() == 600)

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
    check("non-positive env is fatal", "must be positive" in str(exc), str(exc))

check("timeout label drops trailing .0", th._timeout_label(600) == "600")
check("timeout label keeps a fraction", th._timeout_label(0.5) == "0.5")
check("captured None decodes to empty", th._decode_captured(None) == "")
check("captured bytes decode", th._decode_captured(b"hi") == "hi")


# --- 5. verdict() spawn uses this interpreter, not a bare python3 ---------

src = (ROOT / "hooks" / "test-no-clobbering-push.py").read_text(encoding="utf-8")
start = src.index("def verdict(")
end = src.index("\ndef ", start + 1)
body = src[start:end]
check("verdict() spawns sys.executable",
      "[sys.executable, hook_path]" in body, body)
check("verdict() does not spawn a bare python3",
      '["python3", hook_path]' not in body, body)


print(f"\n{passes}/{passes + failures} checks passed")
sys.exit(1 if failures else 0)
