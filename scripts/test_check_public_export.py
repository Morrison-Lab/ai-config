#!/usr/bin/env python3
"""Tests for scripts/check_public_export.py: the stale-pin check.

Run: python3 scripts/test_check_public_export.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check_public_export.py")
OTHER_REPO_SHA = "0123456789012345678901234567890123456789"


def git(root: Path, *args: str) -> str:
    cmd = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org", *args]
    return subprocess.run(cmd, capture_output=True, check=True, text=True).stdout.strip()


class StalePinTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src = Path(tmp.name) / "src"
        self.exp = Path(tmp.name) / "exp"
        self.src.mkdir()
        self.exp.mkdir()
        git(self.src, "init", "-q")
        (self.src / "a.txt").write_text("hello\n", encoding="utf-8")
        git(self.src, "add", "a.txt")
        git(self.src, "commit", "-q", "-m", "init")
        self.old_sha = git(self.src, "rev-parse", "HEAD")
        (self.exp / "a.txt").write_text("hello\n", encoding="utf-8")

    def run_check(self, pinned: str) -> subprocess.CompletedProcess:
        pin = f"ref: {pinned}\n"
        (self.exp / "t.yml").write_text(pin, encoding="utf-8")
        (self.src / "t.yml").write_text(pin, encoding="utf-8")
        git(self.src, "add", "t.yml")
        git(self.src, "commit", "-q", "-m", "add pin")
        return subprocess.run([sys.executable, str(SCRIPT), str(self.src), str(self.exp)],
                              capture_output=True, text=True)

    def test_commit_of_source_history_fails(self) -> None:
        result = self.run_check(self.old_sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(self.old_sha, result.stdout)

    def test_commit_of_another_repository_passes(self) -> None:
        result = self.run_check(OTHER_REPO_SHA)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
