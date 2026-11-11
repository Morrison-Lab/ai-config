#!/usr/bin/env python3
"""Tests for warn-unlabelled-agent-issue.py.

The guard asks for two things on a create: the `ai-authored` label and one of
the priority labels `P1`, `P2`, `P3`. The FIRES lists hold creates missing the
authorship label, the ONE_MISSING lists pin that each label is asked for
separately. The QUIET lists hold creates carrying both labels, and commands
that are not creates.

The NEGATIVE cases carry the weight, in both directions. A guard that fired on
prose quoting `gh issue create` would go off in every reply that cites the rule
it enforces --- this corpus quotes that command constantly --- and one that
fired on an already-labelled create would be pure noise.

Run: python3 hooks/test-warn-unlabelled-agent-issue.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

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
    ("backtick command-substitution capture", 'URL=`gh issue create --title "t" --body "b"`'),
    ("a label that only contains the authorship label", 'gh issue create --title "t" --label ai-authored-improvement'),
    ("a model label that only contains the authorship label", 'gh issue create --title "t" --label "model:not-ai-authored-review"'),
    ("after &&", 'git status && gh issue create --title "t" --body "b"'),
    ("after a newline", 'set -e\ngh issue create --title "t" --body "b"'),
    ("env-assignment prefix", 'GH_TOKEN=x gh issue create --title "t"'),
    ("unlabelled inside backticks, the labels on the next command",
     'URL=' + chr(96) + 'gh issue create -t x' + chr(96) + '; gh pr create -l ai-authored,P2'),
    ("unlabelled behind an environment assignment, the labels on the next command",
     'GH_TOKEN=x gh issue create -t x; gh pr create -l ai-authored,P2'),
    ("the labels belong to an issue edit before the create",
     'gh issue edit 3 -l ai-authored,P2; gh issue create -t x'),
    ("unlabelled glab create, the labels on the next command",
     'glab issue create -t x; gh pr create -l ai-authored,P2'),
    ("unlabelled inside a double-quoted command substitution",
     'echo "$(gh issue create -t x)"'),
    ("the labels belong to an echo that only names the command",
     'echo gh issue create -l ai-authored,P2; gh issue create --title "t"'),
    (
        "body-file behind a heredoc, unlabelled",
        "gh issue create --title 't' --body-file - <<'EOF'\nsome body\nEOF",
    ),
    ("--repo form", 'gh issue create --repo O/R --title "t" --body "b"'),
    (
        "both labels on an earlier command in the chain",
        'gh pr create --label P2 --label ai-authored && gh issue create --title "t"',
    ),
    (
        "both labels on a later command in the chain",
        'gh issue create --title "t"; gh issue edit 3 --add-label x -l ai-authored,P2',
    ),
    (
        "both labels on the next line's command",
        'gh issue create --title "t"\ngh pr create --label ai-authored,P2',
    ),
    (
        "a trailing comment, then both labels on the next line's command",
        'gh issue create --title "t" # note\ngh pr create --label ai-authored,P2',
    ),
    (
        "an apostrophe in a trailing comment, labels on the next line",
        "gh issue create --title t # don't\ngh pr create --label ai-authored,P2",
    ),
    (
        "both labels in a trailing comment",
        'gh issue create --title "t" # --label ai-authored --label P2',
    ),
    (
        "the second of two creates is unlabelled",
        'gh issue create --title "a" -l ai-authored,P2 && gh issue create --title "b"',
    ),
    (
        "the label named in a heredoc body, not in a flag",
        "gh issue create --title 't' --body-file - <<'EOF'\n"
        "We should require the ai-authored label on filed issues.\nEOF",
    ),
    (
        "the label named in the title",
        'gh issue create --title "warn-unlabelled-agent-issue misses ai-authored" --body "b"',
    ),
    (
        "the label named in the body",
        'gh issue create --title "t" --body "issue-first.md says to pass ai-authored"',
    ),
    (
        "the label FLAG quoted inside the body",
        'gh issue create --title "t" '
        '--body "the rule is to pass --label ai-authored when filing"',
    ),
    (
        "the label FLAG quoted inside the title",
        'gh issue create '
        '--title "warn-unlabelled-agent-issue: --label ai-authored in a body" '
        '--body "b"',
    ),
]

BASH_QUIET = [
    ("labelled, repeated flags", 'gh issue create --title "t" --label ai-authored --label "model:x" --label P2'),
    ("labelled, comma-separated glab form", 'glab issue create --title "t" --label "ai-authored,model:x,P3"'),
    ("labelled with --label=", 'gh issue create --title "t" --label=ai-authored --label=P1'),
    ("labelled with -l", 'gh issue create --title "t" -l ai-authored -l P2'),
    ("labelled with -l and a quoted pair", 'gh issue create -l "ai-authored,model:x,P2"'),
    ("labelled with --labels=", 'gh issue create --labels=ai-authored,model:x,P2'),
    ("unbalanced quoting falls back to the regex", 'gh issue create --label ai-authored --label P2 --title "t'),
    ("the command quoted inline-code-style inside single quotes",
     "git commit -m 'mentions of `gh issue create` in prose'"),
    ("a lowercase priority, which GitHub resolves to the label",
     'gh issue create --title "t" --label ai-authored --label p2'),
    ("a mixed-case authorship label, which GitHub resolves to the label",
     'gh issue create --title "t" --label AI-Authored --label P2'),
    ("labelled inside a command substitution",
     'URL=$(gh issue create --title "t" --label ai-authored --label P3) && echo "$URL"'),
    ("labelled inside backticks",
     'URL=`gh issue create --title "t" --label ai-authored --label P3`'),
    ("labelled across a backslash-newline continuation",
     'gh issue create --title "t" \\\n  --label ai-authored \\\n  --label P2'),
    ("labelled, with a newline inside the quoted body",
     'gh issue create --body "line one\nline two" --label ai-authored --label P2'),
    ("labelled, then an unrelated command on the next line",
     'gh issue create --title "t" -l ai-authored,P2\ngit status'),
    ("labelled, with a quoted title that starts with a hash",
     'gh issue create --title "#5 follow-up" --label ai-authored --label P2'),
    ("labelled, with a quoted body that starts with a hash",
     'gh issue create --title "t" --body "# Heading" --label ai-authored,P2'),
    ("labelled, then a trailing comment with an apostrophe",
     "gh issue create --title t --label ai-authored,P2 # don't"),
    ("two labelled creates",
     'gh issue create --title "a" -l ai-authored,P2 && gh issue create --title "b" -l ai-authored,P3'),
    ("unbalanced quoting with a glued short flag",
     'gh issue create -lai-authored -lP2 --title "t'),
    ("a glued short flag", 'gh issue create --title "t" -lai-authored -lP2'),
    ("labelled, after an issue list that carries no labels",
     'gh issue list --state all; gh issue create -t x -l ai-authored,P2'),
    ("labelled, after an empty quoted body",
     'gh issue create --title "t" --body "" --label ai-authored --label P2'),
    ("labelled, behind an environment assignment",
     'GH_TOKEN=x gh issue create --title "t" -l ai-authored -l P2'),
    ("labelled inside a double-quoted command substitution, read by the fallback",
     'echo "$(gh issue create -t x -l ai-authored,P2)"'),
    ("fallback: the bare label ends at a semicolon",
     'echo "$(gh issue create -t x -l ai-authored,P2; true)"'),
    ("fallback: the bare label ends at a pipe",
     'echo "$(gh issue create -t x -l ai-authored,P2|cat)"'),
    ("fallback: the bare label ends at an ampersand",
     'echo "$(gh issue create -t x -l ai-authored,P2&& true)"'),
    ("fallback: the bare label ends at a backtick",
     'echo "' + chr(96) + 'gh issue create -t x -l ai-authored,P2' + chr(96) + '"'),
    ("labelled, with the label flags before a quoted operator title",
     'gh issue create -l ai-authored,P2 --title ";"'),
    ("unbalanced quoting with a comma-and-space value",
     'gh issue create --label "ai-authored, P2" --title "t'),
    ("unbalanced quoting with a single-quoted value",
     "gh issue create --label 'ai-authored,P2' --title \"t"),
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

# (label, command, text the reminder must carry, text it must not carry)
AUTHORSHIP_MARK = "no `ai-authored` label"
PRIORITY_MARK = "no priority label"

BASH_ONE_MISSING = [
    (
        "authorship present, priority missing",
        'gh issue create --title "t" --label ai-authored --label "model:x"',
        PRIORITY_MARK,
        AUTHORSHIP_MARK,
    ),
    (
        "priority present, authorship missing",
        'gh issue create --title "t" --label P2',
        AUTHORSHIP_MARK,
        PRIORITY_MARK,
    ),
    (
        "a label that only contains a priority label",
        'gh issue create --title "t" --label ai-authored --label P10',
        PRIORITY_MARK,
        AUTHORSHIP_MARK,
    ),
    (
        "unbalanced quoting, a spaced value missing the priority",
        'gh issue create --label "ai-authored, model:x" --title "t',
        PRIORITY_MARK,
        AUTHORSHIP_MARK,
    ),
    (
        "the priority named in the title, not in a flag",
        'gh issue create --title "P1: the gate is open" --label ai-authored',
        PRIORITY_MARK,
        AUTHORSHIP_MARK,
    ),
]

MCP_ONE_MISSING = [
    (
        "issue_write create, authorship present, priority missing",
        "mcp__github__issue_write",
        {"method": "create", "labels": ["ai-authored", "model:x"]},
        PRIORITY_MARK,
        AUTHORSHIP_MARK,
    ),
    (
        "issue_write create, priority present, authorship missing",
        "mcp__github__issue_write",
        {"method": "create", "labels": ["bug", "P3"]},
        AUTHORSHIP_MARK,
        PRIORITY_MARK,
    ),
]

MCP_FIRES = [
    (
        "issue_write create with a label that only contains the authorship label",
        "mcp__github__issue_write",
        {"method": "create", "labels": ["ai-authored-improvement", "model:x"]},
    ),
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
        {"method": "create", "labels": ["ai-authored", "model:x", "P2"]},
    ),
    (
        "issue_write create, labelled as a bare comma-joined string",
        "mcp__github__issue_write",
        {"method": "create", "labels": "ai-authored,P2"},
    ),
    (
        "issue_write create, labels given as objects",
        "mcp__github__issue_write",
        {"method": "create", "labels": [{"name": "ai-authored"}, {"name": "p1"}]},
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

    for label, command, wanted, unwanted in BASH_ONE_MISSING:
        result = guard.evaluate_bash(command) or ""
        if wanted not in result or unwanted in result:
            print(f"::error::wrong reminder: {label}\n    {command}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   one reminder: {label}")

    for label, tool, payload, wanted, unwanted in MCP_ONE_MISSING:
        result = guard.evaluate_mcp(tool, payload) or ""
        if wanted not in result or unwanted in result:
            print(f"::error::wrong reminder (mcp): {label}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   one reminder (mcp): {label}")

    # With scripts/lib/shellcmd.py missing, the hook says so on stderr and
    # reads label flags across the whole command: a bare create still warns
    # and a labelled one stays quiet. The copy sits in a directory tree that
    # has no scripts/lib beside it.
    with tempfile.TemporaryDirectory() as tree:
        copy_dir = pathlib.Path(tree) / "hooks"
        copy_dir.mkdir()
        copy = copy_dir / "warn-unlabelled-agent-issue.py"
        shutil.copy(HERE / "warn-unlabelled-agent-issue.py", copy)
        runs = {}
        for name, command in (
            ("bare", "gh issue create -t x"),
            ("labelled", "gh issue create -t x -l ai-authored,P2"),
        ):
            runs[name] = subprocess.run(
                [sys.executable, str(copy)],
                input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
                capture_output=True,
                text=True,
                timeout=10,
            )
    if (
        "cannot load scripts/lib/shellcmd.py" not in runs["bare"].stderr
        or "ai-authored" not in runs["bare"].stdout
        or runs["labelled"].stdout.strip()
        or runs["bare"].returncode != 0
        or runs["labelled"].returncode != 0
    ):
        print("::error::wrong behaviour with scripts/lib/shellcmd.py missing", file=sys.stderr)
        failures += 1
    else:
        print("OK   degrades to the whole-command read without the splitter")

    # The message must name both labels and the escape, or it teaches nothing.
    message = guard.evaluate_bash('gh issue create --title "t"')
    for needed in (
        "ai-authored",
        "model:<model-id>",
        "label-agent-filed-issues.md",
        "not a refusal",
        AUTHORSHIP_MARK,
        PRIORITY_MARK,
        "`P1`, `P2` or `P3`",
        "comment on its tracker",
    ):
        if needed not in message:
            print(f"::error::warning text omits {needed!r}", file=sys.stderr)
            failures += 1

    # The harness reads a PreToolUse warning from hookSpecificOutput
    # additionalContext; stderr is not injected into the model's context.
    proc = subprocess.run(
        [sys.executable, str(HERE / "warn-unlabelled-agent-issue.py")],
        input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": 'gh issue create --title "t"'}}
        ),
        capture_output=True,
        text=True,
        timeout=10,
    )
    try:
        emitted = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    except (json.JSONDecodeError, KeyError, TypeError):
        emitted = ""
    if "ai-authored" not in emitted:
        print(
            "::error::end-to-end run emitted no additionalContext carrying the warning",
            file=sys.stderr,
        )
        failures += 1
    else:
        print("OK   emits additionalContext")

    total = (
        len(BASH_FIRES) + len(BASH_QUIET) + len(MCP_FIRES) + len(MCP_QUIET)
        + len(BASH_ONE_MISSING) + len(MCP_ONE_MISSING)
    )
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} warn-unlabelled-agent-issue cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
