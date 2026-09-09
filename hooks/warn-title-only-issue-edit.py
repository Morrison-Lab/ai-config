#!/usr/bin/env python3
"""Stop-hook reminder: a title-only issue edit leaves a stale body standing.

WHAT HAPPENED (Morrison-Lab/gha#839, 2026-09-07)
-------------------------------------------------
An issue was filed claiming exactly ONE example stub was broken. A reviewer
showed the true count was FIVE. The session ran:

    gh issue edit 839 -R Morrison-Lab/gha --title \
      "examples/: five stubs have a second commented with: that uncomments \
      into a duplicate key"

and posted a correction COMMENT -- but never edited the issue BODY. The body
still read, verbatim, in its own "Scope" section:

    - 34 stubs carry a commented `with:` line.
    - 33 of them survive that transformation cleanly.
    - `examples/claude-code-review.yml` is the only one that does not.
    So this is a single-file defect, not a repo-wide convention problem.

The title said five; the body said one, with the superseded derivation still
standing as the authoritative "Scope" section. The session then asserted in
a PR body that the issue had been "corrected and retitled ... with the
flawed derivation and its replacement written up there" -- false of the
body. Caught only because a reviewer fetched the live issue body and
compared it against the title.

WHY THIS FIRES ON `Stop` RATHER THAN `PreToolUse`
--------------------------------------------------
The obvious shape is `PreToolUse` on Bash, firing the instant a title-only
edit runs -- it is the earliest possible moment, and several sibling hooks
in this file's own neighborhood (`flag-unmeasured-timestamp.py`,
`warn-stale-issue-edit.py`) take exactly that shape for an analogous "did
you check X first" question.

It is the wrong shape here, and the negative controls this hook must pass
are what settle it. One of them is: "a title edit for issue N followed by a
body edit for the SAME N must stay silent." That control describes a
TEMPORAL relationship -- title now, body later -- and "later" can mean a
later command in the SAME turn. A `PreToolUse` hook fires at the moment the
title-only command is ABOUT to run; by construction it has seen nothing that
has not executed yet, so it cannot know whether the very next tool call in
this turn repairs the body. Firing there and warning would be correct in the
worst case and noisy in the common one -- a session that types the title fix
and the body fix as two separate commands, back to back, is not the failure
this hook exists to catch, and pretending it can't see the second command
would make every ordinary two-step edit trip the guard.

A `Stop` hook has no such blind spot. It runs once the turn (and everything
in it) has already happened, so "no body edit for the same issue appears
elsewhere in the transcript" is a question this hook can actually answer --
elsewhere means anywhere, before or after, in this turn or an earlier one.
The real incident's own shape confirms this is the right window: the
correction COMMENT and the title edit happened together, and the missing
body edit was never going to arrive in a later command of that same turn --
it just never arrived at all. A `Stop` check catches that; a `PreToolUse`
check firing on the title edit alone could not tell the incident apart from
an ordinary two-step edit, and softening it to tolerate the two-step case
would have to look forward in time, which `PreToolUse` structurally cannot
do.

THE CHECK
---------
Walk every Bash `tool_use` in the transcript (plus `mcp__github__issue_write`
calls, method `update`) looking for a `gh issue edit` / `glab issue update`
invocation that sets a title and no body (`--title`/`-t` present; none of
`--body`, `--body-file`, `-b`, `-F`, or glab's own `--description`/`-d`
present). For each such title-only edit, check whether ANY later call in the
transcript -- for the same issue number -- sets a body. If none does, warn.
Tracked per issue rather than a single overall "most recent offender", so
two DIFFERENT issues left stale at once are both reported, each once per
distinct offending occurrence (a resolved-then-repeated offense on the
same issue gets its own warning rather than being silenced by the first
one's sentinel).

Only an actual Bash/MCP tool invocation counts. This corpus quotes
`gh issue edit --title` constantly, including in this very docstring and in
its own test file, so a check that scanned assistant PROSE for the command
string would warn on itself being described. Every match here comes from a
`tool_use` block's `input`, never from a `text` block.

WARN ONLY
---------
A title-only edit is often exactly right -- fixing a typo, narrowing scope
in a way the body already covers, correcting a misspelled issue number in
the title. The hook cannot tell those apart from the incident shape, so it
names the risk and asks for a re-read rather than blocking anything.

FAILS OPEN
----------
Unreadable stdin, a missing transcript, or any parse trouble prints nothing
and exits 0.

See `hooks/test-warn-title-only-issue-edit.py` for the fixtures.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same idiom `flag-unmeasured-timestamp.py` uses to reuse
    `warn-stale-issue-edit.py`'s transcript walk and
    `require-agent-disclosure.py`'s quote-aware segment splitter, rather
    than re-implementing either.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_stale = _sibling("warn-stale-issue-edit.py", "_sib_title_only_stale")
_disclosure = _sibling("require-agent-disclosure.py", "_sib_title_only_disclosure")

load_entries = getattr(_stale, "load_entries", None)
_tool_uses = getattr(_stale, "_tool_uses", None)
strip_heredocs = getattr(_stale, "strip_heredocs", None)
split_segments = getattr(_disclosure, "split_segments", None)

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")
MCP_ISSUE_WRITE_TOOLS = ("mcp__github__issue_write",)

STEM_GH = ("gh", "issue", "edit")
STEM_GLAB = ("glab", "issue", "update")

TITLE_FLAGS = frozenset({"--title", "-t"})
BODY_FLAGS = frozenset({"--body", "--body-file", "-b", "-F"})
# glab's real flag is `--description`/`-d`, not `--body` -- gh and glab
# disagree on the flag name for the same concept. Treating either spelling
# as "sets the body" only ever ADDS a true-positive discharge; it never
# creates a false one, since each flag is only recognized inside a segment
# already matched as `gh issue edit` or `glab issue update`.
DESC_FLAGS = frozenset({"--description", "-d"})
REPO_FLAGS = frozenset({"-R", "--repo"})

# Flags known to consume a following token as their value, so the scan for
# the issue-number positional does not mistake a flag's argument for it.
# Deliberately over-inclusive of `gh issue edit --help`'s real flag set
# (covers state/milestone/label/project/assignee mutators) rather than an
# exact reproduction -- an unlisted no-value flag merely costs nothing
# (the loop below treats any other `-`-leading token as taking no value),
# while an unlisted VALUE flag would misread its argument as the issue
# number.
VALUE_FLAGS = TITLE_FLAGS | BODY_FLAGS | DESC_FLAGS | REPO_FLAGS | frozenset({
    "-a", "--add-assignee", "--remove-assignee",
    "-c", "--add-label", "--remove-label",
    "-m", "--milestone", "--remove-milestone",
    "--add-project", "--remove-project",
})

RX_ISSUE_URL_NUMBER = re.compile(r"/issues/(\d+)\b")
RX_ENV_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _issue_number(token):
    """Extract a bare issue number from a plain number or an issue URL."""
    token = token.strip("'\"")
    if token.isdigit():
        return token
    matched = RX_ISSUE_URL_NUMBER.search(token)
    return matched.group(1) if matched else None


class EditCall:
    __slots__ = ("tool", "number", "repo", "has_title", "has_body")

    def __init__(self, tool, number, repo, has_title, has_body):
        self.tool = tool
        self.number = number
        self.repo = repo
        self.has_title = has_title
        self.has_body = has_body

    def label(self):
        return f"{self.repo}#{self.number}" if self.repo else f"#{self.number}"


def parse_edit_segment(segment):
    """Return an `EditCall` for an edit invocation at the head of `segment`.

    `segment` is one shell command already split on unquoted `;`/`&&`/`||`/
    `|`/newline (see `split_segments`), so every flag token found here
    belongs to the SAME invocation the stem matched -- an env-var prefix
    (`GH_TOKEN=... gh issue edit ...`) is skipped, not mistaken for part of
    the stem.
    """
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        return None

    i = 0
    while i < len(tokens) and RX_ENV_PREFIX.match(tokens[i]):
        i += 1

    lowered = [t.lower() for t in tokens]
    if lowered[i:i + 3] == list(STEM_GH):
        tool = "gh"
    elif lowered[i:i + 3] == list(STEM_GLAB):
        tool = "glab"
    else:
        return None
    i += 3

    number = None
    repo = None
    has_title = False
    has_body = False

    while i < len(tokens):
        tok = tokens[i]
        flag, _, inline_val = tok.partition("=")
        if flag in VALUE_FLAGS and tok.startswith("-"):
            value = inline_val if inline_val or "=" in tok else (
                tokens[i + 1] if i + 1 < len(tokens) else None)
            consumed_next = not inline_val and "=" not in tok and value is not None
            if flag in TITLE_FLAGS:
                has_title = True
            elif flag in BODY_FLAGS or flag in DESC_FLAGS:
                has_body = True
            elif flag in REPO_FLAGS and value:
                repo = value
            i += 2 if consumed_next else 1
            continue
        if tok.startswith("-"):
            # An unrecognized flag: assume no value, so it cannot swallow
            # the real positional issue number.
            i += 1
            continue
        if number is None:
            number = _issue_number(tok)
        i += 1

    if not number:
        return None
    return EditCall(tool=tool, number=number, repo=repo,
                     has_title=has_title, has_body=has_body)


def _bash_command(tool_input):
    if not isinstance(tool_input, dict):
        return None
    command = (tool_input.get("command") or tool_input.get("cmd")
               or tool_input.get("CommandLine") or tool_input.get("script"))
    return command if isinstance(command, str) and command.strip() else None


def _mcp_edit_call(tool_input):
    """An `EditCall` for a `mcp__github__issue_write` update, or None.

    Only `method: update` counts -- `method: create` is a new issue, not an
    edit of an existing one, and cannot be title-only in the sense this
    hook cares about. Field names follow the GitHub MCP server's documented
    shape for this tool family (`issue_number`/`issueNumber`/`number`,
    `owner`, `repo`, `title`, `body`).
    """
    if not isinstance(tool_input, dict):
        return None
    method = tool_input.get("method")
    if isinstance(method, str) and method != "update":
        return None
    number = tool_input.get("issue_number") or tool_input.get("issueNumber") \
        or tool_input.get("number")
    if number is None:
        return None
    number = str(number)
    owner = tool_input.get("owner")
    repo_name = tool_input.get("repo")
    repo = f"{owner}/{repo_name}" if owner and repo_name else None
    has_title = "title" in tool_input and tool_input.get("title") is not None
    has_body = "body" in tool_input and tool_input.get("body") is not None
    # A call setting NEITHER is tracked for nothing: it can't be a
    # title-only offender (no title) and can't resolve one either (no
    # body). A body-only update, though, must still be returned -- it
    # carries no title but is exactly what resolves an earlier title-only
    # edit of the same issue.
    if not has_title and not has_body:
        return None
    return EditCall(tool="mcp", number=number, repo=repo,
                     has_title=has_title, has_body=has_body)


def extract_edit_events(entries):
    """Yield `(record_index, EditCall)` for every edit invocation, in order.

    Every call is inspected, not only title-only ones -- a call with
    `has_body=True` is what lets a LATER title-only edit discharge as
    resolved, so a body-setting call must appear in this stream too.
    """
    if not entries or _tool_uses is None:
        return
    for idx, entry in enumerate(entries):
        for block in _tool_uses(entry):
            name = block.get("name") or ""
            tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
            if name in BASH_TOOL_NAMES:
                command = _bash_command(tool_input)
                if not command:
                    continue
                stripped = strip_heredocs(command) if strip_heredocs else command
                segments = split_segments(stripped) if split_segments else [stripped]
                for segment in segments:
                    call = parse_edit_segment(segment)
                    if call:
                        yield idx, call
            elif name in MCP_ISSUE_WRITE_TOOLS:
                call = _mcp_edit_call(tool_input)
                if call:
                    yield idx, call


def same_issue(left, right):
    """True when two `EditCall`s target the same issue.

    Numbers must match; repos are compared only when BOTH sides name one,
    mirroring `warn-stale-issue-edit.py`'s own `same_issue` -- an edit with
    no `-R` is assumed to target the same repo as any other unscoped edit
    of the same number in this session, rather than treated as unknowable.
    """
    if left.number != right.number:
        return False
    if left.repo and right.repo:
        return left.repo.lower() == right.repo.lower()
    return True


def find_unresolved_title_only_edits(entries):
    """Every issue LEFT with an unresolved title-only edit, in first-
    outstanding order.

    Returns a list of `(record_index, EditCall)`, at most one per issue --
    the issue's OWN most recent title-only occurrence, since an earlier
    occurrence of the same issue is superseded by title text alone, not
    resolved by it.

    Tracking a single overall "last offender" (an earlier version of this
    function) silently dropped every OTHER simultaneously-unresolved issue:
    a transcript retitling #100 and then #200, neither ever getting a body
    edit, reported only #200 -- #100 stayed unwarned for as long as #200
    remained the most recently touched issue, which could be the rest of
    the session. Tracking one outstanding slot PER issue instead means
    two different issues left stale at once are both reported (found by
    adversarial review; see the module docstring for the incident this
    guard exists for).

    A body-setting call (`has_body`) resolves and REMOVES any outstanding
    entry for the same issue, wherever in the transcript it appears --
    "later" is deliberately unbounded (same turn or a later one), which is
    exactly what a `Stop` hook can see and a `PreToolUse` hook, firing
    before that later command has run, structurally cannot; see the module
    docstring's "WHY THIS FIRES ON `Stop`" section. Matching by
    `same_issue` rather than a dict keyed on the bare number, so an entry
    recorded with no `-R` and a later body edit that DOES carry `-R` (or
    vice versa) still resolve each other, exactly as a direct `same_issue`
    comparison would say they should.
    """
    events = list(extract_edit_events(entries))
    outstanding = []
    for idx, call in events:
        if call.has_body:
            outstanding = [o for o in outstanding if not same_issue(o[1], call)]
            continue
        if call.has_title:
            outstanding = [o for o in outstanding if not same_issue(o[1], call)]
            outstanding.append((idx, call))
    return outstanding


NOTE = """\
Title-only edit on issue {label}: {cmd_desc} set a new title with no body \
change, and no later body edit for this issue appears in this session.

