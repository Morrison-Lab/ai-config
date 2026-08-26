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

# `gh issue list` (or its documented `ls` alias --- cli/cli `list.go`
# registers `Aliases: []string{"ls"}`, fetched 2026-08-26) at a command
# position. Discharge separators stay NARROW (no `(` / `{`), same reason as
# RX_DISCHARGE.
RX_GH_ISSUE_LIST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+issue\s+(?:list|ls)\b",
    re.MULTILINE,
)

# glab's flags are not gh's. Verified 2026-08-26 against GitLab Docs
# `glab issue list`: all-state is `-A`/`--all`, search is `--search`, and
# `-s` is `--sort`. Applying gh's `--state all` / `-s all` here would
# discharge a command glab rejects and miss the one it accepts. `ls` is
# matched on the same footing as gh's alias above --- widening a discharge
# match is the safe direction for this hook (see "PR discharge stays
# generous" above), so an unconfirmed glab alias costs nothing if it turns
# out not to exist.
RX_GLAB_ISSUE_LIST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"glab\s+issue\s+(?:list|ls)\b",
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

# A `--state` VALUE of any kind (open, closed, or anything else, including
# the invalid `all` --- `gh search issues` only accepts open|closed, so
# `--state all`/`--state=all` is a command gh itself rejects and the search
# never ran). Any explicit value disqualifies the all-state-by-omission
# reading, which is what actually satisfies `gh search issues`.
RX_GH_SEARCH_STATE_FLAG = re.compile(
    r"--state\b(?:=|\s+)['\"]?\S+",
    re.IGNORECASE,
)

# `state:open`/`is:open` (and closed) as a bare GitHub search qualifier ---
# valid syntax for both `gh search issues` positional query terms and a
# GitHub MCP `search_issues` query string. Present anywhere in a search's
# flags or query text, this narrows the result set exactly like `--state
# open` does, so it disqualifies an all-state search the same way.
RX_OPEN_CLOSED_QUALIFIER = re.compile(
    r"\b(?:is|state):(?:open|closed)\b",
    re.IGNORECASE,
)

# gh issue list: `--state VALUE` / `--state=VALUE`, and short `-s VALUE`
# (`gh issue list -h`: -s is --state, -S is --search). Captures the value
# rather than matching `all` directly, because gh's Cobra/pflag parsing is
# LAST-FLAG-WINS: a repeated `--state`/`-s` does not error, each occurrence
# silently overrides the ones before it. `--state all --search "x" --state
# open` therefore searches OPEN ISSUES ONLY --- gh itself never sees the
# `all`, it is discarded the instant the second `--state` is parsed. A
# `.search()` for the literal `all` finds that discarded flag anyway and
# discharges the reminder in exactly the direction the hook must stay
# conservative about: an issue closed last week is invisible to the
# open-only search gh actually ran (caught in review on #2324, verified by
# direct execution of the reproducer above).
RX_GH_STATE_FLAG = re.compile(
    r"(?:--state(?:=|\s+)|(?<![A-Za-z0-9-])-s(?:=|\s+))(\S+)"
)
RX_GH_SEARCH_FLAG = re.compile(
    r"(?:--search\b|(?<![A-Za-z0-9-])-S\b)"
)

# The VALUE following --search/-S (gh) or --search (glab): a single- or
# double-quoted span (the latter honoring `\"` per shell double-quote
# escaping), or an unquoted bareword. Used to reject an empty/missing value
# (`--search` with nothing after it, which gh itself would refuse to run)
# and to inspect the value for an embedded is:/state: qualifier.
RX_SEARCH_VALUE = re.compile(
    r"(?:--search(?:=|\s+)|(?<![A-Za-z0-9-])-S(?:=|\s+))"
    r"(?P<val>'[^']*'|\"(?:[^\"\\]|\\.)*\"|\S+)"
)

# glab issue list: `--all` / `-A`, and `--search` (no short search flag).
# Captures an explicit `=VALUE` when present (a bare flag has none and
# defaults true, per Cobra/pflag boolean-flag parsing) rather than matching
# the flag alone, for the same last-flag-wins reason as RX_GH_STATE_FLAG
# above: `--all --all=false` parses to false, not true, and a plain
# containment check for `--all\b(?!=false)` matches the FIRST occurrence
# and never sees the second one override it.
RX_GLAB_ALL_FLAG = re.compile(
    r"(?:--all|(?<![A-Za-z0-9-])-A)\b(?:=(\S+))?"
)
RX_GLAB_SEARCH_FLAG = re.compile(r"--search\b")

