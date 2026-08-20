#!/usr/bin/env python3
"""Regression tests for check-section-refs.py.

The load-bearing cases are the negative controls: a synthetic corpus
carrying a KNOWN stale quoted reference, asserted to be reported, paired
with a KNOWN valid one, asserted NOT to be reported.  Until the checker has
been seen to fire on a real positive, a zero from it against the real corpus
is not evidence of anything (shared/principles/fail-fast.md).

Text matching alone cannot tell a genuinely-renamed heading apart from a
paraphrase citation that never named a heading at all, so the checker's
verdict now depends on git history: it flags a quote ONLY when history
confirms the quote once matched a heading/bold-lead and the current state
does not.  That means many of the fixtures below now need to be REAL git
repositories with real commit history, not just directories of files --
check_repo() cannot confirm a "used to be true, now is not" claim from a
directory that has never been committed.

check_repo() now returns a dict (findings / unverified / examined / scanned
/ history_* keys), not a 3-tuple.
"""
import subprocess
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


def run_git(root: Path, args: list) -> None:
    subprocess.run(
        ["git", "-C", str(root)] + args,
        capture_output=True, text=True, check=True,
    )


def git_init(root: Path) -> None:
    run_git(root, ["init", "-q"])
    run_git(root, ["config", "user.email", "test@example.com"])
    run_git(root, ["config", "user.name", "Test"])
    # A checkout of this synthetic repo defaults to whatever branch name the
    # local git config prefers; nothing here depends on the branch name, so
    # no init.defaultBranch override is needed.


def git_commit_all(root: Path, message: str) -> None:
    run_git(root, ["add", "-A"])
    run_git(root, ["commit", "-q", "-m", message])


def run(root: Path) -> dict:
    return csr.check_repo(root, GLOBS)


def finding_keys(report: dict, bucket: str = "findings"):
    return {(f["referring_file"].name, f["line"]) for f in report[bucket]}


# --- Form A: the negative control, now git-backed ---------------------------
# A quote naming a heading that existed in an earlier commit and was removed
# in a later one -- the actual shape of the real bug this checker exists
# for -- paired with a quote naming the current heading, in the same run.

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(
        root, "target.md",
        "# Target\n\n## Old Renamed Title\n\n## Current Real Title\n\n"
        "Body text.\n",
    )
    git_commit_all(root, "add target with both headings")
    write(
        root, "target.md",
        "# Target\n\n## Current Real Title\n\nBody text.\n",
    )
    git_commit_all(root, "rename away the old heading")
    write(
        root, "citing.md",
        'See [`target.md`](target.md)\'s "Old Renamed Title" for detail.\n\n'
        'See [`target.md`](target.md)\'s "Current Real Title" too.\n',
    )
    git_commit_all(root, "add citing.md")

    report = run(root)
    findings = finding_keys(report)
    unverified = finding_keys(report, "unverified")
    check(
        "Form A: a quote naming a heading CONFIRMED removed by history is flagged",
        ("citing.md", 1) in findings,
    )
    check(
        "Form A: that same quote is not left in the unverified bucket too",
        ("citing.md", 1) not in unverified,
    )
    check(
        "Form A: a quote naming the real current heading is not flagged",
        ("citing.md", 3) not in findings
        and ("citing.md", 3) not in unverified,
    )
    check("references are counted", report["examined"] == 2)
    check("files are counted", report["scanned"] == 2)
    check("history was actually consulted", report["history_available"])

# --- The other new required direction: a quote that NEVER was a heading ----
# (a paraphrase citation) must be verifiably dropped, not flagged and not
# left "unverified" -- history genuinely has nothing to confirm here.

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "target.md", "## An Unrelated Heading\n\nSome body text.\n")
    git_commit_all(root, "add target")
    write(
        root, "citing.md",
        'See [`target.md`](target.md)\'s "This phrase was never a heading" '
        "here.\n",
    )
    git_commit_all(root, "add citing.md")

    report = run(root)
    check(
        "a quote that never matched any revision's heading/bold-lead is "
        "NOT flagged",
        ("citing.md", 1) not in finding_keys(report),
    )
    check(
        "and it is not parked as unverified either -- history WAS checked, "
        "it just found nothing",
        ("citing.md", 1) not in finding_keys(report, "unverified"),
    )

