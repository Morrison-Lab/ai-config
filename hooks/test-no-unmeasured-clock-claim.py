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

# This hook's own source (or its tests) echoed into a tool_result. It quotes
# the marker, so it must not supply a VALUE -- reading the file would otherwise
# inject a fabricated reading. See shared/writing/examples-are-scanned.md.
HOOK_SOURCE_READ = {"type": "assistant", "message": {"content": [
    {"type": "tool_result", "content":
     "RX_HOOK_CLOCK = ... # Current time -- local: 2026-08-21 15:02:20 PDT"}]}}

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


# A plain user prompt, carrying no reading. It is what separates one turn from
# the next, and several cases below need it explicitly: an assistant turn
# normally emits narration, tool calls, and THEN the recap as separate
# messages, so consecutive `say()`s are one turn rather than two. Writing "a
# later message" as two bare `say()`s modelled a turn boundary that is not
# there, and keying the guard's window on it is what made it fire on ordinary
# recaps (ai-config#1917). Where a case means "a later turn", it must say so.
NEXT_TURN = {"type": "user", "content": "and what about the other one?"}


# The harness's injected reading as it ACTUALLY arrives, copied from a live
# transcript (2026-08-22). It is not a user turn: it is its own record, type
# "attachment", carrying the text under `attachment.content` /
# `attachment.stdout`, with neither a `message` nor a top-level `content`. It
# is emitted AFTER the prompt record it belongs to.
#
# The earlier fixtures modelled it as a bare-string user turn, which is why
# the carve-out looked covered while being inert in practice: `measured`
# stayed None however recently the harness had supplied a real value.
def attach_clock(stamp, date="2026-08-21", zone="PDT"):
    line = (f"Current time -- local: {date} {stamp} {zone} | "
            f"UTC: 2026-08-22T04:30:36Z")
    return {"type": "attachment", "attachment": {
        "hookEvent": "UserPromptSubmit",
        "hookName": "inject-local-time.sh",
        "content": line + "\nUse the local value verbatim in recaps.",
        "stdout": line + "\n",
        "exitCode": 0}}


# A real prompt record, and the assorted non-user records a transcript
# interleaves around it. None of these may advance the turn boundary past the
# reading that arrives beside them.
PROMPT = {"type": "user", "message": {"content": "is this intended behavior?"}}
TRANSCRIPT_NOISE = [
    {"type": "last-prompt", "content": "is this intended behavior?"},
    {"type": "custom-title", "content": "session title"},
]


# (events, should_fire, label)
CASES = [
    # --- ai-config#1917, part two: the injected reading is an ATTACHMENT ---
    #     Verified against a live transcript. Reading only user turns made the
    #     carve-out inert, so the guard fired on precisely the case the rule
    #     tells you to trust. The noise records are included because they sit
    #     between the reading and the recap in a real transcript.
    ([PROMPT, attach_clock("21:30:00")] + TRANSCRIPT_NOISE +
     [say("Looking into it."), GIT_LOG, say("Recap: 21:30 PDT")], False,
     "#1917: an attached reading discharges, with narration and noise after it"),
    ([PROMPT, attach_clock("21:30:00")] + TRANSCRIPT_NOISE +
     [say("Recap: 23:59 PDT")], True,
     "#1917: a claim ahead of the ATTACHED reading still fires"),
    ([PROMPT, attach_clock("21:30:00"), say("first recap"), NEXT_TURN,
      say("Recap: 21:30 PDT")], True,
     "#1917: an attached reading from an earlier turn has still expired"),

    # --- ai-config#1917: the window must start where the USER spoke ---
    #     An assistant turn emits narration, then tool calls, then the recap.
    #     Keying the window on the previous assistant TEXT BLOCK put the
    #     boundary inside the current turn, expiring a reading taken at its
    #     top -- so the guard fired on ordinary recaps, and even on a turn
    #     that ran `date` itself. Each of these is that shape.
    ([hook_clock("21:30:00"), say("Looking into it."), GIT_LOG,
      say("Stopping Point: clean, as of 21:30 PDT")], False,
     "#1917: narration before the recap must not expire the injected reading"),
    ([hook_clock("21:30:00"), say("Checking."), GIT_LOG, say("Found it."),
      GIT_LOG, say("Recap: 21:30 PDT")], False,
     "#1917: two narrations before the recap, same turn"),
    ([hook_clock("21:30:00"), DATE, say("Got it."), say("Recap: 21:31 PDT")],
     False,
     "#1917: an explicit `date` THIS turn discharges even with narration after"),

    # --- the incident, and its shape ---
    ([DATE, say("first recap"), NEXT_TURN, say("UPDATE -- 19:24 PDT")], True,
     "the incident: measured once, extrapolated in a later message"),
    ([HOOK_CLOCK, say("first recap"), NEXT_TURN,
      say("as of 18:52 PDT, three PRs open")], True,
     "session-start hook reading, then an extrapolated time a message later"),
    ([DATE, say("earlier"), NEXT_TURN, say("Session Summary -- 6:40 PM PT")], True,
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
    ([hook_clock("15:02:20"), say("as of 14:20 PDT")], False,
     "a time BEHIND the reading is not fired on -- a past time read off an "
     "artifact is prescribed behavior and is indistinguishable by value"),
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
    ([hook_clock("14:48:23"), say("first recap"), NEXT_TURN,
      say("as of 15:22 PDT")], True,
     "a departing claim fires from a later message too"),

    # --- review round 1 on #1850: the three regressions the value
    #     comparison introduced, each traced by the reviewer ---
    ([hook_clock("14:48:23"), say("first recap"), NEXT_TURN,
      say("as of 14:48 PDT")], True,
     "a STALE reading must not discharge by numeric proximity -- that is the "
     "#1848 bug in a new shape"),
    ([hook_clock("08:18:00"),
      say("Scheduled. I'll check back at 08:22 PT (~4 min).")], False,
     "CLAUDE.md's own prescribed scheduled-check-in sentence states a future "
     "time and must not fire"),
    ([hook_clock("15:02:20"),
      say("The next wakeup fires at 15:30 PT.")], False,
     "a wakeup time is ahead of the clock by design, not by invention"),
    ([hook_clock("14:48:23"), HOOK_SOURCE_READ, say("as of 14:48 PDT")], False,
     "reading this hook's source must not poison the measured value"),
    ([hook_clock("14:48:23"), HOOK_SOURCE_READ, say("as of 15:02 PDT")], True,
     "and must not let an invented time near the poisoned value pass either"),

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
        for e in (DATE, say("earlier"), NEXT_TURN,
                  say("UPDATE -- 19:24 PDT")):
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