# Quoted spans in a list command's flags are search terms, not flags.
# `--state open --search "--state all"` must not discharge. The double-quote
# branch honors backslash-escaped quotes (`"x \" y"` is one span, not two),
# since an earlier version split there and mis-scanned the trailing flags.
RX_QUOTED_SPAN = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")

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
searched issues with `--state all --search`. A bug that feels obviously
unfiled is exactly the kind two independent sessions can each hit.

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
    """Flags of the command starting at start, up to the next separator.

    Quote-aware: a `;`, `&`, `|`, or newline inside a single- or
    double-quoted span (the latter honoring `\\"`) is part of the search
    term, not a command separator. An earlier version scanned for the
    separator characters unconditionally, so a compliant search whose term
    contained one of them (`--search "foo; bar" --state all`) had its
    trailing `--state all` truncated away and was wrongly reported as
    lacking a state filter.
    """
    rest = text[start:]
    in_single = False
    in_double = False
    i = 0
    n = len(rest)
    while i < n:
        ch = rest[i]
        if in_single:
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch in ";&|\n":
            return rest[:i]
        i += 1
    return rest


def _search_value_ok(rest_raw):
    """True when the LAST --search/-S occurrence carries a non-empty value
    with no is:/state: open|closed qualifier that would narrow an intended
    all-state search.

    Same last-flag-wins reasoning as `_gh_state_is_all`/`_glab_all_is_true`:
    gh's and glab's Cobra/pflag parsing takes the LAST occurrence of a
    repeated flag, so `--search "x" --search "is:open x"` runs only the
    second, narrowed search --- the first, clean one is discarded and never
    reaches the API. `RX_SEARCH_VALUE.search` finds the FIRST occurrence
    instead, so it read the discarded clean value and discharged a reminder
    for a search that gh actually narrowed to open issues (caught in review
    on #2324, verified by direct execution of the reproducer above).

    `rest_raw` must be UNSTRIPPED (quotes intact) so the value token can be
    told apart from the flags around it, and so a quoted qualifier
    (`--search "is:open foo"`) is still inspected rather than erased.
    """
    matches = list(RX_SEARCH_VALUE.finditer(rest_raw))
    if not matches:
        return False
    match = matches[-1]
    val = match.group("val")
    quoted = len(val) >= 2 and val[0] in "'\"" and val[-1] == val[0]
    if quoted:
        val = val[1:-1]
    elif val.startswith("-"):
        # An unquoted token starting with `-` is the next FLAG, not a
        # value --- `--search --limit 10` has no search term at all.
        return False
    if not val.strip():
        return False
    return not RX_OPEN_CLOSED_QUALIFIER.search(val)


def _gh_state_is_all(rest):
    """True when the LAST `--state`/`-s` occurrence in `rest` is `all`.

    gh's Cobra/pflag parsing is last-flag-wins: `--state all --search "x"
    --state open` is parsed as `--state open` alone, the earlier `all` simply
    discarded. `RX_GH_STATE_FLAG.finditer` in source order and taking the
    LAST match mirrors that parse; a plain containment test for the literal
    `all` would instead report whichever occurrence happens to exist,
    independent of which one gh actually applied (caught in review on
    #2324, verified by direct execution of the reproducer above).

    `rest` must have quoted spans stripped (as `command_has_issue_dupe_check`
    already does before calling this), so a `--search "--state all"` value
    is never mistaken for a real flag.
    """
    matches = list(RX_GH_STATE_FLAG.finditer(rest))
    if not matches:
        return False
    return matches[-1].group(1).strip("'\"").lower() == "all"


def _glab_all_is_true(rest):
    """True when the LAST `--all`/`-A` occurrence in `rest` resolves true.

    Same last-flag-wins reasoning as `_gh_state_is_all`: Cobra/pflag boolean
    flags accept a trailing `=VALUE`, and a later occurrence overrides every
    earlier one. `--all --all=false` therefore parses to false, not true,
    and a plain containment check for `--all\\b(?!=false)` matches the FIRST
    occurrence and never sees the second one override it. A bare flag (no
    `=VALUE`) means true, per Cobra/pflag boolean-flag defaults.

    `rest` must have quoted spans stripped, for the same reason as above.
    """
    matches = list(RX_GLAB_ALL_FLAG.finditer(rest))
    if not matches:
        return False
    value = matches[-1].group(1)
    if value is None:
        return True
    return value.strip("'\"").lower() != "false"


