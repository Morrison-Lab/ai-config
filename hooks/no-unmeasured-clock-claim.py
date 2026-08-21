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

    message states a Pacific clock time  AND  no clock read since the previous
    assistant message

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
# explicitly tells you to trust.
RX_HOOK_CLOCK = re.compile(r"Current time\s*--\s*local:", re.I)

# The value that line carries, e.g. "Current time -- local: 2026-08-21 15:02:20
# PDT". Captured so a claim can be compared against it rather than merely
# counted as "a reading happened".
RX_HOOK_CLOCK_VALUE = re.compile(
    r"Current time\s*--\s*local:\s*\d{4}-\d{2}-\d{2}\s+"
    r"([01]?\d|2[0-3]):([0-5]\d)",
    re.I,
)

# How far a stated time may sit from the last measured one and still read as
# quoting it. Wide enough for a recap that rounds seconds away or is composed a
# moment later; far tighter than the drift that makes a timestamp misleading.
TOLERANCE_MIN = 2


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
    """Return (opaque_clock_idx, prev_assistant_idx, text, measured_minutes).

    `opaque_clock_idx` counts only reads whose VALUE this guard cannot see -- a
    `date` invocation, whose output lands in a later tool_result the scan does
    not attribute back to it. Those still discharge by position.
    `measured_minutes` is the value of the most recent injected reading, which
    can be compared against the claim instead.
    """
    last_clock = -1
    last_assistant = -1
    prev_assistant = -1
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
            blocks = (m.get("message") or {}).get("content")
            if blocks is None:
                blocks = m.get("content") or []
            if isinstance(blocks, str):
                # A user/system turn can carry a bare string, which is where
                # the UserPromptSubmit clock line arrives.
                if RX_HOOK_CLOCK.search(blocks):
                    got = RX_HOOK_CLOCK_VALUE.search(blocks)
                    if got:
                        measured = int(got.group(1)) * 60 + int(got.group(2))
                    else:
                        last_clock = i
                continue
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                btype = b.get("type")
                if btype == "tool_use":
                    blob = (b.get("name") or "") + " " + json.dumps(
                        b.get("input") or {})
                    if RX_CLOCK_READ.search(blob):
                        last_clock = i
                elif btype == "tool_result":
                    content_text = json.dumps(
                        b.get("content") or b.get("text") or "")
                    if RX_HOOK_CLOCK.search(content_text):
                        got = RX_HOOK_CLOCK_VALUE.search(content_text)
                        if got:
                            measured = int(got.group(1)) * 60 + int(got.group(2))
                        else:
                            last_clock = i
                elif btype == "text":
                    if role == "assistant" and b.get("text", "").strip():
                        prev_assistant = last_assistant
                        last_assistant = i
                        text = b["text"]
                    elif role != "assistant" and RX_HOOK_CLOCK.search(
                            b.get("text", "")):
                        got = RX_HOOK_CLOCK_VALUE.search(b.get("text", ""))
                        if got:
                            measured = int(got.group(1)) * 60 + int(got.group(2))
                        else:
                            last_clock = i
    return last_clock, prev_assistant, text, measured


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_clock, prev_assistant, text, measured = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_CLAIM.search(text)
    if not hit:
        return 0

    # A `date` invocation after the previous assistant message makes this
    # turn's claim measured. Its output is not attributed back here, so there
    # is no value to check it against -- position is all this branch has.
    if last_clock > prev_assistant:
        return 0

    detail = (
        "no clock read appears in this transcript since your previous message")
    if measured is not None:
        claimed = _claim_minutes(hit.group(0))
        if claimed is None:
            return 0  # fail open on a claim shape we cannot compare
        skew = _skew(claimed, measured)
        if abs(skew) <= TOLERANCE_MIN:
            return 0  # quoting the injected reading, which the rule prescribes
        measured_hhmm = f"{measured // 60:02d}:{measured % 60:02d}"
        direction = "ahead of" if skew > 0 else "behind"
        detail = (
            f"the last measured reading in this transcript is "
            f"{measured_hhmm}, so the stated time runs {abs(skew)} minutes "
            f"{direction} it"
        )

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
    print(json.dumps({
        "systemMessage": (
            f"Your message states a Pacific clock time -- "
            f"\"{hit.group(0).strip()}\" -- and {detail}.\n\n"
            "A reading expires the moment it is taken, so a time extrapolated "
            "from an earlier one is invented, however honestly the earlier one "
            "was measured. That is the mechanism `CLAUDE.md`'s \"Timestamp "
            "recaps in local time\" names: the memory of having consulted the "
            "clock obscures that the measurement has expired.\n\n"
            "Re-run it now, in this same message, and use the output "
            "verbatim:\n\n"
            "    TZ=America/Los_Angeles date \"+%Y-%m-%d %H:%M %Z\"\n\n"
            "Check the `%Z` in what it prints. On Windows Git Bash the `TZ` "
            "override silently falls back to GMT, and the rule's PowerShell "
            "fallback is what to use there.\n\n"
            "For a time in the PAST, do not re-run the clock and subtract -- "
            "read it off an artifact that recorded it: a git committer date "
            "(`git log --date=format-local:'%H:%M'`), or an API `created_at`."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
