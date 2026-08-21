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

# Payloads a fire produced that the harness would discard; see run().
SHAPE_ERRORS = []

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

def hook_clock(stamp, date="2026-08-21"):
    """The injected reading, at a chosen time."""
    return {"type": "user", "content":
            f"UserPromptSubmit hook success: Current time -- local: "
            f"{date} {stamp} PDT | UTC: 2026-08-21T22:00:00Z"}


# The injected line with no parseable timestamp -- the value capture must fall
# back to counting it as a read rather than treating it as no read at all.
HOOK_CLOCK_UNPARSEABLE = {"type": "user", "content":
                          "UserPromptSubmit hook success: Current time -- "
                          "local: (unavailable)"}

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

    # --- ai-config#1848: the reading is present, and the claim departs from
    #     it. The whole point of capturing the value rather than the position.
    ([hook_clock("14:48:23"), say("as of 15:22 PDT, three PRs open")], True,
     "#1848 incident: claim 34 min AHEAD of the injected reading, same turn"),
    ([hook_clock("15:02:20"), say("as of 14:20 PDT")], True,
     "claim well behind the injected reading has expired"),
    ([hook_clock("14:48:23"), say("as of 14:48 PDT")], False,
     "claim equal to the injected reading is quoting it"),
    ([hook_clock("14:48:50"), say("as of 14:49 PDT")], False,
     "rounding seconds up stays within tolerance"),
    ([hook_clock("23:58:00"), say("as of 00:24 PDT")], True,
     "wraparound: past midnight is still ahead, not 23 hours behind"),
    ([hook_clock("23:59:30"), say("as of 00:00 PDT")], False,
     "wraparound within tolerance does not fire"),
    ([hook_clock("14:48:23"), DATE, say("as of 15:22 PDT")], False,
     "a `date` run in this turn discharges even when a stale reading exists"),
    ([HOOK_CLOCK_UNPARSEABLE, say("as of 15:22 PDT")], False,
     "an injected line with no readable value falls back to counting as a read"),
    ([hook_clock("14:48:23"), say("first recap"), say("as of 15:22 PDT")], True,
     "a departing claim fires from a later message too"),

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
    if not out:
        return False
    # `bool(out)` alone would score any output as a fire, including output the
    # harness discards. A `Stop` hook's `reason` is read only alongside
    # `"decision": "block"`, so a warn-only hook emitting `reason` by itself is
    # a silent no-op -- valid JSON that reaches nobody. Requiring the field
    # that actually surfaces is what makes a "fires" result mean the warning
    # was delivered. (ai-config#1566 review round 1: the hook shipped with
    # `reason` and these tests passed anyway, because they only asked whether
    # anything was printed.)
    payload = json.loads(out)
    surfaced = payload.get("systemMessage") or (
        payload.get("decision") == "block" and payload.get("reason"))
    if not surfaced:
        # Recorded rather than raised: an assert here aborts the matrix at the
        # first fire case and masks every case after it, which is the
        # early-abort failure the corpus warns about. The run still fails --
        # main() reports SHAPE_ERRORS -- and the remaining cases still report.
        SHAPE_ERRORS.append(sorted(payload))
    return True


def check_output_shape():
    """The finding from review round 1, as its own explicit case.

    Kept separate from CASES because it asserts the *shape* of the payload
    rather than whether the guard fired, and because a reader scanning the
    matrix should see it named.
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in (DATE, say("earlier"), say("UPDATE -- 19:24 PDT")):
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
    payload = json.loads(out) if out else {}
    ok = bool(payload.get("systemMessage"))
    print(f"{'ok  ' if ok else 'FAIL'}  "
          f"payload keys={sorted(payload)}  "
          "the warning is emitted in a field the harness surfaces")
    return 0 if ok else 1


def main():
    failures = check_output_shape()
    for events, want, label in CASES:
        got = run(events)
        ok = got == want
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'FAIL'}  fire={got!s:5} want={want!s:5}  {label}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    if SHAPE_ERRORS:
        print(f"FAIL  {len(SHAPE_ERRORS)} fire(s) emitted a payload the harness "
              f"would discard: {SHAPE_ERRORS[0]}")
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
