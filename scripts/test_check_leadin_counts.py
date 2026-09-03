#!/usr/bin/env python3
"""Tests for scripts/check-leadin-counts.py (ai-config#3005).

The negative control comes first and carries the most weight: a fixture in
the exact shape of the measured instance -- a lead-in saying two above three
bold-header paragraphs -- that the checker MUST catch. A zero result is
otherwise indistinguishable from a detector that never ran, which is
`shared/workflow/batch-merge-and-resolve.md`'s rule.

The rest are mostly must-NOT-fire cases, inverting the usual balance for a
detector on purpose. This checker reads ordinary prose, where a numeral or a
count word next to a list is far commoner than a real mismatch, so the cases
proving it stays quiet are what make it usable at all.
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "leadin", Path(__file__).parent / "check-leadin-counts.py"
)
leadin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(leadin)

passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


def findings(text):
    return leadin.scan_text(text)


def fires(text):
    return bool(findings(text))


# The measured instance from ai-config#3005: memories/quarto-sites.md said
# "Two things ..." after an edit split the second item, and three bold-header
# paragraphs followed it.
NEGATIVE_CONTROL = """## A section

Prose above the lead-in.

Two things the new observation adds to those two records.

**The blast radius is the whole site.**
Body prose under the first item.

**A green CI check was no evidence either way.**
Body prose under the second item.

