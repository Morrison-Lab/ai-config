#!/usr/bin/env python3
"""Tests for scripts/check-links.py (ai-config#2842).

Verifies that:
1. External URI schemes and email addresses are recognized and skipped.
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
9. A fragment, in-page or on a link to a Markdown file or a directory's README, must name a heading or HTML anchor there (ai-config#3630).
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import time
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

    def test_markdown_footnotes_produce_no_false_positives(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "Here is a claim[^1] with another note[^named-footnote].\n\n"
                "[^1]: Footnote content without links.\n"
                "[^named-footnote]: Footnote referencing valid [target](target.md).\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 0)
            self.assertEqual(mod.checked, 1)

    def test_broken_link_inside_footnote_definition_flagged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            doc = td / "doc.md"
            doc.write_text(
                "Here is text with a footnote[^note].\n\n"
                "[^note]: Footnote referencing broken [missing](missing.md).\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing.md", mod.broken[0])

    def test_link_text_starting_with_caret_is_checked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            target = td / "target.md"
            target.write_text("# Target", encoding="utf-8")

            doc = td / "doc.md"
            doc.write_text(
                "Link with caret: [^valid link](target.md) and broken: [^broken link](missing.md).\n",
                encoding="utf-8",
            )

            check_file(doc, root=td)
            self.assertEqual(len(mod.broken), 1)
            self.assertIn("missing.md", mod.broken[0])
            self.assertEqual(mod.checked, 2)


class TestFragments(unittest.TestCase):
    """In-page and cross-file anchors must name a heading (ai-config#3630)."""

    def setUp(self):
        mod.broken.clear()
        mod.checked = 0
        mod.anchors_in.cache_clear()

    def run_doc(self, body, files=None, **others):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            pages = {"sub/README.md": "# Inner\n", **(files or {})}
            pages.update({f"{name}.md": text for name, text in others.items()})
            for name, text in pages.items():
                (td / name).parent.mkdir(parents=True, exist_ok=True)
                (td / name).write_text(text, encoding="utf-8")
            doc = td / "doc.md"
            doc.write_text(body, encoding="utf-8")
            check_file(doc, root=td)
        return list(mod.broken)

    def test_heading_slugs_resolve(self):
        broken = self.run_doc(
            "# Use `foo_bar` and [the guide](x.md)!\n\n## Repeated\n\n## Repeated\n\n"
            '<a id="custom"></a>\n\n'
            "[a](#use-foo_bar-and-the-guide) [b](#repeated) [c](#repeated-1) [d](#custom)\n",
            x="# X\n")
        self.assertEqual(broken, [])
        self.assertEqual(mod.checked, 5)  # four fragments plus x.md

    def test_github_slugs_of_awkward_headings_pass(self):
        # Each pair is a heading and the slug GitHub gives it.
        cases = [
            ("The `__init__` method", "the-__init__-method"),
            (r"A \_literal\_ underscore", "a-_literal_-underscore"),
            ("_private name", "_private-name"),
            ("trailing_", "trailing_"),
            ("Use foo_bar here", "use-foo_bar-here"),
            ("Use **bold** and _em_", "use-bold-and-em"),
            ("Tom &amp; Jerry", "tom--jerry"),
            ("Caf&eacute; menu", "café-menu"),
            ("`&lt;tag&gt;` in code", "lttaggt-in-code"),
            ("Tom &lt;b&gt; Jerry", "tom-b-jerry"),
            ("See <https://example.com>", "see-httpsexamplecom"),
            ("Use [foo][bar] ref\n\n[bar]: sub/", "use-foo-ref"),
            ("Undefined [foo][nope] ref", "undefined-foonope-ref"),
            ("![logo](x.png) Title", "-title"),
            ("![logo][l] Title\n\n[l]: sub/", "-title"),
            ("Closed heading ##", "closed-heading"),
            ("Tom <b>and</b> Jerry", "tom-and-jerry"),
            ("The `<!-- allow -->` pragma", "the--allow---pragma"),
            ("O(n²) sorting", "on-sorting"),
            ("Ⅻ rules", "ⅻ-rules"),
            ("Step two", "user-content-step-two"),
            ("हिन्दी शीर्षक", "हिन्दी-शीर्षक"),
        ]
        for heading, slug in cases:
            with self.subTest(heading=heading):
                mod.anchors_in.cache_clear()
                mod.broken.clear()
                self.assertEqual(self.run_doc(f"# {heading}\n\n[x](#{slug})\n"), [])

    def test_setext_quoted_and_listed_headings(self):
        broken = self.run_doc("Setext Title\n============\n\nLine one\nline two\n---\n\n"
                              "> Quoted setext\n> ===\n\n> ## Quoted\n\n- ## Listed\n\n"
                              "1.  Item title\n    ===\n\n"
                              "[a](#setext-title) [b](#line-one-line-two) [c](#quoted-setext)"
                              " [d](#quoted) [e](#listed) [f](#item-title)\n")
        self.assertEqual(broken, [])

    def test_renamed_heading_is_broken(self):
        # The leading BOM is skipped, as cmark-gfm skips it.
        broken = self.run_doc("﻿# Real heading\n\n## Step 2\n\n## Ⅻ rules\n\n## ![logo](i.png)\n\n"
                              "[gone](#renamed-heading) [ok](#step-2) [other](#step-3)"
                              " [numeral](#rules) [first](#real-heading) [dashes](#---)\n")
        self.assertEqual(broken, ["doc.md -> #renamed-heading (no such heading)",
                                  "doc.md -> #step-3 (no such heading)",
                                  "doc.md -> #rules (no such heading)", "doc.md -> #--- (no such heading)"])

    def test_code_span_comment_opener_hides_no_heading(self):
        broken = self.run_doc("# Writing `<!--` markers\n\n## Middle\n\nClose with `-->`.\n\n[x](#middle)\n")
        self.assertEqual(broken, [])

    def test_heading_inside_a_fence_or_front_matter_is_not_an_anchor(self):
        broken = self.run_doc("---\ntitle: x\n# Not a heading\n---\n\n```\n# Fenced\n```\n\n"
                              "[a](#not-a-heading) [b](#fenced)\n")
        self.assertEqual(broken, ["doc.md -> #not-a-heading (no such heading)",
                                  "doc.md -> #fenced (no such heading)"])

    def test_cross_file_anchor(self):
        broken = self.run_doc("[ok](other.md#present) [bad](other.md#absent)\n",
                              other="# Present\n")
        self.assertEqual(broken, ["doc.md -> other.md#absent (no such heading)"])

    def test_html_anchors(self):
        broken = self.run_doc('<div data-id="dataid"></div>\n\n<!-- <a id="commented"></a> -->\n\n'
                              '`<a id="spanned"></a>`\n\n<span NAME="real"></span>\n\n'
                              "Text <a ID=bare></a> and <a\nid='split'></a> here.\n\n"
                              "[a](#dataid) [b](#commented) [c](#spanned) [d](#real) [e](#bare)"
                              " [f](#split)\n")
        self.assertEqual(broken, [f"doc.md -> #{a} (no such heading)"
                                  for a in ("dataid", "commented", "spanned")])

    def test_block_anchor_unclosed_comment_marks_and_front_matter(self):
        broken = self.run_doc('---\ntitle: Foo\n--- \n\n<div id="blk"></div>\n\n## \u0915\u093f\n\n'
                              "[a](#blk) [b](#title-foo) [c](#\u0915) [d](#after)\n\n"
                              '<!-- unclosed\n<a id="after"></a>\n')
        self.assertEqual(broken, [f"doc.md -> #{a} (no such heading)"
                                  for a in ("title-foo", "\u0915", "after")])

    def test_fragment_forms(self):
        broken = self.run_doc(
            "# Mixed Case\n\n# Café\n\n"
            "[a](#Mixed-Case) [b](#caf%C3%A9) [c](other.md?x=1#present) [d](other.md?plain=1#L3)"
            " [e](other.md#L3) [f](other.md?plain=1#absent) [g](sub/#inner) [h](sub/#nope)"
            " [i](idx/#anything) [j](x.py#L3) [k](#) [m](#<slug>) [l][ref]"
            " [n](rst/#anything) [o](idx/) [p](low/#lower) [q](assets/#x)\n\n"
            "[ref]: other.md#gone\n",
            files={"idx/index.md": "# From index\n", "x.py": "", "rst/readme.rst": "",
                   "low/readme.md": "# Lower\n", "assets/readme_assets/a.png": ""},
            other="# Present\n")
        self.assertEqual(broken, ["doc.md -> other.md#L3 (no such heading)",
                                  "doc.md -> other.md?plain=1#absent (no such heading)",
                                  "doc.md -> sub/#nope (no such heading)",
                                  "doc.md -> idx/#anything (no README for the heading)",
                                  "doc.md -> other.md#gone (no such heading)",
                                  "doc.md -> assets/#x (no README for the heading)"])

    def test_pathological_scanner_input_stays_fast(self):
        # Not emphasis-delimiter runs, on which markdown-it-py is quadratic.
        started = time.perf_counter()
        self.run_doc("# a" + " " * 20000 + "x\n\n" + "< " * 20000 + "\n\n# " + "](" * 20000
                     + "\n\n# " + "![" * 20000 + "\n\n<a " + "x" * 20000 + "\n\n[x](#nope)\n")
        self.assertLess(time.perf_counter() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
