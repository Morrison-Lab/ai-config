#!/usr/bin/env python3
"""Run every hook's own test suite, so the guards in `hooks/` are enforced.

The hooks in `hooks/` each ship a `test-<name>.py` beside a `<name>.py`, but
those tests ran nowhere: `.pre-commit-config.yaml` and `validate.yml` invoke
`scripts/test_*.py` by name and never reach into `hooks/`. So a guard could
regress -- start blocking a message it should pass, stop catching the case it
exists for -- and no check would notice. That is the gap ai-config#1065's
"algorithmatize whenever possible" points at, one level up: the instruments
that enforce the corpus's rules were themselves unverified.

This is the bridge. It discovers each `hooks/test-*.py`, pairs it with its
subject `hooks/<name>.py` (the convention every hook test already uses, taking
the subject as argv[1]), runs it, and fails if any case fails. A test with no
matching subject is itself a failure -- a renamed hook that orphaned its test
is exactly the drift this should catch.

Run: python3 scripts/test_hooks.py
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")


def pairs():
    """Yield (test_path, subject_path) for each hooks/test-*.py."""
    for test_path in sorted(glob.glob(os.path.join(HOOKS, "test-*.py"))):
        subject = os.path.join(HOOKS, os.path.basename(test_path)[len("test-"):])
        yield test_path, subject


def main() -> int:
    found = list(pairs())
    if not found:
        print("no hooks/test-*.py found -- nothing to run")
        return 1

    failures = 0
    for test_path, subject in found:
        rel_test = os.path.relpath(test_path, ROOT)
        rel_subj = os.path.relpath(subject, ROOT)
        if not os.path.isfile(subject):
            print(f"FAIL: {rel_test} has no subject at {rel_subj}")
            failures += 1
            continue
        proc = subprocess.run(
            [sys.executable, test_path, subject],
            capture_output=True, text=True,
        )
        tail = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
        if proc.returncode == 0:
            print(f"PASS: {rel_test} -- {tail}")
        else:
            print(f"FAIL: {rel_test} (exit {proc.returncode})")
            # Surface the child's own output so CI logs show which case failed.
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
            failures += 1

    print(f"\n{len(found) - failures}/{len(found)} hook test suites passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
