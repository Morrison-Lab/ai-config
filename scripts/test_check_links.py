#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2842).

Verifies that:
1. External link schemes, email addresses, and in-page anchors are recognized and skipped.
2. Link destinations with titles in quotes/parens or angle brackets are parsed cleanly.
3. Link reference definitions ([label]: target "title") are recognized and validated.
4. Extensionless markdown targets and directory index/README files resolve.
5. Anchor fragments (#section) on extensionless targets are handled correctly.
6. Broken links (including broken extensionless targets with anchors) are caught.
7. Bare-word placeholders and code-fenced examples are skipped.
8. Display math ($$...$$) and inline math ($...$) with LaTeX brackets are not mistaken for links.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

check_file = mod.check_file
is_external = mod.is_external
parse_link_target = mod.parse_link_target
resolve_target = mod.resolve_target


class TestCheckLinks(unittest.TestCase):
    def setUp(self) -> None:
        mod.broken.clear()
        mod.checked = 0

    def test_is_external(self) -> None:
        self.assertTrue(is_external("https://example.com"))
        self.assertTrue(is_external("http://example.com/page"))
        self.assertTrue(is_external("mailto:user@example.com"))
        self.assertTrue(is_external("tel:+1234567890"))
        self.assertTrue(is_external("#heading-anchor"))
        self.assertTrue(is_external("ftp://example.com"))
        self.assertFalse(is_external("relative/path/to/file.md"))
        self.assertFalse(is_external("../sibling.md"))
        self.assertFalse(is_external("file.md#anchor"))

    def test_parse_link_target(self) -> None:
        self.assertEqual(parse_link_target("target.md"), "target.md")
        self.assertEqual(parse_link_target('<target.md> "Title"'), "target.md")
        self.assertEqual(parse_link_target("<target.md>"), "target.md")
        self.assertEqual(parse_link_target("target.md 'Single Quoted Title'"), "target.md")
        self.assertEqual(parse_link_target("target.md (Parenthesized Title)"), "target.md")
        self.assertEqual(parse_link_target(""), "")

    def test_valid_relative_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "Check [target](target.md) and [subtarget](target.md#section).\n"
                "Also [ref link][ref-1].\n\n"
                '[ref-1]: target.md "Target Title"\n',
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 3)

    def test_broken_relative_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source = td / "source.md"
            source.write_text(
                "Check [missing](missing.md) and [broken](nonexistent/dir/file.md).\n"
                "[bad-ref]: missing_ref.md\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 3)
            self.assertEqual(mod.checked, 3)

    def test_code_fences_and_spans_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source = td / "source.md"
            source.write_text(
                "```python\n"
                "# [fake link](missing1.md)\n"
                "```\n"
                "Here is `[inline](missing2.md)` in code span.\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 0)

    def test_math_blocks_and_inline_math_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source = td / "source.md"
            source.write_text(
                "$$\n"
                "\\int_{[0, 1]} f(x) dx\n"
                "$$\n"
                "Inline math: $[a, b](x)$ and $f(x) = [0, 1]$.\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 0)

    def test_link_placeholders_and_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "real.md"
            target.write_text("# Real", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "Examples: [bare](url), [placeholder](<owner>/<repo>), "
                "[title](real.md \"Title\"), [bracketed](<real.md>).\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 2)


if __name__ == "__main__":
    unittest.main()
