#!/usr/bin/env python3
"""Regression tests for check-section-refs.py.

The load-bearing cases are the negative controls: a synthetic corpus
carrying a KNOWN stale quoted reference, asserted to be reported, paired
with a KNOWN valid one, asserted NOT to be reported.  Until the checker has
been seen to fire on a real positive, a zero from it against the real corpus
is not evidence of anything (shared/principles/fail-fast.md).

check_repo() takes a root directory and globs, so each fixture is a small
temp-directory corpus rather than depending on this repo's real files.
"""
import sys
import tempfile
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "csr", Path(__file__).parent / "check-section-refs.py"
)
csr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csr)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


GLOBS = ["*.md", "docs/**/*.md"]


def write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def run(root: Path):
    return csr.check_repo(root, GLOBS)


def finding_keys(findings):
    return {(f["referring_file"].name, f["line"]) for f in findings}


# --- Form A: the negative control -------------------------------------------
# A known-STALE reference (quotes a title that used to be the heading, which
# has since been renamed) paired with a known-VALID one in the same corpus,
# so a single run proves both that the checker fires and that it does not
# over-fire.

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`target.md`](target.md)\'s "Old Renamed Title" for detail.\n\n'
        'See [`target.md`](target.md)\'s "Current Real Title" too.\n',
    )
    write(
        root, "target.md",
        "# Target\n\n## Current Real Title\n\nBody text.\n",
    )
    findings, examined, scanned = run(root)
    keys = finding_keys(findings)
    check(
        "Form A: a quote naming a renamed-away heading is flagged",
        ("citing.md", 1) in keys,
    )
    check(
        "Form A: a quote naming the real current heading is not flagged",
        ("citing.md", 3) not in keys,
    )
    check("references are counted", examined == 2)
    check("files are counted", scanned == 2)

# --- Form A: truncated quotes (substring, not just prefix) ------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "A cancelled dispatch that fired a" bullet.\n\n'
        'See [`t.md`](t.md)\'s "partial is worse than absent" bullet.\n',
    )
    write(
        root, "t.md",
        "## A cancelled dispatch that fired a failure webhook\n\n"
        "## In a guard you ship: partial is worse than absent\n",
    )
    findings, _, _ = run(root)
    keys = finding_keys(findings)
    check(
        "Form A: a quote that is a heading PREFIX is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form A: a quote that is a heading SUFFIX (after a colon) is not flagged",
        ("citing.md", 3) not in keys,
    )

# --- Bold-lead targets (paragraph and list-item) ----------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "A bolded paragraph lead" note.\n\n'
        'See [`t.md`](t.md)\'s "403 caveat" note.\n\n'
        'See [`t.md`](t.md)\'s "This bold lead is gone" note.\n',
    )
    write(
        root, "t.md",
        "**A bolded paragraph lead sentence.**\n\n"
        "- **403 caveat -- scoped sessions can only push one branch.**\n",
    )
    findings, _, _ = run(root)
    keys = finding_keys(findings)
    check(
        "a quote matching a paragraph-leading bold span is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "a quote matching a list item's own bold lead is not flagged",
        ("citing.md", 3) not in keys,
    )
    check(
        "a quote naming a bold lead that no longer exists is flagged",
        ("citing.md", 5) in keys,
    )

# --- Form A2: the comma idiom, scoped -----------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`x.cases.md`](x.cases.md), "A Real Case Title".\n\n'
        'See [`x.cases.md`](x.cases.md), "A Gone Case Title".\n\n'
        'See [`plain.md`](plain.md), "A Real Heading".\n\n'
        'Per [`plain.md`](plain.md), "just a quoted phrase" means nothing.\n',
    )
    write(root, "x.cases.md", "## A Real Case Title\n")
    write(root, "plain.md", "## A Real Heading\n\nAnother sentence.\n")
    findings, examined, _ = run(root)
    keys = finding_keys(findings)
    check(
        "Form A2: a comma-form quote matching a real .cases.md heading is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form A2: a comma-form quote naming a gone .cases.md heading is flagged",
        ("citing.md", 3) in keys,
    )
    check(
        'Form A2: a "See X, "quote"" citation to a plain heading is checked',
        ("citing.md", 5) not in keys,
    )
    check(
        'Form A2: an unscoped comma-quote ("Per X, ...") is never examined at all',
        examined == 3,  # only the three "See ..." references count
    )