# --- Requirement 1: follow a rename/split across two DIFFERENT paths -------
# Mirrors the real bug this whole layer exists for: predecessor.md carried
# the heading, then a later commit deletes predecessor.md and adds target.md
# with most of the same body content (so git's rename detection registers
# the two as related) but WITHOUT the old heading.  A reference now pointing
# at target.md must still find the heading by walking back through
# predecessor.md's history -- git log --follow on target.md's OWN path
# history alone cannot see it.

PADDING = "\n".join(f"Shared filler line {i} of body text." for i in range(30))

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(
        root, "predecessor.md",
        f"# Predecessor\n\n## Heading That Moves\n\n{PADDING}\n",
    )
    git_commit_all(root, "add predecessor with the heading")
    (root / "predecessor.md").unlink()
    write(root, "target.md", f"# Target\n\n{PADDING}\n")
    git_commit_all(root, "split predecessor into target, dropping the heading")
    write(
        root, "citing.md",
        'See [`target.md`](target.md)\'s "Heading That Moves" for detail.\n',
    )
    git_commit_all(root, "add citing.md")

    follows = csr.follow_history_pairs(root, "target.md")
    check(
        "sanity: git log --follow on target.md's own path alone reaches "
        "back into predecessor.md's history (rename detected)",
        follows is not None and len(follows) >= 2
        and any(p == "predecessor.md" for _, p in follows),
    )

    report = run(root)
    check(
        "requirement 1: a heading that only ever existed in a PRE-SPLIT "
        "predecessor file is found by following the rename, and the "
        "reference is flagged",
        ("citing.md", 1) in finding_keys(report),
    )

# --- Truncated quotes (substring, not just prefix) -- current match, no
# history needed -----------------------------------------------------------

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
    report = run(root)
    keys = finding_keys(report)
    check(
        "Form A: a quote that is a heading PREFIX is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form A: a quote that is a heading SUFFIX (after a colon) is not flagged",
        ("citing.md", 3) not in keys,
    )

# --- Bold-lead targets (paragraph and list-item) ----------------------------
# The "still true" halves need no git history (current match succeeds); the
# "no longer true" half does, so it gets its own git-backed corpus.

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "A bolded paragraph lead" note.\n\n'
        'See [`t.md`](t.md)\'s "403 caveat" note.\n',
    )
    write(
        root, "t.md",
        "**A bolded paragraph lead sentence.**\n\n"
        "- **403 caveat -- scoped sessions can only push one branch.**\n",
    )
    report = run(root)
    keys = finding_keys(report)
    check(
        "a quote matching a paragraph-leading bold span is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "a quote matching a list item's own bold lead is not flagged",
        ("citing.md", 3) not in keys,
    )

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "t.md", "**This bold lead is gone.**\n\nOther text.\n")
    git_commit_all(root, "add t.md with the bold lead")
    write(root, "t.md", "Other text.\n")
    git_commit_all(root, "remove the bold lead")
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "This bold lead is gone" note.\n',
    )
    git_commit_all(root, "add citing.md")
    report = run(root)
    check(
        "a quote naming a bold lead CONFIRMED removed by history is flagged",
        ("citing.md", 1) in finding_keys(report),
    )

