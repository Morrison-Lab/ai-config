#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2518)."""
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

clean_target = mod.clean_target
find_targets = mod.find_targets
check_file = mod.check_file


class TestCheckLinksTargetCleaning(unittest.TestCase):
    def test_clean_target_basic(self):
        self.assertEqual(clean_target("relative/path.md"), "relative/path.md")
        self.assertEqual(clean_target("./relative/path.md"), "./relative/path.md")
        self.assertEqual(clean_target("../relative/path.md"), "../relative/path.md")

    def test_clean_target_angle_brackets(self):
        self.assertEqual(clean_target("<relative/path.md>"), "relative/path.md")

    def test_clean_target_anchors_and_queries(self):
        self.assertEqual(clean_target("path.md#heading"), "path.md")
        self.assertEqual(clean_target("path.md?version=1"), "path.md")
        self.assertEqual(clean_target("path.md#heading?version=1"), "path.md")
        self.assertIsNone(clean_target("#pure-anchor"))

    def test_clean_target_external_and_placeholders(self):
        self.assertIsNone(clean_target("https://example.com/doc.md"))
        self.assertIsNone(clean_target("http://example.com/doc.md"))
        self.assertIsNone(clean_target("mailto:user@example.com"))
        self.assertIsNone(clean_target("tel:+1234567890"))
        self.assertIsNone(clean_target("git://github.com/repo"))
        self.assertIsNone(clean_target("<owner>/<repo>"))
        self.assertIsNone(clean_target("bareword"))


class TestCheckLinksParsing(unittest.TestCase):
    def test_inline_links(self):
        text = "See [doc](path/to/doc.md) and [other](<path/to/other.md> \"title\")."
        self.assertEqual(find_targets(text), ["path/to/doc.md", "path/to/other.md"])

    def test_reference_link_definition_basic(self):
        text = "[ref]: path/to/doc.md"
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_reference_link_definition_angle_brackets(self):
        text = "[ref]: <path/to/doc.md>"
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_reference_link_definition_quoted_titles(self):
        text = (
            "[ref1]: path/one.md \"double quoted title\"\n"
            "[ref2]: path/two.md 'single quoted title'\n"
        )
        self.assertEqual(find_targets(text), ["path/one.md", "path/two.md"])

    def test_reference_link_definition_paren_title_single_line(self):
        text = "[ref]: path/to/doc.md (a parenthesized title)"
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_reference_link_definition_multiline_paren_title(self):
        text = (
            "[ref1]: path/one.md\n"
            "  (multiline\n"
            "   paren title)\n"
            "\n"
            "[ref2]: <path/two.md>\n"
            "  (another multiline\n"
            "   title)\n"
        )
        self.assertEqual(find_targets(text), ["path/one.md", "path/two.md"])

    def test_reference_link_definition_destination_and_paren_title_on_newlines(self):
        text = (
            "[ref]:\n"
            "  path/to/doc.md\n"
            "  (multiline\n"
            "   title)\n"
        )
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_reference_link_definition_escaped_and_nested_parens_in_title(self):
        text = (
            "[ref1]: path/one.md (title with \\) escaped paren)\n"
            "[ref2]: path/two.md (title with (nested) parens)\n"
        )
        self.assertEqual(find_targets(text), ["path/one.md", "path/two.md"])

    def test_reference_link_definition_indented_up_to_three_spaces(self):
        text = "   [ref]: path/to/doc.md\n     (indented title)"
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_reference_link_definition_multiline_quotes(self):
        text = (
            "[ref1]: path/one.md\n"
            "  \"multiline\n"
            "   double quote title\"\n"
            "[ref2]: path/two.md\n"
            "  'multiline\n"
            "   single quote title'\n"
        )
        self.assertEqual(find_targets(text), ["path/one.md", "path/two.md"])

    def test_reference_link_definition_blank_line_breaks_title(self):
        # CommonMark: a link title cannot span a blank line
        text = (
            "[ref]: path/to/doc.md\n"
            "\n"
            "  (not part of title)\n"
        )
        self.assertEqual(find_targets(text), ["path/to/doc.md"])

    def test_code_regions_ignored(self):
        text = (
            "Here is inline code: `[inline](code/inline.md)`\n"
            "Here is multi-backtick code: `` `[multi](code/multi.md)` ``\n"
            "```markdown\n"
            "[fence-inline](code/fence.md)\n"
            "[fence-ref]: code/fence-ref.md\n"
            "  (title)\n"
            "```\n"
            "Real link: [real](real/path.md)\n"
            "[real-ref]: real/ref.md\n"
            "  (multiline\n"
            "   title)\n"
        )
        self.assertEqual(find_targets(text), ["real/path.md", "real/ref.md"])


class TestCheckFileExecution(unittest.TestCase):
    def test_check_file_detects_existing_and_broken_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "existing.md").write_text("# Existing", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "# Source\n\n"
                "Inline: [ok](existing.md) and [bad](missing.md)\n\n"
                "[ref-ok]: existing.md\n"
                "  (multiline\n"
                "   title)\n"
                "[ref-bad]: missing_ref.md\n"
                "  (multiline\n"
                "   title)\n",
                encoding="utf-8",
            )
            mod.broken.clear()
            mod.checked = 0
            check_file(source)

            self.assertEqual(mod.checked, 4)
            self.assertEqual(len(mod.broken), 2)
            self.assertTrue(any("missing.md" in b for b in mod.broken))
            self.assertTrue(any("missing_ref.md" in b for b in mod.broken))


if __name__ == "__main__":
    unittest.main()
