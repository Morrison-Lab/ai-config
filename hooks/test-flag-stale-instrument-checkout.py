#!/usr/bin/env python3
"""Tests for flag-stale-instrument-checkout.py.

Real git repositories are built in $TMPDIR per case, because the whole
question is what `git rev-list --count HEAD..origin/<default>` answers, and a
mocked answer would test the mock.

The NEGATIVE cases carry the weight, as with every warn-only guard here: a
current checkout, a bare script name, an unrelated script, and a repo with no
remote must all stay silent, or the guard becomes noise and gets switched off.

Run: python3 hooks/test-flag-stale-instrument-checkout.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "guard", HERE / "flag-stale-instrument-checkout.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True,
                   capture_output=True, text=True)


def build(tmp, behind, default="main", with_remote=True):
    """A clone `behind` commits behind its origin's default branch."""
    origin = pathlib.Path(tmp) / "origin"
    origin.mkdir()
    sh(origin, "git", "init", "-q", "-b", default)
    sh(origin, "git", "config", "user.email", "t@e.st")
    sh(origin, "git", "config", "user.name", "t")
    scripts = origin / "scripts"
    scripts.mkdir()
    (scripts / "check-pr-fully-clean.py").write_text("print(0)\n")
    sh(origin, "git", "add", "-A")
    sh(origin, "git", "commit", "-qm", "base")

    clone = pathlib.Path(tmp) / "clone"
    if not with_remote:
        # A repo that is not a clone at all: no origin, nothing to compare.
        sh(pathlib.Path(tmp), "git", "clone", "-q", str(origin), "clone")
        sh(clone, "git", "remote", "remove", "origin")
        return clone
    sh(pathlib.Path(tmp), "git", "clone", "-q", str(origin), "clone")
    for i in range(behind):
        (origin / f"f{i}").write_text("x")
        sh(origin, "git", "add", "-A")
        sh(origin, "git", "commit", "-qm", f"c{i}")
    if behind:
        sh(clone, "git", "fetch", "-q", "origin")
    return clone


def run(command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    buf = io.StringIO()
    stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        with redirect_stderr(buf):
            rc = guard.main()
    finally:
        sys.stdin = stdin
    return rc, buf.getvalue()


def main():
    failures = 0

    def check(label, got, want_fire, needle=None):
        nonlocal failures
        rc, out = got
        fired = bool(out.strip())
        ok = (fired == want_fire) and rc == 0
        if ok and needle:
            ok = needle in out
        if not ok:
            print(f"FAIL {label}: fired={fired} want={want_fire} rc={rc}\n{out[:400]}")
            failures += 1
        else:
            print(f"OK   {label}")

    with tempfile.TemporaryDirectory() as tmp:
        clone = build(tmp, behind=3)
        s = clone / "scripts" / "check-pr-fully-clean.py"
        # FIRES
        check("a behind checkout warns",
              run(f"python3 {s} 811 -R o/r"), True, "3 commit(s) behind")
        check("the message names the checkout",
              run(f"python3 {s} 811"), True, str(clone))
        check("warns mid-pipeline",
              run(f"python3 {s} 811 | tail -5"), True)
        # A second deciding script, to prove the list is consulted rather
        # than one name being hard-coded.
        (clone / "scripts" / "pr-overlap.py").write_text("x")
        check("a second deciding script warns too",
              run(f"python3 {clone}/scripts/pr-overlap.py -R o/r"), True)
        # QUIET
        check("a bare name with no path is quiet",
              run("python3 check-pr-fully-clean.py 811"), False)
        check("an unrelated script is quiet",
              run(f"python3 {clone}/scripts/some-other-thing.py"), False)
        check("a non-Bash tool is quiet",
              guard_non_bash(f"python3 {s} 811 -R o/r"), False)

    with tempfile.TemporaryDirectory() as tmp:
        clone = build(tmp, behind=0)
        s = clone / "scripts" / "check-pr-fully-clean.py"
        check("a current checkout is quiet",
              run(f"python3 {s} 811"), False)

    with tempfile.TemporaryDirectory() as tmp:
        clone = build(tmp, behind=0, with_remote=False)
        s = clone / "scripts" / "check-pr-fully-clean.py"
        check("a repo with no origin is quiet",
              run(f"python3 {s} 811"), False)

    # A non-default default branch must not produce a bogus warning: the
    # branch name is derived from origin/HEAD, never assumed to be `main`.
    with tempfile.TemporaryDirectory() as tmp:
        clone = build(tmp, behind=0, default="trunk")
        s = clone / "scripts" / "check-pr-fully-clean.py"
        check("a repo whose default is not main is quiet",
              run(f"python3 {s} 811"), False)

    with tempfile.TemporaryDirectory() as tmp:
        clone = build(tmp, behind=2, default="trunk")
        s = clone / "scripts" / "check-pr-fully-clean.py"
        check("a behind non-main default still warns",
              run(f"python3 {s} 811"), True, "origin/trunk")

    check("a path that does not exist is quiet",
          run("python3 /nonexistent/dir/scripts/check-pr-fully-clean.py 1"), False)
    check("malformed payload is quiet", (run_malformed()), False)

    if failures:
        print(f"\n{failures} case(s) failed")
        return 1
    print("\nAll stale-instrument-checkout cases passed.")
    return 0


def guard_non_bash(command="python3 x"):
    # The command must be one that WOULD fire under Bash, or this case passes
    # for the wrong reason and the tool gate is unpinned (caught by mutation).
    payload = {"tool_name": "Read", "tool_input": {"command": command}}
    buf = io.StringIO()
    stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        with redirect_stderr(buf):
            rc = guard.main()
    finally:
        sys.stdin = stdin
    return rc, buf.getvalue()


def run_malformed():
    buf = io.StringIO()
    stdin = sys.stdin
    sys.stdin = io.StringIO("not json{")
    try:
        with redirect_stderr(buf):
            rc = guard.main()
    finally:
        sys.stdin = stdin
    return rc, buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