A title-only edit leaves the body asserting whatever it asserted before. \
If the title changed because a claim in the body was superseded, the body \
now contradicts the title -- the body is not automatically corrected by \
retitling. Re-read the body before claiming the issue was corrected; do \
not infer the body's state from the title alone.

If the body already matches the new title (a typo fix, a scope narrowing \
the body already covers), this warning is a false positive -- carry on."""


def _cmd_desc(call):
    """The command this offense actually named, for the warning text.

    An earlier version normalized every source to a `gh` command label but
    still passed the ORIGINAL, un-normalized `call.tool` ("mcp") into a
    helper that only recognized "gh", so an MCP-sourced offense quoted
    `` `gh issue update N --title ...` `` -- a command that does not exist
    ("issue update" is not a real `gh` subcommand; "issue edit" is). Named
    per-source instead, so each description matches a command that could
    actually be typed.
    """
    if call.tool == "gh":
        return f'`gh issue edit {call.number} --title ...`'
    if call.tool == "glab":
        return f'`glab issue update {call.number} --title ...`'
    return f'`mcp__github__issue_write` (method: update, issue_number: {call.number})'


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"transcript_path": raw}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def _sentinel_path(path, idx, call):
    """Keyed on the OFFENDING RECORD, not just the issue.

    Keying on (transcript, issue) alone means the FIRST warning about an
    issue permanently silences every later one, including a genuine
    reoffense: title-only edit, warn, a body edit resolves it, then a
    SECOND title-only edit on the same issue later in the same session
    stays unresolved too -- and deserves its own warning, not the first
    one's leftover sentinel (found by adversarial review). Including the
    offending record's own index means a later, different occurrence of
    the same issue gets a fresh key, while repeated Stop calls that still
    see the SAME unresolved occurrence keep hitting the same key and stay
    quiet, exactly as before.
    """
    key = hashlib.sha256(
        f"{path}|{call.number}|{call.repo}|{idx}".encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f".claude-title-only-issue-{key}")


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    try:
        path = payload.get("transcript_path") or ""
        entries = load_entries(path) if load_entries else None
        if entries is None:
            return 0
        offenders = find_unresolved_title_only_edits(entries)
        if not offenders:
            return 0

        # Report every issue newly left outstanding, in one message --
        # each issue's own sentinel decides whether it is "new". A prior
        # design reported only the single most-recently-touched issue,
        # which silently dropped every OTHER simultaneously-unresolved one
        # (see `find_unresolved_title_only_edits`'s own docstring).
        to_report = []
        for idx, call in offenders:
            sentinel = _sentinel_path(path, idx, call)
            if not is_dry_run:
                if os.path.exists(sentinel):
                    continue
                try:
                    open(sentinel, "w").close()
                except Exception:
                    pass
            to_report.append(call)
        if not to_report:
            return 0

        blocks = [
            NOTE.format(label=call.label(), cmd_desc=_cmd_desc(call))
            for call in to_report
        ]
        print(json.dumps({"systemMessage": "\n\n---\n\n".join(blocks)}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
