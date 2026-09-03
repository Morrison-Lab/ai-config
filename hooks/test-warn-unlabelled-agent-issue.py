#!/usr/bin/env python3
"""Tests for warn-unlabelled-agent-issue.py.

The NEGATIVE cases carry the weight, in both directions. A guard that fired on
prose quoting `gh issue create` would go off in every reply that cites the rule
it enforces --- this corpus quotes that command constantly --- and one that
fired on an already-labelled create would be pure noise.

Run: python3 hooks/test-warn-unlabelled-agent-issue.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "guard", HERE / "warn-unlabelled-agent-issue.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

BASH_FIRES = [
    ("bare gh issue create", 'gh issue create --title "t" --body "b"'),
    ("glab issue create", 'glab issue create --title "t" --description "b"'),
    ("a different label only", 'gh issue create --title "t" --label bug'),
    ("command-substitution capture", 'URL=$(gh issue create --title "t" --body "b")'),
    ("after &&", 'git status && gh issue create --title "t" --body "b"'),
    ("after a newline", 'set -e\ngh issue create --title "t" --body "b"'),
    ("env-assignment prefix", 'GH_TOKEN=x gh issue create --title "t"'),
    (
        "body-file behind a heredoc, unlabelled",
        "gh issue create --title 't' --body-file - <<'EOF'\nsome body\nEOF",
    ),
    ("--repo form", 'gh issue create --repo O/R --title "t" --body "b"'),
]

BASH_QUIET = [
    ("labelled, repeated flags", 'gh issue create --title "t" --label ai-authored --label "model:x"'),
    ("labelled, comma-separated glab form", 'glab issue create --title "t" --label "ai-authored,model:x"'),
    ("labelled with --label=", 'gh issue create --title "t" --label=ai-authored'),
    ("labelled with -l", 'gh issue create --title "t" -l ai-authored'),
    ("not a create at all", "gh issue list --state all --search 'x'"),
    ("editing labels on an existing issue", 'gh issue edit 12 --add-label ai-authored'),
    ("a PR create", 'gh pr create --title "t" --body "b"'),
    ("no gh command at all", "git commit -F /tmp/msg.txt"),
    (
        "the phrase quoted inside a heredoc body",
        "cat > /tmp/note.md <<'EOF'\nRun gh issue create to file it.\nEOF",
    ),
    (
        "the phrase mid-sentence in a commit message",
        'git commit -m "document the gh issue create workflow"',
    ),
]

MCP_FIRES = [
    ("issue_write create, no labels", "mcp__github__issue_write", {"method": "create", "title": "t"}),
    (
        "issue_write create, other labels",
        "mcp__github__issue_write",
        {"method": "create", "labels": ["bug", "P3"]},
    ),
    ("legacy create_issue, no labels", "mcp__github__create_issue", {"title": "t"}),
    (
        "labels given as a non-list of the wrong value",
        "mcp__github__issue_write",
        {"method": "create", "labels": "bug"},
    ),
]

MCP_QUIET = [
    (
        "issue_write create, labelled",
        "mcp__github__issue_write",
        {"method": "create", "labels": ["ai-authored", "model:x"]},
    ),
    (
        "issue_write create, labelled as a bare string",
        "mcp__github__issue_write",
        {"method": "create", "labels": "ai-authored"},
    ),
    (
        "issue_write update is not a create",
        "mcp__github__issue_write",
        {"method": "update", "labels": ["bug"]},
    ),
    (
        "issue_write with no method is not a create",
        "mcp__github__issue_write",
        {"labels": ["bug"]},
    ),
    ("an unrelated MCP tool", "mcp__github__add_issue_comment", {"body": "hi"}),
    ("an unrelated MCP read", "mcp__github__issue_read", {"method": "get"}),
]


def main() -> int:
    failures = 0

    for label, command in BASH_FIRES:
        if guard.evaluate_bash(command) is None:
            print(f"::error::expected a warning: {label}\n    {command}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   fires: {label}")

    for label, command in BASH_QUIET:
        result = guard.evaluate_bash(command)
        if result is not None:
            print(f"::error::expected silence: {label}\n    {command}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet: {label}")

    for label, tool, payload in MCP_FIRES:
        if guard.evaluate_mcp(tool, payload) is None:
            print(f"::error::expected a warning (mcp): {label}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   fires (mcp): {label}")

    for label, tool, payload in MCP_QUIET:
        if guard.evaluate_mcp(tool, payload) is not None:
            print(f"::error::expected silence (mcp): {label}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet (mcp): {label}")

    # The message must name both labels and the escape, or it teaches nothing.
    message = guard.evaluate_bash('gh issue create --title "t"')
    for needed in (
        "ai-authored",
        "model:<model-id>",
        "label-agent-filed-issues.md",
        "not a refusal",
    ):
        if needed not in message:
            print(f"::error::warning text omits {needed!r}", file=sys.stderr)
            failures += 1

    total = len(BASH_FIRES) + len(BASH_QUIET) + len(MCP_FIRES) + len(MCP_QUIET)
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} warn-unlabelled-agent-issue cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
