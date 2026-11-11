#!/usr/bin/env python3
"""PreToolUse reminder: filing an issue without `ai-authored` or a priority.

`shared/workflow/issue-first.md`'s "Label an agent-filed issue with its
authorship and its model" section requires every issue an agent files into a
repo we administrate to carry `ai-authored` and `model:<model-id>`, set in the
creating command rather than as a follow-up edit.

The same section's "Set the priority when you file" paragraph requires one of
`P1`, `P2` or `P3` in the same creating command (Ezra, ai-config#3140: "when
filing issues, assign priority level, task size, and all other applicable
fields and labels"). An issue filed without one waits for the weekly triage
pass, and a pass on 2026-11-11 found 190 open issues in ai-config with no
priority label (ai-config#5306).
Each missing label gets its own paragraph in the reminder, so a create that
carries one of the two is told only about the other.

WHY A HOOK RATHER THAN THE RULE ALONE
-------------------------------------
`shared/workflow/disclose-agent-authorship.md` scopes its marker line to
comment BODIES and explicitly excludes an issue body, so an agent-filed issue
is the one artifact that discloses nothing. The labels are what close that,
and they are consulted at read time while the omission happens at composition
time --- the shape `shared/workflow/algorithmatize-checks.md` says to
mechanize rather than restate. The condition is lexically decidable over the
one command, and this corpus already intercepts that exact surface with
`warn-pr-create-without-dupe-check.py`.

Nothing downstream reports the omission either. The create succeeds, the issue
URL comes back, and the unlabelled issue is indistinguishable from one the
maintainer typed --- which is the whole defect.

THE CHECK
---------
Bash: `gh issue create` / `glab issue create` at a COMMAND POSITION, with
heredoc bodies stripped, and no `ai-authored`, or no `P1`/`P2`/`P3`, in a
label flag's value.

MCP: `mcp__github__issue_write` with `method` == "create" (and the legacy
`mcp__github__create_issue`), with no `ai-authored`, or no `P1`/`P2`/`P3`, in
its `labels`.

Command-position anchoring is load-bearing rather than tidiness, for the
reason `warn-pr-create-without-dupe-check.py` records at length: this corpus
quotes `gh issue create` constantly --- in fragments, in issue bodies, in
heredocs documenting the workflow, and in this very docstring --- so a
substring matcher would fire on every reply that cites the rule it enforces.
A heredoc body is prose, so it is stripped before matching; the opener line's
tail is still shell and is kept, since `gh issue create --body-file -` behind
a heredoc is the idiomatic way to file with a long body.

The discharge splits that same heredoc-stripped text into shell tokens and
reads a label flag's argument, covering `--label a --label b`, `--label a,b`,
`--label=a`, `--labels`, and `-l a`. `ai-authored` quoted inside a title or a
body sits at no argument position, so it does not discharge.

WHY WARN RATHER THAN BLOCK
--------------------------
Three reasons, all pointing the same way.

An unlabelled issue is cheap: `gh issue edit <N> --add-label` fixes it in one
command, and the issue itself --- the durable record --- already exists. A
blocked `gh issue create` is expensive, because filing is the act that makes a
problem visible to every other session, and
`shared/workflow/report-mistakes-proactively.md`'s "filing is not gated on
approval" says a redundant entry is cheap while a lost one is not.

The rule is also scoped to repos we administrate, and this hook cannot tell
which repo a command targets is one of ours. An issue filed upstream through
`skills/sup/SKILL.md` legitimately carries neither label, so some fraction of
firings are expected false positives. That is affordable for a reminder and
would be intolerable for a refusal.

And the labels may not exist yet in the target repo, in which case the rule
itself says to file anyway and report the gap.

FAILS OPEN
----------
Any parse trouble, an unrecognized payload shape, or a missing command returns
0 silently. A reminder that cannot establish its own precondition must not
fire --- see `shared/principles/fail-fast.md` on keeping a fallback explicit
and bounded.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# `gh issue create` / `glab issue create` at a command position. The separator
# class includes `(`, `{`, and the backtick so `URL=$(gh issue create ...)` and
# URL=`gh issue create ...` are real creates, matching
# warn-pr-create-without-dupe-check.py's RX_ISSUE_CREATE.
RX_ISSUE_CREATE = re.compile(
    r"(?:^|[;&|\n({`])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:gh\s+issue\s+create|glab\s+issue\s+create)\b",
    re.MULTILINE,
)

# A heredoc body is prose, not commands. Strip it before position matching,
# keeping the opener line's tail (a redirect or pipe may follow the opener).
RX_HEREDOC = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?([^\n]*)\n"
    r".*?\n[ \t]*\1\b",
    re.DOTALL,
)

AUTHORSHIP_LABEL = "ai-authored"

# The three priority labels shared/workflow/triage-backlog.md defines.
PRIORITY_LABELS = frozenset(("P1", "P2", "P3"))


def split_labels(value: str) -> set:
    """The whole-token labels in one label VALUE (one flag argument, possibly
    comma-joined). Whole tokens, because a substring match would let
    `ai-authored-improvement`, `model:not-ai-authored` or `P10` discharge a
    reminder."""
    return {part.strip() for part in value.split(",")}


def carries_priority(labels: set) -> bool:
    """True when `labels` holds a priority label. GitHub matches a label name
    without regard to case, so `p2` applies `P2` and discharges the reminder."""
    return bool(PRIORITY_LABELS & {label.upper() for label in labels})


# Inside single quotes nothing is a command: a commit message or echo that
# quotes `gh issue create` inline-code-style must not read as a create at
# command position. Double-quoted spans stay, since a backtick runs there.
RX_SINGLE_QUOTED = re.compile(r"'[^']*'")


def strip_single_quoted(command: str) -> str:
    """Blank single-quoted spans before position matching, keeping length."""
    return RX_SINGLE_QUOTED.sub(lambda m: "'" + " " * (len(m.group(0)) - 2) + "'", command)


LABEL_FLAGS = ("--label", "--labels", "-l")

# Fallback for a command shlex cannot tokenize: the value of a `--label` /
# `--labels` / `-l` flag, separated by `=` or whitespace. A quoted value runs to
# its closing quote, so `"ai-authored, P2"` is read whole; a bare one runs to
# the next space.
RX_LABEL_FLAG = re.compile(
    r"(?:--labels?|(?<![-\w])-l)[=\s]+(?:\"([^\"]*)\"|'([^']*)'|([^'\"\s]+))"
)

BASH_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

MCP_ISSUE_CREATE_TOOLS = ("mcp__github__issue_write", "mcp__github__create_issue")

NOTE_AUTHORSHIP = """\
This issue is being filed with no `ai-authored` label.

