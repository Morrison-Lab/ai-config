#!/usr/bin/env python3
"""Stop-hook guard: catch stating a local clock time nobody measured.

`CLAUDE.md`'s "Timestamp recaps in local time" already requires running the
clock fresh for every recap, and says why: "Each reading expires immediately:
run the command fresh for every recap rather than extrapolating elapsed time
from a prior reading."

The rule is consulted at read time and broken at composition time, which is why
re-reading it does not reach the moment it breaks. A recap's timestamp is
written last, in a message otherwise full of measured facts, and the session
usually *did* measure the clock once -- at session start, from the
`UserPromptSubmit` hook. That single honest reading is precisely what licenses
the invented one: the memory of having consulted a clock obscures that the
measurement expired, so an extrapolated time feels remembered rather than
guessed. `CLAUDE.md` names that mechanism outright.

The condition is exactly decidable from the transcript, which is what makes
this a hook rather than another sentence in the rule:

    message states a Pacific clock time  AND  no clock read since the current
    turn began

What counts as a clock read is deliberately broad -- any `date` invocation, the
PowerShell fallback the rule prescribes for Git Bash, or the `UserPromptSubmit`
hook line that carries "Current time -- local:". The last one matters: when the
harness has just injected a real reading, quoting it is correct and must not
trip this.

Deliberately narrow on the claim side. It fires only on a time carrying an
explicit Pacific marker (`PDT`/`PST`/`PT`), because that is the form a recap
uses to assert "now". An ISO/UTC timestamp read out of an API response, a
duration, and a time inside a quoted log line are all left alone -- those are
reported data rather than a claim about the present.

Warns rather than blocks. A wrong timestamp misleads a later reader but breaks
nothing, and a guard that blocks a whole recap over one field would be switched
off, taking the real cases with it (see `algorithmatize-checks`'s "Limits").

The carve-out for the injected reading is value-aware, and has to be. Tracking
only *whether* a reading happened discharges the guard for any claimed time in
that turn, however far from what was actually measured -- which is the failure
this guard exists to catch, arriving through the guard itself (ai-config#1848:
an injected `14:48:23 PDT` and a recap stating `15:22 PDT`, silent). So when the
reading is one whose value is readable, the claim is compared against it: a time
running AHEAD of the last measurement cannot have been observed, and one far
behind it has expired. Quoting the reading, which the rule prescribes, stays
correct and stays silent.

A `date` invocation discharges unconditionally, because this guard reads the
transcript's tool *calls* and not their output, so no measured value exists to
compare against. That is the honest limit rather than an oversight: the rule's
remedy is to run the clock in the same message, and a session that just did so
is the case the guard is not for.

Fails OPEN on any parse trouble, and fires at most once per distinct message,
so it cannot wedge a session.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# A claim about the present, in the form the recap convention prescribes.
# The Pacific marker is required: it is what distinguishes "it is now 18:52 PT"
# from an ISO timestamp quoted out of an API response.
RX_CLAIM = re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*(?:AM|PM)?\s*"
    r"(?:PDT|PST|\bPT\b)",
    re.I,
)

# Context directly preceding a timestamp indicating a historical action or artifact conversion
# (e.g. "merged at 14:51 PT", "committed at 18:19 PDT"), rather than a present-time recap claim (#2661).
# Must have an explicit preposition ("at", "on", "in", "since", "from", etc.) and not cross sentence boundaries.
RX_PAST_CONTEXT = re.compile(
    r"\b(?:merged|closed|created|committed|pushed|failed|passed|started|finished|ran|dated|recorded|received|sent|authored|opened|landed|tagged)\s+(?:at|on|in|since|from|before|until|between)\s+[^.!?;\n]{0,35}$",
    re.I,
)

# UTC-to-local conversions in historical summaries or merge reports (e.g. "... 21:51 UTC (14:51 PT)").
RX_UTC_CONVERT = re.compile(
    r"\bUTC\s*(?:[/]\s*|\(\s*|\s+at\s+)[^.!?;\n]{0,25}$",
    re.I,
)

# Any fresh reading of the wall clock. Covers the bash form the rule
# prescribes, a bare `date`, and the PowerShell fallback for Git Bash.
# The lookbehind excludes a word character and a hyphen, so `apt-get update`
# and git's `--date=format-local` are not read as clock reads, while a bare
# `date` -- which reaches this scan JSON-quoted, as `"date"` -- still is.
RX_CLOCK_READ = re.compile(
    r"(?<![\w-])date\b"
    r"|\bTZ=[A-Za-z_]+/[A-Za-z_]+\s+date\b"
    r"|ConvertTimeBySystemTimeZoneId"
    r"|\[DateTime\]::UtcNow",
    re.I,
)

# The harness's own injected reading. Quoting this is correct, so it counts as
# a measurement -- otherwise the guard would fire on the one case the rule
# explicitly tells you to trust. Supports both Claude Code's "Current time -- local:"
# (via inject-local-time.sh) and Antigravity/Gemini CLI's "<ADDITIONAL_METADATA>\nThe current local time is:".
RX_HOOK_CLOCK = re.compile(
    r"Current time\s*--\s*local:|The current local time is:",
    re.I,
)

# The value that line carries. The example is deliberately written with
# placeholders rather than a real timestamp: a literal one would match the
# regex directly below it, so reading, grepping, or diffing THIS FILE during
# ordinary work would inject a fabricated reading into the transcript the
# guard scans. `shared/writing/examples-are-scanned.md` names exactly that.
# Shape: "Current time -- local: <YYYY-MM-DD> <HH:MM:SS> <PDT|PST>" or ISO string.
RX_HOOK_CLOCK_VALUE = re.compile(
    r"(?:Current time\s*--\s*local:\s*\d{4}-\d{2}-\d{2}\s+|"
    r"The current local time is:\s*\d{4}-\d{2}-\d{2}[T\s])"
    r"([01]?\d|2[0-3]):([0-5]\d)",
    re.I,
)

# How far a stated time may sit from the last measured one and still read as
# quoting it. Raised from 2 to 5 minutes (#2661) to accommodate multi-step turns
# where commands/subagents run for several minutes before the final recap is emitted.
TOLERANCE_MIN = 5

# Only a claim running AHEAD of the last measurement is fired on, and the
# asymmetry is deliberate rather than an oversight.
#
# Ahead is decidable: the turn cannot have run forward of the clock, so a time
# later than the last reading was not observed. Behind is not. A past time read
# off an artifact -- a merge timestamp, a committer date, a job's `startedAt` --
# is exactly what this guard's own warning text tells you to do, and it is
# indistinguishable by value from a stale recap. Firing on it would flag the
# prescribed behavior, and a guard that flags what the rule requires gets
# switched off, taking the real cases with it.
RX_FUTURE_REFERENCE = re.compile(
    r"\b(?:check(?:ing)?\s+back|check\s*-?\s*in|schedul\w*|wake\s*up|"
    r"wakeup|fires?\s+at|due\s+at|runs?\s+at|will\s+run|next\s+run|"
    r"re-?arm\w*|poll\w*\s+again)\b",
    re.I,
)


def _claim_minutes(claim):
    """Minutes-of-day for a matched claim, or None if it does not parse."""
    m = re.match(
        r"\s*([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\s*(AM|PM)?",
        claim, re.I)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    meridiem = (m.group(3) or "").upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def _skew(claimed, measured):
    """Signed minutes from measured to claimed, shortest way around the clock.

    Positive means the claim runs ahead of the measurement.
    """
    diff = (claimed - measured) % 1440
    return diff - 1440 if diff > 720 else diff


def scan(path):
    """Return (opaque_clock_idx, turn_start_idx, text, measured_minutes).

    `turn_start` is the index of the most recent real user prompt, which is
    where the current turn begins. It is deliberately NOT the previous
    assistant text block: an assistant turn normally emits narration, then
    tool calls, then the recap, so keying on text blocks put the window
    boundary INSIDE the current turn and expired a reading taken at its top
    (ai-config#1917 -- it fired even on a turn that ran `date` itself).

    `opaque_clock_idx` counts only reads whose VALUE this guard cannot see -- a
    `date` invocation, whose output lands in a later tool_result the scan does
    not attribute back to it. Those still discharge by position.
    `measured` is `(index, minutes)` for the most recent injected reading, or
    None. It carries its index because a value with no position reopens the
    very bug this guard was fixed for: a session-start reading restated as
    "now" many turns later would discharge by numeric proximity alone.

    The injected marker is honoured ONLY in a user/system turn, which is how
    the harness delivers it. A `tool_result` quoting the same marker is ignored
    entirely -- neither a value nor a position -- because this file and its
    tests both quote it, so an ordinary `Read` of either would otherwise
    discharge the guard or inject a fabricated reading.
    """
    last_clock = -1
    turn_start = -1
    measured = None
    text = ""
    i = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                m = json.loads(line)
            except Exception:
                continue
            role = m.get("type")

            # The UserPromptSubmit hook's reading does NOT arrive as a user
            # turn. It is its own record: type "attachment", carrying the text
            # under `attachment.content` / `attachment.stdout`, with neither a
            # `message` nor a top-level `content`. Measured against a live
            # transcript 2026-08-22 -- the record's own keys are `hookEvent`
            # and `hookName`, and it is emitted AFTER the prompt record it
            # belongs to. Reading only user turns made the whole
            # injected-reading carve-out inert: `measured` stayed None however
            # recently the harness had supplied a real value, so the guard
            # fired on exactly the case the rule tells you to trust.
            if role == "attachment":
                att = m.get("attachment") or {}
                if isinstance(att, dict):
                    blob = ""
                    for field in ("content", "stdout"):
                        val = att.get(field)
                        if isinstance(val, str):
                            blob += val + "\n"
                    if RX_HOOK_CLOCK.search(blob):
                        got = RX_HOOK_CLOCK_VALUE.search(blob)
                        if got:
                            measured = (
                                i, int(got.group(1)) * 60 + int(got.group(2)))
                        else:
                            last_clock = i
                continue

            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []
            if isinstance(blocks, str):
                # A bare string is a real user prompt, so it opens a new turn.
                # Restricted to `user` deliberately: a transcript also carries
                # `attachment`, `last-prompt`, `custom-title` and similar
                # records, which belong to the turn already open. Advancing
                # past one of those expires the injected reading that arrives
                # beside it.
                if role == "user":
                    turn_start = i
                if role != "assistant" and RX_HOOK_CLOCK.search(blocks):
                    got = RX_HOOK_CLOCK_VALUE.search(blocks)
                    if got:
                        measured = (i, int(got.group(1)) * 60 + int(got.group(2)))
                    else:
                        last_clock = i
                continue
            if not isinstance(blocks, list):
                continue
            # A user-role message carrying a `text` block is a real prompt and
            # opens a new turn. One carrying only `tool_result` blocks is this
            # turn's own tool output, which opens nothing -- that distinction is
            # the whole fix: the window must start where the USER spoke, not
            # wherever the assistant last emitted text.
            if role == "user" and any(
                    isinstance(b, dict) and b.get("type") == "text"
                    for b in blocks):
                turn_start = i
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                btype = b.get("type")
                if btype == "tool_use":
                    blob = (b.get("name") or "") + " " + json.dumps(
                        b.get("input") or {})
                    if RX_CLOCK_READ.search(blob):
                        last_clock = i
                # A tool_result is deliberately not scanned for the injected
                # marker at all, by value or by position. File content echoed
                # into one is not a reading of the clock, whatever it quotes,
                # and this file and its tests both quote it -- so counting it
                # would let an ordinary `Read` of this hook discharge the guard.
                # A real `date` run is still caught, on its tool_use above.
                elif btype == "text":
                    if role == "assistant" and b.get("text", "").strip():
                        text = b["text"]
                    elif role != "assistant" and RX_HOOK_CLOCK.search(
                            b.get("text", "")):
                        got = RX_HOOK_CLOCK_VALUE.search(b.get("text", ""))
                        if got:
                            measured = (
                                i, int(got.group(1)) * 60 + int(got.group(2)))
                        else:
                            last_clock = i
    return last_clock, turn_start, text, measured


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_clock, turn_start, text, measured = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hits = list(RX_CLAIM.finditer(text))
    if not hits:
        return 0

    # A `date` invocation inside this turn makes the claim measured. The
    # comparison is inclusive because the injected read arrives ON the prompt
    # line that opens the turn, so `>` would expire a reading taken at the very
    # moment the turn began. Its output is not attributed back here, so there
    # is no value to check it against -- position is all this branch has.
    if last_clock >= 0 and last_clock >= turn_start:
        return 0

    unmeasured_hit = None
    detail = ""

    for hit in hits:
        start, end = hit.start(), hit.end()
        prefix = text[max(0, start - 60):start]
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        local_line = text[line_start:line_end]

        if RX_UTC_CONVERT.search(prefix) or RX_PAST_CONTEXT.search(prefix):
            continue

        if RX_FUTURE_REFERENCE.search(local_line):
            # A scheduled check-in states a time that has not happened yet, and
            # CLAUDE.md requires stating it. It is ahead of the clock by
            # design, not by invention.
            continue

        # A value is usable only when the reading it came from is itself in this
        # turn. An older one has expired exactly as a `date` invocation would have.
        if measured is not None and measured[0] >= turn_start:
            claimed = _claim_minutes(hit.group(0))
            if claimed is None:
                continue  # fail open on a claim shape we cannot compare
            skew = _skew(claimed, measured[1])
            if skew <= TOLERANCE_MIN:
                # Quoting the reading, or within tolerance.
                continue
            measured_hhmm = f"{measured[1] // 60:02d}:{measured[1] % 60:02d}"
            detail = (
                f"the last measured reading in this transcript is "
                f"{measured_hhmm}, so the stated time runs {skew} minutes ahead "
                f"of it and cannot have been observed"
            )
            unmeasured_hit = hit
            break
        else:
            detail = (
                "no clock read appears in this transcript since your previous message")
            unmeasured_hit = hit
            break

    if not unmeasured_hit:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-clock-claim-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w"):
            pass
    except Exception:
        pass

    # `systemMessage`, not `reason`. A `Stop` hook's `reason` is read only
    # alongside `"decision": "block"`, so a warn-only hook emitting `reason`
    # alone prints valid JSON that reaches nobody -- a detector that fires
    # silently, which is indistinguishable from one that never fires at all.
    # Every warn-only hook in this repo emits `systemMessage` for exactly that
    # reason; see `flag-unassigned-worktree.py` and
    # `flag-unchained-branch-switch.py`.
    # Single-line message avoids emitting multi-line "Stop says:" blocks in Claude Code.
    print(json.dumps({
        "systemMessage": (
            f"Timestamp reminder: Your message states Pacific time \"{unmeasured_hit.group(0).strip()}\" "
            f"and {detail}. Run 'TZ=America/Los_Angeles date \"+%Y-%m-%d %H:%M %Z\"' "
            "fresh for recaps; cite artifacts for past times."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
