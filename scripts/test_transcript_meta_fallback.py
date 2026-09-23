#!/usr/bin/env python3
"""Pins the degraded-import message every ai-config#3860 hook prints when
`scripts/lib/transcript_meta.py` cannot be loaded.

shared/principles/fail-fast.md: "make it explicit and observable: message
the degradation." Each of the six hooks fixed for ai-config#3860 falls back
to a permissive `is_skill_load_meta(entry): return False` on import failure.
Silently, that reintroduces the ORIGINAL #3860 bug with no signal at all --
a stale consumer copy lacking scripts/lib/transcript_meta.py degrades with
nothing to notice it by.

This test forces the import to fail (by temporarily corrupting the real
`scripts/lib/transcript_meta.py` with a stub that raises on import, restored
in a `finally` block even if the test itself errors) and, for each of the six
hooks, checks two things:

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
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
HOOKS = os.path.join(ROOT, "hooks")
REAL_MODULE = os.path.join(ROOT, "scripts", "lib", "transcript_meta.py")

failures = []


def check(label, condition):
    if condition:
        print(f"PASS: {label}")
    else:
        failures.append(label)
        print(f"FAIL: {label}")


def write_transcript(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return path


def run(hook_name, payload, extra_env=None):
    """Run one hook with an ISOLATED fire-once-sentinel temp directory.

    Several of these hooks dedupe on a sentinel file written under
    `tempfile.gettempdir()`, keyed by the message text (see
    `require-stopping-point.py` and `remind-ums-on-scrutiny.py`). Without a
    fresh TMPDIR/TEMP/TMP per call, the baseline run's sentinel silently
    suppresses the corrupted-import run that immediately follows with the
    SAME transcript text, which is a collision in this test's own harness,
    not evidence about the fix.
    """
    hook_path = os.path.join(HOOKS, hook_name)
    fresh = tempfile.mkdtemp(prefix="tmeta-fallback-")
    env = dict(os.environ)
    for var in ("TMPDIR", "TEMP", "TMP"):
        env[var] = fresh
    if extra_env:
        env.update(extra_env)
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

    with open(REAL_MODULE, "r", encoding="utf-8") as f:
        real_source = f.read()

    # Baseline: capture each hook's stdout/stderr with the REAL module in
    # place, so the corrupted run can be compared against it rather than
    # against an assumption of what "unchanged" means.
    baseline = {}
    for hook_name, stem, make_payload, transcript_lines in CASES:
        path = write_transcript(transcript_lines)
        try:
            proc = run(hook_name, make_payload(path))
        finally:
            os.unlink(path)
        baseline[hook_name] = proc.stdout

    try:
        with open(REAL_MODULE, "w", encoding="utf-8") as f:
            f.write(STUB_SOURCE)

        for hook_name, stem, make_payload, transcript_lines in CASES:
            path = write_transcript(transcript_lines)
            try:
                proc = run(hook_name, make_payload(path))
            finally:
                os.unlink(path)

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
        with open(REAL_MODULE, "w", encoding="utf-8") as f:
            f.write(real_source)

    # Confirm restoration actually took, not just that the finally ran.
    with open(REAL_MODULE, "r", encoding="utf-8") as f:
        check("scripts/lib/transcript_meta.py restored byte-for-byte",
              f.read() == real_source)

    print(f"\n{len(CASES) * 5 - len(failures)} passed, {len(failures)} failed")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
