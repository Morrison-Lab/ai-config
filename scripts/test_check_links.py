#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2519)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {SCRIPT_PATH}")
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)


class TestCheckLinks(unittest.TestCase):
    def setUp(self) -> None:
        mod.broken.clear()
        mod.checked = 0

    def test_is_external(self) -> None:
        self.assertTrue(mod.is_external("https://example.com"))
        self.assertTrue(mod.is_external("http://example.com"))
        self.assertTrue(mod.is_external("mailto:user@example.com"))
        self.assertTrue(mod.is_external("tel:+123456789"))
        self.assertTrue(mod.is_external("#section-anchor"))
        self.assertTrue(mod.is_external("ftp://files.example.com"))
        self.assertFalse(mod.is_external("target.md"))
        self.assertFalse(mod.is_external("./target.md"))
        self.assertFalse(mod.is_external("../target.md"))
        self.assertFalse(mod.is_external("docs/guide.md#section"))

    def test_inline_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            md = root / "index.md"
            md.write_text(
                "[basic](target.md)\n"
                "[bracketed](<target.md>)\n"
                "[with title](target.md 'Single Quote Title')\n"
                "[with double title](target.md \"Double Quote Title\")\n"
                "[with paren title](target.md (Paren Title))\n"
                "[multiline single](target.md\n  'multiline\n   single title')\n"
                "[multiline double](target.md\n  \"multiline\n   double title\")\n"
                "[with anchor](target.md#section)\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 8)

    def test_reference_link_definitions_single_quotes_multiline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            md = root / "index.md"
            md.write_text(
                "[ref1]: target.md\n"
                "  'multiline\n"
                "   single-quoted\n"
                "   title'\n\n"
                "[ref2]: <target.md>\n"
                "  'multiline\n"
                "   bracketed\n"
                "   title'\n\n"
                "[ref3]:\n"
                "  target.md\n"
                "  'title on\n"
                "   new line'\n\n"
                "  [ref4]: target.md 'same line single title'\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 4)

    def test_reference_link_definitions_double_and_paren_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            md = root / "index.md"
            md.write_text(
                "[ref1]: target.md\n"
                "  \"multiline\n"
                "   double-quoted\n"
                "   title\"\n\n"
                "[ref2]: target.md\n"
                "  (multiline\n"
                "   paren-quoted\n"
                "   title)\n\n"
                "[ref3]: target.md\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 3)

    def test_broken_reference_link_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md = root / "index.md"
            md.write_text(
                "[broken-ref]: nonexistent.md\n"
                "  'multiline\n"
                "   title'\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("nonexistent.md", mod.broken[0])

    def test_broken_inline_link_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md = root / "index.md"
            md.write_text(
                "[broken](missing-file.md 'title')\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing-file.md", mod.broken[0])

    def test_code_fences_and_spans_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md = root / "index.md"
            md.write_text(
                "```markdown\n"
                "[broken-fence]: missing1.md\n"
                "  'multiline\n"
                "   title'\n"
                "[broken-inline](missing2.md)\n"
                "```\n\n"
                "`[broken-span]: missing3.md 'title'`\n"
                "`[broken-span-link](missing4.md)`\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 0)

    def test_placeholders_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md = root / "index.md"
            md.write_text(
                "[placeholder](<owner>/<repo>)\n"
                "[bare-word](url)\n"
                "[anchor-only](#section)\n"
                "[ext](https://example.com 'external')\n"
                "[ext-ref]: https://example.com\n"
                "  'multiline\n"
                "   external'\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 0)


if __name__ == "__main__":
    unittest.main()
