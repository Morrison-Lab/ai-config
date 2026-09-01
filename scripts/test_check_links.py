#!/usr/bin/env python3
"""Unit tests for scripts/check-links.py (ai-config#2527).

Tests:
1. Inline markdown link extraction ([text](url), [text](<url> "title"), etc.).
2. CommonMark reference link definition extraction:
   - Single-line ([label]: url, [label]: url "title", [label]: <url>).
   - Multiline destination ([label]:\\n  url, [label]:\\n  <url> "title").
   - Multiline title ([label]: url\\n  "title", [label]: <url>\\n  "title").
   - Multiline destination and title ([label]:\\n  url\\n  "title").
3. Negative cases (fenced code, inline backticks, prose, blank line separators).
4. Filesystem link validation and exit codes.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-links.py"

spec = importlib.util.spec_from_file_location("check_links", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_links"] = mod
spec.loader.exec_module(mod)

extract_links = mod.extract_links
is_external = mod.is_external
check_file = mod.check_file


class TestLinkExtraction(unittest.TestCase):
    def test_inline_links(self):
        text = (
            "See [docs](docs/guide.md) and [site](https://example.com) "
            "and [api](<docs/api.md> \"API docs\")."
        )
        links = extract_links(text)
        self.assertIn("docs/guide.md", links)
        self.assertIn("https://example.com", links)
        self.assertIn("docs/api.md", links)

    def test_ref_link_single_line(self):
        text = (
            "[ref1]: ./path/to/one.md\n"
            "[ref2]: ./path/to/two.md \"Title Two\"\n"
            "[ref3]: ./path/to/three.md 'Title Three'\n"
            "[ref4]: ./path/to/four.md (Title Four)\n"
            "[ref5]: <./path/to/five.md> \"Title Five\"\n"
            "[ref6]: <./path/to/six.md>\n"
        )
        links = extract_links(text)
        self.assertEqual(
            links,
            [
                "./path/to/one.md",
                "./path/to/two.md",
                "./path/to/three.md",
                "./path/to/four.md",
                "./path/to/five.md",
                "./path/to/six.md",
            ],
        )

    def test_ref_link_multiline_destination(self):
        text = (
            "[dest-next]:\n"
            "  ./path/to/dest.md\n"
            "[dest-next-title]:\n"
            "  ./path/to/dest_with_title.md \"Destination Title\"\n"
            "[dest-next-bracket]:\n"
            "  <./path/to/bracket_dest.md>\n"
            "[dest-next-bracket-title]:\n"
            "  <./path/to/bracket_dest_title.md> \"Bracket Title\"\n"
        )
        links = extract_links(text)
        self.assertEqual(
            links,
            [
                "./path/to/dest.md",
                "./path/to/dest_with_title.md",
                "./path/to/bracket_dest.md",
                "./path/to/bracket_dest_title.md",
            ],
        )

    def test_ref_link_multiline_title(self):
        text = (
            "[title-next]: ./path/to/file1.md\n"
            "  \"Title on next line\"\n"
            "[title-next-single]: ./path/to/file2.md\n"
            "  'Single quoted title'\n"
            "[title-next-paren]: ./path/to/file3.md\n"
            "  (Parenthesized title)\n"
            "[title-next-bracket]: <./path/to/file4.md>\n"
            "  \"Title on next line\"\n"
        )
        links = extract_links(text)
        self.assertEqual(
            links,
            [
                "./path/to/file1.md",
                "./path/to/file2.md",
                "./path/to/file3.md",
                "./path/to/file4.md",
            ],
        )

    def test_ref_link_multiline_destination_and_title(self):
        text = (
            "[all-multiline]:\n"
            "  ./path/to/target.md\n"
            "  \"Title on third line\"\n"
            "[bracket-multiline]:\n"
            "  <./path/to/target2.md>\n"
            "  \"Title on third line\"\n"
        )
        links = extract_links(text)
        self.assertEqual(
            links,
            [
                "./path/to/target.md",
                "./path/to/target2.md",
            ],
        )

    def test_ref_link_indentation(self):
        text = (
            "   [indented]: ./path/to/indent.md \"3 spaces indent\"\n"
            "  [indented-multi]:\n"
            "    ./path/to/indent_multi.md\n"
        )
        links = extract_links(text)
        self.assertEqual(
            links,
            [
                "./path/to/indent.md",
                "./path/to/indent_multi.md",
            ],
        )

    def test_ref_link_blank_line_not_allowed(self):
        text = (
            "[broken-ref]:\n"
            "\n"
            "  ./path/to/file.md\n"
        )
        links = extract_links(text)
        self.assertEqual(links, [])

    def test_ref_link_non_link_prose(self):
        text = (
            "[NOTE]: This is an informational note.\n"
            "[WARNING]: Something dangerous might happen.\n"
            "- [x]: Completed todo item\n"
        )
        links = extract_links(text)
        self.assertEqual(links, [])

    def test_code_fences_and_spans_ignored(self):
        text = (
            "```markdown\n"
            "[fenced]: ./ignore/me.md\n"
            "[fenced-inline](ignore/inline.md)\n"
            "```\n"
            "Here is inline code: `[inline]: ./ignore/inline.md`.\n"
            "Real link: [real](./real/file.md)\n"
        )
        links = extract_links(text)
        self.assertEqual(links, ["./real/file.md"])


class TestFileSystemValidation(unittest.TestCase):
    def setUp(self):
        mod.broken.clear()
        mod.checked = 0

    def test_valid_relative_reference_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target1 = root / "target1.md"
            target1.write_text("# Target 1", encoding="utf-8")
            target2 = root / "target2.md"
            target2.write_text("# Target 2", encoding="utf-8")
            target3 = root / "target3.md"
            target3.write_text("# Target 3", encoding="utf-8")

            doc = root / "index.md"
            doc.write_text(
                "# Index\n\n"
                "See [one][ref1], [two][ref2], and [three][ref3].\n\n"
                "[ref1]: target1.md\n"
                "[ref2]:\n"
                "  target2.md \"Title 2\"\n"
                "[ref3]: target3.md\n"
                "  \"Title 3\"\n",
                encoding="utf-8",
            )

            check_file(doc)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 3)

    def test_broken_relative_reference_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            doc = root / "index.md"
            doc.write_text(
                "# Index\n\n"
                "[ref]:\n"
                "  missing.md\n"
                "  \"Missing file\"\n",
                encoding="utf-8",
            )

            check_file(doc)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing.md", mod.broken[0])

    def test_anchors_and_queries_stripped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "guide.md"
            target.write_text("# Guide\n## Section\n", encoding="utf-8")

            doc = root / "index.md"
            doc.write_text(
                "[ref1]: guide.md#section\n"
                "[ref2]:\n"
                "  guide.md?version=2\n"
                "[pure-anchor]: #section\n",
                encoding="utf-8",
            )

            check_file(doc)
            self.assertEqual(mod.broken, [])
            self.assertEqual(mod.checked, 2)


class TestCLIExecution(unittest.TestCase):
    def test_cli_runs_and_passes_on_repo(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Checked", proc.stdout)
        self.assertIn("no broken relative links", proc.stdout)


if __name__ == "__main__":
    unittest.main()