# --- Form B: quoted link text -----------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'The ["Real Section"](t.md) explains this.\n\n'
        'The ["Gone Section"](t.md) explains that.\n',
    )
    write(root, "t.md", "## Real Section\n")
    findings, _, _ = run(root)
    keys = finding_keys(findings)
    check(
        "Form B: quoted link text matching a real heading is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form B: quoted link text naming a gone heading is flagged",
        ("citing.md", 3) in keys,
    )

# --- Code regions: fenced blocks and inline spans are handled correctly ----

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        "```\n"
        'See [`t.md`](t.md)\'s "A Gone Fenced Title" inside a fence.\n'
        "```\n\n"
        '`See [t.md](t.md)\'s "Also Gone" all inline-coded`\n\n'
        'See [`t.md`](t.md)\'s "`quoted` term title" for real prose.\n',
    )
    write(root, "t.md", "## `quoted` term title\n")
    findings, examined, _ = run(root)
    keys = finding_keys(findings)
    check(
        "a reference entirely inside a fenced code block is not examined",
        all(f["line"] != 2 for f in findings),
    )
    check(
        "a reference entirely inside one inline code span is not examined",
        all(f["line"] != 5 for f in findings),
    )
    check(
        "a quote containing a backtick-wrapped term still extracts and "
        "matches correctly (the code-span-corruption regression)",
        ("citing.md", 7) not in keys,
    )
    check(
        "only the real (non-code) reference was counted",
        examined == 1,
    )

# --- Missing target file: not our job (check-links.py's job) ---------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`missing.md`](missing.md)\'s "Anything" for detail.\n',
    )
    findings, examined, _ = run(root)
    check("a reference to a missing file is skipped, not flagged", findings == [])
    check("a reference to a missing file is not counted as examined", examined == 0)

# --- External links are ignored ---------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [GitHub](https://github.com)\'s "Anything at all" page.\n',
    )
    findings, examined, _ = run(root)
    check("an external link is never treated as a reference", examined == 0)
    check("an external link produces no finding", findings == [])

# --- MIN_QUOTE_LEN guard -----------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(root, "citing.md", 'See [`t.md`](t.md)\'s "Hi" for detail.\n')
    write(root, "t.md", "## Hi\n")
    findings, _, _ = run(root)
    check(
        "a quote shorter than MIN_QUOTE_LEN is flagged even if it "
        "technically matches (too short to trust as real evidence)",
        len(findings) == 1,
    )

# --- normalize() / quote_matches() unit checks ------------------------------

check(
    "normalize collapses whitespace across a wrapped quote",
    csr.normalize("Some\n  wrapped   text") == "some wrapped text",
)
check(
    "normalize strips backticks",
    csr.normalize("`ai-config` never") == "ai-config never",
)
check(
    "quote_matches finds a substring anywhere in a candidate",
    csr.quote_matches("middle bit", ["a middle bit of text"]),
)
check(
    "quote_matches rejects a quote below MIN_QUOTE_LEN",
    not csr.quote_matches("hi", ["hi there, this exists"]),
)

# --- exit code contract ------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(root, "a.md", "Nothing to see here.\n")
    rc = csr.main(["--root", str(root)])
    check("main() exits 0 on a clean corpus", rc == 0)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "A Gone Title" for detail.\n',
    )
    write(root, "t.md", "## Something Else\n")
    rc = csr.main(["--root", str(root)])
    check("main() exits 1 when a stale reference is found", rc == 1)

rc = csr.main(["--root", "/definitely/not/a/real/path/anywhere"])
check("main() exits 2 (usage error) on a bad --root", rc == 2)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
