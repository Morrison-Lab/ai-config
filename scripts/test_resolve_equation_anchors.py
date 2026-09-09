#!/usr/bin/env python3
"""Tests for scripts/resolve-equation-anchors.py.

The cases that matter are the ones where a wrong replay still produces a
plausible-looking mapping:

1. A labeled equation must keep its own id and consume NO counter number.
   If it consumed one, every later anchor would be off by the number of
   labeled equations, and the output would still look like a valid list.
2. Two display equations sharing one parent must yield ONE generated
   anchor, because the script mutates the parent's id and the second
   equation then finds it. A replay that tracks assignment in a side table
   instead of mutating gets this wrong, and gets it wrong only on pages
   that happen to have such a pair.
3. A page with no display equations must fail rather than report an empty
   mapping, so "the parser could not read this" is distinguishable from
   "this page has no equations".
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "resolve_equation_anchors", os.path.join(HERE, "resolve-equation-anchors.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def page(body: str) -> str:
    return f"<html><body>{body}</body></html>"


def display(latex: str) -> str:
    return f'<span class="math display">{latex}</span>'


class ResolveAnchors(unittest.TestCase):
    def test_unlabeled_equations_number_in_document_order(self):
        html = page(
            f"<p>{display('a')}</p><p>{display('b')}</p><p>{display('c')}</p>"
        )
        resolved = MODULE.resolve_anchors(html)
        self.assertEqual(
            [r["anchor"] for r in resolved],
            ["eq-anchor-1", "eq-anchor-2", "eq-anchor-3"],
        )
        self.assertEqual([r["latex"] for r in resolved], ["a", "b", "c"])
        self.assertTrue(all(r["generated"] for r in resolved))

    def test_labeled_equation_consumes_no_counter_number(self):
        html = page(
            f"<p>{display('a')}</p>"
            f'<span id="eq-named">{display("b")}</span>'
            f"<p>{display('c')}</p>"
        )
        resolved = MODULE.resolve_anchors(html)
        self.assertEqual(
            [r["anchor"] for r in resolved],
            ["eq-anchor-1", "eq-named", "eq-anchor-2"],
        )
        self.assertEqual(
            [r["generated"] for r in resolved], [True, False, True]
        )

    def test_two_equations_in_one_parent_share_a_single_anchor(self):
        html = page(f"<p>{display('a')}{display('b')}</p>")
        resolved = MODULE.resolve_anchors(html)
        self.assertEqual(
            [r["anchor"] for r in resolved], ["eq-anchor-1", "eq-anchor-1"]
        )

    def test_parent_id_that_is_not_an_eq_label_is_reused_not_renumbered(self):
        html = page(f'<p id="para">{display("a")}</p><p>{display("b")}</p>')
        resolved = MODULE.resolve_anchors(html)
        self.assertEqual(
            [r["anchor"] for r in resolved], ["para", "eq-anchor-1"]
        )

    def test_page_with_no_display_equations_fails(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False
        ) as handle:
            handle.write(page("<p>no math here</p>"))
            path = handle.name
        try:
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                status = MODULE.main([path])
            self.assertEqual(status, 2)
            self.assertIn("no display equations", err.getvalue())
        finally:
            os.unlink(path)

    def test_selecting_a_missing_anchor_reports_failure(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False
        ) as handle:
            handle.write(page(f"<p>{display('a')}</p>"))
            path = handle.name
        try:
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = MODULE.main([path, "--anchor", "9"])
            self.assertEqual(status, 1)
            self.assertIn("eq-anchor-9 does not exist", err.getvalue())
            self.assertEqual(out.getvalue().strip(), "")
        finally:
            os.unlink(path)

    def test_selecting_a_present_anchor_prints_only_that_equation(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False
        ) as handle:
            handle.write(
                page(f"<p>{display('a')}</p><p>{display('wanted')}</p>")
            )
            path = handle.name
        try:
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                status = MODULE.main([path, "--anchor", "2"])
            self.assertEqual(status, 0)
            printed = out.getvalue()
            self.assertIn("wanted", printed)
            self.assertNotIn("eq-anchor-1", printed)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
