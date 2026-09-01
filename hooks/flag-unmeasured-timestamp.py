#!/usr/bin/env python3
"""PreToolUse guard: a clock time typed into a forge comment needs a reading.

`CLAUDE.md`'s "Timestamp recaps in local time" requires running
`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` fresh before typing a
Pacific clock time anywhere -- a chat recap, a file edit, and (since
ai-config#2900) a forge comment. The rule is consulted at read time and
broken at composition time, so the prose alone does not reach the moment it
breaks (`shared/principles/deterministic-tools.md`). This is the instrument
for the forge-comment surface.

THE MEASUREMENT (2026-09-01, ai-config#2900 and #2903)
------------------------------------------------------
One real reading at 12:02 PDT was followed by claim comments on wai#81,
wai#96 and wai#95 stamped "12:15 PT", "12:40 PT" and "12:58 PT", every one
extrapolated from how many tool calls had run since the reading. The next
real reading came back 12:21 PDT, up to an hour behind the invented stamps.
#2900 wrote the rule down; within minutes, in the same session, two chat
recaps went out headed "12:44 PDT" and "12:47 PDT" with no reading in the
turn, and the next measurement came back 12:44 PDT -- the second stamp was in
the future. #2903 asked for the guard.

WHICH HALF THIS IS, AND WHY THERE IS NOT A SECOND Stop HOOK
-----------------------------------------------------------
#2903 asked for a `Stop` hook over the reply plus a `PreToolUse` check over
comment bodies. The `Stop` half already exists and is registered:
`hooks/no-unmeasured-clock-claim.py` (`grep -n unmeasured hooks/hooks.json`)
reads the reply for the same Pacific-marked clock time, discharges on a
`date` call in the turn, and goes further -- it compares the stated time
against the harness's injected reading and exempts the scheduled-check-in
sentence `CLAUDE.md` itself prescribes. Registering a second, simpler `Stop`
guard beside it would warn twice on every recap and would fire on exactly
the cases the existing one deliberately exempts, which is how a guard gets
switched off. So this hook covers the surface that one cannot see: a comment
body about to leave through `gh` or an MCP comment tool, which never reaches
a `Stop` hook at all.

WHAT IT CHECKS
--------------
    the outgoing comment body contains a clock time in the recap format
        (`no-unmeasured-clock-claim.py`'s own `RX_CLAIM`: `HH:MM`, an
        optional `:SS`, an optional `AM`/`PM`, then `PDT`, `PST`, or `PT`)
    AND no clock read appears in the transcript since the current turn began

The transcript walk is `no-unmeasured-clock-claim.py`'s own `scan()`,
imported rather than re-implemented, so the two guards agree by
construction on what a turn is and what a clock read is: any `date`
invocation (the lookbehind there keeps `--date=format-local` and
`apt-get update` from counting), the PowerShell
`ConvertTimeBySystemTimeZoneId` fallback, or the `UserPromptSubmit` hook's
injected reading. When that reading carries a value, the stamp is compared
against it the same way: a stamp within `TOLERANCE_MIN` of the reading is
quoting it and stays silent, and one running ahead of it cannot have been
observed. The sibling's three context exemptions (`RX_PAST_CONTEXT`,
`RX_UTC_CONVERT`, `RX_FUTURE_REFERENCE`) are imported too, so "merged at
14:51 PT", "21:51 UTC (14:51 PT)", and the prescribed "I'll check back at
08:22 PT" are skipped by both guards alike.

Covers the Bash CLI forms (`gh pr comment`, `gh issue comment`,
`gh api .../comments`, `.../comments/N/replies`, with the body read off
disk for `--body-file` and `-F body=@file` per `flag-uncited-rebuttal.py`'s
`RX_COMMENT_POST` and `extract_body_text()`; plus `gh pr review` carrying a
body flag, which that sibling's pattern does not list and this hook anchors
locally after `require-agent-disclosure.py`'s `REVIEW_ONLY_RE`, so a review
body posted through the CLI gets the same treatment as one posted through
`mcp__github__pull_request_review_write`) and the `mcp__github__` comment
tools that `require-agent-disclosure.py`'s `MCP_POST_TOOLS` names, since a
remote/web session has no `gh` at all and the #2900 claim comments went out
through exactly those tools. REGISTERED TWICE, under `Bash` and under
`mcp__github__.*`, because `hooks.json` matches by tool name.

WARNS, never blocks. A quoted or relayed time is legitimate -- a CI
timestamp, a reviewer's own "posted at 14:51 PT", a merge time read off an
artifact -- and none of those is distinguishable from an invented one by the
body alone. A wrong stamp misleads a later reader but breaks nothing, while
a blocked `gh pr comment` interrupts the one action that makes a claim
visible to other sessions. So the warning names the stamp it found and says
what to run before restating it, and leaves the decision with the author.
Emits `hookSpecificOutput.additionalContext` plus a single-line
`systemMessage`; never a `permissionDecision`.

Fires once per distinct (transcript, body, stamp) via a `/tmp` sentinel, so
a retried identical command does not nag twice.

Fails OPEN on any parse trouble, deliberately and bounded: the worst
outcome of a guard that raises at `PreToolUse` is a blocked comment over a
transcript it could not read, and the cost of its silence is one missed
reminder. The sibling import fails the same way -- a renamed sibling makes
this hook silent rather than broken.

The one parse failure that is NOT silent is a body the hook can see it
cannot read: a comment-post form matched, but the body comes from a
`--body-file` that is not on disk yet (a heredoc in the same Bash call
writes it, and the call runs after this hook), from `--body-file -`
(stdin), or from `--editor`. Silence there reads as a clean verdict over a
body never examined, so -- following `require-agent-disclosure.py`'s third
verdict -- the hook says it could not read the body and names the command
to run if the body states a time. Still warn-only, and still discharged by
a clock read in the turn, since any stamp the body carries would be.

See `hooks/test-flag-unmeasured-timestamp.py` for the fixtures.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern `flag-uncounted-comment-claims.py` and `no-empty-promise.py`
    use. Fails open, per the file-wide contract.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_clock = _sibling("no-unmeasured-clock-claim.py", "_sib_unmeasured_timestamp_clock")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_unmeasured_timestamp_rebuttal")

# The transcript walk and the value comparison, reused verbatim so the two
# guards cannot disagree about what a turn or a clock read is.
scan = getattr(_clock, "scan", None)
_claim_minutes = getattr(_clock, "_claim_minutes", None)
_skew = getattr(_clock, "_skew", None)
TOLERANCE_MIN = getattr(_clock, "TOLERANCE_MIN", 5)

# The sibling's context exemptions, imported so a stamp the Stop hook leaves
# alone is left alone here too: a past action's time ("merged at 14:51 PT"),
# a UTC-to-local conversion ("21:51 UTC (14:51 PT)"), and the scheduled
# check-in sentence `CLAUDE.md` itself prescribes ("I'll check back at
# 08:22 PT"), which is ahead of the clock by design. Without them the two
# guards disagreed on `CLAUDE.md`'s own example sentence. A missing
# attribute falls back to a pattern that matches nothing, so the guard warns
# rather than skipping when the sibling has been reshaped.
_NEVER = re.compile(r"(?!)")
RX_PAST_CONTEXT = getattr(_clock, "RX_PAST_CONTEXT", _NEVER)
RX_UTC_CONVERT = getattr(_clock, "RX_UTC_CONVERT", _NEVER)
RX_FUTURE_REFERENCE = getattr(_clock, "RX_FUTURE_REFERENCE", _NEVER)

# The comment-post parser's parts: command detection plus body extraction,
# including reading `--body-file` / `-F body=@file` off disk. Taken apart
# rather than as `parse_comment_post()`, which folds "posts no comment" and
# "posts a body I cannot read" into one None -- and only the first of those
# is silence.
RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", None)
strip_heredocs = getattr(_rebuttal, "strip_heredocs", None)
extract_body_text = getattr(_rebuttal, "extract_body_text", None)

# `gh pr review` posts a body too, and the rebuttal sibling's pattern does
# not list it. Anchored at a command position the same way, after
# `require-agent-disclosure.py`'s `REVIEW_ONLY_RE`, so prose that merely
# mentions `gh pr review` does not match. A review with no body flag
# (`gh pr review 5 --approve`) posts no prose and is not a post here.
RX_REVIEW_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+pr\s+review\b",
    re.I | re.M,
)
RX_REVIEW_BODY_FLAG = re.compile(
    r"(?<![^\s])(?:--body(?:-file)?(?=[\s=]|$)|-[bF](?=[\s=\"']))")

# `gh pr comment` / `gh pr review` / `gh issue comment` shorthand the
# rebuttal sibling's extractor does not parse: `-b "..."` for the literal
# and `-F <file>` for the file. The `-F` form excludes a `=` so `gh api`'s
# `-F body=@file`, which the sibling already reads, is not re-read as a path.
RX_SHORT_BODY_LITERAL = re.compile(
    r"(?<![^\s])-b\s+(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')", re.S)
RX_SHORT_BODY_FILE = re.compile(
    r"(?<![^\s])-F[= ]+(?:\"([^\"=]+)\"|'([^'=]+)'|([^\s=]+))")

# The MCP comment tools, imported from require-agent-disclosure.py so the
# two guards cover the same set (five tools at the time of writing, including
# `pull_request_review_write` and `discussion_comment_write`). The two #2903
# names are only the fallback, so the guard still covers the measured
# surface if the sibling is ever unavailable.
_disclosure = _sibling("require-agent-disclosure.py", "_sib_unmeasured_timestamp_disclosure")
# `gh pr comment --delete-last` deletes a comment rather than posting one, and
# `--edit-last` with no body flag reopens the previous comment rather than
# posting new text; neither carries a body to judge (review round on
# ai-config#2906). The disclosure sibling draws the same line.
RX_DELETING = getattr(_disclosure, "DELETING_RE", re.compile(r"--delete-last\b|--delete\b"))
RX_EDIT_LAST = re.compile(r"--edit-last\b")
MCP_POST_TOOLS = getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
))

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# A clock time in the recap format: the Stop sibling's own `RX_CLAIM`, so the
# two guards agree on what a stamp is -- `HH:MM`, an optional `:SS`, an
# optional AM/PM, then the Pacific marker. A narrower local pattern let
# "1:05 PM PT" through silent and captured "12:47:30 PDT" as "47:30 PDT",
# which `_claim_minutes` then could not parse. The Pacific marker is
# required: it is what separates "it is now 12:47 PT" from a duration, an
# ISO timestamp quoted out of an API response, or a time in another zone
# that the body is relaying rather than asserting. The fallback is that
# pattern restated, for a session where the sibling is unavailable.
RX_STAMP = getattr(_clock, "RX_CLAIM", None) or re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*(?:AM|PM)?\s*"
    r"(?:PDT|PST|\bPT\b)",
    re.I,
)

CLOCK_CMD = 'TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"'

NOTE = (
    "[flag-unmeasured-timestamp] This comment body states the Pacific clock "
    "time \"{stamp}\" and {detail}. A time inferred from how much work has "
    "happened since the last reading drifts by up to an hour (measured "
    "2026-09-01, ai-config#2900). Run `{cmd}` now and restate the stamp from "
    "its output -- or, if the time is quoted from an artifact rather than "
    "asserted as now, say what it was read from. See CLAUDE.md, \"Timestamp "
    "recaps in local time\"."
)

# The third verdict, after `require-agent-disclosure.py`: a post whose body
# the check cannot read is reported as exactly that, never as clean.
UNREADABLE_NOTE = (
    "[flag-unmeasured-timestamp] This posts a forge comment whose body this "
    "check cannot read (it comes from a file not yet on disk, from stdin, or "
    "from an editor), and no clock read appears in this transcript since the "
    "current turn began. If the body states a Pacific clock time, run "
    "`{cmd}` now and restate the stamp from its output before posting. See "
    "CLAUDE.md, \"Timestamp recaps in local time\"."
)
UNREADABLE_STAMP = "(body not readable)"
UNREADABLE_DETAIL = (
    "this check cannot read the body, and no clock read appears in this "
    "transcript since the current turn began")


def _first_group(m):
    return next(g for g in m.groups() if g is not None)


def _short_flag_body(stripped, cwd):
    """The body behind `-F <file>` or `-b "..."`, or None if neither is readable."""
    m = RX_SHORT_BODY_FILE.search(stripped)
    if m:
        rel = _first_group(m)
        if rel == "-":
            return None
        path = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None
    m = RX_SHORT_BODY_LITERAL.search(stripped)
    return _first_group(m) if m else None


def _bash_post(command, cwd):
    """(kind, body) for a Bash command.

    `kind` is None when the command posts no comment, "body" when it posts
    one this hook can read (with the text), and "unreadable" when it posts
    one it cannot: a `--body-file` not on disk yet, `--body-file -`, or
    `--editor`. Heredocs are stripped before matching, as in the rebuttal
    sibling, so a heredoc quoting `gh pr comment` as prose is not a post.
    """
    if RX_COMMENT_POST is None or strip_heredocs is None or extract_body_text is None:
        return None, None
    stripped = strip_heredocs(command)
    if RX_DELETING.search(stripped):
        return None, None
    if RX_EDIT_LAST.search(stripped) and not RX_REVIEW_BODY_FLAG.search(stripped):
        return None, None
    posts = bool(RX_COMMENT_POST.search(stripped)) or (
        bool(RX_REVIEW_POST.search(stripped))
        and bool(RX_REVIEW_BODY_FLAG.search(stripped)))
    if not posts:
        return None, None
    body = extract_body_text(stripped, cwd)
    if body is None:
        body = _short_flag_body(stripped, cwd)
    if body is None:
        return "unreadable", None
    return "body", body


def _post_from_payload(tool_name, tool_input, cwd):
    """(kind, body) for the comment this tool call would post; see `_bash_post`."""
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return None, None
        return _bash_post(command, cwd)
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        # `pull_request_review_write` submits without a body on some methods,
        # and a body never seen is not a body to judge.
        return ("body", body) if isinstance(body, str) else (None, None)
    return None, None


def _transcript_state(transcript_path):
    """(last_clock, turn_start, measured) from the sibling's `scan()`."""
    if transcript_path and os.path.exists(transcript_path):
        last_clock, turn_start, _text, measured = scan(transcript_path)
        return last_clock, turn_start, measured
    return -1, -1, None


