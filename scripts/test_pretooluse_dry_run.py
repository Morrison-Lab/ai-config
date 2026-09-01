#!/usr/bin/env python3
"""Test suite for PreToolUse hooks --dry-run and simulation mode.

Verifies that PreToolUse hooks accept `--dry-run` and `--simulate` offline,
parsing CLI strings and JSON stdin payloads directly and emitting
standard JSON decision/context payloads without live network/forge access.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"


def run_hook(hook_name: str, args: list[str], stdin_data: str = "", env_extra: dict = None) -> tuple[int, dict, str]:
    """Run a hook with given args and stdin, returning (exit_code, json_output, stderr)."""
    env = dict(os.environ)
    env.pop("ANTIGRAVITY_AGENT", None)
    if env_extra:
        env.update(env_extra)

    hook_path = HOOKS_DIR / hook_name
    proc = subprocess.Popen(
        [sys.executable, str(hook_path)] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate(input=stdin_data)
    out_json = {}
    if stdout.strip():
        try:
            out_json = json.loads(stdout.strip())
        except json.JSONDecodeError:
            pass
    return proc.returncode, out_json, stderr


class TestPreToolUseDryRun(unittest.TestCase):
    """Test offline execution of PreToolUse hooks with --dry-run."""

    def test_require_gh_repo_flag(self):
        code, out, _ = run_hook("require-gh-repo-flag.py", ["--dry-run", "gh secret set MY_SECRET"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("Blocked: `gh secret set/delete` without an explicit target", hso.get("permissionDecisionReason", ""))

        code, out, _ = run_hook("require-gh-repo-flag.py", ["--dry-run", "gh secret set MY_SECRET -R owner/repo"])
        self.assertEqual(code, 0)
        self.assertNotIn("permissionDecision", out.get("hookSpecificOutput", {}))

    def test_no_unauthorized_merge(self):
        code, out, _ = run_hook("no-unauthorized-merge.py", ["--dry-run", "gh pr merge 123 --squash"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("MECHANISTIC PROHIBITION", hso.get("permissionDecisionReason", ""))

        code, out, _ = run_hook("no-unauthorized-merge.py", ["--dry-run", "ALLOW_MERGE=1 gh pr merge 123 --squash"])
        self.assertEqual(code, 0)
        self.assertNotIn("permissionDecision", out.get("hookSpecificOutput", {}))

    def test_no_whole_file_punct_replace(self):
        code, out, _ = run_hook("no-whole-file-punct-replace.py", ["--dry-run", "sed -i '' 's/—/--/g' file.txt"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("replaces punctuation glyphs", hso.get("permissionDecisionReason", ""))

    def test_flag_unchained_branch_switch(self):
        code, out, _ = run_hook("flag-unchained-branch-switch.py", ["--dry-run", "git checkout feat ; git merge main"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_no_clobbering_push(self):
        code, out, _ = run_hook("no-clobbering-push.py", ["--dry-run", "git push --force origin main"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("bare `git push --force`", hso.get("permissionDecisionReason", ""))

    def test_no_heavy_work_on_head_node(self):
        code, out, _ = run_hook(
            "no-heavy-work-on-head-node.py",
            ["--dry-run", "R -e 'devtools::test()'"],
            env_extra={"SIMULATE_HEAD_NODE": "1"},
        )
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("on the head node", hso.get("permissionDecisionReason", ""))

    def test_no_handrolled_verdict_parse(self):
        code, out, _ = run_hook(
            "no-handrolled-verdict-parse.py",
            ["--dry-run", "gh pr view 123 --json comments | grep -i 'Ready for merge'"],
        )
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")
        self.assertIn("hand-rolled verdict parse", hso.get("permissionDecisionReason", ""))

    def test_flag_add_a_outside_pathspec(self):
        code, out, _ = run_hook(
            "flag-add-a-outside-pathspec.py",
            ["--dry-run", "git add -A ':!file.txt'"],
            env_extra={"SIMULATE_UNTRACKED": "foo.txt,bar.txt"},
        )
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_flag_reset_hard_uncommitted_work(self):
        code, out, _ = run_hook(
            "flag-reset-hard-uncommitted-work.py",
            ["--dry-run", "git reset --hard"],
            env_extra={"SIMULATE_DIRTY": "script.py"},
        )
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_warn_nonglobal_substitution(self):
        code, out, _ = run_hook("warn-nonglobal-substitution.py", ["--dry-run", "sed -i 's/foo/bar/' script.sh"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_warn_dupe_check_chained_to_create(self):
        code, out, _ = run_hook("warn-dupe-check-chained-to-create.py", ["--dry-run", "gh issue list && gh issue create --title 'x'"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_warn_status_read_after_pipe(self):
        code, out, _ = run_hook("warn-status-read-after-pipe.py", ["--dry-run", "echo test | grep foo; echo $?"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_require_agent_disclosure(self):
        code, out, _ = run_hook("require-agent-disclosure.py", ["--dry-run", "gh pr comment 123 --body 'I fixed this bug.'"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_flag_uncounted_comment_claims(self):
        code, out, _ = run_hook("flag-uncounted-comment-claims.py", ["--dry-run", "gh pr comment 123 --body '5 files: foo.py, bar.py'"])
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)

    def test_flag_unassigned_worktree(self):
        code, out, _ = run_hook(
            "flag-unassigned-worktree.py",
            ["--dry-run"],
            stdin_data=json.dumps({"tool_name": "Agent", "tool_input": {"prompt": "implement feature"}}),
        )
        self.assertEqual(code, 0)
        hso = out.get("hookSpecificOutput", {})
        self.assertIn("additionalContext", hso)


if __name__ == "__main__":
    unittest.main()
