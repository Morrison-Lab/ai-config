#!/usr/bin/env python3
"""Unit tests for scripts/lib/review_payload.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib.review_payload import (
    CLEAN_VERDICTS,
    NOT_CLEAN_VERDICTS,
    code_region_mask,
    extract_structured_review,
    normalize_verdict,
    payload_findings,
    payload_findings_malformed,
    payload_is_blocking,
    payload_is_clean,
)


class TestReviewPayload(unittest.TestCase):
    """Test suite for structured review-data payload helper."""

    def test_normalize_verdict(self):
        self.assertEqual(normalize_verdict("clean"), "CLEAN")
        self.assertEqual(normalize_verdict("Ready for merge"), "READY_FOR_MERGE")
        self.assertEqual(normalize_verdict("NOT-CLEAN"), "NOT_CLEAN")
        self.assertEqual(normalize_verdict("Needs more work"), "NEEDS_MORE_WORK")
        self.assertEqual(normalize_verdict(""), "")
        self.assertEqual(normalize_verdict(None), "")

    def test_extract_structured_review_clean(self):
        body = """
### Summary Verdict
Verdict: Ready for merge

Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b

<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "Claude",
  "commit_sha": "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b",
  "verdict": "CLEAN",
  "findings": []
}
-->
"""
        payload = extract_structured_review(body)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("verdict"), "CLEAN")
        self.assertEqual(payload.get("reviewer"), "Claude")
        self.assertTrue(payload_is_clean(payload))
        self.assertFalse(payload_is_blocking(payload))

    def test_extract_structured_review_not_clean(self):
        body = """
<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "adversarial-reviewer",
  "commit_sha": "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b",
  "verdict": "NOT_CLEAN",
  "findings": [
    {
      "file": "foo.py",
      "line": 10,
      "message": "Syntax error"
    }
  ]
}
-->
"""
        payload = extract_structured_review(body)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("verdict"), "NOT_CLEAN")
        self.assertFalse(payload_is_clean(payload))
        self.assertTrue(payload_is_blocking(payload))
        findings = payload_findings(payload)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["file"], "foo.py")

    def test_findings_override_clean_verdict(self):
        payload = {
            "verdict": "CLEAN",
            "findings": [{"file": "bar.py", "message": "Memory leak"}],
        }
        self.assertTrue(payload_is_blocking(payload))
        self.assertFalse(payload_is_clean(payload))

    def test_code_region_mask_ignores_quoted_examples(self):
        quoted = """
Here is how to structure review output:
```html
<!-- review-data:
{
  "verdict": "CLEAN",
  "findings": []
}
-->
```

Actual report follows:
<!-- review-data:
{
  "verdict": "NOT_CLEAN",
  "findings": [{"file": "main.py", "message": "Bug"}]
}
-->
"""
        payload = extract_structured_review(quoted)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("verdict"), "NOT_CLEAN")

    def test_inline_code_span_ignored(self):
        span = "Check `<!-- review-data: {\"verdict\": \"CLEAN\"} -->` for example."
        self.assertIsNone(extract_structured_review(span))

    def test_indented_code_block_ignored(self):
        indented = "    <!-- review-data: {\"verdict\": \"CLEAN\"} -->"
        self.assertIsNone(extract_structured_review(indented))

    def test_last_valid_payload_wins(self):
        body = """
<!-- review-data:
{
  "verdict": "CLEAN",
  "findings": []
}
-->

<!-- review-data:
{
  "verdict": "NOT_CLEAN",
  "findings": [{"file": "a.py", "message": "Err"}]
}
-->
"""
        payload = extract_structured_review(body)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("verdict"), "NOT_CLEAN")

    def test_code_region_mask_marks_each_region_and_nothing_else(self):
        """`code_region_mask` had no direct test -- it was exercised only
        through `extract_structured_review`, which cannot show WHICH region
        kind the mask attributed a character to.
        """
        body = "plain\n```\nfenced\n```\n    indented\nsee `span` here\n"
        mask = code_region_mask(body)
        self.assertEqual(len(mask), len(body))

        def masked(fragment):
            start = body.index(fragment)
            return set(mask[start:start + len(fragment)])

        self.assertEqual(masked("plain"), {0})
        self.assertEqual(masked("fenced"), {1})
        self.assertEqual(masked("indented"), {1})
        self.assertEqual(masked("`span`"), {1})
        self.assertEqual(masked("see "), {0})

    def test_code_region_mask_offset_arithmetic_edge_cases(self):
        for label, body in {
            "empty": "",
            "no trailing newline": "    indented",
            "CRLF": "a\r\n    indented\r\nb",
            "tab indent": "\tindented\n",
            "multi-byte": "caf\u00e9\n    indented\n",
        }.items():
            with self.subTest(body=label):
                self.assertEqual(len(code_region_mask(body)), len(body))

    def test_verdict_vocabularies_are_disjoint(self):
        """A string in both sets would make `payload_is_blocking` and
        `payload_is_clean` true at once, and the two callers order those
        checks differently.
        """
        self.assertFalse(CLEAN_VERDICTS & NOT_CLEAN_VERDICTS)
        for verdict in CLEAN_VERDICTS | NOT_CLEAN_VERDICTS:
            with self.subTest(verdict=verdict):
                self.assertEqual(normalize_verdict(verdict), verdict,
                                 "set members must already be in normalized form")

    def test_malformed_findings_block_rather_than_clear(self):
        """A present-but-non-list `findings` must never CLEAR, only block.

        Folding it to `[]` made a type deviation do what an empty array does,
        so a payload reading `"findings": "3 defects listed above"` satisfied
        quorum and the PR gate reported fully clean.
        """
        for label, value in {
            "string": '"3 defects listed above"',
            "object": '{"a": 1}',
            "number": "3",
            "null": "null",
        }.items():
            with self.subTest(findings=label):
                body = ('<!-- review-data: {"verdict": "CLEAN", "findings": '
                        + value + "} -->")
                payload = extract_structured_review(body)
                self.assertIsNotNone(payload)
                self.assertTrue(payload_findings_malformed(payload))
                self.assertTrue(payload_is_blocking(payload))
                self.assertFalse(payload_is_clean(payload))
                self.assertEqual(payload_findings(payload), [])

    def test_absent_findings_key_lets_the_verdict_decide(self):
        clean = extract_structured_review('<!-- review-data: {"verdict": "CLEAN"} -->')
        self.assertFalse(payload_findings_malformed(clean))
        self.assertTrue(payload_is_clean(clean))
        self.assertFalse(payload_is_blocking(clean))
        blocking = extract_structured_review('<!-- review-data: {"verdict": "NOT_CLEAN"} -->')
        self.assertTrue(payload_is_blocking(blocking))
        self.assertFalse(payload_is_clean(blocking))

    def test_empty_or_none_inputs(self):
        self.assertIsNone(extract_structured_review(""))
        self.assertIsNone(extract_structured_review(None))
        self.assertFalse(payload_is_blocking(None))
        self.assertFalse(payload_is_clean(None))
        self.assertEqual(payload_findings(None), [])


if __name__ == "__main__":
    unittest.main()
