#!/usr/bin/env python3
"""Regression tests for check-bare-fragment-mentions.py.

The load-bearing case is the negative control: a synthetic file carrying a
KNOWN bare mention after a KNOWN link, asserted to produce a finding.  Until
the checker has been seen to produce a non-zero, a zero from it against the
real corpus is not evidence of anything (shared/principles/fail-fast.md).

The second load-bearing case is line fidelity.  A finding that names the wrong
line is worse than no finding, because the reader looks at innocent prose and
concludes the checker is noise, so a multi-line code span before the mention
is asserted not to shift the reported line number.

Fixtures live in a tmpdir, so no fixture .md file lands anywhere the corpus
scan would pick it up.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cbfm", Path(__file__).parent / "check-bare-fragment-mentions.py"
)
cbfm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cbfm)

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


HERE = Path("docs/host.md")


def scan(body, md=HERE):
    """Findings for one synthetic file body."""
    findings, _, _ = cbfm.scan_text(body, md)
    return findings


def exemptions(body, md=HERE):
    _, exempt, _ = cbfm.scan_text(body, md)
    return exempt


LINKED = "See [`quotable-findings`](quotable-findings.md) for the rule.\n"

# --- the detector fires at all -----------------------------------------------

found = scan(LINKED + "\nThe quotable-findings rule applies here too.\n")
check(
    "a bare mention after a link is reported",
    [(f["fragment"], f["link_line"], f["bare_lines"]) for f in found]
    == [("quotable-findings", 1, [3])],
)
check(
    "a link with no later bare mention is clean",
    scan(LINKED + "\nNothing else names it.\n") == [],
)

# --- line fidelity -----------------------------------------------------------

MULTILINE_SPAN = LINKED + "\nA span `git log\n--name-only` wraps two lines.\n\nThen quotable-findings appears bare.\n"
check(
    "a code span crossing a line does not shift the reported line number",
    # The bare mention sits on line 6 of the fixture; collapsing the span
    # would report line 5 and point the reader at innocent prose.
    [f["bare_lines"] for f in scan(MULTILINE_SPAN)] == [[6]],
)

# --- regions that are not prose ----------------------------------------------

check(
    "a mention inside an inline code span is not a bare mention",
    scan(LINKED + "\nRun `quotable-findings` now.\n") == [],
)
check(
    "a mention inside a fenced block is not a bare mention",
    scan(LINKED + "\n```\nquotable-findings\n```\n") == [],
)
check(
    "a mention inside a second link's text is not a bare mention",
    scan(LINKED + "\nAlso [quotable-findings](other.md) here.\n") == [],
)
check(
    "a blockquoted mention is not a bare mention",
    # Quoted review text names a fragment it is reporting on.
    scan(LINKED + "\n> the quotable-findings rule\n") == [],
)
check(
    "a heading naming the fragment is not a bare mention",
    scan(LINKED + "\n## quotable-findings\n") == [],
)
check(
    "a mention inside a double-quoted span is not a bare mention",
    scan(LINKED + '\nThe log said "actor: quotable-findings (type: Bot)".\n') == [],
)
check(
    "a quoted span wrapped at a semantic line break is still exempt",
    # This corpus wraps quotations constantly, so a line-local quote guard
    # would miss most of them.  Measured on memories/claude-bot-workflows.md,
    # where a CI error message opens on one line and closes on the next.
    scan(LINKED + '\nHe said "the first half\nnames quotable-findings here".\n')
    == [],
)
check(
    "a mention inside an HTML comment is not a bare mention",
    scan(LINKED + "\n<!-- TODO: quotable-findings later -->\n") == [],
)
check(
    "a mention inside an indented code block is not a bare mention",
    scan(LINKED + "\n    grep quotable-findings docs/*.md\n") == [],
)
check(
    "an indented list continuation line is still prose",
    # The indented-code rule must not swallow a list whose continuation is
    # indented for readability, which is the commoner shape in this corpus.
    [f["bare_lines"] for f in scan(LINKED + "\n- a list item\n\n    quotable-findings applies.\n")]
    == [[5]],
)
check(
    "a setext heading naming the fragment is not a bare mention",
    scan(LINKED + "\nquotable-findings\n=================\n") == [],
)
check(
    "a wiki-style cross-link is not a bare mention",
    # `[[name]]` is a first-class link form in memory bodies; see
    # skills/consolidate-memory/SKILL.md.
    scan(LINKED + "\nAnd per [[quotable-findings]], see above.\n") == [],
)
check(
    "a wiki-style cross-link establishes the link, so a later bare mention counts",
    [f["bare_lines"] for f in scan("See [[quotable-findings]].\n\nThe quotable-findings rule.\n")]
    == [[3]],
)
check(
    "an @-import establishes the link, so a later bare mention counts",
    [f["bare_lines"] for f in scan("@shared/workflow/quotable-findings.md\n\nThe quotable-findings rule.\n")]
    == [[3]],
)
check(
    "a mention inside a URL path is not a bare mention",
    scan(LINKED + "\nSee https://example.com/quotable-findings for it.\n") == [],
)
check(
    "a bare repo path is not a bare mention",
    scan(LINKED + "\nSee shared/workflow/quotable-findings.md instead.\n") == [],
)
check(
    "a longer slug containing the name is not a bare mention",
    scan(LINKED + "\nThe quotable-findings-2 variant differs.\n") == [],
)

# --- scope boundaries --------------------------------------------------------

check(
    "a fragment the file never links is out of scope",
    # The mention may be incidental, so the evidence is not unambiguous.
    scan("The quotable-findings rule applies here.\n") == [],
)
check(
    "a bare mention before the first link is not reported",
    scan("The quotable-findings rule.\n\n" + LINKED) == [],
)
check(
    "one finding per (file, fragment), listing every bare line",
    [f["bare_lines"] for f in scan(LINKED + "\nquotable-findings.\n\nquotable-findings.\n")]
    == [[3, 5]],
)
check(
    "a sentence-initial capitalized mention is still a bare mention",
    [f["bare_lines"] for f in scan(LINKED + "\nQuotable-findings governs this.\n")]
    == [[3]],
)

# --- self-reference ----------------------------------------------------------

check(
    "a fragment naming itself is not reported",
    scan(LINKED, md=Path("shared/workflow/quotable-findings.md")) == [],
)
check(
    "a .rationale.md companion naming its parent is not reported",
    scan(
        LINKED + "\nquotable-findings says so.\n",
        md=Path("shared/workflow/quotable-findings.rationale.md"),
    )
    == [],
)
check(
    "a SKILL.md naming its own directory is not reported",
    scan(
        "See [`ardi-loop`](ardi-loop.md).\n\nThe ardi-loop step applies.\n",
        md=Path("skills/ardi-loop/SKILL.md"),
    )
    == [],
)

# --- container basenames resolve to their directory ---------------------------

check(
    "a link to skills/<name>/SKILL.md registers <name>, not SKILL",
    # Taking the basename would collapse every skill cross-reference --- the
    # dominant form in this corpus --- onto one pseudo-fragment.
    cbfm.fragment_name("../skills/post-merge/SKILL.md") == "post-merge",
)
check(
    "a bare mention after a SKILL.md link is reported",
    [f["fragment"] for f in scan(
        "See [`post-merge`](../skills/post-merge/SKILL.md).\n\nRun the post-merge step.\n"
    )]
    == ["post-merge"],
)
check(
    "a bare README.md link keeps its own stem, having no directory to borrow",
    cbfm.fragment_name("README.md") == "README",
)

# --- exemptions are reported, not silent -------------------------------------

single = exemptions("See [`ardi`](ardi.md).\n\nThe ardi loop applies.\n")
check(
    "an unhyphenated basename is exempt as single-word",
    [(e["fragment"], e["reason"]) for e in single] == [("ardi", "single-word")],
)
check(
    "an unhyphenated basename produces no finding",
    scan("See [`ardi`](ardi.md).\n\nThe ardi loop applies.\n") == [],
)

phrase = exemptions("See [`fail-fast`](fail-fast.md).\n\nWe fail-fast here.\n")
check(
    "a name that is also ordinary English is exempt as common-phrase",
    [(e["fragment"], e["reason"]) for e in phrase] == [("fail-fast", "common-phrase")],
)
check(
    "the common-phrase list is configurable",
    cbfm.scan_text(
        "See [`odd-name`](odd-name.md).\n\nThe odd-name rule.\n", HERE, ("odd-name",)
    )[1][0]["reason"]
    == "common-phrase",
)

script = cbfm.scan_text(
    "See [`some-tool`](some-tool.md).\n\nThe some-tool run failed.\n",
    HERE,
    cbfm.DEFAULT_COMMON_PHRASES,
    frozenset({"some-tool"}),
)
check(
    "a basename that also names a script is exempt as script-name",
    # `semantic-line-breaks` is a shared/writing fragment and a scripts/ file
    # at once, so a bare occurrence may be naming the executable.
    [(e["fragment"], e["reason"]) for e in script[1]] == [("some-tool", "script-name")],
)
check(
    "a basename that also names a script produces no finding",
    script[0] == [],
)

# --- corpus walk -------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "docs").mkdir()
    (root / "docs" / "host.md").write_text(
        LINKED + "\nThe quotable-findings rule applies.\n", encoding="utf-8"
    )
    (root / "docs" / "quotable-findings.md").write_text("# Rule\n", encoding="utf-8")
    (root / "docs" / "host.cases.md").write_text(
        LINKED + "\nThe quotable-findings rule applies.\n", encoding="utf-8"
    )
    report = cbfm.collect(root, ["docs/**/*.md"])
    check(
        "collect reports the host file's finding",
        [(f["path"], f["fragment"]) for f in report["findings"]]
        == [("docs/host.md", "quotable-findings")],
    )
    check(
        "a .cases.md companion is skipped whole",
        report["case_records_skipped"] == 1,
    )
    check(
        "collect reports what it examined, not only what it found",
        # A run that scanned nothing must be distinguishable from a clean corpus.
        report["files_scanned"] == 2 and report["links_considered"] == 1,
    )

# --- the command-line surface ------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "docs").mkdir()
    (root / "docs" / "host.md").write_text(
        "See [`odd-name`](odd-name.md) and [`fail-fast`](fail-fast.md).\n"
        "\nThe odd-name rule, and we fail-fast here.\n",
        encoding="utf-8",
    )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        cbfm.main(
            ["--root", str(root), "--glob", "docs/**/*.md",
             "--common-phrase", "odd-name", "--json"]
        )
    tuned = json.loads(buffer.getvalue())
    check(
        "--common-phrase adds to the built-in list rather than replacing it",
        # Replacing would drop `fail-fast` back into findings, so the one
        # documented way to tune the checker would make it noisier.
        sorted((e["fragment"], e["reason"]) for e in tuned["exempt"])
        == [("fail-fast", "common-phrase"), ("odd-name", "common-phrase")]
        and tuned["findings"] == [],
    )

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    exit_code = cbfm.main(
        ["--root", str(Path(__file__).resolve().parent.parent), "--json"]
    )
check("the checker is advisory and always exits 0", exit_code == 0)

payload = json.loads(buffer.getvalue())
check(
    "--json emits every bucket, so a caller can tell empty from unrun",
    set(payload)
    >= {"files_scanned", "case_records_skipped", "links_considered",
        "findings", "exempt"},
)
check(
    "the real corpus is actually scanned",
    payload["files_scanned"] > 0 and payload["links_considered"] > 0,
)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
