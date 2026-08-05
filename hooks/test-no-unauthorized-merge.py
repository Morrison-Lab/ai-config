#!/usr/bin/env python3
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK_PATH = Path(__file__).parent / "no-unauthorized-merge.py"


class TestNoUnauthorizedMerge(unittest.TestCase):
    def run_hook(self, command: str) -> dict:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            check=True,
        )
        if not proc.stdout.strip():
            return {}
        return json.loads(proc.stdout)

    def test_blocks_gh_pr_merge(self):
        res = self.run_hook("gh pr merge 411 --squash")
        self.assertEqual(res.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_blocks_glab_mr_merge(self):
        res = self.run_hook("glab mr merge 12")
        self.assertEqual(res.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_blocks_gh_api_merge(self):
        res = self.run_hook("gh api -X PUT /repos/owner/repo/pulls/123/merge")
        self.assertEqual(res.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_allows_unrelated_gh_commands(self):
        res = self.run_hook("gh pr view 411")
        self.assertEqual(res, {})

    def test_allows_explicit_merge_override(self):
        res = self.run_hook("ALLOW_MERGE=1 gh pr merge 411 --squash")
        self.assertEqual(res, {})


if __name__ == "__main__":
    unittest.main()
