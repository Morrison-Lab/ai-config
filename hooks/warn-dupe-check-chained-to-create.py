#!/usr/bin/env python3
"""PreToolUse reminder: a gating search and the create it gates in ONE Bash call.

[`report-mistakes-proactively`](../shared/workflow/report-mistakes-proactively.md)
makes a tracker dupe-check step 2 of filing, and the shape this hook watches for
is the one that defeats it. Morrison-Lab/ai-config#1954 records the rule, #1955
adds the section stating it in that fragment, and this hook is #1956.

Citations here name the fragment's PATH and the ISSUE rather than that section's
title, deliberately: #1955 is open at the time of writing, so a title citation
would dangle if this merges first. The same applies to the reminder text below,
which a user reads at the moment it fires.

WHAT IT DETECTS
---------------
One Bash `command` string carrying BOTH a tracker/forge SEARCH and a CREATE of
the SAME object kind, with the search first:

    gh issue list -R o/r --search "..." ; gh issue create -R o/r --title "..."

Both commands run. The search returns its match and the create runs anyway,
because nothing can branch on a result that arrives at the same instant as the
action it was supposed to gate. The check is decorative.

WHAT HAPPENED
-------------
2026-08-22, Morrison-Lab/ai-config. A duplicate-search and a `gh issue create`
ran in one call, separated by a `;` and a heredoc:

    gh issue list --repo O/R --state open --search "..." --json number,title --limit 10; cat > /tmp/body.md <<'BODY' ... BODY
    gh issue create -R O/R --title "..." --body-file /tmp/body.md

The search returned the right match --- #1737 --- and #1952 was created anyway,
then closed as a duplicate with its content moved to a comment on #1737. That
comment is the disposition step 2 would have selected had its answer been read.

WHY AN INSTRUMENT IS POSSIBLE HERE AT ALL
-----------------------------------------
The near-miss is that the check is not skipped. It is written, it runs, and it
returns the right answer, so a reply asserting the tracker was searched is true
as far as it goes. Nothing about the moment feels like a dropped step, because
no step was dropped --- only a call boundary was never drawn.

That is also why reading a transcript does not catch it: a compliant session and
a defective one emit the same two commands in the same order. What differs is
the number of CALLS, and a rendered transcript flattens that away while a
`PreToolUse` payload carries it exactly. So this hook sees the one thing a
reader structurally cannot, which is the whole of its claim to exist.

WHY BUILD IT AT A FIRST OCCURRENCE
----------------------------------
Stated plainly because it cuts against a standing bar.
[`deterministic-tools`](../shared/principles/deterministic-tools.md) sets a
"third occurrence" test for building a tool, and this is one dated incident.
[`pr-on-claim`](../shared/workflow/pr-on-claim.md) invokes that bar to reject a
PreToolUse guard for the chained `requested_reviewers` POST (ai-config#1367).

Three things separate this case from that one, and none of them is that the
mistake feels bad.

  1. That rejection was of a BLOCK. Its cost is a refused action plus the
     adversarial hardening `no-unauthorized-merge.py` needed. This is a warn,
     whose cost on a false positive is one line of context.
  2. The bar's own subject is a tool that replaces RECURRING JUDGMENT --- doing
     the same mechanical task repeatedly and never noticing the total. Nobody
     is checking call boundaries by hand today, and nobody can, for the reason
     the section above gives. There is no manual practice here to have
     performed twice.
  3. The condition is a pure function of one string. No transcript walk, no
     discharge heuristic, no state --- which is what makes it cheap enough that
     YAGNI, the thing the bar protects, has little to bite on.

If it turns out noisy in practice, the right response is to delete it, not to
tune it. README's "A hook that misfires is worse than a missing one" governs.

WHAT THIS CANNOT DETECT --- READ THIS BEFORE TRUSTING ITS SILENCE
------------------------------------------------------------------
This hook detects ONE LEXICAL SHAPE: two commands sharing a call. It does not
detect, and cannot detect, the failure the rule is actually about.

A search run in its own call whose result was never read is INDISTINGUISHABLE
from one that was read. Both produce a tool result the model may or may not have
consulted, and nothing in any artifact separates the two. Splitting the commands
into separate calls satisfies this hook completely while changing nothing about
whether anyone looked.

So a silent run is not evidence that a dupe-check happened, and it is not
evidence that its answer was consulted. It is evidence of one thing only: the
two commands were not in the same string. Anyone reading a green hook as proof
the check was honoured has drawn a conclusion this instrument does not support.

Its sibling `warn-pr-create-without-dupe-check.py` has the mirror limit from the
other side: it asks whether a surfacing query appeared ANYWHERE earlier in the
session (a PR-surfacing command before `gh pr create`, or a `--state all
--search` issue query before `gh issue create`), so it establishes that a query
ran and never that its result mattered.
Between them the two cover "no query at all" and "query in the same string".
Neither covers "query read by nobody", and no lexical instrument can.

THE MATCHER
-----------
Fires when, after normalization, some CHECK match and some CREATE match share an
object kind and the check starts earlier in the string.

  check   gh issue list, gh pr list, gh search issues, gh search prs,
          glab issue list, glab mr list
  create  gh issue create, gh pr create, glab issue create, glab mr create

Three narrowings, each of which suppresses a real false positive:

  * COMMAND POSITION. A match counts only at the start of the string or after
    `;`, `&`, `|`, or a newline. This corpus quotes every one of these commands
    constantly, in fragments, issue bodies, and this docstring. `(` and `{` are
    deliberately absent from that class: a parenthetical aside is ordinary in
    prose, and ai-config#1749's third review round caught exactly that shape on
    the sibling hook, where `git commit -m "document (gh pr list) usage"` would
    have matched. Losing `URL=$(gh issue create ...)` chained after a list is
    the cheap direction.
  * SAME OBJECT KIND. `gh pr list ; gh issue create` does not fire. A PR search
    does not gate an issue creation, so the pairing carries no claim to check.
    This deliberately misses genuine cross-kind gating, which is rarer than the
    prose collision it prevents.
  * CHECK BEFORE CREATE. `gh issue create ; gh issue list` does not fire. That
    is create-then-verify, which is legitimate and common.

NORMALIZATION
-------------
Two strips run before matching, and both can only ever REMOVE matches, never
manufacture one --- neither ever inserts a separator character.

  * HEREDOC BODIES, keeping the opener line's tail. The body is prose, and this
    repo routinely writes an issue or PR body that quotes both commands. The
    tail is still shell and routinely carries the real command, so discarding it
    would suppress exactly what the hook exists to catch (ai-config#1749).
  * QUOTED STRINGS. `gh issue comment -b "...gh issue list...gh issue create..."`
    puts both commands at newline-anchored positions inside one argument, which
    position anchoring alone cannot see. Stripping `'...'` and `"..."` spans
    removes it. The cost is a miss on `bash -c "gh issue list; gh issue create"`,
    which is the safe direction and is not a shape this workflow uses.

    The double-quoted branch has to be escape-aware for that "safe direction"
    claim to hold, and an earlier revision's was not. A naive `"[^"]*"` ends its
    span at a `\"` that the shell does not treat as closing, which can expose an
    interior `;` as a real command position and produce a spurious FIRE rather
    than a miss. Caught in review on ai-config#1957 and pinned by a test. Single
    quotes stay escape-blind on purpose: the shell processes no escapes inside
    `'...'`, so `'[^']*'` is exactly right there.

    "Escape-aware" here means two escapes rather than one, and the first fix
    shipped only one. An escaped QUOTE is the obvious case. An escaped NEWLINE
    is the one that bites, because bash reads it inside double quotes as a line
    continuation, keeps the quote open, and hands the whole thing over as one
    argument. Both are covered, and both are pinned by tests --- the second one
    against real `bash` output rather than against what the pattern looks like
    it should do. Caught in review on ai-config#1957, round 2.

A COMMAND SUBSTITUTION IS INVISIBLE, WHICH CUTS THE RIGHT WAY
-------------------------------------------------------------
A check whose output is captured --- `$(gh issue list ...)`, quoted or not ---
never reaches a command position, so it is not seen as a check and the call does
not fire. That is not an oversight, and it is the single most important thing
the narrowing buys:

    if [ -z "$(gh issue list -R o/r --search "x")" ]; then
      gh issue create -R o/r --title t
    fi

This is REAL gating. The create genuinely runs only when the search came back
empty, all inside one call, and firing on it would be a false positive on
precisely the behaviour the rule wants.

The same blindness costs a miss on the capture-and-ignore shape,
`HITS=$(gh issue list ...) ; gh issue create ...`, where the result is captured
and then not branched on. Separating the two would mean deciding whether a
conditional actually consumes the captured value, which is real shell analysis.
Missing a defect is the cheap direction; firing on a correct conditional is not.

KNOWN FALSE POSITIVES, ACCEPTED
-------------------------------
A list whose output FEEDS the create rather than gating it, e.g.

    gh issue list --label bug > /tmp/report.md
    gh issue create --title "bug roundup" --body-file /tmp/report.md

This is a genuine misfire. Detecting it would mean tracking the redirect target
into the create's `--body-file`, which is more machinery than a one-line note is
worth.

REGISTERED UNDER Bash ONLY
--------------------------
Unlike the sibling, there is no `mcp__github__.*` registration, and its absence
is deliberate rather than an oversight. The condition is "two commands in one
call", and an MCP tool call carries exactly one operation, so the shape is
unrepresentable there. A dual registration would add a matcher that can never
fire, which reads to a later maintainer as coverage.

FAILS OPEN
----------
Malformed stdin, a non-dict payload, a non-string command, or any exception all
return 0 with nothing on stdout. A reminder that cannot establish its own
precondition must not fire --- see `fail-fast.md` on bounding a fallback.
"""
import json
import os
import re
import sys

