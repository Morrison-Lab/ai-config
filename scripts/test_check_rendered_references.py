#!/usr/bin/env python3
"""Unit tests for check-rendered-references.py.

Verifies detection of broken rendered cross-references (?@...), missing citations
(<strong>key?</strong>, **key?**), and unprocessed citations ([@key]), while
verifying that valid markdown footnote references ([^1], [^note]) and definitions
([^1]: ...) do not produce false warnings (ai-config#2879).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location(
    "check_rendered_references",
    SCRIPTS_DIR / "check-rendered-references.py",
)
assert spec is not None and spec.loader is not None
crr = importlib.util.module_from_spec(spec)
sys.modules["check_rendered_references"] = crr
spec.loader.exec_module(crr)


class TestCheckRenderedReferences(unittest.TestCase):
    """Test suite for check_rendered_references functions."""

    def test_unresolved_crossrefs(self) -> None:
        content = (
            "Here is a reference to ?@def-coef-interp-procedure in the text.\n"
            "Also broken figure ?@fig-scatter-plot.\n"
        )
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "unresolved_crossref")
        self.assertEqual(findings[0].key, "def-coef-interp-procedure")
        self.assertEqual(findings[1].category, "unresolved_crossref")
        self.assertEqual(findings[1].key, "fig-scatter-plot")

    def test_missing_citations_bold_question(self) -> None:
        content_html = "According to <strong>smith2020?</strong> in recent work.\n"
        content_md = "According to **jones2021?** in recent work.\n"
        findings_html = crr.scan_content(content_html, "test.html")
        findings_md = crr.scan_content(content_md, "test.md")

        self.assertEqual(len(findings_html), 1)
        self.assertEqual(findings_html[0].category, "missing_citation")
        self.assertEqual(findings_html[0].key, "smith2020")

        self.assertEqual(len(findings_md), 1)
        self.assertEqual(findings_md[0].category, "missing_citation")
        self.assertEqual(findings_md[0].key, "jones2021")

    def test_unprocessed_raw_citations(self) -> None:
        content = "As shown in [@doe2022] and [@smith2020; @jones2021].\n"
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0].category, "unprocessed_citation")
        self.assertEqual(findings[0].key, "doe2022")
        self.assertEqual(findings[1].key, "smith2020")
        self.assertEqual(findings[2].key, "jones2021")

    def test_citeproc_suppressed_author(self) -> None:
        content = "As discussed previously [-@author2020] and [-@smith2021; -@doe2022].\n"
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 3)
        for f in findings:
            self.assertEqual(f.category, "unprocessed_citation")
        self.assertEqual(findings[0].key, "author2020")
        self.assertEqual(findings[1].key, "smith2021")
        self.assertEqual(findings[2].key, "doe2022")

    def test_citeproc_bracketed_complex(self) -> None:
        content = "Evidence in [see @author2020, pp. 10-15; also -@doe2021, chap. 3].\n"
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "unprocessed_citation")
        self.assertEqual(findings[0].key, "author2020")
        self.assertEqual(findings[1].category, "unprocessed_citation")
        self.assertEqual(findings[1].key, "doe2021")

    def test_citeproc_narrative_citations(self) -> None:
        content = (
            "According to @author2020, this holds.\n"
            "Also @knuth:1984 [p. 33] and @smith_2022 noted this.\n"
        )
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0].category, "unprocessed_citation")
        self.assertEqual(findings[0].key, "author2020")
        self.assertEqual(findings[1].key, "knuth:1984")
        self.assertEqual(findings[2].key, "smith_2022")

    def test_email_and_urls_not_flagged_as_citations(self) -> None:
        content = (
            "Contact support at user@example.com or dev.team@sub.domain.org.\n"
            "Visit https://git@github.com or [Email us](mailto:support@example.org).\n"
        )
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(findings, [])

    def test_code_fences_and_spans_ignored(self) -> None:
        content = (
            "Prose with code snippet:\n"
            "```markdown\n"
            "?@def-not-a-real-break\n"
            "**missing?**\n"
            "[@citation]\n"
            "```\n"
            "And inline code `?@def-inline` should be ignored.\n"
        )
        findings = crr.scan_content(content, "test.md")
        self.assertEqual(len(findings), 0)

    def test_valid_markdown_footnotes_not_flagged(self) -> None:
        """Ensure valid markdown footnote links and definitions are not flagged (ai-config#2879)."""
        content = (
            "# Document Title\n\n"
            "This is a statement with a numerical footnote[^1].\n"
            "Here is another statement with a named footnote[^note].\n"
            "And a hyphenated footnote reference[^custom-footnote-42].\n\n"
            "[^1]: This is the first footnote definition.\n"
            "[^note]: This is the named footnote definition with additional details.\n"
            "[^custom-footnote-42]: Definition with numbers and hyphens.\n"
        )
        findings = crr.scan_content(content, "document.md")
        self.assertEqual(
            findings,
            [],
            f"Expected 0 findings on valid markdown footnotes, got: {findings}",
        )

    def test_html_rendered_footnotes_not_flagged(self) -> None:
        content = (
            "<p>Statement with footnote"
            '<a href="#fn1" class="footnote-ref" id="fnref1" role="doc-noteref"><sup>1</sup></a>.</p>\n'
            '<section class="footnotes" role="doc-endnotes">\n'
            '<ol><li id="fn1"><p>Footnote content.<a href="#fnref1" class="footnote-back" role="doc-backlink">↩︎</a></p></li></ol>\n'
            "</section>\n"
        )
        findings = crr.scan_content(content, "document.html")
        self.assertEqual(findings, [])

    def test_mixed_document_isolation(self) -> None:
        """Ensure broken references are flagged while footnotes in the same file are ignored."""
        content = (
            "Valid footnote sentence[^1].\n"
            "Broken crossref sentence with ?@fig-missing.\n\n"
            "[^1]: Valid footnote definition.\n"
        )
        findings = crr.scan_content(content, "mixed.md")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "unresolved_crossref")
        self.assertEqual(findings[0].key, "fig-missing")

    def test_main_cli_clean(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "clean.md"
            test_file.write_text("Clean text with footnote[^1].\n\n[^1]: Note.", encoding="utf-8")

            # Test text mode
            rc = crr.main([str(test_file)])
            self.assertEqual(rc, 0)

            # Test JSON mode
            stdout_buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = stdout_buf
                rc = crr.main([str(test_file), "--json"])
                self.assertEqual(rc, 0)
                data = json.loads(stdout_buf.getvalue())
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["findings_count"], 0)
            finally:
                sys.stdout = old_stdout

    def test_main_cli_broken(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "broken.md"
            test_file.write_text("Broken text with ?@sec-missing and footnote[^1].\n", encoding="utf-8")

            stdout_buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = stdout_buf
                rc = crr.main([str(test_file), "--json"])
                self.assertEqual(rc, 1)
                data = json.loads(stdout_buf.getvalue())
                self.assertEqual(data["status"], "broken_references")
                self.assertEqual(data["findings_count"], 1)
                self.assertEqual(data["findings"][0]["key"], "sec-missing")
            finally:
                sys.stdout = old_stdout


if __name__ == "__main__":
    unittest.main()
