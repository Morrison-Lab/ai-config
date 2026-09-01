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


class TestCheckLinks(unittest.TestCase):
    def setUp(self) -> None:
        mod.broken.clear()
        mod.checked = 0

    def test_normalize_label(self) -> None:
        self.assertEqual(mod.normalize_label("Foo Bar"), "foo bar")
        self.assertEqual(mod.normalize_label("  Foo   Bar  "), "foo bar")
        self.assertEqual(mod.normalize_label("Foo\t\nBar"), "foo bar")

    def test_is_external(self) -> None:
        self.assertTrue(mod.is_external("http://example.com"))
        self.assertTrue(mod.is_external("https://example.com/page"))
        self.assertTrue(mod.is_external("mailto:user@example.com"))
        self.assertTrue(mod.is_external("tel:+1234567890"))
        self.assertTrue(mod.is_external("#section-anchor"))
        self.assertTrue(mod.is_external("custom://something"))
        self.assertFalse(mod.is_external("docs/guide.md"))
        self.assertFalse(mod.is_external("../shared/workflow.md"))

    def test_inline_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "[Valid link](target.md)\n"
                "[Valid with title](target.md \"Title\")\n"
                "[Valid with angle](<target.md>)\n"
                "[Pure anchor](#section)\n"
                "[External](https://example.com)\n"
                "[Placeholder](url)\n"
                "[Angle placeholder](<owner>/<repo>)\n"
                "[Broken link](missing.md)\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 4)
            self.assertEqual(len(mod.broken), 1)
            self.assertTrue(mod.broken[0].endswith("-> missing.md"))

    def test_collapsed_reference_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "See [target.md][] for details.\n"
                "See also [target.md][].\n"
                "See [missing.md][].\n\n"
                "[target.md]: target.md\n"
                "[missing.md]: missing.md\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 3)
            self.assertEqual(len(mod.broken), 1)
            self.assertTrue(mod.broken[0].endswith("-> missing.md"))

    def test_full_and_shortcut_reference_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "Full reference: [The Target Doc][target-ref]\n"
                "Shortcut reference: [target-ref]\n"
                "Prose brackets: [NOTE] and [x] and [1] and [TODO]\n\n"
                "[target-ref]: target.md \"Target Title\"\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 2)
            self.assertEqual(len(mod.broken), 0)

    def test_reference_link_definition_variations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target1 = td / "target1.md"
            target1.write_text("# Target 1\n", encoding="utf-8")
            target2 = td / "target2.md"
            target2.write_text("# Target 2\n", encoding="utf-8")
            target3 = td / "target3.md"
            target3.write_text("# Target 3\n", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "See [My Target 1][], [MY TARGET 2][], [target3][].\n\n"
                "[My   Target   1]: <target1.md> 'Single quotes title'\n"
                "   [MY TARGET 2]: target2.md (Parenthesized title)\n"
                "[target3]: target3.md\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 3)
            self.assertEqual(len(mod.broken), 0)

    def test_unused_definitions_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "Prose with no link references.\n\n"
                "[unused-valid]: target.md\n"
                "[unused-broken]: missing.md\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 2)
            self.assertEqual(len(mod.broken), 1)
            self.assertTrue(mod.broken[0].endswith("-> missing.md"))

    def test_code_blocks_and_spans_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "Inline code: `[inline](missing.md)` and `` `[collapsed][]` ``\n"
                "And definition in code: `[def]: missing.md`\n\n"
                "```markdown\n"
                "[fenced](missing.md)\n"
                "[fenced-collapsed][]\n"
                "[fenced-def]: missing.md\n"
                "```\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(len(mod.broken), 0)

    def test_footnotes_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "# Doc\n\n"
                "Here is a footnote reference[^1].\n\n"
                "[^1]: This is footnote text with path/like/tokens.md\n",
                encoding="utf-8",
            )

            mod.check_file(doc)
            self.assertEqual(mod.checked, 0)
            self.assertEqual(len(mod.broken), 0)

    def test_main_cli_clean(self) -> None:
        with patch.object(mod, "ROOT", SCRIPT_PATH.parent.parent), patch.object(
            mod, "SCAN_GLOBS", ["scripts/check-links.py"]
        ), patch("sys.stdout", new=io.StringIO()):
            mod.main()
            self.assertEqual(len(mod.broken), 0)

    def test_main_cli_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "broken.md"
            doc.write_text("[broken](missing.md)\n", encoding="utf-8")

            with patch.object(mod, "ROOT", td), patch.object(
                mod, "SCAN_GLOBS", ["broken.md"]
            ), patch("sys.stdout", new=io.StringIO()), self.assertRaises(SystemExit) as cm:
                mod.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