# One pattern for both halves. Anchored to a command position, tolerant of
# env-assignment prefixes, and classified afterwards by the ROLES table --- a
# subcommand this table does not name (`gh pr view`, `gh search repos`,
# `glab mr merge`) is simply not a match.
RX_COMMAND = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?P<tool>gh|glab)\s+(?P<obj>issue|pr|mr|search)\s+"
    r"(?P<verb>list|create|issues|prs)\b",
    re.MULTILINE,
)

# (tool, object, verb) -> (role, kind). `kind` is what must agree between the
# two halves; `pr` covers GitLab's merge requests, which are the same object.
ROLES = {
    ("gh", "issue", "list"): ("check", "issue"),
    ("gh", "issue", "create"): ("create", "issue"),
    ("gh", "pr", "list"): ("check", "pr"),
    ("gh", "pr", "create"): ("create", "pr"),
    ("gh", "search", "issues"): ("check", "issue"),
    ("gh", "search", "prs"): ("check", "pr"),
    ("glab", "issue", "list"): ("check", "issue"),
    ("glab", "issue", "create"): ("create", "issue"),
    ("glab", "mr", "list"): ("check", "pr"),
    ("glab", "mr", "create"): ("create", "pr"),
}

# `<<WORD`, `<<'WORD'`, `<<-"WORD"`; then the rest of the opener line, which may
# carry a redirect or a pipe on either side of the opener; then the body up to a
# terminator that `<<-` allows to be tab-indented.
RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

