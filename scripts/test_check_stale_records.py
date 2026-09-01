#!/usr/bin/env python3
"""Regression tests for check-stale-records.py.

The load-bearing cases are the two negative controls: a synthetic corpus
carrying a KNOWN orphan and a KNOWN old-but-referenced file, asserted to land
in their respective buckets.  Until the checker has been seen to produce a
non-zero for each bucket, a zero from it against the real corpus is not
evidence of anything (shared/principles/fail-fast.md).

`collect()` takes injectable `now`, `times`, and `shallow` so the fixture can
carry a synthetic history in a tmpdir: no real git repository is needed, and
no fixture .md files land anywhere the corpus scan would pick them up.
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "csr", Path(__file__).parent / "check-stale-records.py"
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


DAY = csr.SECONDS_PER_DAY
NOW = 1_700_000_000  # fixed, so ages do not drift with the wall clock


def build_corpus(tmp):
    """A four-file corpus with one known member of each interesting class.

    Records live in `docs/` so they sit below the root: a root-level file is an
    entry point, exempt from the orphan bucket, and using one as the fixture's
    known orphan would test the exemption rather than the detector.

    index.md            fresh, root-level, links to the two docs/ files
    docs/old-ref.md     90 days old, 1 inbound link  -> old_referenced
    docs/fresh-ref.md   fresh, 1 inbound link        -> neither bucket
    docs/orphan.md      40 days old, 0 inbound links -> orphans
    """
    root = Path(tmp)
    (root / "docs").mkdir()
    (root / "index.md").write_text(
        "# Index\n\n"
        "See [the old one](docs/old-ref.md) and "
        "[the fresh one](docs/fresh-ref.md).\n",
        encoding="utf-8",
    )
    (root / "docs" / "old-ref.md").write_text("# Old\n", encoding="utf-8")
    (root / "docs" / "fresh-ref.md").write_text("# Fresh\n", encoding="utf-8")
    (root / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

    times = {
        (root / "index.md").resolve(): NOW - 1 * DAY,
        (root / "docs" / "old-ref.md").resolve(): NOW - 90 * DAY,
        (root / "docs" / "fresh-ref.md").resolve(): NOW - 1 * DAY,
        (root / "docs" / "orphan.md").resolve(): NOW - 40 * DAY,
    }
    return root, times


GLOBS = ["*.md", "docs/**/*.md"]


def run(root, times, **kw):
    """collect() with the fixture defaults: no real git, no wall clock."""
    kw.setdefault("stale_days", 30)
    kw.setdefault("now", NOW)
    kw.setdefault("shallow", False)
    return csr.collect(root, GLOBS, times=times, **kw)


def names(records):
    return {r["path"].name for r in records}


# --- the two negative controls -------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    report = run(root, times)

    check(
        "fires on a known orphan (positive control for the orphans bucket)",
        names(report["orphans"]) == {"orphan.md"},
    )
    check(
        "fires on a known old-but-referenced file (positive control)",
        names(report["old_referenced"]) == {"old-ref.md"},
    )
    check(
        "a fresh, referenced file lands in neither bucket",
        "fresh-ref.md"
        not in names(report["orphans"]) | names(report["old_referenced"]),
    )
    check(
        "reports what it examined, not only what it found",
        report["examined"] == 4,
    )
    check(
        "an orphan is bucketed as an orphan even though it is also old",
        # orphan.md is 40 days old, past the 30-day threshold: the buckets are
        # exclusive, and no-inbound-links wins, so it is not double-counted.
        "orphan.md" not in names(report["old_referenced"]),
    )
    # Guarded rather than indexed directly: a mutation that empties this bucket
    # must make the suite FAIL, not abort partway through with an IndexError --
    # a crash reports fewer failures than a clean run and hides every case after
    # it, which misattributes what the mutation actually broke.
    old_rec = report["old_referenced"][0] if report["old_referenced"] else None
    check(
        "the old-but-referenced record carries its inbound-link count",
        old_rec is not None and old_rec["refs"] == 1,
    )
    check(
        "age is reported in days from the injected clock",
        old_rec is not None and round(old_rec["age_days"]) == 90,
    )

# --- the checker must be able to report a clean corpus too ----------------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # Everything fresh, and the orphan linked: no findings, but still 4 files.
    (root / "index.md").write_text(
        "# Index\n\n"
        "See [old](docs/old-ref.md), [fresh](docs/fresh-ref.md), "
        "and [orphan](docs/orphan.md).\n",
        encoding="utf-8",
    )
    fresh_times = {p: NOW - 1 * DAY for p in times}
    clean = run(root, fresh_times)
    check(
        "a genuinely clean corpus reports zero in both buckets",
        clean["orphans"] == [] and clean["old_referenced"] == [],
    )
    check(
        "a clean run is still distinguishable from a run that scanned nothing",
        clean["examined"] == 4,
    )

# --- auto-load imports count as inbound references -------------------------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # The harness loads an `@path` import into context unconditionally, so it
    # is at least as strong a reference as a link a reader may never follow.
    # A link-only walk reports every @-imported fragment as an orphan.
    (root / "index.md").write_text(
        "# Index\n\n"
        "See [the old one](docs/old-ref.md) and "
        "[the fresh one](docs/fresh-ref.md).\n\n"
        "@docs/orphan.md\n",
        encoding="utf-8",
    )
    report = run(root, times)
    check(
        "a line-initial @path import counts as an inbound reference",
        report["orphans"] == [],
    )

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # An import shown inside a fence is documentation of the syntax, not a
    # live import -- counting it would let a fragment vouch for any path it
    # happens to quote.
    (root / "index.md").write_text(
        "# Index\n\n"
        "See [the old one](docs/old-ref.md) and "
        "[the fresh one](docs/fresh-ref.md).\n\n"
        "```\n@docs/orphan.md\n```\n",
        encoding="utf-8",
    )
    report = run(root, times)
    check(
        "an @path import inside fenced code is not an inbound reference",
        names(report["orphans"]) == {"orphan.md"},
    )

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # An @path inside a multi-line inline code span is not a live import either (#1567).
    (root / "index.md").write_text(
        "# Index\n\n"
        "See [the old one](docs/old-ref.md) and "
        "[the fresh one](docs/fresh-ref.md).\n\n"
        "example `code\n@docs/orphan.md\nmore`\n",
        encoding="utf-8",
    )
    report = run(root, times)
    check(
        "an @path import inside a multi-line inline code span is not an inbound reference (#1567)",
        names(report["orphans"]) == {"orphan.md"},
    )

check(
    "an import must sit in the first column",
    # A mid-line `@name` is an email address, a handle, or a decorator.
    csr.import_targets("see @shared/a.md inline\n@shared/b.md\n")
    == ["shared/b.md"],
)
check(
    "a bare @word is not an import target",
    # e.g. the `@generated` marker itself, which carries no path.
    csr.import_targets("@generated\n@shared/b.md\n") == ["shared/b.md"],
)
check(
    "reference_targets unions links and imports",
    csr.reference_targets("[x](a.md)\n@b.md\n") == ["a.md", "b.md"],
)

# A four-backtick fence legally wraps an inner three-backtick block, which is
# exactly what CLAUDE.md's Quarto div-syntax example does.  A whole-document
# ```` ```.*?``` ```` regex pairs backtick runs across the file rather than
# tracking open/close positionally, so it consumes the outer fence's opener
# together with the inner one, leaves the outer closer to pair with the next
# real fence, and swallows every reference in between.  Both call sites are
# asserted because each strips fences separately.
NESTED_FENCE = (
    "# Doc\n\n"
    "````\n"
    "```{r}\n"
    "````\n\n"
    "@shared/real.md\n\n"
    "[a link](shared/other.md)\n\n"
    "```bash\n"
    "echo hi\n"
    "```\n"
)
check(
    "an import after a four-backtick fence survives",
    csr.import_targets(NESTED_FENCE) == ["shared/real.md"],
)
check(
    "a link after a four-backtick fence survives",
    csr.link_targets(NESTED_FENCE) == ["shared/other.md"],
)
check(
    # Non-discriminating against the pre-fix whole-document regex, measured:
    # its `~~~.*?~~~` alternative already paired these two tildes.  Kept as a
    # property test of the positional matcher's same-character rule.
    "a tilde fence is not closed by a backtick run",
    csr.link_targets("~~~\n[x](a.md)\n```\n~~~\n[y](b.md)\n") == ["b.md"],
)

# --- generated files are exempt from the orphan bucket, and reported -------

GENERATED = "This is a generated Codex wrapper around the canonical skill.\n"

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    gen = root / "docs" / "wrapper.md"
    gen.write_text(GENERATED, encoding="utf-8")
    times[gen.resolve()] = NOW - 1 * DAY
    report = run(root, times)
    check(
        "a marker-carrying generated file is not reported as an orphan",
        # Nothing links to a generated wrapper by design, so counting them as
        # orphans buries the hand-written records the bucket exists to surface.
        names(report["generated"]) == {"wrapper.md"}
        and "wrapper.md" not in names(report["orphans"]),
    )
    check(
        "the generated exemption is reported, not silently applied",
        # fail-fast: an exemption nobody can see is indistinguishable from a
        # detector that missed the file.
        len(report["generated"]) == 1,
    )
    check(
        "exempting generated files does not empty the orphan bucket",
        names(report["orphans"]) == {"orphan.md"},
    )

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # A marker far past the header region is prose ABOUT generated files, not
    # a generator's own stamp -- a fragment discussing them must not be exempt.
    late = root / "docs" / "prose.md"
    late.write_text(
        "x\n" * csr.GENERATED_HEADER_CHARS + GENERATED, encoding="utf-8"
    )
    times[late.resolve()] = NOW - 1 * DAY
    report = run(root, times)
    check(
        "a generator marker outside the header region does not exempt a file",
        "prose.md" in names(report["orphans"])
        and "prose.md" not in names(report["generated"]),
    )

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # The exemption covers the ORPHAN bucket only: a stale generated file that
    # something does link to is exactly as harmful as any other stale record.
    gen = root / "docs" / "wrapper.md"
    gen.write_text(GENERATED, encoding="utf-8")
    times[gen.resolve()] = NOW - 90 * DAY
    (root / "docs" / "fresh-ref.md").write_text(
        "See [the wrapper](wrapper.md).\n", encoding="utf-8"
    )
    report = run(root, times)
    check(
        "a stale, referenced generated file is still old-but-referenced",
        "wrapper.md" in names(report["old_referenced"])
        and "wrapper.md" not in names(report["generated"]),
    )

# --- entry points are exempt from the orphan bucket, and reported ---------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    report = run(root, times)
    check(
        "a root-level file with no inbound links is an entry point, not an orphan",
        # index.md is reached directly, so its zero inbound links say nothing.
        # Reporting it would put permanent noise in the bucket that must mean
        # something.
        names(report["entry_points"]) == {"index.md"}
        and "index.md" not in names(report["orphans"]),
    )
    check(
        "the entry-point exemption is reported, not silently applied",
        len(report["entry_points"]) == 1,
    )

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    # Link to the root file, and age it past the threshold: the exemption must
    # cover the ORPHAN bucket only, never the harmful old-but-referenced one.
    (root / "docs" / "fresh-ref.md").write_text(
        "See [the index](../index.md).\n", encoding="utf-8"
    )
    aged = dict(times)
    aged[(root / "index.md").resolve()] = NOW - 200 * DAY
    report = run(root, aged)
    check(
        "a stale, linked entry point is still reported as old-but-referenced",
        "index.md" in names(report["old_referenced"])
        and "index.md" not in names(report["entry_points"]),
    )

# --- a shallow clone makes the age bucket uninformative, and says so ------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    shallow = run(root, times, shallow=True)
    full = run(root, times, shallow=False)
    check(
        "a shallow clone marks the age bucket uninformative",
        # `git log` cannot see past the fetch depth, so every file reads as no
        # older than the oldest fetched commit: a zero here is a fact about the
        # clone, not about the corpus.
        shallow["age_informative"] is False and full["age_informative"] is True,
    )
    check(
        "the uninformative label reaches the rendered report",
        "UNINFORMATIVE" in csr.format_report(shallow, 20)
        and "UNINFORMATIVE" not in csr.format_report(full, 20),
    )
    check(
        "shallowness does not change the orphan bucket",
        # Orphanhood is a link-graph fact, so the fetch depth cannot touch it.
        names(shallow["orphans"]) == names(full["orphans"]),
    )

# --- threshold and unknown-age handling -----------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root, times = build_corpus(tmp)
    loose = run(root, times, stale_days=120)
    check(
        "raising --stale-days past a file's age empties the old bucket",
        loose["old_referenced"] == [],
    )
    check(
        "raising --stale-days does not change the orphan bucket",
        # Orphanhood is a link-graph fact, not an age one.
        names(loose["orphans"]) == {"orphan.md"},
    )

with tempfile.TemporaryDirectory() as tmp:
    root, _ = build_corpus(tmp)
    partial = run(root, {})
    check(
        "a file with no commit history lands in unknown_age, not a finding",
        # A shallow clone answers 'never committed' for anything predating its
        # fetch depth, so this must not be reported as stale.
        len(partial["unknown_age"]) == 4
        and partial["orphans"] == []
        and partial["old_referenced"] == [],
    )

# --- link parsing ---------------------------------------------------------

check(
    "external links are not counted as inbound references",
    csr.link_targets("[x](https://example.com/a.md) [y](b.md)") == ["b.md"],
)
check(
    "links inside fenced code are ignored",
    csr.link_targets("```\n[x](a.md)\n```\n[y](b.md)") == ["b.md"],
)
check(
    "links inside inline code are ignored",
    csr.link_targets("`[x](a.md)` [y](b.md)") == ["b.md"],
)
check(
    "links inside multi-backtick inline code spans are ignored",
    csr.link_targets("`` [x](a.md) `` [y](b.md)") == ["b.md"],
)
check(
    "autoload imports inside multi-backtick inline code spans are ignored",
    csr.import_targets("`` @shared/doc.md ``\n@shared/live.md") == ["shared/live.md"],
)
check(
    "an angle-bracket placeholder is not treated as a path",
    csr.link_targets("[x](<owner>/<repo>/a.md) [y](b.md)") == ["b.md"],
)
check(
    "a fragment is stripped from a link target",
    csr.link_targets("[x](a.md#section)") == ["a.md"],
)
check(
    "a pure in-page anchor is not a file reference",
    csr.link_targets("[x](#section) [y](b.md)") == ["b.md"],
)
check(
    "a bare-word placeholder is not treated as a path",
    csr.link_targets("[x](url) [y](b.md)") == ["b.md"],
)

# --- self-links --------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "docs").mkdir()
    (root / "docs" / "self.md").write_text("[me](self.md)\n", encoding="utf-8")
    times = {(root / "docs" / "self.md").resolve(): NOW - 90 * DAY}
    report = run(root, times)
    check(
        "a file linking to itself is still an orphan",
        # Otherwise a stale doc could vouch for its own reachability.
        names(report["orphans"]) == {"self.md"},
    )

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
