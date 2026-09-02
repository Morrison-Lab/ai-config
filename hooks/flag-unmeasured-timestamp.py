#!/usr/bin/env python3
"""PreToolUse guard: a clock time typed into a forge comment, session notebook, or memory file needs a reading.

`CLAUDE.md`'s "Timestamp recaps in local time" requires running
`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"` fresh before typing a
Pacific clock time anywhere -- a chat recap, a file edit, a session notebook /
memory file update, and (since ai-config#2900) a forge comment. The rule is
consulted at read time and broken at composition time, so the prose alone does
not reach the moment it breaks (`shared/principles/deterministic-tools.md`).
This is the instrument for the forge-comment and notebook/memory edit surfaces.

THE MEASUREMENT (2026-09-01, ai-config#2900, #2903, #2947)
-----------------------------------------------------------
One real reading at 12:02 PDT was followed by claim comments on wai#81,
wai#96 and wai#95 stamped "12:15 PT", "12:40 PT" and "12:58 PT", every one
extrapolated from how many tool calls had run since the reading. The next
real reading came back 12:21 PDT, up to an hour behind the invented stamps.
#2900 wrote the rule down; within minutes, in the same session, two chat
recaps went out headed "12:44 PDT" and "12:47 PDT" with no reading in the
turn, and the next measurement came back 12:44 PDT -- the second stamp was in
the future. #2903 asked for the forge-comment guard. Later on 2026-09-01 (#2947),
three consecutive entries in a session notebook were stamped "~17:35 PDT",
"17:50ish", and "18:05ish" with no reading since 17:06, and the next measurement
came back 17:26 PDT (all ahead of the clock). #2947 extended this guard to
session notebooks and memory files.

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
switched off. So this hook covers the surfaces that one cannot see: a comment
body about to leave through `gh` or an MCP comment tool, or an edit/append
to a session notebook (`session-*.md`) or memory file (`memory/*.md`).

WHAT IT CHECKS
--------------
    the outgoing comment body contains a clock time in the recap format
        (`no-unmeasured-clock-claim.py`'s own `RX_CLAIM`: `HH:MM`, an
        optional `:SS`, an optional `AM`/`PM`, then `PDT`, `PST`, or `PT`),
        OR a session notebook / memory file edit contains a Pacific clock time
        or `ish` stamp
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
body flag; file write/append redirects targeting `session-*.md` / `memory/*.md`),
file editing tools (`Write`, `Edit`, `NotebookEdit`, `write_to_file`, etc.),
and the `mcp__github__` comment tools.

WARNS, never blocks. A quoted or relayed time is legitimate -- a CI
timestamp, a reviewer's own "posted at 14:51 PT", a merge time read off an
artifact -- and none of those is distinguishable from an invented one by the
body alone. A wrong stamp misleads a later reader but breaks nothing, while
a blocked command interrupts work. So the warning names the stamp it found
and says what to run before restating it, leaving the decision with the author.
Emits `hookSpecificOutput.additionalContext` plus a single-line
`systemMessage`; never a `permissionDecision`.

Fires once per distinct (transcript, body, stamp) via a `/tmp` sentinel, so
a retried identical command does not nag twice.

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
_disclosure = _sibling("require-agent-disclosure.py", "_sib_unmeasured_timestamp_disclosure")
_stale = _sibling("warn-stale-issue-edit.py", "_sib_unmeasured_timestamp_stale")

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
# 08:22 PT"), which is ahead of the clock by design.
_NEVER = re.compile(r"(?!)")
RX_PAST_CONTEXT = getattr(_clock, "RX_PAST_CONTEXT", _NEVER)
RX_UTC_CONVERT = getattr(_clock, "RX_UTC_CONVERT", _NEVER)
RX_FUTURE_REFERENCE = getattr(_clock, "RX_FUTURE_REFERENCE", _NEVER)

# The comment-post parser's parts: command detection plus body extraction.
RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", None)
strip_heredocs = getattr(_rebuttal, "strip_heredocs", None)
extract_body_text = getattr(_rebuttal, "extract_body_text", None)

RX_REVIEW_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+pr\s+review\b",
    re.I | re.M,
)
RX_REVIEW_BODY_FLAG = re.compile(
    r"(?<![^\s])(?:--body(?:-file)?(?=[\s=]|$)|-[bF](?=[\s=\"']))")

RX_SHORT_BODY_LITERAL = re.compile(
    r"(?<![^\s])-b\s+(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')", re.S)
RX_SHORT_BODY_FILE = re.compile(
    r"(?<![^\s])-F[= ]+(?:\"([^\"=]+)\"|'([^'=]+)'|([^\s=]+))")

RX_DELETING = getattr(_disclosure, "DELETING_RE", re.compile(r"--delete-last\b|--delete\b"))
RX_EDIT_LAST = re.compile(r"--edit-last\b")


def _split_segments(text):
    """Split a command into shell segments, preferring the sibling's splitter."""
    splitter = getattr(_disclosure, "split_segments", None)
    if callable(splitter):
        return list(splitter(text))
    return [seg for seg in re.split(r"[;&|\n]+", text) if seg.strip()]


