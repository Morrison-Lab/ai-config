"""Test the no-unmeasured-clock-claim guard.

Case number one is the reported incident, verbatim: a session that measured the
clock once at start, then printed an extrapolated Pacific time in a later
recap.

The negative cases are what decide whether this guard survives. A recap quoting
the harness's own just-injected reading is CORRECT and must not fire, and
neither must an ISO timestamp read out of an API response, a duration, or a
past time read off a git committer date. A guard that fires on those gets
switched off, and then the real case goes unprotected too.

Run: python3 hooks/test-no-unmeasured-clock-claim.py hooks/no-unmeasured-clock-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "TZ=America/Los_Angeles date \"+%Y-%m-%d %H:%M %Z\""}}]}}
BARE_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "date"}}]}}
PWSH_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "powershell -c \"[System.TimeZoneInfo]::"
                   "ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Pacific "
                   "Standard Time')\""}}]}}
# A date buried mid-pipeline still reads the clock.
CHAINED_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "git log -1 && TZ=America/Los_Angeles date '+%H:%M %Z'"}}]}}

# The harness's own injected reading, which arrives as a bare-string user turn.
HOOK_CLOCK = {"type": "user", "content":
              "UserPromptSubmit hook success: Current time -- local: "
              "2026-08-16 18:55:51 PDT | UTC: 2026-08-17T01:55:51Z"}

# Work that is not a clock read, however much it looks like one.
GIT_LOG = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "git log --format='%h %cd' --date=format-local:'%H:%M'"}}]}}
API_READ = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {
        "command": "gh pr view 629 --json createdAt --jq .createdAt"}}]}}
# `--update` is not the `date` command; the word boundary must not match it.
UPDATE_CMD = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "sudo apt-get update"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


# (events, should_fire, label)
CASES = [
    # --- the incident, and its shape ---
    ([DATE, say("first recap"), say("UPDATE -- 19:24 PDT")], True,
     "the incident: measured once, extrapolated in a later message"),
    ([HOOK_CLOCK, say("first recap"), say("as of 18:52 PDT, three PRs open")], True,
     "session-start hook reading, then an extrapolated time a message later"),
    ([DATE, say("earlier"), say("Session Summary -- 6:40 PM PT")], True,
     "12-hour form with a PT marker"),
    ([say("no clock read at all in this session"), say("now 09:15 PST")], True,
     "no reading anywhere in the transcript"),

    # --- measured, so correct ---
    ([say("earlier"), DATE, say("UPDATE -- 18:30 PDT")], False,
     "clock read in THIS turn, after the previous message"),
    ([say("earlier"), BARE_DATE, say("18:30 PDT")], False,
     "a bare `date` is a clock read"),
    ([say("earlier"), PWSH_DATE, say("18:30 PST")], False,
     "the PowerShell fallback the rule prescribes counts"),
    ([say("earlier"), CHAINED_DATE, say("18:30 PDT")], False,
     "a date chained after another command still reads the clock"),
    ([say("earlier"), HOOK_CLOCK, say("18:55 PDT, as the hook reports")], False,
     "quoting the harness's just-injected reading is exactly what the rule says to do"),

    # --- not a claim about the present ---
    ([DATE, say("earlier"), say("run started 2026-08-17T01:22:50Z")], False,
     "an ISO/UTC timestamp from an API response is reported data"),
    ([DATE, say("earlier"), say("the suite took 14:32 to run")], False,
     "a duration carries no Pacific marker"),
    ([DATE, say("earlier"), GIT_LOG, say("committed at 18:19 per the git log")], False,
     "a past time read off a committer date, with the read in this turn"),
    ([DATE, say("earlier"), say("checks: 17 pass, 2 pending")], False,
     "no time of day at all"),
    ([DATE, say("earlier"), say("see the 18:30 entry")], False,
     "a bare time with no Pacific marker is not a present-tense claim"),

    # --- the near-miss that would make this guard misfire ---
    ([say("earlier"), UPDATE_CMD, say("18:30 PDT")], True,
     "`apt-get update` is NOT a clock read -- the word boundary must not match it"),
    ([DATE, say("18:30 PDT in the same turn as the read")], False,
     "read and claim in one turn, with no previous assistant message"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(".claude-clock-claim-"):
            try:
                os.remove(os.path.join(tempfile.gettempdir(), f))
            except OSError:
                pass
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
    ).stdout.strip()
    os.remove(path)
    return bool(out)


def main():
    failures = 0
    for events, want, label in CASES:
        got = run(events)
        ok = got == want
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  fire={got!s:5} want={want!s:5}  {label}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
