#!/usr/bin/env python3
"""PreToolUse reminder: filing an issue without the `ai-authored` label.

`shared/workflow/issue-first.md`'s "Label an agent-filed issue with its
authorship and its model" section requires every issue an agent files into a
repo we administrate to carry `ai-authored` and `model:<model-id>`, set in the
creating command rather than as a follow-up edit.

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
heredoc bodies stripped, and no `ai-authored` anywhere in the command.

MCP: `mcp__github__issue_write` with `method` == "create" (and the legacy
`mcp__github__create_issue`), with no `ai-authored` in its `labels`.

Command-position anchoring is load-bearing rather than tidiness, for the
reason `warn-pr-create-without-dupe-check.py` records at length: this corpus
quotes `gh issue create` constantly --- in fragments, in issue bodies, in
heredocs documenting the workflow, and in this very docstring --- so a
substring matcher would fire on every reply that cites the rule it enforces.
A heredoc body is prose, so it is stripped before matching; the opener line's
tail is still shell and is kept, since `gh issue create --body-file -` behind
a heredoc is the idiomatic way to file with a long body.

The `ai-authored` discharge is deliberately a plain substring over the whole
command, not a parse of `--label`. The flag has too many accepted spellings
(`--label a --label b`, `--label a,b`, `-l a`, `--label=a`, glab's
comma-separated single flag) for a partial parser to be safer than a
containment test, and the failure direction of an over-broad discharge here is
one missed reminder rather than a wrong refusal.

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
import sys

# `gh issue create` / `glab issue create` at a command position. The separator
# class includes `(` and `{` so `URL=$(gh issue create ...)` is a real create,
# matching warn-pr-create-without-dupe-check.py's RX_ISSUE_CREATE.
RX_ISSUE_CREATE = re.compile(
    r"(?:^|[;&|\n({])\s*"
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

BASH_TOOLS = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

MCP_ISSUE_CREATE_TOOLS = ("mcp__github__issue_write", "mcp__github__create_issue")

NOTE = """\
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


def strip_heredocs(command: str) -> str:
    """Remove heredoc BODIES, keeping the rest of the opener line."""
    return RX_HEREDOC.sub(lambda m: m.group(2), command)


def creates_issue(command: str) -> bool:
    """True when the command creates an issue at a command position."""
    return bool(RX_ISSUE_CREATE.search(strip_heredocs(command)))


def evaluate_bash(command: str) -> str | None:
    """Return warning text when a Bash issue create carries no authorship label."""
    if not command or not creates_issue(command):
        return None
    if AUTHORSHIP_LABEL in command:
        return None
    return NOTE


def _label_values(tool_input: dict) -> list:
    labels = tool_input.get("labels")
    if isinstance(labels, str):
        return [labels]
    if isinstance(labels, (list, tuple)):
        return [str(item) for item in labels]
    return []


def evaluate_mcp(tool_name: str, tool_input: dict) -> str | None:
    """Return warning text when an MCP issue create carries no authorship label."""
    if tool_name not in MCP_ISSUE_CREATE_TOOLS:
        return None
    # issue_write also updates and closes; only a create is in scope. The
    # legacy create_issue tool has no method field, so a missing method on
    # THAT tool still counts as a create.
    method = tool_input.get("method")
    if tool_name == "mcp__github__issue_write" and method != "create":
        return None
    if any(AUTHORSHIP_LABEL in value for value in _label_values(tool_input)):
        return None
    return NOTE


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
        print(warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