def _read_in_turn(last_clock, turn_start):
    """A `date`-shaped call at or after the turn start discharges everything."""
    return last_clock >= 0 and last_clock >= turn_start


def _exempt_context(body, hit):
    """True when the sibling's context exemptions cover this stamp.

    The same windows the Stop hook reads: the 60 characters before the
    stamp for a past-action or UTC-conversion cue, and the stamp's own line
    for a scheduled check-in.
    """
    start, end = hit.start(), hit.end()
    prefix = body[max(0, start - 60):start]
    if RX_UTC_CONVERT.search(prefix) or RX_PAST_CONTEXT.search(prefix):
        return True
    line_start = body.rfind("\n", 0, start) + 1
    line_end = body.find("\n", end)
    if line_end == -1:
        line_end = len(body)
    return bool(RX_FUTURE_REFERENCE.search(body[line_start:line_end]))


def unmeasured_stamp(body, transcript_path):
    """(stamp, detail) for the first stamp in `body` no reading covers, else None.

    The transcript walk is the sibling's: `last_clock` is the index of the
    most recent `date`-shaped tool call, `turn_start` the most recent real
    user prompt, and `measured` the harness's injected reading with its
    value and position. A read at or after the turn start discharges every
    stamp in the body, by position, because a `date` call's output is not
    attributed back and there is no value to compare against. An injected
    reading from this turn is compared by value: a stamp running ahead of it
    was not observed, one within tolerance is quoting it, and -- as in the
    sibling -- one behind it is left alone, since a past time read off an
    artifact is prescribed behaviour and indistinguishable by value.
    """
    hits = list(RX_STAMP.finditer(body))
    if not hits:
        return None
    if scan is None:
        return None
    last_clock, turn_start, measured = _transcript_state(transcript_path)
    if _read_in_turn(last_clock, turn_start):
        return None
    for hit in hits:
        # `RX_CLAIM` has no capture groups: group(0) is the whole stamp,
        # which is the form `_claim_minutes` parses (hour, minute, AM/PM).
        stamp = hit.group(0)
        if _exempt_context(body, hit):
            continue
        if measured is not None and measured[0] >= turn_start:
            if _claim_minutes is None or _skew is None:
                return None
            claimed = _claim_minutes(stamp)
            if claimed is None:
                continue
            skew = _skew(claimed, measured[1])
            if skew <= TOLERANCE_MIN:
                continue
            measured_hhmm = f"{measured[1] // 60:02d}:{measured[1] % 60:02d}"
            return stamp, (
                f"the last measured reading in this transcript is "
                f"{measured_hhmm}, so the stated time runs {skew} minutes "
                f"ahead of it and cannot have been observed")
        return stamp, "no clock read appears in this transcript since the current turn began"
    return None


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    tpath = payload.get("transcript_path") or ""

    try:
        kind, body = _post_from_payload(tool_name, tool_input, cwd)
        found = None
        if kind == "body" and body:
            found = unmeasured_stamp(body, tpath)
        elif kind == "unreadable" and scan is not None:
            # A body never seen gets the cannot-read verdict, not a clean
            # one -- unless a clock read in this turn would discharge any
            # stamp it carries anyway.
            last_clock, turn_start, _measured = _transcript_state(tpath)
            if not _read_in_turn(last_clock, turn_start):
                found = UNREADABLE_STAMP, UNREADABLE_DETAIL
        if not found:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        stamp, detail = found

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + (body or "") + "|" + stamp).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-unmeasured-timestamp-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        if stamp == UNREADABLE_STAMP:
            context = UNREADABLE_NOTE.format(cmd=CLOCK_CMD)
            message = (
                f"Timestamp reminder: this comment's body cannot be read by "
                f"the check and no clock read is in this turn; if it states a "
                f"Pacific time, run '{CLOCK_CMD}' first.")
        else:
            context = NOTE.format(stamp=stamp, detail=detail, cmd=CLOCK_CMD)
            message = (
                f"Timestamp reminder: this comment states Pacific time "
                f"\"{stamp}\" and {detail}. Run '{CLOCK_CMD}' before restating it.")
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            # Single line: a multi-paragraph systemMessage renders as a wall
            # of empty "says:" lines in Claude Code (ai-config#2661).
            out["systemMessage"] = message
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
