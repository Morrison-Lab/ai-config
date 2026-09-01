"""Test the flag-unmeasured-timestamp guard.

The positive cases are the 2026-09-01 measurement (ai-config#2900, #2903),
verbatim in shape: a claim comment stamped with a Pacific clock time no
reading in the turn produced, posted through `gh` and through the MCP
comment tools.

The negative cases decide whether the guard survives. A body that quotes a
`date` run in this turn, or the harness's own just-injected reading, is
exactly what the rule prescribes and must not fire; a body with no Pacific
marker is not a claim about the present; a non-comment tool is out of scope.

Run: python3 hooks/test-flag-unmeasured-timestamp.py hooks/flag-unmeasured-timestamp.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

# Payloads a fire produced that the harness would discard; see run().
SHAPE_ERRORS = []

DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "TZ=America/Los_Angeles date \"+%Y-%m-%d %H:%M %Z\""}}]}}
PWSH_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "powershell -c \"[System.TimeZoneInfo]::"
                   "ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Pacific "
                   "Standard Time')\""}}]}}
# Work that is not a clock read, however much it looks like one.
GIT_LOG = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "git log --format='%h %cd' --date=format-local:'%H:%M'"}}]}}
UPDATE_CMD = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "sudo apt-get update"}}]}}

# A real prompt record, which is what opens a turn.
PROMPT = {"type": "user", "message": {"content": "claim wai#96 and start"}}
NEXT_TURN = {"type": "user", "content": "and the other one?"}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def attach_clock(stamp, date="2026-09-01", zone="PDT"):
    """The harness's injected reading, as it arrives in a live transcript."""
    line = (f"Current time -- local: {date} {stamp} {zone} | "
            f"UTC: 2026-09-01T19:02:00Z")
    return {"type": "attachment", "attachment": {
        "hookEvent": "UserPromptSubmit",
        "hookName": "inject-local-time.sh",
        "content": line + "\nUse the local value verbatim in recaps.",
        "stdout": line + "\n",
        "exitCode": 0}}


MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def mcp(tool, body):
    return {"tool_name": tool, "tool_input": {"owner": "d-morrison", "repo": "wai",
                                              "issue_number": 96, "body": body}}


CLAIM = ("Claiming this issue (Claude Code, remote session) -- 12:47 PT.\n\n"
         + MARKER)

# (transcript events, payload, should_fire, label)
CASES = [
    # --- the measurement, and its shape --------------------------------------
    ([PROMPT, say("Looking at the issue."), GIT_LOG],
     bash(f'gh issue comment 96 -R d-morrison/wai --body "{CLAIM}"'), True,
     "#2900: a claim comment stamped with no date call in the turn warns"),
    ([PROMPT, say("Claiming.")],
     mcp("mcp__github__add_issue_comment", CLAIM), True,
     "#2900: the same stamp through mcp__github__add_issue_comment warns"),
    ([PROMPT],
     mcp("mcp__github__add_reply_to_pull_request_comment",
         "Addressed in a5591a6 -- 12:58 PT.\n\n" + MARKER), True,
     "a review reply through mcp__github__add_reply_to_pull_request_comment warns"),
    ([PROMPT],
     bash('gh pr comment 81 -R d-morrison/wai --body "Status as of 12:15 PDT: '
          'CI green."'), True,
     "a gh pr comment status stamp warns"),
    ([DATE, say("first"), NEXT_TURN, say("later")],
     bash(f'gh issue comment 96 --body "{CLAIM}"'), True,
     "a date call in an EARLIER turn has expired"),
    ([PROMPT, GIT_LOG],
     bash(f'gh issue comment 96 --body "{CLAIM}"'), True,
     "git log --date=format-local is not a clock read"),
    ([PROMPT, UPDATE_CMD],
     bash(f'gh issue comment 96 --body "{CLAIM}"'), True,
     "apt-get update is not a clock read"),
    ([PROMPT, attach_clock("12:02:00")],
     mcp("mcp__github__add_issue_comment",
         "Claiming -- 12:58 PT.\n\n" + MARKER), True,
     "#2900: a stamp 56 minutes AHEAD of the injected reading warns"),
    ([],
     bash(f'gh issue comment 96 --body "{CLAIM}"'), True,
     "no transcript at all: nothing measured, so the stamp warns"),

    # --- measured, so correct -------------------------------------------------
    ([PROMPT, DATE],
     bash(f'gh issue comment 96 -R d-morrison/wai --body "{CLAIM}"'), False,
     "a date call in this turn discharges"),
    ([PROMPT, say("Checking."), DATE, say("Got it.")],
     mcp("mcp__github__add_issue_comment", CLAIM), False,
     "a date call in this turn discharges the MCP route too"),
    ([PROMPT, PWSH_DATE],
     bash(f'gh issue comment 96 --body "{CLAIM}"'), False,
     "the PowerShell fallback the rule prescribes counts"),
    ([PROMPT, attach_clock("12:44:10")],
     mcp("mcp__github__add_issue_comment",
         "Claiming -- 12:44 PDT.\n\n" + MARKER), False,
     "quoting the harness's just-injected reading is what the rule says to do"),
    ([PROMPT, attach_clock("12:44:10")],
     mcp("mcp__github__add_issue_comment",
         "Merged at 12:21 PT per the merge timestamp.\n\n" + MARKER), False,
     "a time BEHIND the injected reading is a past time read off an artifact"),

    # --- not a claim about the present ----------------------------------------
    ([PROMPT],
     bash('gh issue comment 96 --body "Claiming this issue.\n\n' + MARKER + '"'),
     False, "no stamp at all is silent"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment",
         "Run started 2026-09-01T19:22:50Z; the suite took 14:32."), False,
     "an ISO timestamp and a duration carry no Pacific marker"),
    ([PROMPT],
     mcp("mcp__github__add_issue_comment", "See the 12:47 entry in the log."),
     False, "a bare time with no Pacific marker is not a present-tense claim"),

    # --- out of scope ---------------------------------------------------------
    ([PROMPT],
     {"tool_name": "Read", "tool_input": {"file_path": "notes.md"}}, False,
     "a non-comment tool is silent"),
    ([PROMPT],
     bash('echo "as of 12:47 PDT" > notebook.md'), False,
     "a Bash command that posts no comment is silent"),
    ([PROMPT],
     mcp("mcp__github__create_pull_request", "Opened at 12:47 PT."), False,
     "a non-comment MCP tool is silent"),
    ([PROMPT],
     {"tool_name": "mcp__github__pull_request_review_write",
      "tool_input": {"method": "submit_pending"}}, False,
     "an MCP call with no body is not judged"),
]


