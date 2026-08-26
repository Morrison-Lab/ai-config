#!/usr/bin/env python3
"""PreToolUse reminder: creating a PR or issue with no duplicate check earlier
in the session.

[`pr-on-claim`](../shared/workflow/pr-on-claim.md) already names the PR check ---
the authoritative in-flight signal for a piece of work is the issue's
cross-referenced **open PRs**, not the claim comment.
[`issue-first`](../shared/workflow/issue-first.md) and
[`report-mistakes-proactively`](../shared/workflow/report-mistakes-proactively.md)
name the same shape for issues: search the tracker before filing.
Both rules are consulted at read time and broken at composition time, which is
the shape [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)
says to mechanize rather than restate.

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

  * A duplicate PR or issue is cheap. It is visible, it is closeable, and
    closing it costs one comment.
  * A blocked `gh pr create` or `gh issue create` is expensive. It interrupts
    the one action that makes work (or a problem) visible to other sessions,
    which is the very thing these rules exist to encourage.
    `report-mistakes-proactively.md`'s "filing is not gated on approval" points
    the same way: a redundant entry is cheap and a lost one is not.

So the safe direction is a reminder carrying the query to run, not a refusal.
That also means a false positive costs a line of context and nothing else,
which is what lets the matcher stay broad enough to be useful.

THE CHECK
---------
Both must hold, independently for PRs and for issues:

  1. the command creates a PR/MR or an issue at a COMMAND POSITION ---
     `gh pr create` / `glab mr create`, or `gh issue create` /
     `glab issue create`, at the start of the command or after `;`, `&&`,
     `||`, `|`, or a newline.
  2. NO duplicate-surfacing command of the SAME object kind appears earlier
     in the transcript. A `gh pr list` does not discharge an issue create,
     and a `gh issue list` does not discharge a PR create.

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
PR create --- any earlier command that could surface an existing PR:

    gh pr list, gh pr view, gh pr status, gh search prs
    glab mr list, glab mr view
    mcp__github__list_pull_requests, mcp__github__search_pull_requests,
    mcp__github__pull_request_read

Issue create --- a qualifying tracker search, not a listing of open issues:

    gh issue list ... --state all ... --search ...
    glab issue list ... --all ... --search ...
    gh search issues   (omit --state; --state open|closed does not qualify)
    mcp__github__search_issues

`--state all` / glab `--all`, not `--state open`, per
[`check-open-prs-before-duplicating`](../shared/workflow/check-open-prs-before-duplicating.md).
A bug fixed and closed last week is exactly the duplicate an open-state search
cannot see. Measured on Morrison-Lab/ai-config (2026-08): one cp1252 decode
crash had four open issues (#1984, #2040, #2048, #2049) before #2086 closed
them; three of the four would have been caught by an `--state open` search,
but a bug fixed and closed last week is exactly the duplicate an open-state
search cannot see.

The hook prompts that search. It does not adjudicate whether the terms were
good --- that is [`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md).

PR discharge stays generous --- session-wide rather than per-topic.
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md) warns
that an over-broad discharge makes a guard go silent, and that is a real cost
here: a session that listed PRs once at the start is discharged for every PR it
later creates. That was accepted because the target is the session that never
looked at all, which is what the measured PR incident was. Tightening it to
per-topic would need a notion of "same topic" that nothing in the transcript
supplies. Issue discharge is stricter on FLAGS (`--state all` and `--search`)
for the same reason, not on topic.

OUT OF SCOPE
------------
Re-deriving a documented quirk (instance 3 of #2088) is not mechanizable until
after the fact: nothing at composition time distinguishes it from ordinary
work. Authoring a new file under `shared/` or `memories/` without a prior
corpus search (instance 2) is a different instrument --- a Write matcher, a
filesystem "new file" check, and a grep discharge --- not a matcher extension
of this hook.

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

# `gh issue create` / `glab issue create` at a command position. Same
# separator class as RX_CREATE, including `(` and `{`, for the same reason:
# `URL=$(gh issue create ...)` is a real create.
RX_ISSUE_CREATE = re.compile(
    r"(?:^|[;&|\n({])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:gh\s+issue\s+create|glab\s+issue\s+create)\b",
    re.MULTILINE,
)

# `gh issue list` at a command position. Discharge separators stay NARROW
# (no `(` / `{`), same reason as RX_DISCHARGE.
RX_GH_ISSUE_LIST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+issue\s+list\b",
    re.MULTILINE,
)

# glab's flags are not gh's. Verified 2026-08-26 against GitLab Docs
# `glab issue list`: all-state is `-A`/`--all`, search is `--search`, and
# `-s` is `--sort`. Applying gh's `--state all` / `-s all` here would
# discharge a command glab rejects and miss the one it accepts.
RX_GLAB_ISSUE_LIST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"glab\s+issue\s+list\b",
    re.MULTILINE,
)

# `gh search issues` with no `--state open|closed`. Omitting --state is the
# all-state form (`gh search issues -h`, 2026-08-26: --state {open|closed}).
RX_GH_SEARCH_ISSUES = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+search\s+issues\b",
    re.MULTILINE,
)

RX_GH_SEARCH_STATE_FILTER = re.compile(
    r"--state(?:=|\s+)(?:open|closed)\b"
)

# gh issue list: `--state all` or `--state=all`, and short `-s all`
# (`gh issue list -h`: -s is --state, -S is --search).
RX_GH_STATE_ALL = re.compile(
    r"(?:--state(?:=|\s+)|(?<![A-Za-z0-9-])-s(?:=|\s+))all\b"
)
RX_GH_SEARCH_FLAG = re.compile(
    r"(?:--search\b|(?<![A-Za-z0-9-])-S\b)"
)

# glab issue list: `--all` / `-A`, and `--search` (no short search flag).
RX_GLAB_ALL = re.compile(
    r"(?:--all\b|(?<![A-Za-z0-9-])-A\b)"
)
RX_GLAB_SEARCH_FLAG = re.compile(r"--search\b")

# Quoted spans in a list command's flags are search terms, not flags.
# `--state open --search "--state all"` must not discharge.
RX_QUOTED_SPAN = re.compile(r"'[^']*'|\"[^\"]*\"")

# The MCP equivalent of `gh pr create` (tool-mappings.md, CREATE_PR).
MCP_CREATE = "mcp__github__create_pull_request"

# CREATE_ISSUE: the legacy name and the current issue_write method=create
# mapping (tool-mappings.md).
MCP_ISSUE_CREATE = "mcp__github__create_issue"
MCP_ISSUE_WRITE = "mcp__github__issue_write"
MCP_ISSUE_SEARCH = "mcp__github__search_issues"

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

ISSUE_NOTE = """\
No duplicate check ran before this issue creation.