**The later run's log reads like a multi-format render.**
Body prose under the third item.
"""


def main():
    # --- negative control: the known mismatch must be caught ---
    hits = findings(NEGATIVE_CONTROL)
    check("negative control fires", len(hits) == 1)
    if hits:
        line_no, stated, actual, kind, _ = hits[0]
        check("negative control reports the stated count", stated == 2)
        check("negative control reports the actual count", actual == 3)
        check("negative control names the shape", kind == "bold-header paragraph")
        check("negative control points at the lead-in line", line_no == 5)

    # --- must fire: list shapes ---
    for text, label in [
        ("Two reasons:\n\n- first\n- second\n- third\n", "a bulleted list"),
        ("Three steps to run:\n\n1. one\n2. two\n", "a numbered list"),
        ("Two lessons follow:\n- alpha\n- beta\n- gamma\n",
         "a list starting on the next line"),
        ("Four freshness checks to run each session.\n\n- a\n- b\n- c\n",
         "a lead-in whose noun trails an adjective"),
    ]:
        check(f"fires on {label}", fires(text))

    # --- must NOT fire: the count and the items agree ---
    for text, label in [
        ("Two reasons:\n\n- first\n- second\n", "a matching bulleted list"),
        ("Three steps:\n\n1. one\n2. two\n3. three\n", "a matching numbered list"),
        ("Two things follow.\n\n**First.**\nBody.\n\n**Second.**\nBody.\n",
         "matching bold headers"),
    ]:
        check(f"does NOT fire on {label}", not fires(text))

    # --- must NOT fire: the count is not about the list ---
    for text, label in [
        ("Three of those runs failed:\n\n- a\n- b\n",
         "a count followed by 'of'"),
        ("Those three checks are worth repeating:\n\n- a\n- b\n",
         "an explicit back-reference"),
        ("The three rules above compose:\n\n- a\n- b\n",
         "a cross-reference to content above"),
        ("It is a cheap habit with two payoffs rather than a new one.\n\n"
         "- alpha\n- beta\n- gamma\n",
         "a count buried mid-sentence"),
        ("We ran it three times. The result was clean.\n\n- a\n- b\n",
         "a count in an earlier sentence of the line"),
        ("Two was the count agreed.\n\n- a\n- b\n- c\n",
         "a count with no plural noun after it"),
        ("Holding two variables at once is hard.\n\n- a\n- b\n- c\n",
         "a count that names something other than the list"),
        ("One thing to note:\n\n- a\n- b\n", "the word 'one'"),
        ("Write 3 sentences explaining the purpose:\n\n- a\n- b\n- c\n",
         "a bare numeral"),
    ]:
        check(f"does NOT fire on {label}", not fires(text))

    # --- structural bounds ---
    check(
        "does NOT fire when the enumeration is two blank lines below",
        not fires("Two reasons:\n\n\n- a\n- b\n- c\n"),
    )
    check(
        "does NOT fire when the lead-in ends a multi-line paragraph",
        not fires("A sentence of context.\nTwo reasons to care:\n\n- a\n- b\n- c\n"),
    )
    check(
        "does NOT fire when the lead-in is itself a list item",
        not fires("- Interleaving the two phases is the anti-pattern.\n"
                  "- Another anti-pattern.\n- A third.\n"),
    )
    check(
        "does NOT fire on a bold phrase opening the lead-in's own paragraph",
        not fires("Two mechanisms make this survivable.\n"
                  "**Delegate the pass**, per the fragment above.\n"
                  "And **algorithmatize the trigger** as well.\n\n"
                  "**A later header.**\nBody.\n\n"
                  "**Another later header.**\nBody.\n"),
    )
    check(
        "does NOT fire inside a fenced code block",
        not fires("```\nTwo reasons:\n\n- a\n- b\n- c\n```\n"),
    )

    # --- list-counting details ---
    check(
        "a lazy continuation line does not truncate the item count",
        not fires("Two things that stay:\n\n"
                  "- **The per-item hold.**\n"
                  "That is about not re-litigating one item.\n"
                  "- **Reporting the round count.**\n"
                  "Saying so is useful information.\n"),
    )
    check(
        "a Do/Don't block ends the run rather than padding it",
        not fires("Two consequences worth keeping straight:\n\n"
                  "- first\n- second\n\n"
                  "- **Do:** one thing\n- **Don't:** another thing\n"),
    )
    check(
        "an enumeration that opens with a Do/Don't block is not counted",
        not fires("Two consequences follow.\n\n"
                  "- **Do:** one thing\n"
                  "- **Do:** a second thing\n"
                  "- **Don't:** a third thing\n"),
    )
    check(
        "a nested list item does not count as a sibling",
        not fires("Two reasons:\n\n- first\n  - nested\n- second\n"),
    )
    check(
        "the run stops at the next heading",
        not fires("Two reasons:\n\n- first\n- second\n\n## Next\n\n- third\n"),
    )

    # --- bold-header overshoot is discounted, not reported ---
    over = ("Two shapes, both measured.\n\n"
            "**The first shape.**\nBody.\n\n"
            "**A sub-point under it.**\nBody.\n\n"
            "**Another sub-point.**\nBody.\n\n"
            "**The second shape.**\nBody.\n\n"
            "**A trailing sub-point.**\nBody.\n")
    check("a bold run overshooting by more than one is not reported", not fires(over))
    check(
        "a bold run overshooting by exactly one IS reported",
        fires("Two shapes, both measured.\n\n"
              "**The first.**\nBody.\n\n"
              "**The second.**\nBody.\n\n"
              "**A third.**\nBody.\n"),
    )
    check(
        "a bold run falling short of the stated count IS reported",
        fires("Three shapes, all measured.\n\n"
              "**The first.**\nBody.\n\n"
              "**The second.**\nBody.\n"),
    )

    # --- exit codes and the reported population ---
    tmp = Path(tempfile.mkdtemp())
    leadin.ROOT = tmp
    bad = tmp / "bad.md"
    bad.write_text(NEGATIVE_CONTROL, encoding="utf-8")
    good = tmp / "good.md"
    good.write_text("Two reasons:\n\n- a\n- b\n", encoding="utf-8")
    other = tmp / "notes.txt"
    other.write_text("Two reasons:\n\n- a\n- b\n- c\n", encoding="utf-8")

    found, examined = leadin.scan([bad, good, other])
    check("scan reports the population it examined", examined == 2)
    check("scan skips a non-markdown file", len(found) == 1)

    check("main exits 1 on a mismatch", leadin.main([str(bad)]) == 1)
    check("main exits 0 when every count matches", leadin.main([str(good)]) == 0)

    # A check that examined nothing reports clean and is indistinguishable
    # from one that passed, so an empty population is exit 2.
    real_tracked = leadin.tracked_files
    leadin.tracked_files = lambda: []
    try:
        rc = leadin.main([])
    finally:
        leadin.tracked_files = real_tracked
    check("examining zero files exits 2, not 0", rc == 2)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
