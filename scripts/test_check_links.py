#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2881).

Verifies that:
1. External URI schemes and email addresses are recognized as external.
2. Link destinations in angle brackets (<...>) are extracted cleanly without mangling.
3. CommonMark autolinks (<https://...> and <user@domain.tld>) are recognized
   and not treated as broken local file paths.
4. Relative links to existing files pass, while links to missing files fail with
   clean unmangled targets.
5. Links inside fenced code blocks and inline code spans are ignored.
6. Angle bracket placeholders (<owner>/<repo>) and in-page anchors are ignored.
7. Display math ($$...$$) and inline math ($...$) with LaTeX brackets are not mistaken for links.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO / "scripts" / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
check_links = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = check_links
spec.loader.exec_module(check_links)


class TestIsExternal(unittest.TestCase):
    def test_standard_prefixes(self):
        self.assertTrue(check_links.is_external("http://example.com"))
        self.assertTrue(check_links.is_external("https://example.com/path?foo=bar"))
        self.assertTrue(check_links.is_external("mailto:user@example.com"))
        self.assertTrue(check_links.is_external("tel:+1234567890"))
        self.assertTrue(check_links.is_external("#heading-anchor"))

    def test_custom_schemes(self):
        self.assertTrue(check_links.is_external("ftp://ftp.example.org/resource"))
        self.assertTrue(check_links.is_external("vscode://file/path/to/file"))
        self.assertTrue(check_links.is_external("conversation://82f24413-64c3"))
        self.assertTrue(check_links.is_external("data:text/plain;base64,SGVsbG8="))

    def test_email_addresses(self):
        self.assertTrue(check_links.is_external("user@domain.tld"))
        self.assertTrue(check_links.is_external("first.last+tag@sub.domain.co.uk"))

    def test_relative_paths(self):
        self.assertFalse(check_links.is_external("docs/guide.md"))
        self.assertFalse(check_links.is_external("./guide.md"))
        self.assertFalse(check_links.is_external("../shared/doc.md"))
        self.assertFalse(check_links.is_external("guide.md#section"))
        self.assertFalse(check_links.is_external("images/diagram.png"))


class TestExtractTarget(unittest.TestCase):
    def test_plain_target(self):
        self.assertEqual(check_links.extract_target("path/to/file.md"), "path/to/file.md")

    def test_target_with_title(self):
        self.assertEqual(
            check_links.extract_target('path/to/file.md "Document Title"'),
            "path/to/file.md",
        )

    def test_angle_bracket_target(self):
        self.assertEqual(
            check_links.extract_target("<path/to/file.md>"),
            "path/to/file.md",
        )

    def test_angle_bracket_target_with_title(self):
        self.assertEqual(
            check_links.extract_target('<path/to/file.md> "Document Title"'),
            "path/to/file.md",
        )

    def test_angle_bracket_url(self):
        self.assertEqual(
            check_links.extract_target("<https://example.com/path>"),
            "https://example.com/path",
        )
        self.assertEqual(
            check_links.extract_target('<https://example.com/path> "Web Link"'),
            "https://example.com/path",
        )

    def test_angle_bracket_email(self):
        self.assertEqual(
            check_links.extract_target("<user@domain.tld>"),
            "user@domain.tld",
        )

    def test_angle_bracket_placeholder(self):
        self.assertEqual(
            check_links.extract_target("<owner>/<repo>"),
            "<owner>/<repo>",
        )


class TestCheckFile(unittest.TestCase):
    def setUp(self):
        check_links.broken = []
        check_links.checked = 0

    def test_valid_relative_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")
            index = td / "index.md"
            index.write_text(
                "[link1](target.md)\n"
                "[link2](<target.md>)\n"
                '[link3](<target.md> "Title")\n'
                "[link4](target.md#section)\n",
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(check_links.broken, [])
            self.assertEqual(check_links.checked, 4)

    def test_broken_relative_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            index = td / "index.md"
            index.write_text(
                "[link1](missing.md)\n"
                "[link2](<missing.md>)\n"
                '[link3](<missing.md> "Title")\n',
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(
                check_links.broken,
                [
                    "index.md -> missing.md",
                    "index.md -> missing.md",
                    "index.md -> missing.md",
                ],
            )
            self.assertEqual(check_links.checked, 3)

    def test_autolinks_and_emails_not_treated_as_broken(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            index = td / "index.md"
            index.write_text(
                "Contact: <user@domain.tld>\n"
                "Website: <https://example.com/docs>\n"
                "Inquiry: <mailto:support@domain.tld>\n"
                "[Contact 1](user@domain.tld)\n"
                "[Contact 2](<user@domain.tld>)\n"
                "[Contact 3](mailto:user@domain.tld)\n"
                "[Site 1](<https://example.com>)\n",
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(check_links.broken, [])
            self.assertEqual(check_links.checked, 0)

    def test_code_fences_and_spans_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            index = td / "index.md"
            index.write_text(
                "```markdown\n"
                "[code_link](nonexistent_in_fence.md)\n"
                "<https://example.com/in_fence>\n"
                "<missing_in_fence@domain.tld>\n"
                "```\n\n"
                "Here is inline: `[code_link](nonexistent_in_span.md)` and `<not_a_link@span.tld>`\n",
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(check_links.broken, [])
            self.assertEqual(check_links.checked, 0)

    def test_math_blocks_and_inline_math_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            index = td / "index.md"
            index.write_text(
                "$$\n"
                "\\int_{[0, 1]} f(x) dx\n"
                "$$\n"
                "Inline math: $[a, b](x)$ and $f(x) = [0, 1]$.\n",
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(check_links.broken, [])
            self.assertEqual(check_links.checked, 0)

    def test_placeholders_and_anchors_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            index = td / "index.md"
            index.write_text(
                "[Anchor](#heading)\n"
                "[Placeholder](<owner>/<repo>)\n"
                "[Bareword](url)\n"
                "Prose placeholder: <owner>/<repo>\n",
                encoding="utf-8",
            )
            check_links.check_file(index, root=td)
            self.assertEqual(check_links.broken, [])
            self.assertEqual(check_links.checked, 0)


if __name__ == "__main__":
    unittest.main()
