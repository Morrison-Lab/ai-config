#!/usr/bin/env python3
"""Tests for require-agent-disclosure.py.

The cases that matter are the near-misses, per
`shared/workflow/algorithmatize-checks.md`: a matcher that fires on every
`gh pr comment` is useless, and one that fires on none of them is invisible.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

_spec = importlib.util.spec_from_file_location(
    "guard", pathlib.Path(__file__).with_name("require-agent-disclosure.py"))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

MARKER = "_Posted by Claude Code (AI agent) --- not written by a human._"

# (label, command, expect_warning)
CASES = [
    # --- must warn -----------------------------------------------------------
    ("bare pr comment",
     'gh pr comment 12 --body "Working on this."', True),
    ("bare issue comment",
     'gh issue comment 12 --body "Working on this."', True),
    ("glab mr note",
     'glab mr note create 12 --message "Working on this."', True),
    ("glab issue note",
     'glab issue note 12 --message "Working on this."', True),
    ("gh pr review",
     'gh pr review 12 --comment --body "Looks fine."', True),
    ("prose self-id is not the marker",
     'gh pr comment 12 --body "Claude Code CLI (local session) is working on this."',
     True),

    # --- must NOT warn -------------------------------------------------------
    ("marker present",
     f'gh pr comment 12 --body "Working on this.\n\n{MARKER}"', False),
    ("marker with another agent name",
     'gh pr comment 12 --body "Done.\n\n_Posted by Codex (AI agent) -- not a human._"',
     False),
    ("dependabot rebase is exempt",
     'gh pr comment 12 --repo o/r --body "@dependabot rebase"', False),
    ("dependabot squash is exempt",
     'gh pr comment 12 --repo o/r --body "@dependabot squash and merge"', False),
    ("renovate is exempt",
     'gh pr comment 12 --body "@renovate rebase"', False),

    # --- not a comment-posting command at all --------------------------------
    ("reading comments is not posting",
     'gh pr view 12 --json comments', False),
    ("issue create is not a comment",
     'gh issue create --title x --body "y"', False),
    ("git commit is not a comment",
     'git commit -m "Working on this."', False),
    # --- the near-misses this corpus generates constantly ---------------------
    ("prose merely discussing the rule",
     'echo "always end a gh pr comment with the marker"', False),
    ("a doc-writing heredoc quoting the command",
     'cat > doc.md <<\'EOF\'\ngh pr comment <N> --body "Working on this."\nEOF',
     False),
    ("grep for the command is not the command",
     'grep -rn "gh pr comment" skills/', False),
    ("a chained real command still warns",
     'git push && gh pr comment 12 --body "Pushed."', True),
    ("a variable elsewhere does not hide a visible marker",
     f'gh pr comment "$N" --repo "$REPO" --body "Done.\n\n{MARKER}"', False),

    # --- forms the first version missed entirely (review findings 2, 12) ------
    ("gh api issues comments",
     'gh api repos/o/r/issues/12/comments -f body="Working on this."', True),
    ("gh api review-thread reply",
     'gh api repos/o/r/pulls/12/comments/9/replies -f body="Addressed."', True),
    ("gh api reply WITH marker",
     f'gh api repos/o/r/pulls/12/comments/9/replies -f body="Addressed.\n\n{MARKER}"',
     False),
    ("glab mr comment alias",
     'glab mr comment 12 --message "Working on this."', True),
    ("glab issue comment alias",
     'glab issue comment 12 --message "Working on this."', True),
    ("command after then",
     'if true; then gh pr comment 12 --body "bare"; fi', True),
    ("negated command",
     '! gh pr comment 12 --body "bare"', True),
    ("command inside a do-loop",
     'for n in 1 2; do gh pr comment $n --body "bare"; done', True),

    # --- one marker must not vouch for a sibling (review finding 4) -----------
    ("a disclosed comment does not vouch for an undisclosed sibling",
     f'gh pr comment 1 --body "a\n\n{MARKER}" && gh pr comment 2 --body "b"',
     True),
    ("both disclosed is silent",
     f'gh pr comment 1 --body "a\n\n{MARKER}" && gh pr comment 2 --body "b\n\n{MARKER}"',
     False),
    ("a grep for the marker does not vouch for a bare comment",
     'grep -rn "Posted by Claude Code (AI agent)" . ; gh pr comment 2 --body "bare"',
     True),

    # --- heredocs: body when piped, prose when written (review finding 3) -----
    ("heredoc IS the body, and discloses",
     'gh pr comment 12 --body-file - <<\'EOF\'\nDone.\n\n' + MARKER
     + '\nEOF', False),
    ("heredoc IS the body, and does not disclose",
     'gh pr comment 12 --body-file - <<\'EOF\'\nDone, undisclosed.\nEOF', True),
    ("a doc heredoc does not silence a real sibling command",
     'cat > d.md <<\'EOF\'\ngh pr comment <N> --body "x"\nEOF\ngh pr comment 2 --body "bare"',
     True),

    # --- the exemption is whole-body, not first-token (review finding 8) ------
    ("a bot handle followed by prose for humans is NOT exempt",
     'gh pr comment 12 --body "@dependabot rebase please, and a note for the '
     'humans reading this thread: I will also rerun CI"', True),
    ("the review re-request is exempt",
     'gh pr comment 12 --body "@' + 'claude review"', False),

    # --- unreadable vs missing must not be confused (review finding 9) -------
    ("gh pr comment -F <file> is a body-file, reported unreadable",
     'gh pr comment 12 -F /tmp/body.md', None),
    ("--editor is unreadable",
     'gh pr comment 12 --editor', None),
]

# --- the emoji branch --------------------------------------------------------
ROBOT_CASE = (
    'gh pr comment 12 --body "Done.\n\n\U0001f916 Posted by Claude Code."')

# --- the unreadable-body branch ---------------------------------------------
INDIRECT_CASES = [
    ("body-file", 'gh pr comment 12 --body-file /tmp/b.md'),
    ("api body file", 'gh pr comment 12 -F body=@/tmp/b.md'),
    ("variable body", 'gh pr comment 12 --body "$BODY"'),
]


def run():
    failed = 0
    for label, command, expect in CASES:
        reason = guard.verdict(command)
        if expect is None:
            # Must warn, and specifically about a body it could not read --
            # accusing a command of omitting a marker never seen is the
            # misdiagnosis review finding 9 named.
            ok = reason is not None and "cannot read" in reason
            print(f"{'PASS' if ok else 'FAIL'}: {label} "
                  f"(reported unreadable={ok})")
        else:
            got = reason is not None
            ok = got == expect
            print(f"{'PASS' if ok else 'FAIL'}: {label} "
                  f"(warned={got}, expected={expect})")
        failed += not ok

    reason = guard.verdict(ROBOT_CASE)
    ok = reason is not None and "robot emoji" in reason
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: a robot-emoji disclosure is named as "
          f"the wrong marker")

    # Review finding 14: a body merely MENTIONING the emoji discloses nothing,
    # so the emoji advice would be inapplicable and would displace the real one.
    mention = 'gh pr comment 12 --body "The \U0001f916 badge broke; rerunning."'
    reason = guard.verdict(mention)
    ok = reason is not None and "robot emoji" not in reason
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: merely mentioning the emoji is not "
          f"treated as disclosing with it")

    for label, command in INDIRECT_CASES:
        reason = guard.verdict(command)
        ok = reason is not None and "cannot read" in reason
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label} reports an unreadable body "
              f"rather than a missing marker")

    # The hook must never block. Its only output shape is additionalContext.
    src = pathlib.Path(__file__).with_name(
        "require-agent-disclosure.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]
    ok = "permissionDecision" not in body
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: the hook warns and never denies")

    # End-to-end through stdin, because `verdict()` returning a string proves
    # only that the text was COMPUTED. Whether the harness ever surfaces it is a
    # fact about the emitted JSON, and a test asserting bool(verdict) cannot
    # tell a surfaced warning from discarded output.
    for label, payload, expect_warning in (
        ("a bare comment emits additionalContext",
         {"tool_name": "Bash",
          "tool_input": {"command": 'gh pr comment 12 --body "Working on this."'}},
         True),
        ("a disclosed comment emits nothing",
         {"tool_name": "Bash",
          "tool_input": {"command": f'gh pr comment 12 --body "Done.\n\n{MARKER}"'}},
         False),
        ("a non-Bash tool emits nothing",
         {"tool_name": "Edit", "tool_input": {"command": "gh pr comment 1 --body x"}},
         False),
        ("malformed stdin fails open", "not json at all", False),
    ):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        proc = subprocess.run(
            [sys.executable,
             str(pathlib.Path(__file__).with_name("require-agent-disclosure.py"))],
            input=stdin, capture_output=True, text=True)
        out = proc.stdout.strip()
        if expect_warning:
            try:
                emitted = json.loads(out)["hookSpecificOutput"]
            except Exception:
                emitted = {}
            ok = (proc.returncode == 0
                  and emitted.get("hookEventName") == "PreToolUse"
                  and "additionalContext" in emitted
                  and "permissionDecision" not in emitted
                  and "disclosure marker" in emitted.get("additionalContext", ""))
        else:
            ok = proc.returncode == 0 and out == ""
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label}")

    # Review finding 10: a remote/web session has no `gh`, so MCP is its only
    # path -- a Bash-only guard is silent exactly where the CLI is absent.
    for label, tool, body, expect in (
        ("MCP add_issue_comment bare", "mcp__github__add_issue_comment",
         "Working on this.", True),
        ("MCP add_issue_comment disclosed", "mcp__github__add_issue_comment",
         "Working on this.\n\n" + MARKER, False),
        ("MCP review reply bare",
         "mcp__github__add_reply_to_pull_request_comment", "Addressed.", True),
        ("MCP bot-command body is exempt", "mcp__github__add_issue_comment",
         "@dependabot rebase", False),
        ("a non-comment MCP tool is out of scope",
         "mcp__github__create_pull_request", "Closes #1", False),
    ):
        got = guard.verdict_mcp(tool, {"body": body}) is not None
        ok = got == expect
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label} "
              f"(warned={got}, expected={expect})")

    total = len(CASES) + 2 + len(INDIRECT_CASES) + 1 + 4 + 5
    print(f"\n{total - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
