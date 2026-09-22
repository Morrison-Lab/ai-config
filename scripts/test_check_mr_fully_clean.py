#!/usr/bin/env python3
"""Focused tests for the GitLab fully-clean instrument."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-mr-fully-clean.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


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


if __name__ == "__main__":
    unittest.main()
