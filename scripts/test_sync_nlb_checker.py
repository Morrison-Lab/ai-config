#!/usr/bin/env python3
"""Tests for `scripts/sync-nlb-checker.py`'s `_fetch`, offline.

Both routes are stubbed: `subprocess.run` stands in for `gh`, and
`urllib.request.urlopen` for raw HTTPS. The case that matters most is the
one ai-config#2338 was filed for: a machine with no `gh` on PATH, where
`subprocess.run` raises `FileNotFoundError` instead of returning a non-zero
exit, and the HTTPS route must still run.

Run:  python3 scripts/test_sync_nlb_checker.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import urllib.request
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sync-nlb-checker.py"
spec = importlib.util.spec_from_file_location("sync_nlb_checker", SCRIPT)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

SHA = "0123456789abcdef0123456789abcdef01234567"
BODY = b"# classify_line has_late_semicolon\n"


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


@contextlib.contextmanager
def stubs(run=None, urlopen=None):
    saved = (subject.subprocess.run, subject.urllib.request.urlopen)
    try:
        if run is not None:
            subject.subprocess.run = run
        if urlopen is not None:
            subject.urllib.request.urlopen = urlopen
        yield
    finally:
        subject.subprocess.run, subject.urllib.request.urlopen = saved


def gh_missing(*args, **kwargs):
    raise FileNotFoundError(2, "No such file or directory", "gh")


def gh_ok(*args, **kwargs):
    return subprocess.CompletedProcess(args[0], 0, stdout=BODY, stderr=b"")


def gh_fails(*args, **kwargs):
    return subprocess.CompletedProcess(args[0], 1, stdout=b"", stderr=b"gh: HTTP 404")


def https_ok(url):
    assert SHA in url, url
    return _Response(BODY)


def https_down(url):
    raise OSError("connection refused")


failures = 0


def check(label, ok):
    global failures
    print(("ok: " if ok else "FAIL: ") + label)
    if not ok:
        failures += 1


# The incident: no gh binary, HTTPS answers -- must return the bytes, not raise.
with stubs(run=gh_missing, urlopen=https_ok):
    check("missing gh falls through to HTTPS", subject._fetch(SHA) == BODY)

# gh present and working: HTTPS is never consulted.
with stubs(run=gh_ok, urlopen=https_down):
    check("a working gh short-circuits HTTPS", subject._fetch(SHA) == BODY)

# gh present but failing: HTTPS still answers.
with stubs(run=gh_fails, urlopen=https_ok):
    check("a failing gh falls through to HTTPS", subject._fetch(SHA) == BODY)

# Both routes fail: the error names both, including why gh was unusable.
for label, run, needle in (
    ("missing gh", gh_missing, "No such file or directory"),
    ("failing gh", gh_fails, "gh: HTTP 404"),
):
    with stubs(run=run, urlopen=https_down):
        try:
            subject._fetch(SHA)
            check(f"{label} + HTTPS down raises", False)
        except SystemExit as exc:
            message = str(exc.code)
            check(f"{label} + HTTPS down names the gh reason",
                  needle in message and "connection refused" in message)

if failures:
    sys.exit(f"{failures} check(s) failed")
print("PASS: _fetch falls through to HTTPS when gh is missing or failing, and "
      "names both routes when both fail")
