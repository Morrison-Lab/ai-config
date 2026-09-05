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

# ai-config#2991's incident shape, verbatim: the reading goes into a variable
# and from there into a notebook heading, so it never reaches the transcript.
CAPTURED_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_cap", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "cat >> notebook.md <<EOF\n## $t --- checkpoint\nEOF"}}]}}
# The same capture, with the value echoed as well -- printing it makes it
# quotable, which is all this guard asks for.
CAPTURED_ECHOED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_echo", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "echo \"$t\"; cat >> notebook.md <<EOF\n## $t\nEOF"}}]}}
# A capture alongside a second read that does print.
CAPTURED_AND_PRINTED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_both", "input": {
        "command": "stamp=$(date +%s); "
                   "TZ=America/Los_Angeles date '+%H:%M %Z'"}}]}}
# The captured value echoed into a file rather than to the transcript.
CAPTURED_ECHO_APPEND = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_appd", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "echo \"## $t\" >> notebook.md"}}]}}
CAPTURED_PRINTF_APPEND = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_prtf", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "printf '%s' \"$t\" >> notebook.md"}}]}}
# An operator inside the substitution, so the split must not treat it as a
# command boundary.
CAPTURED_SUBSHELL_OP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_subop", "input": {
        "command": "t=$(cd /tmp && TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "echo \"## $t\" >> notebook.md"}}]}}
# The echo sits in a brace group whose redirection is outside the group.
CAPTURED_BRACE_GROUP = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_brace", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "{ echo \"## $t\"; } >> notebook.md"}}]}}
# A format string carrying a literal parenthesis, which is what a paren-
# excluding character class cannot span: the assignment goes unrecognized, its
# text stays in the segment, and the read then reads as printed -- discharging
# the guard on the very shape it exists to catch.
CAPTURED_PAREN_FORMAT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_paren", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M (%Z)\"); "
                   "cat >> notebook.md <<EOF\n## $t --- checkpoint\nEOF"}}]}}
# The same parenthesized format string, with the value echoed. Walking the
# substitution must still recover the NAME, or the echo no longer matches the
# captured variable and the guard fires on a reading that did reach stdout.
CAPTURED_PAREN_ECHOED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_pecho", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M (%Z)\"); "
                   "echo \"$t\""}}]}}
# A parenthesis inside a QUOTED span within the substitution, unbalanced on its
# own. Counting depth without honouring quotes never returns to zero here, so
# the assignment reads as unterminated and is skipped -- which is the same
# discharge the character class produced, by a different route.
CAPTURED_QUOTED_PAREN = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_qpar", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\" "
                   "| sed 's/(//'); echo \"## $t\" >> notebook.md"}}]}}
# An explicitly numbered stdout redirect. Descriptor 1 is stdout, so `1>>`
# sends the reading to a file exactly as a bare `>>` does.
REDIRECTED_FD1_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_fd1", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" 1>>notebook.md"}}]}}
# Only descriptors 2 through 9 are excluded: stderr going to a file leaves
# stdout on the transcript.
STDERR_REDIRECTED_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_fd2", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" 2>/dev/null"}}]}}
# The combined redirect sends stdout and stderr to the file together. The `&`
# sits BEFORE the operator, unlike the `>&2` duplication it must not be
# confused with, so a lookbehind excluding `&` reads this as a print.
COMBINED_REDIRECTED_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_amp", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" &>notebook.md"}}]}}
COMBINED_APPEND_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_ampa", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" &>>notebook.md"}}]}}
# A descriptor duplication after the operator is still not a file redirect.
DUPLICATED_FD_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_dup", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" 2>&1"}}]}}
# A pipe character INSIDE the echoed string is text, not a pipe: the echo is
# unredirected and prints the captured value. The weekday format keeps the
# tool-result fallback from discharging on an HH:MM it would otherwise find,
# so only the print classification can discharge these.
QUOTED_PIPE_ECHOED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_qpipe", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%A\"); "
                   "echo \"a|b today is $t\""}}]}}
QUOTED_SEMI_ECHOED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_qsemi", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%A\"); "
                   "echo \"steps done; today is $t\""}}]}}
QUOTED_AMP_ECHOED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_qamp", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%A\"); "
                   "echo \"a&b today is $t\""}}]}}