# A single- or double-quoted span, scanned left to right so the quote that opens
# first wins. EVERY branch here matches a newline -- the negated classes by
# construction, and the escape class because it is `[\s\S]` rather than `.` --
# which is the point: a multi-line `-b "..."` body is one span, continuation
# backslashes and all.
#
# The double-quoted branch is ESCAPE-AWARE and the single-quoted one is not,
# matching the shell: inside `'...'` a backslash is literal and only `'` closes,
# while inside `"..."` a `\"` does not close. A naive `"[^"]*"` therefore ends
# the span at an escaped quote, which can expose a `;` that shell would have
# treated as ordinary text -- a FALSE POSITIVE rather than the miss the
# NORMALIZATION note claims. Caught in review on ai-config#1957 with
# `echo "before\"; gh issue list -R o/r; gh issue create -R o/r \" after"`.
#
# The escape class is `\\[\s\S]` rather than `\\.`, and the difference is a
# second false positive rather than pedantry. `.` does not match a newline
# without `re.DOTALL`, so `\\.` cannot consume a backslash-NEWLINE -- which bash
# treats as a line continuation INSIDE double quotes, leaving the quote open and
# the whole thing one argument. Confirmed by running it:
#
#     $ bash -c 'echo "before\
#     > gh issue list -R o/r; gh issue create -R o/r"'
#     beforegh issue list -R o/r; gh issue create -R o/r
#
# One `echo`, nothing else run. With `\\.` the span failed to match at all, so
# the text after the continuation was left exposed at a command position --
# a REGRESSION against the naive `"[^"]*"`, whose negated class matched newlines
# by accident. Caught in review on ai-config#1957, round 2.
#
# `[\s\S]` is used rather than the `re.DOTALL` flag so the pattern stays
# self-contained: there is no other `.` here for the flag to affect, and a flag
# set at compile time is easy to drop when the pattern is later edited.
#
# The two alternation branches are disjoint on their first character, so this
# stays linear rather than backtracking.
RX_QUOTED = re.compile(r"'[^']*'|\"(?:\\[\s\S]|[^\"\\])*\"")

