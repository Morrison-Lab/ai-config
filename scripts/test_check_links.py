#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py."""
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

extract_targets = mod.extract_targets
is_external = mod.is_external
check_file = mod.check_file


class TestCheckLinks(unittest.TestCase):
    def test_is_external(self):
        self.assertTrue(is_external("https://github.com"))
        self.assertTrue(is_external("http://example.com"))
        self.assertTrue(is_external("mailto:user@example.com"))
        self.assertTrue(is_external("tel:+1234567890"))
        self.assertTrue(is_external("#section-anchor"))
        self.assertTrue(is_external("custom://protocol/path"))
        self.assertTrue(is_external("user@example.com"))
        self.assertFalse(is_external("path/to/file.md"))
        self.assertFalse(is_external("../other.md"))

    def test_table_header_autolinks(self):
        doc = (
            "| <https://github.com> | Header 2 |\n"
            "| --- | --- |\n"
            "| cell 1 | cell 2 |\n"
        )
        targets = extract_targets(doc)
        self.assertEqual(targets, ["https://github.com"])
        self.assertTrue(is_external(targets[0]))

    def test_table_header_mailto_autolinks(self):
        doc = (
            "| <mailto:support@example.com> | Contact |\n"
            "| --- | --- |\n"
            "| help | info |\n"
        )
        targets = extract_targets(doc)
        self.assertEqual(targets, ["mailto:support@example.com"])
        self.assertTrue(is_external(targets[0]))

    def test_table_body_and_multiple_autolinks(self):
        doc = (
            "| <https://first.com> | <https://second.org> |\n"
            "| --- | --- |\n"
            "| <http://third.net> | normal cell |\n"
        )
        targets = extract_targets(doc)
        self.assertEqual(
            targets,
            ["https://first.com", "https://second.org", "http://third.net"],
        )
        for t in targets:
            self.assertTrue(is_external(t))

    def test_fenced_and_inline_code_stripped(self):
        doc = (
            "Outside `<https://inline-code.com>`\n\n"
            "```markdown\n"
            "| <https://fenced-code.com> | Header |\n"
            "```\n\n"
            "Real autolink: <https://valid.com>\n"
        )
        targets = extract_targets(doc)
        self.assertEqual(targets, ["https://valid.com"])

    def test_standard_inline_links(self):
        doc = "See [GitHub](https://github.com) and [Doc](relative/doc.md)."
        targets = extract_targets(doc)
        self.assertEqual(targets, ["https://github.com", "relative/doc.md"])

    def test_bracketed_pointy_destinations(self):
        doc = "See [Link](<https://example.com>) and [Doc](<path/to/file.md>)."
        targets = extract_targets(doc)
        self.assertEqual(targets, ["https://example.com", "path/to/file.md"])

    def test_check_file_valid_and_broken_relative_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc_path = td / "test.md"
            target_path = td / "existing.md"
            target_path.write_text("# Existing", encoding="utf-8")

            # Save state
            prev_broken = list(mod.broken)
            prev_checked = mod.checked
            mod.broken.clear()
            mod.checked = 0

            try:
                # Valid relative link and autolink in table header
                doc_path.write_text(
                    "| <https://github.com> | Header 2 |\n"
                    "| --- | --- |\n"
                    "| [Valid](existing.md) | Cell |\n",
                    encoding="utf-8",
                )
                check_file(doc_path)
                self.assertEqual(len(mod.broken), 0)
                self.assertEqual(mod.checked, 1)

                # Broken relative link
                doc_path.write_text(
                    "| <https://github.com> | Header 2 |\n"
                    "| --- | --- |\n"
                    "| [Broken](nonexistent.md) | Cell |\n",
                    encoding="utf-8",
                )
                check_file(doc_path)
                self.assertEqual(len(mod.broken), 1)
            finally:
                mod.broken = prev_broken
                mod.checked = prev_checked


if __name__ == "__main__":
    unittest.main()
