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

is_external = mod.is_external
extract_targets = mod.extract_targets
check_file = mod.check_file
ROOT = mod.ROOT


class TestIsExternal(unittest.TestCase):
    def test_http_and_https(self):
        self.assertTrue(is_external("http://example.com"))
        self.assertTrue(is_external("https://example.com"))
        self.assertTrue(is_external("https://example.com/path?arg=1#frag"))

    def test_mailto_and_emails(self):
        self.assertTrue(is_external("mailto:user@example.com"))
        self.assertTrue(is_external("user@example.com"))
        self.assertTrue(is_external("first.last+tag@sub.domain.org"))

    def test_other_schemes(self):
        self.assertTrue(is_external("tel:+1234567890"))
        self.assertTrue(is_external("ftp://files.example.com"))
        self.assertTrue(is_external("file:///path/to/file"))
        self.assertTrue(is_external("ssh://git@github.com"))
        self.assertTrue(is_external("custom-scheme://host/path"))

    def test_anchors(self):
        self.assertTrue(is_external("#heading-anchor"))

    def test_relative_paths_are_not_external(self):
        self.assertFalse(is_external("path/to/doc.md"))
        self.assertFalse(is_external("./relative.md"))
        self.assertFalse(is_external("../parent.md"))
        self.assertFalse(is_external("doc.md#section"))


class TestExtractTargets(unittest.TestCase):
    def test_standard_markdown_links(self):
        text = "Check [docs](docs/readme.md) and [site](https://example.com)."
        self.assertEqual(extract_targets(text), ["docs/readme.md", "https://example.com"])

    def test_angle_bracket_markdown_links(self):
        text = "See [link](<docs/readme.md>) and [external](<https://example.com>)."
        self.assertEqual(extract_targets(text), ["docs/readme.md", "https://example.com"])

    def test_autolinks_in_prose(self):
        text = "Visit <https://example.com> or email <support@example.com>."
        self.assertEqual(extract_targets(text), ["https://example.com", "support@example.com"])

    def test_autolinks_inside_html_elements(self):
        text = (
            "<details>\n"
            "<summary>Links: <https://example.com/summary></summary>\n"
            "<div>\n"
            "  <p>Email us at <mailto:info@example.com> or <dev@example.com>.</p>\n"
            "  <span>Docs: <https://docs.example.org></span>\n"
            "</div>\n"
            "</details>"
        )
        targets = extract_targets(text)
        self.assertIn("https://example.com/summary", targets)
        self.assertIn("mailto:info@example.com", targets)
        self.assertIn("dev@example.com", targets)
        self.assertIn("https://docs.example.org", targets)

    def test_html_tags_not_extracted_as_targets(self):
        text = "<details><summary>Title</summary><div><p>Hello</p><br/></div></details>"
        self.assertEqual(extract_targets(text), [])

    def test_code_fences_and_spans_ignored(self):
        text = (
            "```markdown\n"
            "[ignored fence](missing1.md)\n"
            "<https://ignored-fence.example.com>\n"
            "```\n"
            "Here is `[ignored span](missing2.md)` and `<https://ignored-span.example.com>`.\n"
            "Real link: [real](docs/real.md) and <https://real.example.com>."
        )
        self.assertEqual(extract_targets(text), ["docs/real.md", "https://real.example.com"])


class TestCheckFile(unittest.TestCase):
    def setUp(self):
        mod.broken.clear()
        mod.checked = 0

    def test_valid_relative_links_and_html_autolinks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target_file = td / "target.md"
            target_file.write_text("# Target", encoding="utf-8")

            source_file = td / "source.md"
            source_file.write_text(
                "# Source\n\n"
                "<details>\n"
                "<summary>See <https://example.com> and [Target](target.md)</summary>\n"
                "<div>Contact <mailto:alice@example.com></div>\n"
                "</details>\n",
                encoding="utf-8",
            )

            check_file(source_file)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 1)

    def test_missing_relative_link_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source_file = td / "source.md"
            source_file.write_text(
                "# Source\n\n"
                "[Missing](missing_target.md)\n"
                "<details><summary><https://example.com></summary></details>\n",
                encoding="utf-8",
            )

            check_file(source_file)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing_target.md", mod.broken[0])
            self.assertEqual(mod.checked, 1)

    def test_placeholders_and_anchors_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            source_file = td / "source.md"
            source_file.write_text(
                "# Source\n\n"
                "[In page anchor](#section)\n"
                "[Angle placeholder](<owner>/<repo>)\n"
                "[Bareword placeholder](parameter)\n",
                encoding="utf-8",
            )

            check_file(source_file)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 0)


if __name__ == "__main__":
    unittest.main()