NOTE = """\
A gating check and the action it gates are in the same Bash call.

    check:  {check}
    create: {create}

Both will run. The search's result arrives at the same instant as the create, so
nothing can branch on it --- the check is present, it executes, and it gates
nothing. The rule is `shared/workflow/report-mistakes-proactively.md`'s tracker
dupe-check, recorded as ai-config#1954.

Run the query in its OWN call, read what it returns, and only then compose the
create. If the search finds an existing {kind}, the disposition is to add to it
rather than to file again.

If the list here FEEDS the create rather than gating it --- building a body from
its output --- carry on. This is a reminder, not a refusal.
"""


def normalize(command):
    """Strip heredoc bodies and quoted spans, keeping every real separator.

    Both strips only remove text, and neither inserts `;`, `&`, `|`, or a
    newline, so neither can manufacture a command position that was not already
    there. The heredoc strip keeps the opener line's tail, which is still shell.
    """
    without_bodies = RX_HEREDOC.sub(lambda m: m.group(2), command)
    return RX_QUOTED.sub(" ", without_bodies)


def find_chained_pair(command):
    """Return (check_text, create_text, kind) for the earliest offending pair.

    Returns None when no CHECK of a given object kind precedes a CREATE of that
    same kind. `finditer` yields matches in ascending position, so one forward
    pass remembering the first check per kind decides the ordering constraint
    without comparing offsets.
    """
    first_check = {}
    for match in RX_COMMAND.finditer(normalize(command)):
        tool = match.group("tool")
        obj = match.group("obj")
        verb = match.group("verb")
        role_kind = ROLES.get((tool, obj, verb))
        if role_kind is None:
            continue
        role, kind = role_kind
        text = f"{tool} {obj} {verb}"
        if role == "check":
            first_check.setdefault(kind, text)
        elif kind in first_check:
            return (first_check[kind], text, kind)
    return None


def _read_payload() -> tuple[dict, bool]:
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
        if is_dry_run:
            print(f"warn-dupe-check-chained-to-create: unreadable hook input ({exc})",
                  file=sys.stderr)
        return {}, is_dry_run


def main():
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if not isinstance(payload, dict):
        return 0  # fail open: the harness always sends an object

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = (tool_input.get("command")
               or tool_input.get("cmd")
               or tool_input.get("CommandLine")
               or "")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        pair = find_chained_pair(command)
    except Exception as exc:  # fail open on any parse trouble
        print("warn-dupe-check-chained-to-create: could not evaluate "
              f"({exc})", file=sys.stderr)
        return 0

    if pair is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    check_text, create_text, kind = pair

    # No `permissionDecision` key at all: an absent decision defers to the
    # normal permission flow. Naming "allow" would suppress a prompt the user
    # would otherwise have seen.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                check=check_text, create=create_text, kind=kind),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"`{check_text}` and `{create_text}` are in one Bash call, so the "
            "check runs at the same instant as the create and gates nothing. "
            "Run the query in its own call and read the result first."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
