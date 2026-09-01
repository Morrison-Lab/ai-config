#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py."""
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
extract_reference_definitions = mod.extract_reference_definitions
clean_target = mod.clean_target
check_target = mod.check_target
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


class TestExtractReferenceDefinitions(unittest.TestCase):
    def test_basic_definition(self):
        text = "Some text\n[my-label]: path/to/target.md\nMore text"
        defs, body = extract_reference_definitions(text)
        self.assertEqual(defs, {"my-label": "path/to/target.md"})
        self.assertNotIn("[my-label]:", body)
        self.assertIn("Some text", body)
        self.assertIn("More text", body)

    def test_angle_brackets_and_titles(self):
        text = (
            '[label1]: <path/to/target1.md> "Double Quote Title"\n'
            "[label2]: path/to/target2.md 'Single Quote Title'\n"
            "[label3]: path/to/target3.md (Paren Title)\n"
        )
        defs, _ = extract_reference_definitions(text)
        self.assertEqual(defs["label1"], "path/to/target1.md")
        self.assertEqual(defs["label2"], "path/to/target2.md")
        self.assertEqual(defs["label3"], "path/to/target3.md")

    def test_leading_indentation_limits(self):
        # 0-3 spaces are valid definitions in CommonMark; 4 spaces is an indented code block
        text = (
            "   [valid]: target.md\n"
            "    [invalid]: target2.md\n"
        )
        defs, _ = extract_reference_definitions(text)
        self.assertIn("valid", defs)
        self.assertNotIn("invalid", defs)

    def test_first_definition_precedence(self):
        text = (
            "[duplicate]: first.md\n"
            "[duplicate]: second.md\n"
        )
        defs, _ = extract_reference_definitions(text)
        self.assertEqual(defs["duplicate"], "first.md")


class TestCleanTarget(unittest.TestCase):
    def test_valid_relative_paths(self):
        self.assertEqual(clean_target("path/to/file.md"), "path/to/file.md")
        self.assertEqual(clean_target("<path/to/file.md>"), "path/to/file.md")
        self.assertEqual(clean_target("path/to/file.md#anchor"), "path/to/file.md#anchor")
        self.assertEqual(clean_target("path/to/file.md 'Title'"), "path/to/file.md")

    def test_external_and_anchors_skipped(self):
        self.assertIsNone(clean_target("https://example.com"))
        self.assertIsNone(clean_target("http://example.com"))
        self.assertIsNone(clean_target("mailto:user@example.com"))
        self.assertIsNone(clean_target("#pure-anchor"))

    def test_placeholders_skipped(self):
        self.assertIsNone(clean_target("<owner>/<repo>"))
        self.assertIsNone(clean_target("bareword"))


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

            check_file(doc)
            self.assertEqual(mod.checked, 1)
            self.assertEqual(mod.broken, [])

    def test_broken_shortcut_reference_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "Here is a broken shortcut link: [missing].\n\n"
                "[missing]: missing.md\n",
                encoding="utf-8",
            )

            check_file(doc)
            self.assertEqual(mod.checked, 1)
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

            check_file(doc)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(mod.broken, [])

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

            check_file(doc)
            self.assertEqual(mod.checked, 2)
            self.assertEqual(mod.broken, [])

    def test_code_blocks_and_backticks_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "Inline code: `[missing](missing.md)` and `[missing_shortcut]`\n\n"
                "```markdown\n"
                "[missing_block](missing_block.md)\n"
                "[missing_shortcut_block]: missing.md\n"
                "```\n",
                encoding="utf-8",
            )

            check_file(doc)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(mod.broken, [])


class TestMainCLI(unittest.TestCase):
    def setUp(self):
        mod.broken.clear()
        mod.checked = 0

    def test_main_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")
            doc = td / "doc.md"
            doc.write_text("See [target].\n\n[target]: target.md\n", encoding="utf-8")

            stdout = io.StringIO()
            with patch.object(mod, "ROOT", td), patch.object(mod, "SCAN_GLOBS", ["*.md"]), patch("sys.stdout", stdout):
                main()
            self.assertIn("✓ no broken relative links", stdout.getvalue())

    def test_main_broken(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text("See [broken].\n\n[broken]: nonexistent.md\n", encoding="utf-8")

            stdout = io.StringIO()
            with patch.object(mod, "ROOT", td), patch.object(mod, "SCAN_GLOBS", ["*.md"]), patch("sys.stdout", stdout):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)
            self.assertIn("1 broken link(s)", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
