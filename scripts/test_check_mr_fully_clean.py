#!/usr/bin/env python3
"""Focused tests for the GitLab fully-clean instrument."""
from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-mr-fully-clean.py"
SHA = "0123456789abcdef0123456789abcdef01234567"
MODULE_SPEC = importlib.util.spec_from_file_location("check_mr_fully_clean", SCRIPT)
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


def payload(**overrides):
    value = {
        "project": "health-analytics-core/HACtions",
        "iid": "66",
        "mr": {"iid": 66, "sha": SHA, "state": "opened", "draft": False},
        "pipelines": [{"id": 1, "sha": SHA, "status": "success"}],
        "notes": [{
            "id": 2,
            "type": "Note",
            "created_at": "2026-09-21T22:17:38Z",
            "author": {"username": "project_2058_bot"},
            "body": (
                f"Auto-review of MR !66 (latest: {SHA})\n\n"
                "No correctness, security, or significant maintainability issues found.\n\n"
                "Verdict\nReady for merge"
            ),
            "position": None,
        }],
        "discussions": [],
        "base_ancestor": True,
        "head_rechecked": True,
        "head_rechecked_sha": SHA,
    }
    value.update(overrides)
    return value


class CheckMrFullyCleanTests(unittest.TestCase):
    def run_checker(self, value):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(value, handle)
            path = handle.name
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "66", "--project", "2058", "--from-json", path],
            text=True,
            capture_output=True,
        )
        Path(path).unlink()
        return result

    def test_clean_payload_passes(self):
        result = self.run_checker(payload())
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("FULLY CLEAN", result.stdout)
        self.assertIn(SHA, result.stdout)

    def test_missing_head_recheck_fails_closed_as_not_clean(self):
        value = payload()
        value.pop("head_rechecked")
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("was not re-read", result.stdout)

    def test_unresolved_diff_note_blocks(self):
        value = payload()
        value["notes"].append({
            "id": 3,
            "type": "DiffNote",
            "resolvable": True,
            "resolved": False,
            "author": {"username": "reviewer"},
            "body": "Please fix this.",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Unresolved GitLab diff note", result.stdout)

    def test_unresolved_clean_summary_does_not_block(self):
        value = payload()
        value["notes"][0]["resolvable"] = True
        value["notes"][0]["resolved"] = False
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_duplicate_diff_note_is_reported_once(self):
        value = payload()
        note = {
            "id": 3,
            "type": "DiffNote",
            "resolvable": True,
            "resolved": False,
            "author": {"username": "reviewer"},
            "body": "Please fix this.",
        }
        value["notes"].append(note)
        value["discussions"] = [{"notes": [note]}]
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Unresolved GitLab diff note(s): 3.", result.stdout)
        self.assertNotIn("3, 3", result.stdout)

    def test_idless_diff_notes_are_not_deduplicated(self):
        value = payload()
        value["notes"].extend([
            {"type": "DiffNote", "resolvable": True, "resolved": False, "body": "First."},
            {"type": "DiffNote", "resolvable": True, "resolved": False, "body": "Second."},
        ])
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Unresolved GitLab diff note(s): unknown, unknown.", result.stdout)

    def test_missing_currency_proof_is_usage_error(self):
        value = payload()
        value.pop("base_ancestor")
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("base_ancestor", result.stderr)

    def test_merge_conflict_blocks(self):
        value = payload()
        value["mr"]["has_conflicts"] = True
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("merge conflicts", result.stdout)

    def test_local_currency_uses_fetched_remote_ref_first(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0)

        with patch.object(MODULE.subprocess, "run", side_effect=run):
            self.assertTrue(MODULE._local_base_ancestor("main", SHA))
        self.assertEqual(calls[0][3], "origin/main")

    def test_missing_note_author_does_not_use_shared_identity(self):
        first = {"id": 1, "author": {}}
        second = {"id": 2, "author": {}}
        self.assertNotEqual(MODULE._note_author(first), MODULE._note_author(second))

    def test_mr_author_addressed_reply_is_not_counted_as_reviewer_verdict(self):
        """Regression test for #4018 modeled on note 16189."""
        value = payload()
        value["mr"]["author"] = {"username": "demorrison"}
        value["notes"].append({
            "id": 16189,
            "type": "Note",
            "created_at": "2026-09-26T15:00:00Z",
            "author": {"username": "demorrison"},
            "body": (
                "Addressed the `claude-manual` reviews of pipelines 9531 and 9535:\n\n"
                "- **Changes requested** in pipeline 9531:\n"
                "  - **Medium**, NA-unsafe index access in process_batch: wrapped in is.na() check.\n"
                "- **Low**, docstring typo in validate(): fixed.\n"
            ),
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("FULLY CLEAN", result.stdout)
        self.assertNotIn("demorrison", result.stdout)

    def test_mr_author_note_without_review_marker_is_not_reviewer_verdict(self):
        """The MR author's own notes are not reviewer identities (#4018)."""
        value = payload()
        value["mr"]["author"] = {"username": "demorrison"}
        value["notes"].append({
            "id": 16190,
            "type": "Note",
            "created_at": "2026-09-26T15:05:00Z",
            "author": {"username": "demorrison"},
            "body": "Checking whether **Changes requested** was resolved on this branch.",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("FULLY CLEAN", result.stdout)
        self.assertNotIn("demorrison", result.stdout)

    def test_addressed_reply_without_mr_author_is_not_reviewer_verdict(self):
        """An addressed reply is not classified as a reviewer verdict even if mr.author is missing."""
        value = payload()
        value["notes"].append({
            "id": 16191,
            "type": "Note",
            "created_at": "2026-09-26T15:10:00Z",
            "author": {"username": "contributor"},
            "body": "Addressed findings from review of `01234567`:\n\n- **Changes requested**: fixed.\n",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("FULLY CLEAN", result.stdout)
        self.assertNotIn("contributor", result.stdout)

    def test_non_author_reviewer_verdict_still_blocks(self):
        """A genuine reviewer verdict from another identity still blocks (#4018)."""
        value = payload()
        value["mr"]["author"] = {"username": "demorrison"}
        value["notes"].append({
            "id": 16192,
            "type": "Note",
            "created_at": "2026-09-26T15:15:00Z",
            "author": {"username": "yyren"},
            "body": "Verdict: Changes requested\n\nPlease fix the concurrency issue.",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Standing reviewer verdict(s) are not clean: yyren.", result.stdout)

    def test_system_note_is_ignored(self):
        """GitLab system notes are not treated as reviewer verdicts."""
        value = payload()
        value["notes"].append({
            "id": 16193,
            "type": "Note",
            "system": True,
            "created_at": "2026-09-26T15:20:00Z",
            "author": {"username": "demorrison"},
            "body": "marked this merge request as draft",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_mr_author_helper(self):
        self.assertEqual(MODULE._mr_author({"author": {"username": "demorrison"}}), "demorrison")
        self.assertEqual(MODULE._mr_author({"author": {"name": "Douglas Morrison"}}), "Douglas Morrison")
        self.assertEqual(MODULE._mr_author({"author": "demorrison"}), "demorrison")
        self.assertEqual(MODULE._mr_author({}), "")
        self.assertTrue(MODULE._is_mr_author("demorrison", "demorrison"))
        self.assertTrue(MODULE._is_mr_author("DeMorrison", "demorrison"))
        self.assertFalse(MODULE._is_mr_author("yyren", "demorrison"))
        self.assertFalse(MODULE._is_mr_author("", "demorrison"))

    def test_is_addressed_reply_helper(self):
        self.assertTrue(MODULE._is_addressed_reply("Addressed the `claude-manual` reviews..."))
        self.assertTrue(MODULE._is_addressed_reply("Addressing comments..."))
        self.assertTrue(MODULE._is_addressed_reply("- Addressed: fixed bug"))
        self.assertFalse(MODULE._is_addressed_reply("Verdict: Changes requested"))
        self.assertFalse(MODULE._is_addressed_reply("Ready for merge"))
        self.assertFalse(MODULE._is_addressed_reply(""))

    def test_addressed_prefix_with_review_marker_still_blocks(self):
        """A review starting with 'Addressed' that carries a review body marker still blocks."""
        value = payload()
        value["notes"].append({
            "id": 16194,
            "type": "Note",
            "created_at": "2026-09-26T15:25:00Z",
            "author": {"username": "reviewer"},
            "body": "Addressed comments review:\n\nVerdict: Changes requested\n\nStill broken.",
        })
        result = self.run_checker(value)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Standing reviewer verdict(s) are not clean: reviewer.", result.stdout)


if __name__ == "__main__":
    unittest.main()
