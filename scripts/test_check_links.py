#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2510)."""
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

    def test_reference_link_definitions_multiline_with_trailing_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            md = root / "index.md"
            md.write_text(
                "[ref1]: target.md\n"
                "  'multiline\n"
                "   single-quoted\n"
                "   title' <!-- trailing comment -->\n\n"
                "[ref2]: <target.md>\n"
                "  \"multiline\n"
                "   double-quoted\n"
                "   title\" <!-- trailing comment with spaces -->   \n\n"
                "[ref3]: target.md\n"
                "  (multiline\n"
                "   parenthesized\n"
                "   title) <!-- multiple --> <!-- comments -->\n\n"
                "[ref4]:\n"
                "  target.md\n"
                "  'multiline\n"
                "   destination on new line' <!-- comment -->\n\n"
                "[ref5]:\n"
                "  <target.md>\n"
                "  (bracketed dest on new line) <!-- comment -->\n\n"
                "[ref6]: target.md 'single line title' <!-- comment -->\n"
                "[ref7]: target.md <!-- comment without title -->\n"
                "[ref8]: <target.md> <!-- bracketed without title -->\n"
                "  [ref9]: target.md\n"
                "  'indented up to 3 spaces' <!-- comment -->\n"
                "[ref10]: target.md\n"
                "  'trailing whitespace only'   \t  \n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 10)

    def test_reference_link_definitions_anchors_and_escaped_delimiters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.md"
            target.write_text("# Target\n", encoding="utf-8")

            md = root / "index.md"
            md.write_text(
                "[ref1\\]label]: target.md#heading\n"
                "  'title with \\'escaped single quote\\'' <!-- comment -->\n"
                "[ref2]: <target.md?query=1#sec>\n"
                "  \"title with \\\"escaped quote\\\"\" <!-- comment -->\n"
                "[ref3]: target.md\n"
                "  (title with \\) escaped paren and (nested) parens) <!-- comment -->\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 3)

    def test_broken_reference_links_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md = root / "index.md"
            md.write_text(
                "[broken1]: nonexistent1.md\n"
                "  'multiline\n"
                "   title' <!-- trailing comment -->\n\n"
                "[broken2]: <nonexistent2.md>\n"
                "  \"multiline\n"
                "   title\" <!-- comment -->\n\n"
                "[broken3]: nonexistent3.md (title) <!-- comment -->\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(len(mod.broken), 3)
            self.assertTrue(any("nonexistent1.md" in b for b in mod.broken))
            self.assertTrue(any("nonexistent2.md" in b for b in mod.broken))
            self.assertTrue(any("nonexistent3.md" in b for b in mod.broken))

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
                "   title' <!-- comment -->\n"
                "[broken-inline](missing2.md)\n"
                "```\n\n"
                "`[broken-span]: missing3.md 'title' <!-- comment -->`\n"
                "`[broken-span-link](missing4.md)`\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 0)

    def test_placeholders_and_negatives_ignored(self) -> None:
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
                "   external' <!-- comment -->\n"
                "[^footnote]: footnote definition is not a link reference\n"
                "    [indented-code-block]: target.md 'title' <!-- comment -->\n",
                encoding="utf-8",
            )

            mod.check_file(md)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 0)


if __name__ == "__main__":
    unittest.main()