# A REAL pipe between the echo and the variable: the echo feeds grep, and the
# variable is grep's pattern, so the value never prints.
PIPED_PAST_VAR = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_rpipe", "input": {
        "command": "t=$(TZ=America/Los_Angeles date \"+%H:%M %Z\"); "
                   "echo done | grep -c $t"}}]}}
# An arrow inside the quoted format string is text: the read prints to the
# transcript, and its `>` is not a redirect.
QUOTED_ARROW_PRINTED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_arrow", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z -> checkpoint\""}}]}}
QUOTED_ARROW_SINGLE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_arrow1", "input": {
        "command": "TZ=America/Los_Angeles date '+%H:%M %Z -> checkpoint'"}}]}}
# A redirect inside a brace group is a real redirect, and must stay one.
GROUPED_REDIRECT = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_grp", "input": {
        "command": "{ TZ=America/Los_Angeles date \"+%H:%M %Z\" >> notebook.md; }"}}]}}
# A read substituted into the argument of a command that does not reprint it:
# the comment body carries the time, the tool result is a URL, and nothing
# reached the transcript.
GH_COMMENT_INLINE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_ghc", "input": {
        "command": "gh pr comment 123 --body \"Status as of "
                   "$(TZ=America/Los_Angeles date \"+%H:%M %Z\"): still working\""}}]}}
CURL_INLINE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_curl", "input": {
        "command": "curl -sX POST -d \"t=$(TZ=America/Los_Angeles date +%A)\" "
                   "https://example.com/log"}}]}}
# The same swallow through a heredoc body fed to a non-reprinting command.
HEREDOC_TO_GH = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_ghh", "input": {
        "command": "gh pr comment 123 --body-file - <<EOF\n"
                   "As of $(TZ=America/Los_Angeles date \"+%H:%M %Z\")\nEOF"}}]}}
# A reprinting head behind an env assignment still prints the substitution.
ENV_ECHO_INLINE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_envecho", "input": {
        "command": "LC_ALL=C echo \"as of $(TZ=America/Los_Angeles date \"+%H:%M %Z\")\""}}]}}
# `NAME=$(` inside a quoted argument is not an assignment: the read prints as
# part of the echoed string, and the transcript carries it.
QUOTED_HEAD_PRINTED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_qhead", "input": {
        "command": "echo \"stamp=$(TZ=America/Los_Angeles date +%H:%M) "
                   "checkpoint\""}}]}}
# The same heading, with no intermediate variable.
HEREDOC_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_here", "input": {
        "command": "cat >> notebook.md <<EOF\n"
                   "## $(TZ=America/Los_Angeles date \"+%H:%M %Z\") --- checkpoint\nEOF"}}]}}
# A read whose own stdout is redirected into a file.
REDIRECTED_DATE = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_redir", "input": {
        "command": "TZ=America/Los_Angeles date \"+%H:%M %Z\" >> notebook.md"}}]}}
# A heredoc that prints, because nothing redirects it.
HEREDOC_PRINTED = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "call_hprt", "input": {
        "command": "cat <<EOF\n"
                   "## $(TZ=America/Los_Angeles date \"+%H:%M %Z\")\nEOF"}}]}}