MCP_POST_TOOLS = getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
))

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")
WRITE_TOOL_NAMES = getattr(_stale, "WRITE_TOOLS", (
    "Write", "Edit", "write_to_file", "replace_file_content", "apply_diff",
    "NotebookEdit", "StrReplace", "EditNotebook", "MultiEdit",
))

# For forge comments: a Pacific marker (PDT, PST, PT) is strictly required,
# so plain durations (14:32, 2:30) and non-Pacific times stay silent.
RX_STAMP = getattr(_clock, "RX_CLAIM", None) or re.compile(
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*(?:AM|PM)?\s*"
    r"(?:PDT|PST|\bPT\b)",
    re.I,
)

# For session notebooks and memory files: match explicit Pacific markers
# (~17:35 PDT, 17:50ish PDT, 18:05ish PT, 17:50 PDTish), or timestamps with ish
# in heading, parenthesized entry, or timestamp-indicator contexts (ai-config#2947).
RX_NOTEBOOK_STAMP = re.compile(
    r"(?:\b|~)(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*(?:AM|PM)?\s*"
    r"(?:(?:PDT|PST|\bPT\b)(?:\s*ish\b)?|ish\b\s*(?:PDT|PST|\bPT\b))"
    r"|(?:\((?:[01]?\d|2[0-3]):[0-5]\d\s*ish(?:\s*(?:PDT|PST|\bPT\b))?\))"
    r"|(?:(?:^|\n)\s*#{1,6}\s*(?:.*?\b)?(?:[01]?\d|2[0-3]):[0-5]\d\s*ish\b)"
    r"|(?:\b(?:at|around|about|as of|Status at)\s+(?:[01]?\d|2[0-3]):[0-5]\d\s*ish\b)"
    r"|(?:~[01]?\d|2[0-3]):[0-5]\d\s*ish\b",
    re.I,
)

# File path pattern matching on-disk session notebooks and memory files
RX_NOTEBOOK_OR_MEMORY = re.compile(
    r"(?:^|[/\\])(?:session-[^/\\]*\.md|.*[/\\]memory[/\\][^/\\]*\.md|.*[/\\]memories[/\\][^/\\]*\.md)$",
    re.I,
)

# Bash file write / append redirect to notebook or memory files
RX_BASH_REDIRECT_NOTEBOOK = re.compile(
    r"(?:>>?|tee\s+(?:-a\s+)?)\s*[\"']?([^\s\"';&|]+(?:session-[^\s\"';&|]*\.md|[/\\]memory[/\\][^\s\"';&|]*\.md|[/\\]memories[/\\][^\s\"';&|]*\.md))",
    re.I,
)

# Command substitution calling `date` inside a specific command segment
RX_IN_COMMAND_DATE = re.compile(r"(?:\$\(|\`)[^\)\`]*\bdate\b", re.I)

# Explicit duration phrasing (e.g. "the suite took 14:32", "the run took 2:30ish")
RX_DURATION_CONTEXT = re.compile(
    r"\b(?:took|duration(?:\s*[:=])?|elapsed(?:\s*[:=])?|running for|runtime(?:\s*[:=])?)\s*$",
    re.I,
)

CLOCK_CMD = 'TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"'

NOTE = (
    "[flag-unmeasured-timestamp] This {surface} states the Pacific clock "
    "time \"{stamp}\" and {detail}. A time inferred from how much work has "
    "happened since the last reading drifts by up to an hour (measured "
    "2026-09-01, ai-config#2900, #2947). Run `{cmd}` now and restate the stamp from "
    "its output -- or, if the time is quoted from an artifact rather than "
    "asserted as now, say what it was read from. See CLAUDE.md, \"Timestamp "
    "recaps in local time\"."
)

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


