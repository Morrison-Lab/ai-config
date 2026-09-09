#!/usr/bin/env python3
"""Regression tests for check-docx-tracked-changes.py.

Every fixture is a minimal .docx built in a tmpdir at run time rather than
committed.  That is this suite's own choice, not a rule quoted from
elsewhere: a committed binary fixture is invisible to review, it gets swept
into whatever content scans the repo runs, and a few lines of XML build one
anyway.

The load-bearing cases are the negative controls: a well-formed document
with legal markup produces zero findings (so a run isn't reporting "clean"
because it examined nothing -- the stats line is asserted non-zero too), and
the one legal exception (w:ins/w:del inside w:pPr's own w:rPr, i.e.
CT_ParaRPr) is confirmed NOT to fire the marker-in-rpr check.
"""
import importlib.util
import io
import contextlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "cdtc", Path(__file__).parent / "check-docx-tracked-changes.py"
)
cdtc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdtc)

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


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"

DOC_HEADER = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:m="{M}">
<w:body>
"""
DOC_FOOTER = "</w:body></w:document>"

MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def make_docx(tmp_path, name, document_xml, extra_parts=None):
    """Build a minimal .docx-shaped zip with the given word/document.xml."""
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document_xml)
        for part_name, data in (extra_parts or {}).items():
            z.writestr(part_name, data)
    return path


def run_check(paths, reference=None):
    """Call main() and capture both its exit code and printed report."""
    argv = [str(p) for p in paths]
    if reference is not None:
        argv = ["--reference", str(reference)] + argv
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cdtc.main(argv)
    return rc, buf.getvalue()


# -- Fixture bodies --------------------------------------------------------

# A well-formed, Word-authored-shaped deletion: the marker WRAPS w:rPr + m:t.
VALID_OMATH_DEL = (
    DOC_HEADER
    + f"""<w:p><m:oMath>
  <m:r><w:del w:id="9" w:author="A" w:date="2026-01-01T00:00:00Z">
    <w:rPr><w:rFonts w:ascii="Cambria Math"/></w:rPr><m:t>x</m:t>
  </w:del></m:r>
</m:oMath></w:p>
"""
    + DOC_FOOTER
)

# The bug: w:ins as a CHILD of w:rPr, whose own parent (m:r) is not w:pPr.
INVALID_MARKER_IN_RPR = (
    DOC_HEADER
    + f"""<w:p><m:oMath>
  <m:r><w:rPr><w:ins w:id="9301" w:author="A" w:date="2026-01-01T00:00:00Z"/>
    <w:rFonts w:ascii="Cambria Math"/></w:rPr><m:t>x</m:t></m:r>
</m:oMath></w:p>
"""
    + DOC_FOOTER
)

# The one LEGAL place w:ins/w:del sits inside w:rPr: CT_ParaRPr, i.e. the
# w:rPr is itself a child of w:pPr (the inserted/deleted paragraph mark).
LEGAL_PARA_MARK_INS = (
    DOC_HEADER
    + f"""<w:p><w:pPr>
  <w:rPr><w:ins w:id="42" w:author="A" w:date="2026-01-01T00:00:00Z"/></w:rPr>
</w:pPr><w:r><w:t>hello</w:t></w:r></w:p>
"""
    + DOC_FOOTER
)

MALFORMED_XML = DOC_HEADER + "<w:p><w:r><w:t>unterminated</w:r></w:p>" + DOC_FOOTER

DUAL_RPR = (
    DOC_HEADER
    + """<w:p><w:r>
  <w:rPr><w:b/></w:rPr>
  <w:rPr><w:i/></w:rPr>
  <w:t>oops</w:t>
</w:r></w:p>
"""
    + DOC_FOOTER
)

DUPLICATE_ID = (
    DOC_HEADER
    + """<w:p>
  <w:del w:id="9" w:author="A" w:date="2026-01-01T00:00:00Z">
    <w:r><w:delText>one</w:delText></w:r>
  </w:del>
  <w:ins w:id="9" w:author="A" w:date="2026-01-01T00:00:00Z">
    <w:r><w:t>two</w:t></w:r>
  </w:ins>
</w:p>
"""
    + DOC_FOOTER
)

# The classic-markup mirror of the OMML bug: text marked <w:delText> that
# has no <w:del> wrapper, so nothing gates it out under accept.
ORPHAN_DELTEXT = (
    DOC_HEADER
    + """<w:p><w:r><w:delText>should have been wrapped in w:del</w:delText></w:r></w:p>
"""
    + DOC_FOOTER
)

# w:delText correctly wrapped -- must NOT be flagged.
WRAPPED_DELTEXT = (
    DOC_HEADER
    + """<w:p><w:del w:id="1" w:author="A" w:date="2026-01-01T00:00:00Z">
  <w:r><w:delText>correctly wrapped</w:delText></w:r>
