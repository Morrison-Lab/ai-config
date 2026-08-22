#!/usr/bin/env python3
"""PreToolUse reminder: creating a PR with no duplicate check earlier in the session.

[`pr-on-claim`](../shared/workflow/pr-on-claim.md) already names the check --- the
authoritative in-flight signal for a piece of work is the issue's
cross-referenced **open PRs**, not the claim comment. That rule is consulted at
read time and broken at composition time, which is the shape
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) says to
mechanize rather than restate.

WHAT HAPPENED
-------------
Measured on `Morrison-Lab/wai`, 2026-08-19/20. Five branches attacked the same
`check-non-standard-chars` failure across about five hours:

    20:14  fix/replace-em-dashes
    23:29  fix/replace-em-dashes-v2
    23:38  fix/replace-all-non-standard-chars
    00:16  fix/all-non-standard-chars          -> PR #77
    01:16  fix/ascii-punctuation               -> PR #78

Two reached PRs and duplicated each other. #77 was additionally cut from an
unrelated PR's branch while targeting `main`, so merging it would have shipped
a version of that PR's content its own reviewer had already rejected.

The session that opened #78 had filed the tracking issue minutes earlier. Filing
an issue and opening a PR against it *feels* like following the issue-first
workflow, so nothing in the moment suggests a step was skipped. That is why a
rule does not reach it: the omission is invisible from the inside, and the more
sessions run in parallel, the likelier the collision and the less any one
session can see it.

WHY WARN RATHER THAN BLOCK
--------------------------
Deliberate. README's "A hook that misfires is worse than a missing one" sets the
bar, and the asymmetry here runs the opposite way from
`no-handrolled-verdict-parse.py`'s:

  * A duplicate PR is cheap. It is visible, it is closeable, and closing it
    costs one comment.
  * A blocked `gh pr create` is expensive. It interrupts the one action that
    makes work visible to other sessions, which is the very thing this rule
    exists to encourage.

So the safe direction is a reminder carrying the query to run, not a refusal.
That also means a false positive costs a line of context and nothing else,
which is what lets the matcher stay broad enough to be useful.

THE CHECK
---------
Both must hold:

  1. the command creates a PR/MR at a COMMAND POSITION --- `gh pr create` or
     `glab mr create` at the start of the command or after `;`, `&&`, `||`,
     `|`, or a newline.
  2. NO duplicate-surfacing command appears earlier in the transcript.

Clause 1's anchoring is load-bearing, not tidiness. This corpus quotes
`gh pr create` constantly --- in fragments, in issue bodies, in heredocs
documenting the workflow, and in this very docstring. A substring matcher would
fire on every reply that cites the rule it enforces, which is exactly the
failure `CLAUDE.md` records for `no-placeholder-reply.py` and solves there with
whole-message anchoring. Here the equivalent is position anchoring.

A heredoc is the specific trap: writing an issue body that contains the words
`gh pr create` on its own line puts the phrase at what looks like a command
position. Clause 1 therefore strips heredoc bodies before matching.

The stripper has to accept every shape the shell does, not the one that came to
mind first. A redirect may follow the opener as readily as precede it
(`cat <<'EOF' > file`, `cat <<'EOF' | tee file`), and `<<-` permits a
tab-indented terminator. An earlier revision matched only `cat > file <<'EOF'`,
and its tests covered only that form --- so the suite inherited the blind spot
rather than exposing it. Caught in review on #1749.

WHAT DISCHARGES IT
------------------
Any earlier command that could surface an existing PR:

    gh pr list, gh pr view, gh pr status, gh search prs
    glab mr list, glab mr view
    mcp__github__list_pull_requests, mcp__github__search_pull_requests,
    mcp__github__pull_request_read

The discharge is deliberately generous --- session-wide rather than per-topic.
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) warns
that an over-broad discharge makes a guard go silent, and that is a real cost
here: a session that listed PRs once at the start is discharged for every PR it
later creates. That was accepted because the target is the session that never
looked at all, which is what the measured incident was. Tightening it to
per-topic would need a notion of "same topic" that nothing in the transcript
supplies.

FAILS OPEN
----------
Any parse trouble, an unreadable transcript, or a missing transcript path all
return 0 silently. A reminder that cannot establish its own precondition must
not fire --- see `fail-fast.md` on making a fallback explicit and bounded.
"""
import json
import os
import re
import sys

# `gh pr create` / `glab mr create` at a command position.
RX_CREATE = re.compile(
    r"(?:^|[;&|\n({])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"      # env-assignment prefixes
    r"(?:gh\s+pr\s+create|glab\s+mr\s+create)\b",
    re.MULTILINE,
)