def _blank_quotes(text):
    """Replace the inside of quoted strings with spaces, keeping offsets."""
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
                  lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1],
                  text)


def _extract_heredoc_bodies(command):
    """Extract all heredoc bodies from command."""
    bodies = []
    heredoc_re = re.compile(
        r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n(.*?)\n\s*\1\b",
        re.DOTALL,
    )
    for m in heredoc_re.finditer(command):
        bodies.append(m.group(2))
    return bodies


def _bash_post(command, cwd):
    """(kind, body, surface, is_notebook) for a Bash command."""
    # Check if the Bash command writes/appends to a notebook or memory file
    m_redir = RX_BASH_REDIRECT_NOTEBOOK.search(command)
    if m_redir:
        pos = m_redir.start()
        # Quote-aware separator scan to avoid splitting on ; or | inside quotes
        blanked_pre = _blank_quotes(command[:pos])

        # If redirect is `tee`, single pipe '|' connects the producer to tee,
        # so separator before the pipeline is [;&\n] or double pipes/amps (&&, ||).
        is_tee = bool(re.search(r"\btee\b", m_redir.group(0), re.I))
        sep_pattern = r"(?:&&|\|\||[;&\n])\s*" if is_tee else r"(?:&&|\|\||[;&|\n])\s*"

        stmt_start = 0
        for m_sep in re.finditer(sep_pattern, blanked_pre):
            stmt_start = m_sep.end()

        # Find statement end after redirect
        blanked_rest = _blank_quotes(command[stmt_start:])
        heredocs = _extract_heredoc_bodies(command[stmt_start:])
        if heredocs:
            m_hd = re.search(
                r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n(.*?)\n\s*\1\b",
                command[stmt_start:],
                re.DOTALL,
            )
            stmt_end = (stmt_start + m_hd.end()) if m_hd else len(command)
            stmt = command[stmt_start:stmt_end]
        else:
            rel_redir_end = m_redir.end() - stmt_start
            m_end = re.search(r"(?:&&|\|\||[;&|\n])", blanked_rest[rel_redir_end:])
            stmt_end = (m_redir.end() + m_end.start()) if m_end else len(command)
            stmt = command[stmt_start:stmt_end]

        # If this writing statement contains an in-command date read, it is measured by construction
        if not RX_IN_COMMAND_DATE.search(stmt):
            target_path = m_redir.group(1)
            base = os.path.basename(target_path)
            body = "\n\n".join(heredocs) if heredocs else stmt
            return "body", body, f"edit to `{base}`", True

    if RX_COMMENT_POST is None or strip_heredocs is None or extract_body_text is None:
        return None, None, None, False
    stripped = strip_heredocs(command)
    for segment in _split_segments(stripped):
        flags_only = _blank_quotes(segment)
        if RX_DELETING.search(flags_only):
            continue
        if RX_EDIT_LAST.search(flags_only) and not RX_REVIEW_BODY_FLAG.search(flags_only):
            continue
        posts = bool(RX_COMMENT_POST.search(segment)) or (
            bool(RX_REVIEW_POST.search(segment))
            and bool(RX_REVIEW_BODY_FLAG.search(flags_only)))
        if not posts:
            continue
        body = extract_body_text(segment, cwd)
        if body is None:
            body = _short_flag_body(segment, cwd)
        if body is None:
            return "unreadable", None, "comment body", False
        return "body", body, "comment body", False
    return None, None, None, False


def _extract_write_content(tool_input):
    """Extract target path and text content from file write/edit tool inputs."""
    target_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("TargetFile")
        or tool_input.get("target_file")
        or tool_input.get("filePath")
        or tool_input.get("notebook_path")
        or ""
    )
    if not target_path or not RX_NOTEBOOK_OR_MEMORY.search(target_path):
        return None, None

    content = (
        tool_input.get("content")
        or tool_input.get("text")
        or tool_input.get("replacement")
        or tool_input.get("new_string")
        or tool_input.get("new_source")
        or tool_input.get("CodeContent")
        or tool_input.get("ReplacementContent")
        or ""
    )
    if not content and "edits" in tool_input and isinstance(tool_input["edits"], list):
        content = "\n".join(
            e.get("replacement") or e.get("new_string") or ""
            for e in tool_input["edits"] if isinstance(e, dict)
        )
    if not content and "cells" in tool_input and isinstance(tool_input["cells"], list):
        content = "\n".join(
            c.get("source") or c.get("text") or c.get("new_source") or ""
            for c in tool_input["cells"] if isinstance(c, dict)
        )
    return target_path, content