# --- Form A2: the comma idiom, scoped ---------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "x.cases.md", "## A Real Case Title\n")
    write(root, "plain.md", "## A Real Heading\n\nAnother sentence.\n")
    git_commit_all(root, "add real headings")
    write(root, "x.cases.md", "## A Real Case Title\n\n## A Gone Case Title\n")
    git_commit_all(root, "add a case that will be removed")
    write(root, "x.cases.md", "## A Real Case Title\n")
    git_commit_all(root, "remove the gone case")
    write(
        root, "citing.md",
        'See [`x.cases.md`](x.cases.md), "A Real Case Title".\n\n'
        'See [`x.cases.md`](x.cases.md), "A Gone Case Title".\n\n'
        'See [`plain.md`](plain.md), "A Real Heading".\n\n'
        'Per [`plain.md`](plain.md), "just a quoted phrase" means nothing.\n',
    )
    git_commit_all(root, "add citing.md")

    report = run(root)
    keys = finding_keys(report)
    check(
        "Form A2: a comma-form quote matching a real .cases.md heading is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form A2: a comma-form quote naming a CONFIRMED-removed .cases.md "
        "heading is flagged",
        ("citing.md", 3) in keys,
    )
    check(
        'Form A2: a "See X, "quote"" citation to a plain heading is checked',
        ("citing.md", 5) not in keys,
    )
    check(
        'Form A2: an unscoped comma-quote ("Per X, ...") is never examined at all',
        report["examined"] == 3,  # only the three "See ..." references count
    )

# --- Form B: quoted link text -----------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "t.md", "## Real Section\n\n## Gone Section\n")
    git_commit_all(root, "add both headings")
    write(root, "t.md", "## Real Section\n")
    git_commit_all(root, "remove Gone Section")
    write(
        root, "citing.md",
        'The ["Real Section"](t.md) explains this.\n\n'
        'The ["Gone Section"](t.md) explains that.\n',
    )
    git_commit_all(root, "add citing.md")
    report = run(root)
    keys = finding_keys(report)
    check(
        "Form B: quoted link text matching a real heading is not flagged",
        ("citing.md", 1) not in keys,
    )
    check(
        "Form B: quoted link text naming a CONFIRMED-removed heading is flagged",
        ("citing.md", 3) in keys,
    )

# --- Code regions: fenced blocks and inline spans are handled correctly ----
# No history needed: either the reference is never examined, or it matches
# current state.

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
    report = run(root)
    check(
        "a reference entirely inside a fenced code block is not examined",
        all(f["line"] != 2 for f in report["findings"] + report["unverified"]),
    )
    check(
        "a reference entirely inside one inline code span is not examined",
        all(f["line"] != 5 for f in report["findings"] + report["unverified"]),
    )
    check(
        "a quote containing a backtick-wrapped term still extracts and "
        "matches correctly (the code-span-corruption regression)",
        ("citing.md", 7) not in finding_keys(report)
        and ("citing.md", 7) not in finding_keys(report, "unverified"),
    )
    check("only the real (non-code) reference was counted", report["examined"] == 1)

# --- Missing target file: not our job (check-links.py's job) ---------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`missing.md`](missing.md)\'s "Anything" for detail.\n',
    )
    report = run(root)
    check(
        "a reference to a missing file is skipped, not flagged",
        report["findings"] == [] and report["unverified"] == [],
    )
    check("a reference to a missing file is not counted as examined", report["examined"] == 0)

# --- External links are ignored ---------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [GitHub](https://github.com)\'s "Anything at all" page.\n',
    )
    report = run(root)
    check("an external link is never treated as a reference", report["examined"] == 0)
    check("an external link produces no finding", report["findings"] == [])

# --- MIN_QUOTE_LEN guard -----------------------------------------------------
# A quote below the length floor can never be confirmed a match against
# EITHER current or historical state (quote_matches enforces the floor in
# both directions), so under the new "flag only with positive evidence"
# design it can never land in `findings` -- unlike the pre-history-check
# version of this script, which flagged it outright.  A too-short quote is
# not evidence either way, so it is surfaced as unverified for a human to
# look at, not silently trusted as either clean or a confirmed break.  This
# is a deliberate, reasoned change from the checker's earlier behavior (see
# the commit that added the git-history layer), not an oversight.

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(root, "citing.md", 'See [`t.md`](t.md)\'s "Hi" for detail.\n')
    write(root, "t.md", "## Hi\n")
    report = run(root)
    check(
        "a quote shorter than MIN_QUOTE_LEN is never confirmed (findings "
        "stays empty even though the text is technically present)",
        report["findings"] == [],
    )
    check(
        "...and it is surfaced as unverified rather than silently dropped "
        "with no trace (this fixture is not a git repo, so history "
        "genuinely could not be consulted)",
        ("citing.md", 1) in finding_keys(report, "unverified"),
    )