`issue-first.md`, "Label an agent-filed issue with its authorship and its
model": every issue an agent files into a repo we administrate carries
`ai-authored` and `model:<model-id>`, set in the creating command rather than
as a follow-up edit.

`disclose-agent-authorship.md` scopes its marker line to comment bodies and
excludes an issue body, so without the labels nothing distinguishes this from
an issue the maintainer typed --- it goes out under their login, as
`type: User`.

    gh issue create ... --label ai-authored --label "model:<model-id>"
    glab issue create ... --label "ai-authored,model:<model-id>"

Normalize the model id first (strip a context-window suffix, resolve an
alias), and create the labels once per repo if they are missing --- see
shared/workflow/label-agent-filed-issues.md.

Carry on if this is deliberate: an issue filed into a repo we do NOT
administrate takes neither label, and a repo whose labels cannot be created
still gets the issue. This is a reminder, not a refusal.
"""

NOTE_PRIORITY = """\
This issue is being filed with no priority label.

`issue-first.md`, "Set the priority when you file": every issue an agent files
into a repo we administrate carries one of `P1`, `P2` or `P3` in the creating
command (Ezra, ai-config#3140). `triage-backlog.md` defines the three:

    P1  blocks work now, merged bad state, or hides a failure
    P2  an actionable defect or improvement with a workaround (the default)
    P3  a directive with no acceptance criterion, a question, a nice-to-have

    gh issue create ... --label P2
    glab issue create ... --label P2

Before filing at all, search for the tracking issue of the defect family this
belongs to: a new symptom of a tracked family is a comment on its tracker, not
a new issue.

Carry on if this is deliberate: an issue filed into a repo we do NOT
administrate takes no priority label, and a repo that lacks the labels still
gets the issue. This is a reminder, not a refusal.
"""


def build_note(labels: set) -> str | None:
    """The reminder for a create carrying `labels`, or None when it has both an
    authorship label and a priority label. Both are matched without regard to
    case, as GitHub matches label names."""
    parts = []
    if AUTHORSHIP_LABEL not in {label.lower() for label in labels}:
        parts.append(NOTE_AUTHORSHIP)
    if not carries_priority(labels):
        parts.append(NOTE_PRIORITY)
    if not parts:
        return None
    return "\n".join(parts)


def strip_heredocs(command: str) -> str:
    """Remove heredoc BODIES, keeping the rest of the opener line."""
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def command_labels(command: str) -> set:
    """Every label named in a label flag's ARGUMENT."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        values = ["".join(groups) for groups in RX_LABEL_FLAG.findall(command)]
    else:
        values = []
        for index, token in enumerate(tokens):
            for flag in LABEL_FLAGS:
                if token == flag and index + 1 < len(tokens):
                    values.append(tokens[index + 1])
                elif token.startswith(flag + "="):
                    values.append(token[len(flag) + 1:])
            # The short flag also takes a glued value: `-lP2`.
            if token.startswith("-l") and len(token) > 2 and token[2] != "=":
                values.append(token[2:])
    labels = set()
    for value in values:
        labels |= split_labels(value)
    return labels


def evaluate_bash(command: str) -> str | None:
    """Return warning text when a Bash issue create lacks a required label."""
    if not command:
        return None
    stripped = strip_heredocs(command)
    if not RX_ISSUE_CREATE.search(strip_single_quoted(stripped)):
        return None
    return build_note(command_labels(stripped))


def _label_values(tool_input: dict) -> list:
    labels = tool_input.get("labels")
    if isinstance(labels, str):
        return [labels]
    if isinstance(labels, (list, tuple)):
        # A label may arrive as an object with a `name`, the shape the REST
        # API returns, as well as a bare string.
        return [
            str(item.get("name", "")) if isinstance(item, dict) else str(item)
            for item in labels
        ]
    return []


def evaluate_mcp(tool_name: str, tool_input: dict) -> str | None:
    """Return warning text when an MCP issue create lacks a required label."""
    if tool_name not in MCP_ISSUE_CREATE_TOOLS:
        return None
    # issue_write also updates and closes; only a create is in scope. The
    # legacy create_issue tool has no method field, so a missing method on
    # THAT tool still counts as a create.
    method = tool_input.get("method")
    if tool_name == "mcp__github__issue_write" and method != "create":
        return None
    labels = set()
    for value in _label_values(tool_input):
        labels |= split_labels(value)
    return build_note(labels)


def _emit(note: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        }
    }))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if tool_name in BASH_TOOLS:
        command = (
            tool_input.get("command")
            or tool_input.get("CommandLine")
            or tool_input.get("cmd")
            or tool_input.get("script")
            or ""
        )
        warning = evaluate_bash(str(command))
    else:
        warning = evaluate_mcp(tool_name, tool_input)

    if warning:
        _emit(warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