# A CLI command that could have surfaced an already-open PR. Anchored to a
# command position and applied to heredoc-stripped text, as RX_CREATE is: an
# unanchored discharge is strictly worse than an unanchored trigger, because
# prose that merely mentions `gh pr list` would silence the guard for the rest
# of the session rather than emit one spurious note. Caught in review on #1749,
# where this file's own reminder text contains the phrase.
#
# The separator class is DELIBERATELY NARROWER than RX_CREATE's: it omits `(`
# and `{`. Those two were added to RX_CREATE to catch real command-position
# uses -- `$(gh pr create)`, `{ gh pr create; }`, `(gh pr create)` -- but this
# module cannot parse shell quoting, so it cannot tell a subshell from a
# parenthesis inside an already-open quoted argument. Unlike `;`, `&`, `|` and
# a newline, a parenthetical aside is ordinary inside prose, so
# `git commit -m "document (gh pr list) usage"` would match. On the trigger
# side that costs one spurious note; here it silences the guard for the
# session, which is the asymmetry the paragraph above is about. Losing the
# genuine `(gh pr list)` shape costs one note, and is the cheap direction.
RX_DISCHARGE = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:gh\s+pr\s+(?:list|view|status)\b"
    r"|gh\s+search\s+prs\b"
    r"|glab\s+mr\s+(?:list|view)\b)",
    re.MULTILINE,
)

# MCP tool NAMES have no command position, so they are matched exactly.
MCP_DISCHARGE = (
    "mcp__github__list_pull_requests",
    "mcp__github__search_pull_requests",
    "mcp__github__pull_request_read",
)

# The MCP equivalent of `gh pr create` (tool-mappings.md, CREATE_PR).
MCP_CREATE = "mcp__github__create_pull_request"

# A heredoc body is prose, not commands. Strip it before position matching.
RX_HEREDOC = re.compile(
    # `<<WORD`, `<<'WORD'`, `<<-"WORD"`; then anything else on the opener line
    # (a redirect or a pipe may follow the opener, not only precede it); then
    # the body, up to a terminator that `<<-` allows to be tab-indented.
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

NOTE = """\
No duplicate check ran before this PR creation.

`pr-on-claim` makes the issue's cross-referenced **open PRs** the authoritative
in-flight signal, and nothing in this session's transcript has listed or
searched them. Parallel sessions collide most often on exactly the work that
feels obviously unclaimed.

Measured on Morrison-Lab/wai (2026-08-19/20): five branches fixed the same CI
failure across five hours, two of them reaching duplicate PRs.

One query settles it before you spend a PR:

    gh pr list --repo <owner>/<repo> --state all --search "<keywords>"

If a PR already covers this, add to it instead. If you have already checked
another way, carry on --- this is a reminder, not a refusal.
"""


def strip_heredocs(command):
    """Remove heredoc BODIES, keeping the rest of the opener line.

    Only the body is prose. The opener line's tail is still shell, and it
    routinely carries the very command this hook looks for --- piping a heredoc
    into `gh pr create --body-file -` is the idiomatic way to open a PR with a
    multi-line body. Discarding that tail along with the body suppressed exactly
    the commands the hook exists to catch (caught in review on #1749).
    """
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def creates_pr(command):
    """True when the command creates a PR/MR at a command position."""
    return bool(RX_CREATE.search(strip_heredocs(command)))


def transcript_has_dupe_check(transcript_path):
    """True when some earlier transcript command could have surfaced a PR.

    Returns True (i.e. discharged, silent) on any read failure --- fail open.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return True
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                for kind, text in _tool_inputs(entry):
                    if kind == "name":
                        if text in MCP_DISCHARGE:
                            return True
                    elif RX_DISCHARGE.search(strip_heredocs(text)):
                        return True
    except OSError:
        return True
    return False


def _tool_inputs(entry):
    """Yield command-ish strings from one transcript entry."""
    message = entry.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name")
        if isinstance(name, str):
            yield ("name", name)
        payload = block.get("input")
        if isinstance(payload, dict):
            for key in ("command", "cmd", "CommandLine"):
                value = payload.get(key)
                if isinstance(value, str):
                    yield ("command", value)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print("warn-pr-create-without-dupe-check: unreadable hook input "
              f"({exc})", file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        return 0  # fail open: the harness always sends an object

    tool_name = payload.get("tool_name")
    if tool_name == MCP_CREATE:
        # No command string to inspect; the tool itself is the creation.
        if transcript_has_dupe_check(payload.get("transcript_path") or ""):
            return 0
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE,
            }
        }))
        return 0

    if tool_name not in ("Bash", "bash", "run_command"):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = (tool_input.get("command")
               or tool_input.get("cmd")
               or tool_input.get("CommandLine")
               or "")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        if not creates_pr(command):
            return 0
        if transcript_has_dupe_check(payload.get("transcript_path") or ""):
            return 0
    except Exception as exc:  # fail open on any parse trouble
        print("warn-pr-create-without-dupe-check: could not evaluate "
              f"({exc})", file=sys.stderr)
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
