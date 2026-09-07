#!/usr/bin/env python3
"""Tests for scripts/check-rendered-page.py.

The two design decisions that carry the value each have a test, and each
exists because getting it wrong was measured on real pages:

FALSE POSITIVES sink a checker. A text-level `word?` citation scan reported
eleven hits on a page with no citation problem, and a regex-based math strip
reported twenty unexpanded macros on the same page. Both are pinned here as
negative cases.

FALSE NEGATIVES are worse and less visible. Suppressing that citation noise
by skipping `class="citation"` made the checker silent on the exact defect it
exists for, because pandoc puts the unresolved-key markup inside that class.
That is pinned as a positive case.

Run: python3 scripts/test_check_rendered_page.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "checker", Path(__file__).parent / "check-rendered-page.py"
)
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)


# Pandoc's real rendering of an unresolved key, copied from a live rme
# preview (pr-1140, chapters/parametric-survival-models.html).
UNRESOLVED_CITE = (
    '<p>alongside the scale parameter '
    '<span class="citation" data-cites="kalbfleisch2002">'
    '(<a href="#ref-kalbfleisch2002" role="doc-biblioref">'
    '<strong>kalbfleisch2002?</strong></a>)</span>.</p>'
)
# A RESOLVED citation, same markup shape minus the trailing `?`.
RESOLVED_CITE = (
    '<p>see <span class="citation" data-cites="kalbfleisch2011statistical">'
    '(<a href="#ref-kalbfleisch2011statistical" role="doc-biblioref">'
    'Kalbfleisch and Prentice 2011</a>)</span>.</p>'
)
# KaTeX output nests several spans deep; a non-greedy regex strip stops at
# the first inner close and leaks the rest into the prose.
NESTED_MATH = (
    '<p>the estimator <span class="math inline"><span class="katex">'
    '<span class="katex-mathml"><math><semantics>'
    '<annotation encoding="application/x-tex">\\hat{\\beta}\\eqdef\\eta</annotation>'
    '</semantics></math></span><span class="katex-html">'
    '<span class="base"><span class="mord">x</span></span></span>'
    '</span></span> is unbiased.</p>'
)

CASES = [
    ("an unresolved citation is caught",
     UNRESOLVED_CITE, "unresolved citation key", True),
    ("a resolved citation is not flagged",
     RESOLVED_CITE, "unresolved citation key", False),
    ("ordinary prose ending in a question mark is not a citation",
     "<p>Is that assumption plausible? Is the measurement ordinal?</p>",
     "unresolved citation key", False),
    ("nested KaTeX does not leak macros into prose",
     NESTED_MATH, "unexpanded macro in rendered text", False),
    ("a macro in real prose is caught",
     "<p>The estimator \\vL was never defined.</p>",
     "unexpanded macro in rendered text", True),
    ("a list that lost its blank line is caught",
     "<p>- a bullet that rendered as a paragraph</p>",
     "list rendered as a paragraph", True),
    ("a real list is not flagged",
     "<ul><li>a genuine list item</li></ul>",
     "list rendered as a paragraph", False),
    ("a numbered list that lost its blank line is caught",
     "<p>1. a numbered bullet that rendered as a paragraph</p>",
     "list rendered as a paragraph", True),
    ("an unresolved crossref is caught",
     "<p>See ?@fig-missing for details.</p>", "unresolved crossref", True),
    ("a katex-error span is caught",
     '<span class="katex-error" title="x">\\eExp{}</span>',
     "KaTeX / LaTeX error", True),
    # Pins the SKIP_CLASS decision. Quarto emits a literal `?@fig-x` INSIDE
    # a citation span; adding "citation" to SKIP_CLASS makes it invisible.
    # The live false positive found on a 4.3 MB real page: a display
    # equation ending `... + \\hat\\beta_p x_p` puts a `+` right after the
    # ellipsis's final `.`, which the mid-paragraph branch read as a bullet.
    # _list_failed was the one check not routed through the parser.
    ("a display equation with '... +' is not a broken list",
     '<p><span class="math display">\\[\\begin{aligned}'
     '\\hat\\beta_0 \\cdot 1 + \\hat\\beta_1 x_1 + ... + \\hat\\beta_p x_p'
     '\\end{aligned}\\]</span></p>',
     "list rendered as a paragraph", False),
    # Inline <code> is common in this corpus's own prose, showing markdown
    # syntax or a literal @key. Without `code` in SKIP_TAGS those examples
    # become findings on every page that documents a convention.
    ("a markdown example inside inline code is not a broken list",
     '<p>Write it as <code>- item</code> in the source.</p>',
     "list rendered as a paragraph", False),
    ("a crossref example inside inline code is not a finding",
     '<p>Write <code>?@fig-x</code> to reference a figure.</p>',
     "unresolved crossref", False),
    ("a citation example inside inline code is not a finding",
     '<p>Use <code>?@fig-x</code> to see the failure.</p>',
     "unresolved citation key", False),
    # Pandoc's ACTUAL output when a list loses its blank line after a
    # lead-in sentence: the marker ends up mid-paragraph, not at <p> start.
    # This is the commoner shape, since a list usually introduces something.
    ("a bullet list after a lead-in sentence is caught",
     '<p>Some paragraph of prose here. - <strong>Do:</strong> run the checker.</p>',
     "list rendered as a paragraph", True),
    ("a colon lead-in followed by a bullet is caught",
     '<p>Steps: - first thing</p>', "list rendered as a paragraph", True),
    # The false positives that forced mid-paragraph detection to bullets only.
    ("an abbreviation followed by a sentence is not a list",
     '<p>See Fig. 1. It shows the trend.</p>',
     "list rendered as a paragraph", False),
    ("decimals in prose are not a list",
     '<p>values are 1. 2. and 3. in order</p>',
     "list rendered as a paragraph", False),
    ("a hyphenated word is not a list",
     '<p>a-b hyphenated</p>', "list rendered as a paragraph", False),
    # Pins the second KaTeX-error branch, which survived a mutation.
    ("a bare Undefined control sequence is caught",
     '<p>Undefined control sequence \\vL at line 3</p>',
     "KaTeX / LaTeX error", True),
    # Pins EXACT class-token exclusion. Substring containment also matches
    # `gt_footnotes`, a real class gt emits on live pages, so a genuine
    # defect inside a gt table footer became invisible to every check.
    ("a class merely CONTAINING an excluded name is not excluded",
     '<div class="gt_footnotes odd"><p>The estimator \\vL was never defined.</p></div>',
     "unexpanded macro in rendered text", True),
    ("a genuinely excluded class is still excluded",
     '<div class="footnotes"><p>\\vL</p></div>',
     "unexpanded macro in rendered text", False),
    # Pins the list detector's tolerance. `- **Do:** ...` is this corpus's
    # own commonest bullet shape, and an earlier 3-plain-character bound
    # missed it because the tag arrives immediately after the marker.
    ("a broken list item opening with inline markup is caught",
     '<p>- <strong>Do:</strong> run the checker before pushing.</p>',
     "list rendered as a paragraph", True),
    ("a short broken list item is caught",
     '<p>- ok</p>', "list rendered as a paragraph", True),
    ("a dash inside ordinary prose is not a list",
     '<p>the range a - b is inclusive</p>',
     "list rendered as a paragraph", False),
    ("a literal ?@ inside a citation span is still caught",
     '<span class="citation" data-cites="fig-x">?@fig-x</span>',
     "unresolved citation key", True),
    ("the bibliography's raw keys are not flagged",
     '<div class="csl-entry" id="ref-x">Author. ?@notacite</div>',
     "unresolved citation key", False),
    ("a code block quoting a macro is not flagged",
     "<pre><code>\\vL and \\eqdef appear here</code></pre>",
     "unexpanded macro in rendered text", False),
]


def run_checks(html):
    """Return {label: hits} for every check that fired."""
    out = {}
    for label, fn in checker.CHECKS:
        found = fn(html)
        if found:
            out[label] = found
    return out


def main():
    passes = failures = 0
    for name, html, label_frag, want in CASES:
        fired = run_checks(html)
        got = any(label_frag in k for k in fired)
        if got == want:
            print(f"PASS: {name}")
            passes += 1
        else:
            print(f"FAIL: {name} (expected {want}, got {got}; fired={list(fired)})")
            failures += 1

    # A clean page must produce NO findings at all, not merely none of one
    # kind -- a per-check assertion cannot catch a checker that fires
    # something else on every page it sees.
    clean = "<html><body><p>Ordinary prose.</p><ul><li>item</li></ul></body></html>"
    if not run_checks(clean):
        print("PASS: a wholly clean page fires nothing"); passes += 1
    else:
        print(f"FAIL: clean page fired {list(run_checks(clean))}"); failures += 1

    # Exit codes are the contract for CI use.
    import tempfile, os, subprocess
    fd, p = tempfile.mkstemp(suffix=".html"); os.close(fd)
    open(p, "w").write(UNRESOLVED_CITE)
    rc = subprocess.run([sys.executable, str(Path(__file__).parent / "check-rendered-page.py"), p],
                        capture_output=True).returncode
    os.unlink(p)
    if rc == 1:
        print("PASS: a defective page exits 1"); passes += 1
    else:
        print(f"FAIL: defective page exited {rc}, want 1"); failures += 1

    rc = subprocess.run([sys.executable, str(Path(__file__).parent / "check-rendered-page.py"),
                         "/nonexistent-target-xyz"], capture_output=True).returncode
    if rc == 2:
        print("PASS: an unfetchable target exits 2"); passes += 1
    else:
        print(f"FAIL: unfetchable target exited {rc}, want 2"); failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
