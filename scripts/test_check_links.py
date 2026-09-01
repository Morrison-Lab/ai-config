#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2513)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"
spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

is_external = mod.is_external
extract_targets = mod.extract_targets
check_file = mod.check_file


class TestCheckLinks(unittest.TestCase):
    def setUp(self) -> None:
        mod.broken.clear()
        mod.checked = 0

    def test_is_external(self) -> None:
        self.assertTrue(is_external("https://example.com"))
        self.assertTrue(is_external("http://example.com/foo"))
        self.assertTrue(is_external("mailto:user@example.com"))
        self.assertTrue(is_external("tel:+1234567890"))
        self.assertTrue(is_external("#section-heading"))
        self.assertTrue(is_external("ftp://example.com/file"))
        self.assertTrue(is_external("custom://app/path"))
        self.assertTrue(is_external("user@example.com"))
        self.assertFalse(is_external("relative/path/to/file.md"))
        self.assertFalse(is_external("../sibling.md"))
        self.assertFalse(is_external("file.md#anchor"))

    def test_extract_targets_inline_links(self) -> None:
        text = "Here is a [link](https://example.com) and [local](path/to/doc.md)."
        targets = extract_targets(text)
        self.assertEqual(targets, ["https://example.com", "path/to/doc.md"])

    def test_extract_targets_autolinks(self) -> None:
        text = "See <https://example.com/info> or contact <mailto:support@example.com>."
        targets = extract_targets(text)
        self.assertEqual(
            targets,
            ["https://example.com/info", "mailto:support@example.com"],
        )

    def test_alert_header_autolinks(self) -> None:
        alert_text = (
            "> [!NOTE] <https://example.com/note>\n"
            "> [!TIP] <mailto:tips@example.com>\n"
            "> [!IMPORTANT] <https://github.com/Morrison-Lab/ai-config>\n"
            "> [!WARNING] <https://example.com/warning>\n"
            "> [!CAUTION] <https://example.com/caution>\n"
        )
        targets = extract_targets(alert_text)
        self.assertEqual(
            targets,
            [
                "https://example.com/note",
                "mailto:tips@example.com",
                "https://github.com/Morrison-Lab/ai-config",
                "https://example.com/warning",
                "https://example.com/caution",
            ],
        )
        for target in targets:
            self.assertTrue(
                is_external(target),
                f"Target {target} should be recognized as external",
            )

    def test_alert_body_and_code_spans(self) -> None:
        text = (
            "> [!NOTE]\n"
            "> Visit <https://example.com> for more info.\n"
            "> Do not visit `<https://ignored-code.com>`.\n"
        )
        targets = extract_targets(text)
        self.assertEqual(targets, ["https://example.com"])

    def test_fenced_code_block_stripping(self) -> None:
        text = (
            "Prose link: <https://example.com>\n\n"
            "```markdown\n"
            "> [!NOTE] <https://example-in-code.com>\n"
            "[example](docs/fake.md)\n"
            "```\n"
        )
        targets = extract_targets(text)
        self.assertEqual(targets, ["https://example.com"])

    def test_angle_bracket_placeholders_ignored(self) -> None:
        text = "Use `<owner>/<repo>` or <owner/repo> in your config."
        targets = extract_targets(text)
        self.assertEqual(targets, [])

    def test_check_file_detects_broken_relative_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target_file = td / "existing.md"
            target_file.write_text("# Existing", encoding="utf-8")

            md_file = td / "test.md"
            md_file.write_text(
                "> [!NOTE] <https://example.com>\n"
                "> [!TIP] [Existing](existing.md)\n"
                "> [!WARNING] [Broken](nonexistent.md)\n",
                encoding="utf-8",
            )

            check_file(md_file)
            self.assertEqual(mod.checked, 2)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("nonexistent.md", mod.broken[0])


if __name__ == "__main__":
    unittest.main()