# --- Requirement 3: shallow clone is detected and reported, not silently
# treated as clean -----------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp_src, tempfile.TemporaryDirectory() as tmp_dst:
    src = Path(tmp_src)
    git_init(src)
    write(src, "t.md", "## An Old Heading\n")
    git_commit_all(src, "commit 1: add the heading")
    write(src, "t.md", "Something else entirely.\n")
    git_commit_all(src, "commit 2: remove the heading")
    write(
        src, "citing.md",
        'See [`t.md`](t.md)\'s "An Old Heading" for detail.\n',
    )
    git_commit_all(src, "commit 3: add citing.md")

    dst = Path(tmp_dst) / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{src}", str(dst)],
        capture_output=True, text=True, check=True,
    )

    report = run(dst)
    check("a shallow clone is detected", report["shallow_clone"] is True)
    check(
        "history is still reported as available in a shallow clone (it is "
        "a real repo, just a truncated one)",
        report["history_available"] is True,
    )
    check(
        "requirement 3: a reference whose confirming commit lies beyond the "
        "shallow fetch depth is reported as unverified, not silently clean",
        ("citing.md", 1) in finding_keys(report, "unverified"),
    )
    check(
        "and it is NOT reported as a confirmed finding either -- the check "
        "genuinely could not tell",
        ("citing.md", 1) not in finding_keys(report, "findings"),
    )

# --- A directory that is not a git repository at all ------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "Some Heading" for detail.\n',
    )
    write(root, "t.md", "## A Different Heading\n")
    report = run(root)
    check(
        "history_available is False for a plain (non-git) directory",
        report["history_available"] is False,
    )
    check(
        "an unmatched quote in a non-git directory is unverified, not flagged",
        ("citing.md", 1) in finding_keys(report, "unverified"),
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

# --- batch_fetch_blobs() parsing: matches real revisions, skips a missing
# object without raising -----------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "a.md", "## Heading One\n")
    git_commit_all(root, "commit a")
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    specs = [f"{head}:a.md", "0" * 40 + ":missing.md"]
    blobs = csr.batch_fetch_blobs(root, specs)
    check(
        "batch_fetch_blobs reads a real blob's content",
        blobs.get(specs[0], "").strip() == "## Heading One",
    )
    check(
        "batch_fetch_blobs silently omits a missing object rather than raising",
        specs[1] not in blobs,
    )

# --- exit code contract ------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(root, "a.md", "Nothing to see here.\n")
    rc = csr.main(["--root", str(root)])
    check("main() exits 0 on a clean corpus", rc == 0)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    git_init(root)
    write(root, "t.md", "## Something That Existed\n")
    git_commit_all(root, "add heading")
    write(root, "t.md", "## Something Else\n")
    git_commit_all(root, "rename heading away")
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "Something That Existed" for detail.\n',
    )
    git_commit_all(root, "add citing.md")
    rc = csr.main(["--root", str(root)])
    check("main() exits 1 when a CONFIRMED stale reference is found", rc == 1)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(
        root, "citing.md",
        'See [`t.md`](t.md)\'s "Unverifiable Quote" for detail.\n',
    )
    write(root, "t.md", "## Something Else\n")
    rc = csr.main(["--root", str(root)])
    check(
        "main() exits 0 on an unverified-only result (non-git directory) "
        "-- advisory, like check-stale-records.py's shallow-clone note, "
        "not a hard failure",
        rc == 0,
    )

rc = csr.main(["--root", "/definitely/not/a/real/path/anywhere"])
check("main() exits 2 (usage error) on a bad --root", rc == 2)

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