def result(tool_use_id, content):
    """The output of a tool call, as a transcript records it."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_use_id,
         "content": content}]}}

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


def iso_clock(stamp, date="2026-08-21"):
    """The injected reading from an ISO format string."""
    return {"type": "user", "content":
            f"The current local time is: {date}T{stamp}-07:00."}


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

    # --- historical timestamps and artifact conversions (#2661) ---
    ([say("earlier"),
      say("PR #1131 merged at 2026-07-27 21:51:49 UTC (14:51 PT), landing as 39f94d73.")], False,
     "#2661: UTC conversion in historical PR merge report does not fire"),
    ([say("earlier"),
      say("PR #1141 merged (2026-07-28 06:14 UTC / 23:14 PT)")], False,
     "#2661: parenthesized UTC conversion does not fire"),
    ([say("earlier"),
      say("committed at 18:19 PDT per the git log")], False,
     "#2661: past action verb 'committed at' before PDT does not fire"),
    ([iso_clock("18:55:51"),
      say("Recap: as of 18:55 PDT")], False,
     "#2661: ISO local time injection discharges"),
    ([say("earlier"),
      say("PR #1131 merged at 2026-07-27 21:51:49 UTC (14:51 PT)\n\nRecap: as of 19:24 PDT")], True,
     "#2661: mixed message with past event and unmeasured recap still catches recap"),
     ([say("earlier"),
      say("All tests passed. Stopping Point: 18:30 PDT")], True,
     "#2661: action verb before stopping point does not silence unmeasured recap"),
    ([say("earlier"),
      say("Branch pushed. Recap: 18:30 PDT")], True,
     "#2661: action verb before recap does not silence unmeasured recap"),
    ([say("earlier"),
      say("Stopping Point: non-clean, as of 19:24 PDT\nScheduled timer to check back at 19:34 PDT")], True,
     "#2661: mixed recap and timer still catches unmeasured recap"),
    ([say("earlier"),
      say("Status: PR #123 closed at 14:51 PT after the fix landed.")], False,
     "#2661: status header followed by past action verb does not fire"),
    ([say("earlier"),
      say("I'm continuing this work now. For context, the earlier build finished at 14:51 PT yesterday.")], False,
     "#2661: 'now' in earlier sentence followed by past action does not fire"),
    ([{"type": "assistant", "content": "The current local time is: 2026-08-21T18:55:51-07:00 according to my check."},
      say("Recap: as of 23:59 PDT")], True,
     "#2661: assistant message containing ISO time string does not discharge guard for unmeasured claim"),

    # --- ai-config#2991: a reading captured into a variable and never printed
    #     The four recaps of 2026-09-02 each sat in a turn that really did run
    #     `date` -- into a `$(...)` whose value went straight to a file. The
    #     session never saw the value, so the stated time was still typed from
    #     a sense of elapsed work, and the guard stayed silent.
    ([CAPTURED_DATE, result("call_cap", ""), say("Recap: 01:07 PDT")], True,
     "#2991: a date captured into a variable, with no output in its result, "
     "does not discharge"),
    ([CAPTURED_DATE, say("Recap: 01:07 PDT")], True,
     "#2991: a capture whose output never appears in the transcript is not a "
     "reading either"),
    ([CAPTURED_DATE, result("call_cap", "00:59 PDT"), say("Recap: 00:59 PDT")],
     False,
     "#2991: the same capture discharges once its output does reach the "
     "transcript"),
    ([CAPTURED_DATE,
      result("call_cap", [{"type": "text", "text": "Wed Sep 3 00:59:12 PDT 2026"}]),
      say("Recap: 00:59 PDT")], False,
     "#2991: a result carrying its text in blocks is read the same way"),
    ([CAPTURED_DATE, result("call_cap", 42), say("Recap: 00:59 PDT")], False,
     "#2991: a result whose content cannot be read fails open"),
    ([CAPTURED_ECHOED, say("Recap: 00:59 PDT")], False,
     "#2991: echoing the captured value prints it, so the read discharges"),
    ([CAPTURED_AND_PRINTED, say("Recap: 00:59 PDT")], False,
     "#2991: a second read in the same command does print, so it discharges"),
    ([CAPTURED_DATE, result("call_other", "00:59 PDT"),
      say("Recap: 00:59 PDT")], True,
     "#2991: another call's output is not this read's output"),
    ([CAPTURED_ECHO_APPEND, result("call_appd", ""), say("Recap: 01:07 PDT")],
     True,
     "#2991: an echo of the captured value into a file is not a print"),
    ([CAPTURED_PRINTF_APPEND, result("call_prtf", ""), say("Recap: 01:07 PDT")],
     True,
     "#2991: printf into a file is not a print either"),
    ([CAPTURED_SUBSHELL_OP, result("call_subop", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: an operator inside the substitution is not a command boundary"),
    ([CAPTURED_BRACE_GROUP, result("call_brace", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: a brace group's redirection covers the echo inside it"),
    ([HEREDOC_DATE, result("call_here", ""), say("Recap: 01:07 PDT")], True,
     "#2991: a read inside a redirected heredoc body never reaches the "
     "transcript"),
    ([REDIRECTED_DATE, result("call_redir", ""), say("Recap: 01:07 PDT")], True,
     "#2991: a read whose own stdout goes to a file is not a reading"),
    ([HEREDOC_PRINTED, say("Recap: 01:07 PDT")], False,
     "#2991: an unredirected heredoc puts the read on stdout, so it "
     "discharges"),

    # --- review round 1 on #2991: the substitution and the redirect were each
    #     matched by a character class that excluded the very characters the
    #     real commands carry, so both shapes discharged the guard silently.
    ([CAPTURED_PAREN_FORMAT, result("call_paren", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: a parenthesis in the format string does not end the "
     "substitution -- the capture is still a capture"),
    ([CAPTURED_PAREN_ECHOED, say("Recap: 00:59 PDT")], False,
     "#2991: walking that substitution still recovers the variable, so "
     "echoing it discharges"),
    ([CAPTURED_QUOTED_PAREN, result("call_qpar", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: a parenthesis inside a quoted span does not change the "
     "substitution's depth"),
    ([REDIRECTED_FD1_DATE, result("call_fd1", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: `1>>` is a stdout redirect, so the reading went to the file "
     "rather than the transcript"),
    ([STDERR_REDIRECTED_DATE, say("Recap: 00:59 PDT")], False,
     "#2991: `2>` is not a stdout redirect -- the reading still prints"),

    # --- review round 2 on #2991: the lookbehind that excluded `>&2` by its
    #     `&` also excluded `&>`, the combined redirect, which sends stdout to
    #     the file; and a capture head matched inside a quoted argument.
    ([COMBINED_REDIRECTED_DATE, result("call_amp", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: `&>` sends stdout to the file, so the reading never printed"),
    ([COMBINED_APPEND_DATE, result("call_ampa", ""),
      say("Recap: 01:07 PDT")], True,
     "#2991: `&>>` is the append form of the same combined redirect"),
    ([DUPLICATED_FD_DATE, say("Recap: 00:59 PDT")], False,
     "#2991: `2>&1` duplicates a descriptor and redirects nothing to a file"),
    ([QUOTED_HEAD_PRINTED, say("Recap: 00:59 PDT")], False,
     "#2991: `NAME=$(` inside a quoted argument is not a capture -- the "
     "echo prints the reading"),

    # --- review round 3 on #2991: the echoed-variable search excluded `;`,
    #     `&`, `|` from its span, which are text inside a quoted argument.
    ([QUOTED_PIPE_ECHOED, say("Recap: 00:59 PDT")], False,
     "#2991: a `|` inside the echoed string is text, so the echo prints "
     "the captured value"),
    ([QUOTED_SEMI_ECHOED, say("Recap: 00:59 PDT")], False,
     "#2991: a `;` inside the echoed string is text too"),
    ([QUOTED_AMP_ECHOED, say("Recap: 00:59 PDT")], False,
     "#2991: and a `&` inside the echoed string"),
    ([PIPED_PAST_VAR, result("call_rpipe", "0"), say("Recap: 01:07 PDT")],
     True,
     "#2991: a real pipe between the echo and the variable hands the echo "
     "to grep, so the value never prints and the guard still fires"),

    # --- review round 4 on #2991: the redirect search ran over the raw
    #     segment, so a `>` inside a quoted format string read as a redirect.
    ([QUOTED_ARROW_PRINTED, say("Recap: 00:59 PDT")], False,
     "#2991: a `>` inside the double-quoted format string is text, and the "
     "read prints"),
    ([QUOTED_ARROW_SINGLE, say("Recap: 00:59 PDT")], False,
     "#2991: the same inside single quotes"),
    ([GROUPED_REDIRECT, result("call_grp", ""), say("Recap: 01:07 PDT")],
     True,
     "#2991: a redirect inside a brace group is still a redirect, so the "
     "reading went to the file"),

    # --- review round 5 on #2991: a read substituted into the argument of a
    #     command that does not reprint it was classed as printing.
    ([GH_COMMENT_INLINE,
      result("call_ghc", "https://github.com/o/r/pull/123#issuecomment-1"),
      say("Recap: 01:07 PDT")], True,
     "#2991: a read inside `gh pr comment --body \"$(date ...)\"` never "
     "reaches the transcript; the tool result is a URL"),
    ([CURL_INLINE, result("call_curl", "ok"), say("Recap: 01:07 PDT")], True,
     "#2991: the same through `curl -d`"),
    ([HEREDOC_TO_GH,
      result("call_ghh", "https://github.com/o/r/pull/123#issuecomment-2"),
      say("Recap: 01:07 PDT")], True,
     "#2991: a heredoc body fed to a non-reprinting command is swallowed too"),
    ([ENV_ECHO_INLINE, say("Recap: 00:59 PDT")], False,
     "#2991: an echo behind an env assignment reprints the substitution, so "
     "the read discharges"),
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