def write_transcript(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def run(events, payload, extra_args=()):
    """Run the hook end-to-end; return the parsed stdout payload, or {}.

    A FRESH `TMPDIR` per call, per `test-flag-uncounted-comment-claims.py`'s
    runner: the fire-once sentinel lives in `tempfile.gettempdir()`, and
    several cases below post the same body, so a sentinel written by one
    would silently suppress a later one.
    """
    tpath = write_transcript(events) if events else ""
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(payload, transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        env.pop("ANTIGRAVITY_AGENT", None)
        r = subprocess.run(
            [sys.executable, HOOK, *extra_args], input=json.dumps(full),
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr}"
        assert "permissionDecision" not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return {}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if tpath:
            os.unlink(tpath)


def fired(out):
    """True when the payload carries a warning the harness would surface.

    `bool(out)` alone would score any output as a fire. A warn-only
    PreToolUse hook surfaces through `hookSpecificOutput.additionalContext`
    (to the model) and `systemMessage` (to the user); a payload with neither
    is recorded as a shape error rather than counted as a fire.
    """
    if not out:
        return False
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ctx or not isinstance(out.get("systemMessage"), str):
        SHAPE_ERRORS.append(sorted(out))
        return False
    return True


def check_output_shape():
    """The warning names the stamp and the command to run before restating it."""
    out = run([PROMPT], mcp("mcp__github__add_issue_comment", CLAIM))
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    msg = out.get("systemMessage") or ""
    ok = ("12:47 PT" in ctx and "12:47 PT" in msg
          and 'TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"' in ctx
          and "TZ=America/Los_Angeles date" in msg
          and "\n" not in msg
          and (out.get("hookSpecificOutput") or {}).get("hookEventName") == "PreToolUse")
    print(f"{'ok  ' if ok else 'FAIL'}  the warning names the stamp and the "
          f"clock command, in both additionalContext and a one-line systemMessage")
    return 0 if ok else 1


def check_body_file():
    """A `--body-file` body is read off disk, per the corpus's own convention."""
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w") as fh:
        fh.write(CLAIM)
    try:
        out = run([PROMPT], bash(f"gh pr comment 96 -R d-morrison/wai --body-file {path}"))
    finally:
        os.unlink(path)
    ok = fired(out)
    print(f"{'ok  ' if ok else 'FAIL'}  a --body-file body read off disk warns")
    return 0 if ok else 1


def check_dry_run():
    """--dry-run reports the verdict offline and never writes a sentinel."""
    out = run([PROMPT], mcp("mcp__github__add_issue_comment", CLAIM), ("--dry-run",))
    again = run([PROMPT], mcp("mcp__github__add_issue_comment", CLAIM), ("--dry-run",))
    ok = fired(out) and fired(again)
    quiet = run([PROMPT], bash("git status"), ("--dry-run",))
    ok = ok and quiet == {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    print(f"{'ok  ' if ok else 'FAIL'}  --dry-run warns without a sentinel, and "
          f"reports an empty PreToolUse payload when silent")
    return 0 if ok else 1


def check_sentinel():
    """Once per distinct body: the second identical post in one TMPDIR is silent."""
    tpath = write_transcript([PROMPT])
    tmpdir = tempfile.mkdtemp()
    try:
        full = dict(mcp("mcp__github__add_issue_comment", CLAIM),
                    transcript_path=tpath, cwd=os.getcwd())
        env = dict(os.environ, TMPDIR=tmpdir)
        first = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                               capture_output=True, text=True, env=env).stdout
        second = subprocess.run([sys.executable, HOOK], input=json.dumps(full),
                                capture_output=True, text=True, env=env).stdout
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.unlink(tpath)
    ok = "systemMessage" in first and not second.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  warns once per distinct body")
    return 0 if ok else 1


def check_malformed_stdin():
    r = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True)
    ok = r.returncode == 0 and not r.stdout.strip()
    print(f"{'ok  ' if ok else 'FAIL'}  malformed stdin fails open and silent")
    return 0 if ok else 1


def main():
    failures = 0
    failures += check_output_shape()
    failures += check_body_file()
    failures += check_dry_run()
    failures += check_sentinel()
    failures += check_malformed_stdin()
    case_failures = 0
    for events, payload, want, label in CASES:
        got = fired(run(events, payload))
        ok = got == want
        if not ok:
            case_failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  fire={got!s:5} want={want!s:5}  {label}")
    failures += case_failures
    print(f"\n{len(CASES) - case_failures}/{len(CASES)} cases passed")
    if SHAPE_ERRORS:
        print(f"FAIL  {len(SHAPE_ERRORS)} fire(s) emitted a payload the harness "
              f"would discard: {SHAPE_ERRORS[0]}")
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
