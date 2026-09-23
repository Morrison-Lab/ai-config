#!/usr/bin/env python3
"""Pins the degraded-import message every ai-config#3860 hook prints when
`scripts/lib/transcript_meta.py` cannot be loaded.

shared/principles/fail-fast.md: "make it explicit and observable: message
the degradation." Each of the six hooks fixed for ai-config#3860 falls back
to a permissive `is_skill_load_meta(entry): return False` on import failure.
Silently, that reintroduces the ORIGINAL #3860 bug with no signal at all --
a stale consumer copy lacking scripts/lib/transcript_meta.py degrades with
nothing to notice it by.

WHY THIS TEST NEVER WRITES THE REAL TRACKED FILE
--------------------------------------------------
An earlier revision corrupted the real `scripts/lib/transcript_meta.py` IN
PLACE and relied on a `finally` block to restore it. That is unsafe on its
own terms: a SIGKILL or a CI force-cancel skips `finally` entirely, leaving
the real module a raising stub in that checkout -- the exact silent
degradation this whole PR exists to prevent, now caused by the PR's own
test. It also races a concurrent test run or any live hook firing from the
same checkout while the corrupted content sits on disk.

So this test never opens the real file for writing. Instead, for each run
it copies `hooks/` and `scripts/lib/` into a fresh `tempfile.mkdtemp()`
tree and corrupts ONLY the COPY's `transcript_meta.py`. This works because
each hook resolves its own `scripts/lib` path from `os.path.realpath(
__file__)` at runtime (see e.g. `warn-stale-issue-edit.py`'s `HERE`/`ROOT`/
`_LIB` computation) -- running the COPIED hook file makes it compute `_LIB`
relative to the copy, so `from transcript_meta import ...` finds the
copy's (corrupted) module. An environment override such as PYTHONPATH
cannot substitute for this: every hook's own `sys.path.insert(0, _LIB)`
runs at import time and takes priority over whatever PYTHONPATH already
put on `sys.path` at interpreter startup.

After every run (success, failure, or exception) the test asserts the REAL
`scripts/lib/transcript_meta.py`'s bytes and mtime are byte-for-byte and
timestamp-for-timestamp unchanged, and cleans up the temp tree -- a leaked
temp directory is harmless, an altered tracked file is not.

For each of the six hooks this checks two things:

  1. stderr names the hook and the import error, matching the style
     `hooks/no-clobbering-push.py` already uses for a failed
     `scripts/lib/shellcmd.py` import.
  2. stdout is UNCHANGED by the corruption -- still whatever valid JSON (or
     nothing) the hook would emit for that payload, never a traceback.

Lives under scripts/ rather than hooks/test-*.py because it does not fit the
one-test-one-subject convention scripts/test_hooks.py enforces (a
`hooks/test-<name>.py` takes `hooks/<name>.py` as its sole subject via
argv[1]); this test instead targets all six hooks that import the shared
predicate, so it is wired into validate.yml directly, the same way
scripts/test_fences.py tests scripts/lib/fences.py.

Run: python3 scripts/test_transcript_meta_fallback.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
REAL_HOOKS_DIR = os.path.join(ROOT, "hooks")
REAL_LIB_DIR = os.path.join(ROOT, "scripts", "lib")
REAL_MODULE = os.path.join(REAL_LIB_DIR, "transcript_meta.py")

failures = []
total_checks = 0


def check(label, condition):
    global total_checks
    total_checks += 1
    if condition:
        print(f"PASS: {label}")
    else:
        failures.append(label)
        print(f"FAIL: {label}")


def write_transcript(dirpath, lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=dirpath)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return path


def run(hooks_dir, hook_name, payload, tmproot):
    """Run one COPIED hook with an ISOLATED fire-once-sentinel temp directory.

    Several of these hooks dedupe on a sentinel file written under
    `tempfile.gettempdir()`, keyed by the message text (see
    `require-stopping-point.py` and `remind-ums-on-scrutiny.py`). Without a
    fresh TMPDIR/TEMP/TMP per call, a baseline run's sentinel would silently
    suppress a later run of the same transcript text, which is a collision
    in this test's own harness, not evidence about the fix.
    """
    hook_path = os.path.join(hooks_dir, hook_name)
    fresh = tempfile.mkdtemp(prefix="tmeta-fallback-sentinel-", dir=tmproot)
    env = dict(os.environ)
    for var in ("TMPDIR", "TEMP", "TMP"):
        env[var] = fresh
    proc = subprocess.run(
        [sys.executable, hook_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc


# Six (hook filename, stem used in its own stderr message, payload) triples.
# The payload for each is whatever minimally exercises the code path that
# calls `is_skill_load_meta` -- it does not need to hit the isMeta branch
# itself, only to run far enough that the import already happened.
NAMING_ISSUE = {
    "type": "user",
    "message": {"content": [{
        "type": "text",
        "text": "Implement https://github.com/Morrison-Lab/ai-config/issues/2282.",
    }]},
}
BASH_CMD_REPLY = {
    "type": "assistant",
    "message": {"content": [{
        "type": "text",
        "text": "```bash\ncd foo && git status\n```",
    }]},
}
BRIEF_PS = {
    "type": "attachment",
    "rendered": [{"content": (
        "<system-reminder>\n# Environment\n - Shell: PowerShell (primary); "
        "Bash tool also available\n</system-reminder>"
    )}],
}
MISSING_DECL_REPLY = {
    "type": "assistant",
    "message": {"content": [{"type": "text", "text": "Done, no declaration here."}]},
}
QUESTION = {
    "type": "user",
    "message": {"content": [{"type": "text", "text": "are you sure about that?"}]},
}
WRONG_CORRECTION = {
    "type": "assistant",
    "message": {"content": [{
        "type": "text",
        "text": "You're right to ask -- I was wrong, the count is 12 not 9.",
    }]},
}
PROMISE_NO_MECHANISM = {
    "type": "assistant",
    "message": {"content": [{
        "type": "text",
        "text": "Going forward, I'll run the checker before reporting status.",
    }]},
}
DATE_CALL = {
    "type": "assistant",
    "message": {"content": [{
        "type": "tool_use",
        "input": {"command": "TZ=America/Los_Angeles date \"+%Y-%m-%d %H:%M %Z\""},
    }]},
}
UNMEASURED_CLAIM = {
    "type": "assistant",
    "message": {"content": [{"type": "text", "text": "Recap: 23:59 PDT"}]},
}

CASES = [
    (
        "warn-stale-issue-edit.py",
        "warn-stale-issue-edit",
        lambda path: {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.py", "content": "y"},
            "transcript_path": path,
            "hook_event_name": "PreToolUse",
        },
        [NAMING_ISSUE],
    ),
    (
        "warn-bash-command-for-powershell-user.py",
        "warn-bash-command-for-powershell-user",
        lambda path: {"transcript_path": path},
        [BRIEF_PS, BASH_CMD_REPLY],
    ),
    (
        "require-stopping-point.py",
        "require-stopping-point",
        lambda path: {"transcript_path": path},
        [MISSING_DECL_REPLY],
    ),
    (
        "remind-ums-on-scrutiny.py",
        "remind-ums-on-scrutiny",
        lambda path: {"transcript_path": path},
        [QUESTION, WRONG_CORRECTION],
    ),
    (
        "no-empty-promise.py",
        "no-empty-promise",
        lambda path: {"transcript_path": path},
        [PROMISE_NO_MECHANISM],
    ),
    (
        "no-unmeasured-clock-claim.py",
        "no-unmeasured-clock-claim",
        lambda path: {"transcript_path": path},
        [DATE_CALL, UNMEASURED_CLAIM],
    ),
]


def is_valid_stdout(stdout: str) -> bool:
    """True unless `stdout` looks like an uncaught-exception crash.

    Not every hook here emits JSON on stdout -- `remind-ums-on-scrutiny.py`
    prints a plain `[hook: ...]` text line as its UserPromptSubmit
    `additionalContext`, while others emit `{"decision": ...}` JSON or
    nothing at all. The one shape common to all of them, and the one a
    broken import could actually produce if the fallback def were missing
    or wrong, is a Python traceback leaking onto stdout instead of stderr.
    """
    return "Traceback (most recent call last)" not in stdout


STUB_SOURCE = (
    "raise ImportError('transcript_meta stub: forced failure for "
    "test_transcript_meta_fallback.py')\n"
)


def main() -> int:
    if not os.path.isfile(REAL_MODULE):
        print(f"FATAL: {REAL_MODULE} not found", file=sys.stderr)
        return 1

    # Snapshot the REAL tracked file's identity before touching anything, so
    # the end-of-run assertion has something to compare against. This file
    # is read-only for the whole test -- never opened for writing.
    real_stat = os.stat(REAL_MODULE)
    with open(REAL_MODULE, "rb") as f:
        real_bytes = f.read()

    tmproot = tempfile.mkdtemp(prefix="transcript-meta-fallback-")
    try:
        copied_hooks = os.path.join(tmproot, "hooks")
        copied_lib = os.path.join(tmproot, "scripts", "lib")
        shutil.copytree(
            REAL_HOOKS_DIR, copied_hooks,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test-*.py"),
        )
        os.makedirs(os.path.dirname(copied_lib), exist_ok=True)
        shutil.copytree(
            REAL_LIB_DIR, copied_lib,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        # Baseline: capture each hook's stdout/stderr from the PRISTINE copy,
        # so the corrupted run can be compared against it rather than against
        # an assumption of what "unchanged" means. Both phases run from the
        # copy, so the comparison is copy-vs-corrupted-copy, not
        # real-tree-vs-copy (which could differ for unrelated reasons, e.g.
        # a repo file this test's copy does not include).
        baseline = {}
        for hook_name, stem, make_payload, transcript_lines in CASES:
            path = write_transcript(tmproot, transcript_lines)
            proc = run(copied_hooks, hook_name, make_payload(path), tmproot)
            baseline[hook_name] = proc.stdout

        copied_module = os.path.join(copied_lib, "transcript_meta.py")
        with open(copied_module, "w", encoding="utf-8") as f:
            f.write(STUB_SOURCE)

        for hook_name, stem, make_payload, transcript_lines in CASES:
            path = write_transcript(tmproot, transcript_lines)
            proc = run(copied_hooks, hook_name, make_payload(path), tmproot)

            check(
                f"{hook_name}: exits 0 even with a broken transcript_meta import",
                proc.returncode == 0,
            )
            check(
                f"{hook_name}: stderr names the hook",
                f"{stem}: cannot load scripts/lib/transcript_meta.py" in proc.stderr,
            )
            check(
                f"{hook_name}: stderr includes the import error text",
                "transcript_meta stub: forced failure" in proc.stderr,
            )
            check(
                f"{hook_name}: stdout is still well-formed (no traceback)",
                is_valid_stdout(proc.stdout),
            )
            check(
                f"{hook_name}: stdout is unchanged from the working-import baseline",
                proc.stdout == baseline[hook_name],
            )
    finally:
        shutil.rmtree(tmproot, ignore_errors=True)

    # The real tracked file was opened read-only above and never again --
    # confirm neither its bytes nor its mtime moved, rather than trusting
    # that "we never wrote to it" from reading the code alone.
    after_stat = os.stat(REAL_MODULE)
    with open(REAL_MODULE, "rb") as f:
        after_bytes = f.read()
    check(
        "the real scripts/lib/transcript_meta.py bytes are untouched",
        after_bytes == real_bytes,
    )
    check(
        "the real scripts/lib/transcript_meta.py mtime is untouched",
        after_stat.st_mtime_ns == real_stat.st_mtime_ns,
    )

    print(f"\n{total_checks - len(failures)} passed, {len(failures)} failed")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