</w:del></w:p>
"""
    + DOC_FOOTER
)

# mc:Ignorable names ten prefixes; only w14 is actually declared.  This is
# the second, independent defect: a part re-serialized by a generic XML
# library that dropped the other nine xmlns declarations while leaving the
# Ignorable attribute's text untouched.
UNDECLARED_IGNORABLE = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:mc="{MC}" xmlns:w14="urn:w14"
    mc:Ignorable="w14 w15 w16se w16cid w16 w16cex w16sdtdh w16sdtfl w16du wp14">
<w:body><w:p><w:r><w:t>hi</w:t></w:r></w:p></w:body>
</w:document>
"""

# Every named prefix is declared -- must NOT be flagged.
DECLARED_IGNORABLE = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:mc="{MC}" xmlns:w14="urn:w14" xmlns:w15="urn:w15"
    mc:Ignorable="w14 w15">
<w:body><w:p><w:r><w:t>hi</w:t></w:r></w:p></w:body>
</w:document>
"""

# Reference has no element other than w:rPr/m:t ever sitting directly under
# m:r; the edited copy below introduces a novel sibling the three named
# checks above have no rule for at all -- this is what the general
# reference-diff form is FOR.
REFERENCE_CLEAN = VALID_OMATH_DEL
NOVEL_STRUCTURE = (
    DOC_HEADER
    + f"""<w:p><m:oMath>
  <m:r><w:rPr><w:rFonts w:ascii="Cambria Math"/></w:rPr>
    <w:bogusRevisionTag w:id="1"/>
    <m:t>x</m:t>
  </m:r>
</m:oMath></w:p>
"""
    + DOC_FOOTER
)


# Same LOCAL names as REFERENCE_CLEAN throughout, different namespaces: a
# WordprocessingML run where the reference has an OMML one. Collapsing a tag
# to its local name makes this indistinguishable from the reference, which is
# the one confusion this checker exists to prevent.
NAMESPACE_ONLY_NOVELTY = (
    DOC_HEADER
    + f"""<w:p><m:oMath>
  <w:r><w:del w:id="9" w:author="A" w:date="2026-01-01T00:00:00Z">
    <w:rPr><w:rFonts w:ascii="Cambria Math"/></w:rPr><w:t>x</w:t>
  </w:del></w:r>
