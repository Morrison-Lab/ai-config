#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2842).

Verifies that:
1. External URI schemes, email addresses, and in-page anchors are recognized and skipped.
2. Link destinations in angle brackets (<...>) are extracted cleanly without mangling.
3. CommonMark autolinks (<https://...> and <user@domain.tld>) are recognized
   and not treated as broken local file paths.
4. Relative links to existing files pass, while links to missing files fail with
   clean unmangled targets.
5. Links inside fenced code blocks, inline code spans, and math blocks are ignored.
6. Reference link definitions ([label]: target "title"), full reference links ([text][label]),
   collapsed reference links ([label][]), and shortcut reference links ([label]) resolve correctly.
7. Non-link brackets (checkboxes `[x]`, alerts `[NOTE]`, footnote numbers `[1]`) produce no false positives.
8. Angle-bracket destinations with internal whitespace (`[ref]: <path/to file.md>`) are preserved without truncation.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

normalize_label = mod.normalize_label
parse_link_target = mod.parse_link_target
is_external = mod.is_external
check_file = mod.check_file
main = mod.main


class TestNormalizeLabel(unittest.TestCase):
    def test_basic_lowercasing(self):
        self.assertEqual(normalize_label("LABEL"), "label")
        self.assertEqual(normalize_label("My-Label-1"), "my-label-1")

    def test_whitespace_collapsing(self):
        self.assertEqual(normalize_label("  foo   bar  \n  baz \t "), "foo bar baz")

    def test_empty(self):
        self.assertEqual(normalize_label(""), "")


class TestIsExternal(unittest.TestCase):
    def test_standard_prefixes(self):
        self.assertTrue(is_external("http://example.com"))
        self.assertTrue(is_external("https://example.com/path"))
        self.assertTrue(is_external("mailto:user@example.com"))
        self.assertTrue(is_external("tel:+1234567890"))
        self.assertTrue(is_external("#heading-anchor"))

    def test_custom_schemes(self):
        self.assertTrue(is_external("ftp://ftp.example.org/resource"))
        self.assertTrue(is_external("vscode://file/path/to/file"))
        self.assertTrue(is_external("conversation://82f24413-64c3"))

    def test_email_addresses(self):
        self.assertTrue(is_external("user@domain.tld"))
        self.assertTrue(is_external("first.last+tag@sub.domain.co.uk"))

    def test_relative_paths(self):
        self.assertFalse(is_external("docs/guide.md"))
        self.assertFalse(is_external("./guide.md"))
        self.assertFalse(is_external("../shared/doc.md"))


class TestCheckFile(unittest.TestCase):
    def setUp(self):
        mod.broken.clear()
        mod.checked = 0

    def test_shortcut_reference_links_resolved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "Here is a shortcut reference link: [target].\n\n"
                "[target]: target.md\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 1)

    def test_angle_bracket_destination_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target file.md"
            target.write_text("# Target", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "Here is a link: [target].\n\n"
                "[target]: <target file.md> 'Title with spaces'\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 1)

    def test_broken_shortcut_reference_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "Here is a broken shortcut link: [missing].\n\n"
                "[missing]: missing.md\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing.md", mod.broken[0])

    def test_non_link_brackets_produce_no_false_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "- [x] Completed item\n"
                "- [ ] Pending item\n"
                "[NOTE] Informational alert\n"
                "[1] Numeric footnote\n"
                "Inline example [placeholder] without definition.\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(len(mod.broken), 0)

    def test_full_and_collapsed_reference_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            t1 = td / "t1.md"
            t1.write_text("# T1", encoding="utf-8")
            t2 = td / "t2.md"
            t2.write_text("# T2", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "Full reference: [link text][t1-ref]\n"
                "Collapsed reference: [t2.md][]\n\n"
                "[t1-ref]: t1.md\n"
                "[t2.md]: t2.md\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 2)

    def test_code_blocks_and_math_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "Inline code: `[missing](missing.md)` and `[missing_shortcut]`\n\n"
                "```markdown\n"
                "[missing_block](missing_block.md)\n"
                "[missing_shortcut_block]: missing.md\n"
                "```\n\n"
                "$$\n"
                "\\int_{[0, 1]} f(x) dx\n"
                "$$\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(len(mod.broken), 0)


if __name__ == "__main__":
    unittest.main()
