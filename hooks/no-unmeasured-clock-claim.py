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


def scan(path):
    """Return (last_clock_read_idx, last_assistant_idx, last_assistant_text)."""
    last_clock = -1
    last_assistant = -1
    prev_assistant = -1
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
                        last_clock = i
                elif btype == "text":
                    if role == "assistant" and b.get("text", "").strip():
                        prev_assistant = last_assistant
                        last_assistant = i
                        text = b["text"]
                    elif role != "assistant" and RX_HOOK_CLOCK.search(
                            b.get("text", "")):
                        last_clock = i
    return last_clock, prev_assistant, text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_clock, prev_assistant, text = scan(path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    hit = RX_CLAIM.search(text)
    if not hit:
        return 0

    # A clock read after the previous assistant message is exactly what makes
    # this turn's claim measured. Anything earlier has expired.
    if last_clock > prev_assistant:
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

    print(json.dumps({
        "reason": (
            f"Your message states a Pacific clock time -- "
            f"\"{hit.group(0).strip()}\" -- and no clock read appears in this "
            "transcript since your previous message.\n\n"
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
