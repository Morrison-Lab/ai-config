#!/usr/bin/env python3
"""Tests for `scripts/sync-nlb-checker.py`'s `_fetch` and CLI, offline.

Both fetch routes are stubbed: `subprocess.run` stands in for `gh`, and
`urllib.request.urlopen` for raw HTTPS. The case that matters most is the
one ai-config#2338 was filed for: a machine with no `gh` on PATH, where
`subprocess.run` raises `FileNotFoundError` instead of returning a non-zero
exit, and the HTTPS route must still run.

The CLI checks cover ai-config#3095: `--help` used to run the sync, so it
must now print usage and exit 0 with `_fetch` never reached, and an unknown
argument must exit 2 rather than being ignored. They run twice: in-process
against `main(argv)`, and as a subprocess against the real entry point, which
is the one the issue was reported against and the only one that exercises the
`argv=None` default and the `if __name__ == "__main__"` wiring.

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

# ai-config#3095: `--help` ran the sync, fetching over the network and
# rewriting two tracked files. It must print usage and exit 0 instead, and
# `_fetch` must never be reached -- so stub it to fail loudly if it is.
saved_fetch = subject._fetch


class _Reached(Exception):
    """Raised by the stub, so a check can tell whether `_fetch` ran."""


def fetch_stub(sha):
    raise _Reached(sha)


subject._fetch = fetch_stub
try:
    for flag in ("--help", "-h"):
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                subject.main([flag])
            check(f"{flag} exits", False)
        except _Reached:
            check(f"{flag} exits before fetching", False)
        except SystemExit as exc:
            check(f"{flag} exits 0", exc.code == 0)
        check(f"{flag} prints the module docstring",
              "Refresh the vendored" in out.getvalue()
              and "Do not hand-edit" in out.getvalue())

    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            subject.main(["--bogus"])
        check("an unknown argument exits", False)
    except _Reached:
        check("an unknown argument exits before fetching", False)
    except SystemExit as exc:
        check("an unknown argument exits 2", exc.code == 2)

    # The no-argument invocation parses to no options and is still the sync,
    # so it must reach `_fetch` rather than stopping at the parser.
    check("no arguments parse to an empty namespace",
          vars(subject._parse_args([])) == {})
    try:
        subject.main([])
        check("no arguments reach the fetch", False)
    except _Reached:
        check("no arguments reach the fetch", True)
finally:
    subject._fetch = saved_fetch

# The checks above drive `main(argv)` in-process, which cannot see the
# `argv=None` default or the `if __name__ == "__main__"` line that forwards
# the process command line into it -- and that entry point is the one #3095
# was reported against. Exercise it for real. Neither run touches the
# network, because the parse now precedes the fetch.
VENDORED = subject.nlb_gate.VENDOR_PY
before = VENDORED.stat().st_mtime_ns if VENDORED.exists() else None

help_run = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                          capture_output=True, text=True)
check("the real CLI exits 0 on --help", help_run.returncode == 0)
check("the real CLI prints the module docstring on --help",
      "Refresh the vendored" in help_run.stdout
      and "Do not hand-edit" in help_run.stdout)

bogus_run = subprocess.run([sys.executable, str(SCRIPT), "--bogus"],
                           capture_output=True, text=True)
check("the real CLI exits 2 on an unknown argument", bogus_run.returncode == 2)

after = VENDORED.stat().st_mtime_ns if VENDORED.exists() else None
check("the real CLI writes nothing when it only parses", before == after)

if failures:
    sys.exit(f"{failures} check(s) failed")
print("PASS: _fetch falls through to HTTPS when gh is missing or failing, "
      "names both routes when both fail, and the CLI -- in-process and as the "
      "real entry point -- prints usage for --help/-h without fetching")