`issue-first` and `report-mistakes-proactively` require a tracker search
before filing, and nothing in this session's transcript has listed or
searched issues with `--state all --search`. Parallel sessions collide most
often on exactly the bug that feels obviously unfiled.

Measured on Morrison-Lab/ai-config (2026-08): one cp1252 decode crash had
four open issues (#1984, #2040, #2048, #2049) before #2086 closed them.

`--state all`, not `--state open`: a bug fixed and closed last week is
exactly the duplicate an open-state search cannot see.

One query settles it before you spend an issue:

    gh issue list --repo <owner>/<repo> --state all --search "<keywords>"

On GitLab the equivalent is `glab issue list --all --search "<keywords>"`.

This prompts the search; it does not judge whether the terms were good.
If an issue already covers this, comment there instead. If you have already
checked another way, carry on --- this is a reminder, not a refusal.
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


def creates_issue(command):
    """True when the command creates an issue at a command position."""
    return bool(RX_ISSUE_CREATE.search(strip_heredocs(command)))


def _command_rest(text, start):
    """Flags of the command starting at start, up to the next separator."""
    rest = text[start:]
    match = re.search(r"[;&|\n]", rest)
    return rest if match is None else rest[: match.start()]


def command_has_issue_dupe_check(command):
    """True when this command string is a qualifying issue search.

    Qualifying means command-position `gh search issues` without
    `--state open|closed`, command-position `gh issue list` whose own flags
    include both `--state all` (or gh's `-s all`) and `--search` (or gh's
    `-S`), or command-position `glab issue list` with both `--all`/`-A` and
    `--search`. `--state open --search` does not qualify. `glab --state all`
    does not qualify: that flag is not glab's.
    """
    text = strip_heredocs(command)
    for match in RX_GH_SEARCH_ISSUES.finditer(text):
        rest = RX_QUOTED_SPAN.sub(" ", _command_rest(text, match.end()))
        if not RX_GH_SEARCH_STATE_FILTER.search(rest):
            return True
    for match in RX_GH_ISSUE_LIST.finditer(text):
        rest = RX_QUOTED_SPAN.sub(" ", _command_rest(text, match.end()))
        if RX_GH_STATE_ALL.search(rest) and RX_GH_SEARCH_FLAG.search(rest):
            return True
    for match in RX_GLAB_ISSUE_LIST.finditer(text):
        rest = RX_QUOTED_SPAN.sub(" ", _command_rest(text, match.end()))
        if RX_GLAB_ALL.search(rest) and RX_GLAB_SEARCH_FLAG.search(rest):
            return True
    return False


def _mcp_creates_issue(tool_name, tool_input):
    """True when this MCP call creates an issue."""
    if tool_name == MCP_ISSUE_CREATE:
        return True
    if tool_name == MCP_ISSUE_WRITE:
        method = tool_input.get("method") if isinstance(tool_input, dict) else None
        return isinstance(method, str) and method.lower() == "create"
    return False


def _mcp_is_issue_search(name, _payload):
    """True when this MCP call is a qualifying issue search.

    Only `search_issues`. GitHub MCP `list_issues` (github-mcp-server
    list_issues schema, fetched 2026-08-26) takes state OPEN|CLOSED and
    omits both when unbound --- there is no state=all, and a listing is
    not a keyword search. The CLI path already refuses a list without
    --search.
    """
    return name == MCP_ISSUE_SEARCH


def _tool_uses(entry):
    """Yield (name, payload_dict) for each tool_use in a transcript entry."""
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
        if not isinstance(name, str):
            name = ""
        payload = block.get("input")
        if not isinstance(payload, dict):
            payload = {}
        yield name, payload


def _payload_commands(payload):
    """Yield command-ish strings from a tool_use input dict."""
    for key in ("command", "cmd", "CommandLine"):
        value = payload.get(key)
        if isinstance(value, str):
            yield value


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
                for name, payload in _tool_uses(entry):
                    if name in MCP_DISCHARGE:
                        return True
                    for text in _payload_commands(payload):
                        if RX_DISCHARGE.search(strip_heredocs(text)):
                            return True
    except OSError:
        return True
    return False


def transcript_has_issue_dupe_check(transcript_path):
    """True when some earlier transcript command was a qualifying issue search.

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
                for name, payload in _tool_uses(entry):
                    if _mcp_is_issue_search(name, payload):
                        return True
                    for text in _payload_commands(payload):
                        if command_has_issue_dupe_check(text):
                            return True
    except OSError:
        return True
    return False


def _tool_inputs(entry):
    """Yield command-ish strings from one transcript entry.

    Kept as a thin wrapper over `_tool_uses` so older tests that poke at
    this helper still see the same (kind, text) pairs.
    """
    for name, payload in _tool_uses(entry):
        if name:
            yield ("name", name)
        for text in _payload_commands(payload):
            yield ("command", text)


def _emit(note):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        }
    }))


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
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    transcript = payload.get("transcript_path") or ""

    try:
        if tool_name == MCP_CREATE:
            if transcript_has_dupe_check(transcript):
                return 0
            _emit(NOTE)
            return 0

        if _mcp_creates_issue(tool_name, tool_input):
            if transcript_has_issue_dupe_check(transcript):
                return 0
            _emit(ISSUE_NOTE)
            return 0

        if tool_name not in ("Bash", "bash", "run_command"):
            return 0

        command = (tool_input.get("command")
                   or tool_input.get("cmd")
                   or tool_input.get("CommandLine")
                   or "")
        if not isinstance(command, str) or not command.strip():
            return 0

        if creates_pr(command):
            if transcript_has_dupe_check(transcript):
                return 0
            _emit(NOTE)
            return 0
        if creates_issue(command):
            if transcript_has_issue_dupe_check(transcript):
                return 0
            _emit(ISSUE_NOTE)
            return 0
    except Exception as exc:  # fail open on any parse trouble
        print("warn-pr-create-without-dupe-check: could not evaluate "
              f"({exc})", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