def _post_from_payload(tool_name, tool_input, cwd):
    """(kind, body, surface, is_notebook) for the action this tool call would perform."""
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return None, None, None, False
        return _bash_post(command, cwd)
    if tool_name in WRITE_TOOL_NAMES:
        target_path, content = _extract_write_content(tool_input)
        if target_path and isinstance(content, str) and content.strip():
            base = os.path.basename(target_path)
            return "body", content, f"edit to `{base}`", True
        return None, None, None, False
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        return ("body", body, "comment body", False) if isinstance(body, str) else (None, None, None, False)
    return None, None, None, False


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
    """True when context exemptions or duration phrasing covers this stamp."""
    start, end = hit.start(), hit.end()
    prefix = body[max(0, start - 60):start]
    if RX_UTC_CONVERT.search(prefix) or RX_PAST_CONTEXT.search(prefix) or RX_DURATION_CONTEXT.search(prefix):
        return True
    line_start = body.rfind("\n", 0, start) + 1
    line_end = body.find("\n", end)
    if line_end == -1:
        line_end = len(body)
    return bool(RX_FUTURE_REFERENCE.search(body[line_start:line_end]))


def _normalize_stamp_for_minutes(stamp):
    """Normalize a stamp (stripping ~ prefix, ish suffix, and trailing zone) so _claim_minutes parses it."""
    s = stamp.strip()
    s = re.sub(r"^(?:#{1,6}\s*|\b(?:at|around|about|as of|Status at)\s+|\()", "", s, flags=re.I)
    s = re.sub(r"\)$", "", s).strip()
    s = s.lstrip("~").strip()
    s = re.sub(r"\s*ish\b", "", s, flags=re.I).strip()
    m = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b", s)
    if m:
        hhmm = m.group(0)
        tz = "PT"
        m_tz = re.search(r"(?:PDT|PST|\bPT\b)", stamp, re.I)
        if m_tz:
            tz = m_tz.group(0)
        return f"{hhmm} {tz}"
    if not re.search(r"(?:PDT|PST|\bPT\b)", s, flags=re.I):
        s += " PT"
    return s


def unmeasured_stamp(body, transcript_path, is_notebook=False):
    """(stamp, detail) for the first unmeasured stamp in `body`, else None."""
    pattern = RX_NOTEBOOK_STAMP if is_notebook else RX_STAMP
    hits = list(pattern.finditer(body))
    if not hits:
        return None
    if scan is None:
        return None
    last_clock, turn_start, measured = _transcript_state(transcript_path)
    if _read_in_turn(last_clock, turn_start):
        return None
    for hit in hits:
        stamp = hit.group(0)
        if _exempt_context(body, hit):
            continue
        if measured is not None and measured[0] >= turn_start:
            if _claim_minutes is None or _skew is None:
                return None
            norm = _normalize_stamp_for_minutes(stamp)
            claimed = _claim_minutes(norm)
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
        kind, body, surface, is_notebook = _post_from_payload(tool_name, tool_input, cwd)
        found = None
        if kind == "body" and body:
            found = unmeasured_stamp(body, tpath, is_notebook=is_notebook)
        elif kind == "unreadable" and scan is not None:
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

        surface_desc = surface or "comment body"
        if stamp == UNREADABLE_STAMP:
            context = UNREADABLE_NOTE.format(cmd=CLOCK_CMD)
            message = (
                f"Timestamp reminder: this comment's body cannot be read by "
                f"the check and no clock read is in this turn; if it states a "
                f"Pacific time, run '{CLOCK_CMD}' first.")
        else:
            context = NOTE.format(surface=surface_desc, stamp=stamp, detail=detail, cmd=CLOCK_CMD)
            message = (
                f"Timestamp reminder: this {surface_desc} states Pacific time "
                f"\"{stamp}\" and {detail}. Run '{CLOCK_CMD}' before restating it.")
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = message
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

