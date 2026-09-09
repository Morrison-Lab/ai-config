#!/usr/bin/env python3
"""PreToolUse guard: a heredoc body carries a doubled backslash.

## The transport hazard

On this Windows/MINGW64 transport, a doubled backslash `\\\\` typed inside a
Bash-tool heredoc body -- even with a QUOTED delimiter (`<<'EOF'`), which
should be fully literal -- arrives at the interpreter as a single `\\`. A
single `\\` survives intact. So one level of unescaping is applied somewhere
in transport (measured 2026-08-22, ai-config#1923).

It fails silently and plausibly. A patch script's `assert target in s` fails,
which reads as a slightly-wrong anchor string -- the natural response is to
re-dump the region and retype the anchor, which fails identically. The tell
only appears on printing `repr()` of the constructed string. Worse: a heredoc
that writes a doubled-backslash regex escape emits a single-backslash one
instead, with no syntax error and a still-green suite -- a corrupted
matcher, not a crash.

CLAUDE.md's "Tool transport collapses doubled backslashes" section records
the rule and its remedy (build the character with `chr(92)` rather than
typing it, print `repr()` before writing). Re-reading that prose at load time
does not prevent the mistake: the violation happens at composition time,
inside a heredoc body, where the rule is not being actively consulted.
ai-config#3362 is the recurrence that prompted mechanizing it -- broken
twice in one session on 2026-09-08, once in a `printf` line whose newline
escape, written into a markdown snippet through a heredoc, collapsed to a
literal newline in the emitted snippet, and once in a Python-heredoc edit
whose doubled-backslash escapes, written into a test fixture, likewise
collapsed to literal newlines and yielded a SyntaxError pushed before being
caught.

## Why this warns rather than blocks

A doubled backslash inside a heredoc body is not always wrong: content
destined for a regex where the doubling is intentional and will itself be
re-escaped downstream is a legitimate case this hook cannot distinguish from
the mistake. And per README's "A hook that misfires is worse than a missing
one", a check like this -- whose false-positive rate is unknown and whose
subject (heredoc content) is unbounded in shape -- only ever adds context,
never blocks. `hookSpecificOutput.additionalContext` (with a matching
`systemMessage` outside Antigravity, whose adapter surfaces the two
separately and would otherwise double-print) is the only signal this emits.

## Scope

Scans every heredoc body in the command (`<<` or `<<-`, delimiter quoted or
unquoted) for a line containing two consecutive backslashes. It does not
attempt to reason about WHAT the doubled backslash means (a Python string
literal, a shell escape, a regex) -- only that one is present, which is
enough to prompt a second look per the remedy above.

Fails OPEN on any parse trouble, same as every guard here.
"""
import json
import os
import re
import sys

# Matches `<<` or `<<-`, an optional quoted OR unquoted delimiter, up to the
# end of that line (the heredoc "opener"), then captures everything up to a
# line consisting solely of the delimiter (optionally indented, for `<<-`).
# `re.S` lets `.` cross newlines inside the body; the body itself is
# non-greedy so a command with multiple heredocs matches each one separately
# rather than swallowing everything between the first opener and the last
# closer.
#
# The closer requires the delimiter to be the WHOLE line, modulo leading/
# trailing horizontal whitespace: `[ \t]*(?P=delim)[ \t]*` followed by a
# lookahead on `\n` or end of string, rather than the old bare `\b` word
# boundary. Bash's own rule is stricter still and depends on which form
# opened the heredoc -- a plain `<<DELIM` terminator may carry NO leading
# whitespace at all, while `<<-DELIM` strips leading TABS only, never
# spaces -- but this hook does not distinguish the two forms for the
# indent character class; both are matched by the shared `[ \t]*`
# approximation. That approximation only ever widens what counts as a
# closer line (accepting some indentation bash itself would reject), never
# narrows it, so the risk stays on the safe side for a warn-only scan: at
# worst it stops a body one line short of where bash truly would, never
# the reverse. What it DOES reject, which the old `\b` boundary did not, is
# a line carrying trailing content after the delimiter -- `EOF # comment`
# is no longer mistaken for the terminator, since anything other than
# trailing whitespace before the newline fails the lookahead and the
# search continues past it to the real closer.
_HEREDOC_RE = re.compile(
    r"<<-?\s*(?P<q>['\"]?)(?P<delim>\w+)(?P=q)[^\n]*\n"
    r"(?P<body>.*?)"
    r"\n[ \t]*(?P=delim)[ \t]*(?=\n|\Z)",
    re.S,
)

_DOUBLED_BACKSLASH = re.compile(r"\\\\")


def _heredoc_bodies(command):
    """Yield (delimiter, body_text) for every heredoc in COMMAND."""
    for m in _HEREDOC_RE.finditer(command):
        yield m.group("delim"), m.group("body")


def find_offenses(command):
    """[(delimiter, line_text, line_no), ...] for every heredoc body line in
    COMMAND that carries two consecutive backslashes."""
    out = []
    for delim, body in _heredoc_bodies(command):
        for i, line in enumerate(body.split("\n"), start=1):
            if _DOUBLED_BACKSLASH.search(line):
                out.append((delim, line, i))
    return out


NOTE = (
    "A heredoc body in this command (delimiter `{delim}`, line {line_no}) "
    "carries a doubled backslash:\n\n"
    "    {line}\n\n"
    "On this transport a doubled backslash inside a heredoc body -- even "
    "with a quoted delimiter, which should be fully literal -- can arrive "
    "at the interpreter as a SINGLE backslash rather than surviving as "
    "typed (measured ai-config#1923; recurred ai-config#3362). It fails "
    "silently: a match/assert against the intended text fails and reads as "
    "a slightly-wrong anchor, or a regex/escape sequence written this way "
    "is silently corrupted with no syntax error.\n\n"
    "If this heredoc must carry a literal backslash, build it instead of "
    "typing it doubled -- `chr(92)` (or a placeholder token) in Python, or "
    "`printf '%s'` with a variable in shell -- and print `repr()` of any "
    "constructed string before writing it, to confirm what actually "
    "landed.\n\n"
    "If the doubling here is intentional (e.g. content that will itself be "
    "re-escaped downstream), disregard this warning."
)


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
    except Exception as exc:
        print(f"warn-heredoc-doubled-backslash: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        offenses = find_offenses(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-heredoc-doubled-backslash: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0

    if not offenses:
        return 0

    delim, line, line_no = offenses[0]

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                delim=delim, line=line.strip(), line_no=line_no,
            ),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Heredoc `{delim}` line {line_no} carries a doubled backslash; "
            "this transport can collapse it to one on arrival -- build the "
            "character instead of typing it doubled, and print repr() "
            "before writing."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
