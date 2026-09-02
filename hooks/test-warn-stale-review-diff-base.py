"""Test the warn-stale-review-diff-base hook.

Builds a synthetic transcript per case and feeds the hook a PreToolUse payload
pointing at it. A case is WARN when the hook emits a payload carrying
`additionalContext`, and silent otherwise.

The assertion is on payload SHAPE rather than on `bool(stdout)`: a hook that
printed prose, or that emitted a block-shaped `decision`, would satisfy a
truthiness check while being wrong in opposite directions.

Run:  python3 hooks/test-warn-stale-review-diff-base.py \
          hooks/warn-stale-review-diff-base.py
"""

import json
import os
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]

if not os.path.isfile(HOOK):
    sys.exit(
        f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
        "read as 'silent' on every case and print a perfect pass"
    )


def bash(cmd):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Bash",
                                 "input": {"command": cmd}}]},
    }


NOISE = [bash("ls -la"), bash("git status --short")]
FETCH = [bash("git fetch origin --quiet")]


def run(command, records, tool_name="Bash", tool_input=None):
    """Run the hook against a synthetic transcript; return WARN or silent."""
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    if tool_input is None:
        tool_input = {"command": command}
    payload = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "transcript_path": tpath,
    }
    try:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True, text=True,
        )
    finally:
        os.unlink(tpath)

    if proc.returncode != 0:
        sys.exit(f"FATAL: hook exited {proc.returncode}\n{proc.stderr.strip()}")

    out = proc.stdout.strip()
    if not out:
        return "silent"

    try:
        parsed = json.loads(out)
    except ValueError:
        sys.exit(
            "FATAL: hook emitted non-JSON on stdout. A PreToolUse reminder "
            f"must emit a hookSpecificOutput payload.\n{out}"
        )
    if "decision" in parsed or "permissionDecision" in str(parsed):
        sys.exit(
            "FATAL: hook emitted a decision-shaped payload. This hook must "
            f"only ever add context, never block a tool call.\n{out}"
        )
    ctx = (parsed.get("hookSpecificOutput") or {}).get("additionalContext")
    if not isinstance(ctx, str) or not ctx.strip():
        sys.exit(
            "FATAL: hook emitted a payload with no additionalContext. Output "
            f"that is non-empty but unsurfaced is the failure mode.\n{out}"
        )
    if parsed["hookSpecificOutput"].get("hookEventName") != "PreToolUse":
        sys.exit(f"FATAL: wrong hookEventName in payload.\n{out}")
    return "WARN"


WARN_CASES = [
    ("git diff main...pr-98", NOISE,
     "the measured case: a bare local base in a three-dot review range"),
    ("git diff main..pr-98", NOISE,
     "the two-dot form is exposed the same way"),
    ("git diff develop...HEAD", NOISE,
     "a default branch named something other than main"),
    ("git log main...feature/x --oneline", NOISE,
     "git log takes a range too"),
    ("git merge-base main pr-98 && git diff main...pr-98", NOISE,
     "a merge-base call does not itself resolve the base from a remote"),
    ("git diff main...pr-98", [],
     "an empty transcript is not a fetch"),
    ("git diff --stat main...pr-98", NOISE,
     "an option between the subcommand and the range"),
]

SILENT_CASES = [
    ("git diff origin/main...HEAD", NOISE,
     "a remote-tracking base is the correct form"),
    ("git diff github/main...pr-98", NOISE,
     "the remote is not always named origin"),
    ("git diff main...pr-98", NOISE + FETCH,
     "a fetch earlier in the session discharges the reminder"),
    ("git diff HEAD~1..HEAD", NOISE,
     "a symbolic base cannot go stale"),
    ("git diff 6345e92...pr-98", NOISE,
     "a raw SHA names one commit, not a moving branch"),
    ("git diff v1.2.0...v1.3.0", NOISE,
     "version tags are immutable"),
    ("git diff --cached", NOISE,
     "no range at all"),
    ("git diff DESCRIPTION", NOISE,
     "a pathspec is not a range"),
    ("git rebase main", NOISE,
     "rebase is not a range-reading subcommand"),
    ("echo 'git diff origin/<default-branch>...HEAD'", NOISE,
     "a documentation placeholder must not match"),
    ("cat <<'EOF' > f.md\ngit diff main...pr-98\nEOF", NOISE,
     "a heredoc body is file content, not a command"),
    ("git diff -...HEAD", NOISE,
     "a base with no alphanumeric names no ref -- `-` is in the ref class and "
     "survives dot-stripping, so this is the guard `normalize_base` does NOT "
     "subsume"),
]

BRIEF_WARN = (
    "Review the diff: git diff main...pr-98, applying the repo standards.",
    "an Agent brief carrying the same bare local base",
)
BRIEF_SILENT = (
    "Review the diff: git diff origin/main...pr-98.",
    "an Agent brief with a remote-tracking base",
)

total = wrong = 0
print("--- expected WARN")
for cmd, recs, desc in WARN_CASES:
    verdict = run(cmd, recs)
    total += 1
    wrong += verdict != "WARN"
    print(f"{verdict:<7} {desc}")

print("\n--- expected silent")
for cmd, recs, desc in SILENT_CASES:
    verdict = run(cmd, recs)
    total += 1
    wrong += verdict != "silent"
    print(f"{verdict:<7} {desc}")

print("\n--- Agent briefs")
for prompt, desc, want in ((BRIEF_WARN[0], BRIEF_WARN[1], "WARN"),
                           (BRIEF_SILENT[0], BRIEF_SILENT[1], "silent")):
    verdict = run(None, NOISE, tool_name="Agent",
                  tool_input={"prompt": prompt, "description": "review"})
    total += 1
    wrong += verdict != want
    print(f"{verdict:<7} {desc}")

print("\n--- fail-open")
_fd, _p = tempfile.mkstemp(suffix=".jsonl")
os.close(_fd)
os.unlink(_p)
_proc = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": "git diff main...pr-98"},
                      "transcript_path": _p}),
    capture_output=True, text=True,
)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print(f"{'silent' if _ok else 'WARN':<7} a missing transcript fails open")

_proc = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
total += 1
_ok = _proc.returncode == 0 and not _proc.stdout.strip()
wrong += not _ok
print(f"{'silent' if _ok else 'WARN':<7} unparseable stdin fails open")

print(f"\n{total - wrong}/{total} correct")
sys.exit(1 if wrong else 0)
