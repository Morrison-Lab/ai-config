#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2591)."""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

check_file = mod.check_file
is_external = mod.is_external


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

    def test_valid_relative_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "Check [target](target.md) and [subtarget](target.md#section).",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 2)

    def test_broken_relative_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source = td / "source.md"
            source.write_text(
                "Check [missing](missing.md) and [broken](nonexistent/dir/file.md).",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 2)
            self.assertEqual(mod.checked, 2)

    def test_code_fences_and_spans_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source = td / "source.md"
            source.write_text(
                "```python\n"
                "# [fake link](missing1.md)\n"
                "```\n"
                "Inline `[fake](missing2.md)` is ignored.\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 0)

    def test_display_math_stripped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "real.md"
            target.write_text("# Real", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "$$\n"
                "\\mathbf{A} = [a, b](not_a_link.md)\n"
                "$$\n"
                "See [real](real.md).\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 1)

    def test_inline_math_and_dollar_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target1 = td / "target1.md"
            target1.write_text("# Target 1", encoding="utf-8")
            target2 = td / "target2.md"
            target2.write_text("# Target 2", encoding="utf-8")
            target3 = td / "target3.md"
            target3.write_text("# Target 3", encoding="utf-8")

            source = td / "source.md"
            source.write_text(
                "Formula $x \\in [0, 1](not_a_link.md)$ is math.\n"
                "Cost is $50. See [target 1](target1.md). Fee is $100.\n"
                "Variable $VAR is defined. See [$f(x)$](target2.md).\n"
                "See interval [$x \\in [0, 1]$](target3.md).\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 3)

    def test_escaped_dollar_signs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")
            source = td / "source.md"
            source.write_text(
                "Price is \\$50. See [target](target.md). Fee is \\$20.\n",
                encoding="utf-8",
            )

            check_file(source)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 1)

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