def command_has_issue_dupe_check(command):
    """True when this command string is a qualifying issue search.

    Qualifying means command-position `gh search issues` with no explicit
    `--state` value and no bare `is:`/`state:` qualifier in the query,
    command-position `gh issue list`/`ls` whose own flags include
    `--state all` (or gh's `-s all`) as the LAST `--state`/`-s` occurrence
    (gh's Cobra/pflag parsing is last-flag-wins), and the LAST `--search`
    (or gh's `-S`) occurrence carrying a non-empty value with no
    `is:`/`state:` qualifier inside it, or command-position `glab issue
    list`/`ls` with the same shape using `--all`/`-A` (again the LAST
    occurrence, since a trailing `=false` overrides an earlier bare flag)
    and the LAST `--search` occurrence, same as gh's. `--state open
    --search` does not qualify, and neither does `--state all --search "x"
    --state open` or `--state all --search "x" --search "is:open x"` ---
    the trailing `--state open` and the trailing `--search "is:open x"` are
    what gh actually parses. `glab --state all` does not qualify: that flag
    is not glab's.
    """
    text = strip_heredocs(command)
    for match in RX_GH_SEARCH_ISSUES.finditer(text):
        # Inspect UNSTRIPPED flags so `--state "open"` and `--state=OPEN`
        # still count as an open-state filter (quote-stripping would drop
        # the value and look like the all-state form).
        rest = _command_rest(text, match.end())
        if not (RX_GH_SEARCH_STATE_FLAG.search(rest)
                or RX_OPEN_CLOSED_QUALIFIER.search(rest)):
            return True
    for match in RX_GH_ISSUE_LIST.finditer(text):
        rest_raw = _command_rest(text, match.end())
        rest = RX_QUOTED_SPAN.sub(" ", rest_raw)
        if (_gh_state_is_all(rest) and RX_GH_SEARCH_FLAG.search(rest)
                and _search_value_ok(rest_raw)):
            return True
    for match in RX_GLAB_ISSUE_LIST.finditer(text):
        rest_raw = _command_rest(text, match.end())
        rest = RX_QUOTED_SPAN.sub(" ", rest_raw)
        if (_glab_all_is_true(rest) and RX_GLAB_SEARCH_FLAG.search(rest)
                and _search_value_ok(rest_raw)):
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


def _mcp_is_issue_search(name, payload):
    """True when this MCP call is a qualifying issue search.

    Only `search_issues`. GitHub MCP `list_issues` (github-mcp-server
    list_issues schema, fetched 2026-08-26) takes state OPEN|CLOSED and
    omits both when unbound --- there is no state=all, and a listing is
    not a keyword search. The CLI path already refuses a list without
    --search.

    A `query` carrying its own `is:`/`state:open|closed` qualifier narrows
    the search the same way `--state open` does on the CLI path, so it does
    not qualify either --- caught in review on #2324.
    """
    if name != MCP_ISSUE_SEARCH:
        return False
    query = payload.get("query") if isinstance(payload, dict) else None
    if isinstance(query, str) and RX_OPEN_CLOSED_QUALIFIER.search(query):
        return False
    return True


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

        # Evaluated independently, not as an if/elif chain: a single Bash
        # call can create both a PR and an issue (`gh pr create ... && gh
        # issue create ...`), and returning after the PR half left the
        # issue half unevaluated whenever the PR half discharged --- caught
        # in review on #2324.
        notes = []
        if creates_pr(command) and not transcript_has_dupe_check(transcript):
            notes.append(NOTE)
        if (creates_issue(command)
                and not transcript_has_issue_dupe_check(transcript)):
            notes.append(ISSUE_NOTE)
        if notes:
            _emit("\n\n".join(notes))
        return 0
    except Exception as exc:  # fail open on any parse trouble
        print("warn-pr-create-without-dupe-check: could not evaluate "
              f"({exc})", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