</m:oMath></w:p>
"""
    + DOC_FOOTER
)


with __import__("tempfile").TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # -- well-formedness ----------------------------------------------------
    good = make_docx(tmp_path, "good.docx", VALID_OMATH_DEL)
    rc, out = run_check([good])
    check("a well-formed, legally-nested document exits 0", rc == 0)
    check("clean report says so", "no findings" in out)
    check(
        "the run reports it actually examined something (not a vacuous pass)",
        "examined 1 part" in out and "element(s)" in out and "0 element(s)" not in out,
    )

    bad_xml = make_docx(tmp_path, "malformed.docx", MALFORMED_XML)
    rc, out = run_check([bad_xml])
    check("malformed XML is reported and fails the run", rc == 1)
    check("finding names the malformed-xml kind", "malformed-xml" in out)

    # -- marker-in-rpr --------------------------------------------------------
    bug = make_docx(tmp_path, "bug.docx", INVALID_MARKER_IN_RPR)
    rc, out = run_check([bug])
    check("w:ins as a non-pPr w:rPr child fails the run", rc == 1)
    check("finding names the marker-in-rpr kind", "marker-in-rpr" in out)

    legal = make_docx(tmp_path, "legal-para-mark.docx", LEGAL_PARA_MARK_INS)
    rc, out = run_check([legal])
    check(
        "w:ins inside w:pPr's own w:rPr (CT_ParaRPr) is NOT flagged",
        rc == 0 and "marker-in-rpr" not in out,
    )

    # -- duplicate ids --------------------------------------------------------
    dup = make_docx(tmp_path, "dup.docx", DUPLICATE_ID)
    rc, out = run_check([dup])
    check("a reused w:id across w:del/w:ins fails the run", rc == 1)
    check("finding names the duplicate-id kind", "duplicate-id" in out)

    unique_ids = make_docx(tmp_path, "unique.docx", VALID_OMATH_DEL)
    rc, out = run_check([unique_ids])
    check("a document with one revision id has no duplicate-id finding", "duplicate-id" not in out)

    # -- dual w:rPr -------------------------------------------------------
    dual = make_docx(tmp_path, "dual.docx", DUAL_RPR)
    rc, out = run_check([dual])
    check("two sibling w:rPr children fails the run", rc == 1)
    check("finding names the dual-rpr kind", "dual-rpr" in out)

    single_rpr = make_docx(tmp_path, "single.docx", VALID_OMATH_DEL)
    rc, out = run_check([single_rpr])
    check("a single w:rPr child has no dual-rpr finding", "dual-rpr" not in out)

    # -- orphaned w:delText --------------------------------------------------
    orphan = make_docx(tmp_path, "orphan.docx", ORPHAN_DELTEXT)
    rc, out = run_check([orphan])
    check("a w:delText with no w:del ancestor fails the run", rc == 1)
    check("finding names the orphan-deltext kind", "orphan-deltext" in out)

    wrapped = make_docx(tmp_path, "wrapped.docx", WRAPPED_DELTEXT)
    rc, out = run_check([wrapped])
    check(
        "a w:delText correctly wrapped in w:del has no orphan-deltext finding",
        rc == 0 and "orphan-deltext" not in out,
    )

    # -- mc:Ignorable naming an undeclared prefix ----------------------------
    ignorable_bad = make_docx(tmp_path, "ignorable-bad.docx", UNDECLARED_IGNORABLE)
    rc, out = run_check([ignorable_bad])
    check("mc:Ignorable naming an undeclared prefix fails the run", rc == 1)
    check(
        "finding names the undeclared-ignorable-prefix kind",
        "undeclared-ignorable-prefix" in out,
    )
    check(
        "the finding names the actual missing prefixes, not just w14",
        "'w15'" in out and "'wp14'" in out,
    )

    ignorable_good = make_docx(tmp_path, "ignorable-good.docx", DECLARED_IGNORABLE)
    rc, out = run_check([ignorable_good])
    check(
        "mc:Ignorable whose prefixes are all declared has no finding",
        rc == 0 and "undeclared-ignorable-prefix" not in out,
    )

    # -- reference-based nesting-triple check --------------------------------
    reference = make_docx(tmp_path, "reference.docx", REFERENCE_CLEAN)
    novel = make_docx(tmp_path, "novel.docx", NOVEL_STRUCTURE)
    rc, out = run_check([novel], reference=reference)
    check(
        "a nesting shape absent from the reference fails the run "
        "even though no hard-coded check names it",
        rc == 1 and "novel-nesting" in out,
    )

    same_shape = make_docx(tmp_path, "same-shape.docx", VALID_OMATH_DEL)
    rc, out = run_check([same_shape], reference=reference)
    check(
        "identical structure to the reference produces no novel-nesting finding",
        "novel-nesting" not in out,
    )

    # -- multiple documents in one invocation --------------------------------
    rc, out = run_check([good, bug])
    check(
        "one bad document among several fails the whole run",
        rc == 1 and "marker-in-rpr" in out and out.count("==") >= 4,
    )

    # -- a missing/non-zip path is a hard error, not a silent pass -----------
    rc, out = run_check([tmp_path / "does-not-exist.docx"])
    check("a missing file is reported as an error and fails the run", rc == 1)
    check("the error names the problem rather than reporting clean", "ERROR" in out)

    # A directory raises IsADirectoryError, which is an OSError and not a
    # FileNotFoundError, so a narrower except clause lets it escape as a
    # traceback -- which reads as the checker being broken rather than as the
    # path being wrong.
    rc, out = run_check([tmp_path])
    check("a directory is reported as an error rather than raising", rc == 1)
    check("the directory error is the checker's own message", "ERROR" in out)

    # A zip with no XML parts is the vacuous pass the stats line exists to
    # expose: without this, "examined 0 parts ... no findings" exits 0, which
    # is what every caller actually consumes.
    hollow = tmp_path / "hollow.docx"
    with zipfile.ZipFile(hollow, "w") as z:
        z.writestr("word/media/image1.png", b"not xml")
    rc, out = run_check([hollow])
    check("a package with no XML parts is a finding, not a clean pass", rc == 1)
    check("the finding says nothing was examined", "nothing-examined" in out)

    # The same gap on the --reference side is worse than a silent pass: an
    # empty reference makes every triple in the document under test read as
    # absent from it, burying a real finding under false ones.
    rc, out = run_check([good], reference=hollow)
    check("an empty reference is refused rather than used as ground truth", rc == 1)
    check(
        "the empty-reference error says the reference is unusable",
        "not usable as ground truth" in out and "novel-nesting" not in out,
    )

    # -- the nesting diff compares namespaces, not just local names ----------
    ns_novel = make_docx(tmp_path, "ns-novel.docx", NAMESPACE_ONLY_NOVELTY)
    rc, out = run_check([ns_novel], reference=reference)
    check(
        "a shape differing from the reference only by namespace is novel",
        "novel-nesting" in out and rc == 1,
    )
    check(
        "the novel-nesting finding names the namespace prefix, not a bare local name",
        "<w:r>" in out or "<m:oMath>" in out,
    )

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
