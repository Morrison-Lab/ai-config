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
        got = guard.verdict(command) is not None
        ok = got == expect
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {label} "
              f"(warned={got}, expected={expect})")

    reason = guard.verdict(ROBOT_CASE)
    ok = reason is not None and "robot emoji" in reason
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'}: a robot-emoji disclosure is named as "
          f"the wrong marker")

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

    total = len(CASES) + 1 + len(INDIRECT_CASES) + 1 + 4
    print(f"\n{total - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
