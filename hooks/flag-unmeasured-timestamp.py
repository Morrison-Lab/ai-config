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
        (`\\b\\d{1,2}:\\d{2}\\s?(?:PDT|PST|PT)\\b`)
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
observed.

Covers the Bash CLI forms (`gh pr comment`, `gh issue comment`,
`gh api .../comments`, `.../comments/N/replies`, with the body read off
disk for `--body-file` and `-F body=@file` per `flag-uncited-rebuttal.py`'s
`parse_comment_post()`) and the `mcp__github__*` comment tools, since a
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

Fails OPEN and SILENT on any parse trouble, deliberately and bounded: the
worst outcome of a guard that raises at `PreToolUse` is a blocked comment
over a transcript it could not read, and the cost of its silence is one
missed reminder. The sibling import fails the same way -- a renamed sibling
makes this hook silent rather than broken.

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

# The comment-post parser: command detection plus body extraction, including
# reading `--body-file` / `-F body=@file` off disk.
parse_comment_post = getattr(_rebuttal, "parse_comment_post", None)

# The MCP comment tools, shared with require-agent-disclosure.py. The two
# #2903 names are the fallback so the guard still covers the measured
# surface if the sibling is ever unavailable.
_disclosure = _sibling("require-agent-disclosure.py", "_sib_unmeasured_timestamp_disclosure")
MCP_POST_TOOLS = getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
))

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# A clock time in the recap format, exactly as #2903 specifies it. The
# Pacific marker is required: it is what separates "it is now 12:47 PT" from
# a duration, an ISO timestamp quoted out of an API response, or a time in
# another zone that the body is relaying rather than asserting.
RX_STAMP = re.compile(r"\b\d{1,2}:\d{2}\s?(?:PDT|PST|PT)\b")

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


def _body_from_payload(tool_name, tool_input, cwd):
    """The comment body this tool call would post, or None when it posts none."""
    if tool_name in BASH_TOOL_NAMES:
        if parse_comment_post is None:
            return None
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return None
        parsed = parse_comment_post(command, cwd)
        return parsed[3] if parsed else None
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        # `pull_request_review_write` submits without a body on some methods,
        # and a body never seen is not a body to judge.
        return body if isinstance(body, str) else None
    return None


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
    if transcript_path and os.path.exists(transcript_path):
        last_clock, turn_start, _text, measured = scan(transcript_path)
    else:
        last_clock, turn_start, measured = -1, -1, None
    if last_clock >= 0 and last_clock >= turn_start:
        return None
    for hit in hits:
        stamp = hit.group(0)
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
        body = _body_from_payload(tool_name, tool_input, cwd)
        found = unmeasured_stamp(body, tpath) if body else None
        if not found:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        stamp, detail = found

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + body + "|" + stamp).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-unmeasured-timestamp-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(
                    stamp=stamp, detail=detail, cmd=CLOCK_CMD),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            # Single line: a multi-paragraph systemMessage renders as a wall
            # of empty "says:" lines in Claude Code (ai-config#2661).
            out["systemMessage"] = (
                f"Timestamp reminder: this comment states Pacific time "
                f"\"{stamp}\" and {detail}. Run '{CLOCK_CMD}' before restating it."
            )
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
