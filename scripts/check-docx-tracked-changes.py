#!/usr/bin/env python3
"""Check .docx tracked-change markup for structural validity, not just content.

`memories/office-open-xml.md`'s "A tracked change's `w:author`..." and
"An edit that writes cleanly can still be silently dropped" sections already
cover verifying that a tracked edit's *content* is right (a pandoc
accept/reject diff).  Neither catches the failure this script targets: an
edit that writes well-formed-looking XML and still corrupts the document,
because the accept/reject *text* comes out identical whether the markup is
valid or not.

The motivating defect: a tracked-change insertion/deletion marker written as
a CHILD of the run properties instead of WRAPPING them and the run text --

    <m:r><w:rPr><w:ins w:id="9301" .../><w:rFonts .../></w:rPr><m:t>x</m:t></m:r>

`CT_RPr` has no `w:ins`/`w:del` child (the one legal exception is inside
`w:pPr`, i.e. `CT_ParaRPr`, the inserted/deleted paragraph-mark case -- see
`memories/office-open-xml.md`).  Word refused the file outright.  A pandoc
accept/reject text diff cannot see this: the malformed marker is an empty
sibling of `m:t` rather than something that gates it, so the run's text
shows up identically under accept and reject, and the checker used at the
time reported the document clean through five successive deliveries.

This script parses `document.xml` (and every other XML part in the package)
for real, rather than diffing rendered text, and flags the structural shapes
that a content diff cannot see:

  * XML well-formedness, per part.
  * a `w:ins`/`w:del` sitting as a child of a `w:rPr` whose own parent is not
    `w:pPr`.
  * a duplicate `w:id` across revision-bearing elements in one document.
  * an element carrying two sibling `w:rPr` children (the shape the bug's
    own repair script had to merge back into one).
  * a `w:delText` with no `w:del` ancestor -- the classic-WordprocessingML
    mirror of the OMML bug above: a deletion marker that has stopped gating
    the text it names, this time by orphaning the *text* rather than
    misplacing the *marker*.
  * a prefix named in an element's `mc:Ignorable` attribute (Markup
    Compatibility) that is not declared anywhere in scope on that element --
    a second, independent defect found in the same manuscript: a part
    re-serialized by a generic XML library carried `mc:Ignorable="w14 w15
    ..."` while declaring none of those namespace prefixes, which Markup
    Compatibility requires. `ElementTree.fromstring()` discards a document's
    prefix bindings once parsed, so this check re-parses the raw bytes with
    `iterparse`'s namespace events to reconstruct what a library like lxml
    exposes per-element as `.nsmap`.
  * with `--reference`: any (grandparent, parent, child) element-nesting
    triple present in the file under test but never observed anywhere in a
    known-good reference `.docx` -- the general form, since the Word-authored
    original is ground truth for which shapes are legal, independent of any
    hard-coded rule above.
  * an OOXML math (OMML) structure -- m:sSup, m:f, m:nary, and the like --
    orphaned into an empty placeholder box.  Word renders every slot of such
    a structure (a superscript's base and exponent, a fraction's numerator
    and denominator, ...) whether or not it has content, and each carries an
    m:<tag>Pr/m:ctrlPr child holding the structure's OWN revision mark.  If
    an edit deletes every run inside the structure without also marking
    that ctrlPr `w:del`, the structure survives acceptance as an empty box;
    the mirror case (an inserted structure whose ctrlPr isn't marked
    `w:ins`) leaves an empty box on rejection.  A pandoc/text accept-reject
    diff can't see this -- an empty box carries no text -- and it is
    unrelated to the structural-validity checks above: the markup here is
    perfectly well-formed, it just renders wrong.  A structure carrying no
    `m:t` at all is a blank placeholder already present in the source,
    reported for information rather than as a finding.

Every run reports how many parts and elements it actually examined, so a
run that finds nothing is distinguishable from a run that examined nothing.
"""
from __future__ import annotations

import argparse
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
MC_IGNORABLE = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable"

# Elements that carry a w:id and are part of the tracked-change / revision
# machinery (ECMA-376 CT_TrackChange and its relatives). Duplicating an id
# across any two of these within one document is a defect regardless of
# which pair it is.
REVISION_TAGS = frozenset(
    W + name
    for name in (
        "ins",
        "del",
        "moveFrom",
        "moveTo",
        "moveFromRangeStart",
        "moveFromRangeEnd",
        "moveToRangeStart",
        "moveToRangeEnd",
        "customXmlInsRangeStart",
        "customXmlInsRangeEnd",
        "customXmlDelRangeStart",
        "customXmlDelRangeEnd",
        "cellIns",
        "cellDel",
        "cellMerge",
        "rPrChange",
        "pPrChange",
        "tblPrChange",
        "tblGridChange",
        "trPrChange",
        "tcPrChange",
        "sectPrChange",
        "numberingChange",
    )
)

XML_PART_SUFFIXES = (".xml", ".rels")

# OOXML math (OMML) structures Word renders slot-by-slot (m:sSup's base and
# exponent, m:f's numerator and denominator, ...) whether or not a given
# slot has content. Each carries an m:<tag>Pr child holding the m:ctrlPr
# that must carry the structure's OWN revision mark for a structure whose
# text is entirely deleted/inserted to disappear along with it rather than
# surviving as an empty placeholder box -- see check_orphaned_math() below.
MATH_STRUCT_TAGS = (
    "sSup", "sSub", "sSubSup", "sPre", "d", "f", "nary", "func", "rad",
    "limLow", "limUpp", "groupChr", "bar", "acc", "eqArr", "box",
    "borderBox", "phant",
)

# The mark that removes a run's text under each direction: accepting
# changes drops text under w:del, rejecting drops text under w:ins.
MATH_GONE_MARK = {"accept": W + "del", "reject": W + "ins"}


def local(tag: str) -> str:
    """Strip a `{namespace}` prefix off an ElementTree tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


# Prefixes for rendering a fully-qualified tag in the spelling a reader of the
# XML would recognize. Display only: comparison keeps the full "{uri}local"
# tag, per qualified() below.
NS_PREFIXES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main": "w",
    "http://schemas.openxmlformats.org/officeDocument/2006/math": "m",
    "http://schemas.openxmlformats.org/markup-compatibility/2006": "mc",
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships": "r",
    "http://schemas.microsoft.com/office/word/2010/wordml": "w14",
    "http://schemas.microsoft.com/office/word/2012/wordml": "w15",
    "http://schemas.microsoft.com/office/word/2016/wordml/cid": "w16cid",
    "http://schemas.microsoft.com/office/word/2018/wordml/cex": "w16cex",
}


def qualified(tag: str) -> str:
    """Render a tag for a reader without discarding its namespace.

    Comparison keys keep the full "{uri}local" form deliberately. An OMML
    m:r and a WordprocessingML w:r are different elements, and telling that
    pair apart is what this checker is for, so collapsing a tag to its local
    name would let a novel math shape hide behind an ordinary text one.
    """
    if not tag.startswith("{"):
        return tag
    uri, name = tag[1:].split("}", 1)
    prefix = NS_PREFIXES.get(uri)
    return f"{prefix}:{name}" if prefix else f"{{{uri}}}{name}"


class Finding:
    def __init__(self, kind: str, part: str, detail: str) -> None:
        self.kind = kind
        self.part = part
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.kind}] {self.part}: {self.detail}"


def iter_xml_parts(path: Path):
    """Yield (name, bytes) for every XML-shaped part in a .docx/.zip package."""
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(XML_PART_SUFFIXES):
                yield name, z.read(name)


def parent_map_of(root: ET.Element) -> dict:
    return {child: parent for parent in root.iter() for child in parent}


def nesting_triples(root: ET.Element) -> set:
    """(grandparent, parent, child) tags for every non-root element.

    The tags are fully qualified; see qualified() for why the namespace is
    load-bearing here rather than noise.
    """
    parents = parent_map_of(root)
    triples = set()
    for elem in root.iter():
        parent = parents.get(elem)
        if parent is None:
            continue  # elem is the part's document root
        grandparent = parents.get(parent)
        gp_tag = grandparent.tag if grandparent is not None else None
        triples.add((gp_tag, parent.tag, elem.tag))
    return triples


def check_marker_in_rpr(root: ET.Element, part: str, findings: list) -> int:
    """Flag w:ins/w:del as a child of w:rPr, except the CT_ParaRPr (w:pPr) case."""
    parents = parent_map_of(root)
    examined = 0
    for rpr in root.iter(W + "rPr"):
        examined += 1
        # The w:rPr's OWN parent, which is what the CT_ParaRPr exception is
        # stated in terms of: a marker is legal only when this is a w:pPr.
        rpr_parent = parents.get(rpr)
        if rpr_parent is not None and rpr_parent.tag == W + "pPr":
            continue
        parent_desc = local(rpr_parent.tag) if rpr_parent is not None else "(root)"
        for child in rpr:
            if child.tag in (W + "ins", W + "del"):
                findings.append(
                    Finding(
                        "marker-in-rpr",
                        part,
                        f"<{local(child.tag)}> is a child of <w:rPr> under "
                        f"<{parent_desc}> (must wrap w:rPr + text instead, "
                        "unless the w:rPr's own parent is w:pPr)",
                    )
                )
    return examined


def check_duplicate_ids(root: ET.Element, part: str, seen: dict, findings: list) -> int:
    """Flag a w:id reused across revision-bearing elements. `seen` is shared
    across every part of one document, keyed by id -> first-seen part."""
    examined = 0
    for elem in root.iter():
        if elem.tag not in REVISION_TAGS:
            continue
        wid = elem.get(W + "id")
        if wid is None:
            continue
        examined += 1
        if wid in seen:
            findings.append(
                Finding(
                    "duplicate-id",
                    part,
                    f"w:id={wid!r} on <{local(elem.tag)}> already used on a "
                    f"<{seen[wid][1]}> in {seen[wid][0]}",
                )
            )
        else:
            seen[wid] = (part, local(elem.tag))
    return examined


def check_dual_rpr(root: ET.Element, part: str, findings: list) -> int:
    """Flag an element carrying two (or more) direct w:rPr children."""
    examined = 0
    for elem in root.iter():
        rprs = [c for c in elem if c.tag == W + "rPr"]
        if not rprs:
            continue
        examined += 1
        if len(rprs) > 1:
            findings.append(
                Finding(
                    "dual-rpr",
                    part,
                    f"<{local(elem.tag)}> carries {len(rprs)} sibling "
                    "<w:rPr> children (expected at most one)",
                )
            )
    return examined


def check_orphan_deltext(root: ET.Element, part: str, findings: list) -> int:
    """Flag a w:delText with no w:del ancestor -- text marked deleted that
    nothing actually gates, the classic-markup mirror of check_marker_in_rpr
    for OMML: there the marker sat beside the text instead of wrapping it,
    here the text sits outside the wrapper that should contain it."""
    parents = parent_map_of(root)
    examined = 0
    for elem in root.iter(W + "delText"):
        examined += 1
        node = parents.get(elem)
        while node is not None and node.tag != W + "del":
            node = parents.get(node)
        if node is None:
            findings.append(
                Finding(
                    "orphan-deltext",
                    part,
                    "<w:delText> has no <w:del> ancestor, so nothing gates "
                    "it out under an accept reading",
                )
            )
    return examined


def check_ignorable_prefixes(data: bytes, part: str, findings: list) -> int:
    """Flag a prefix named in mc:Ignorable that is not declared in scope on
    the element that carries it.

    ElementTree.fromstring() discards prefix-to-URI bindings once parsed --
    only the resolved `{uri}local` tag/attribute names survive -- so this
    re-parses the raw bytes with iterparse's start-ns/start/end events to
    reconstruct which prefixes are actually in scope at each element, the
    same thing lxml exposes per-element as `.nsmap`. start-ns events for an
    element's own xmlns declarations fire immediately before that element's
    own start event, and are popped again on that same element's end event,
    so declared_at_depth pairs each prefix with the element that owns it
    regardless of how deeply namespaces are nested or shadowed.
    """
    examined = 0
    scope: dict = {}  # prefix -> stack of URIs currently in scope
    declared_at_depth: list = []  # per open element, the prefixes IT declared
    pending: list = []  # prefixes declared since the last 'start' event

    for event, value in ET.iterparse(
        io.BytesIO(data), events=("start-ns", "start", "end")
    ):
        if event == "start-ns":
            prefix, uri = value
            scope.setdefault(prefix, []).append(uri)
            pending.append(prefix)
        elif event == "start":
            declared_at_depth.append(pending)
            pending = []
            ignorable = value.get(MC_IGNORABLE)
            if ignorable is not None:
                examined += 1
                in_scope = {p for p, stack in scope.items() if stack}
                missing = [p for p in ignorable.split() if p not in in_scope]
                if missing:
                    findings.append(
                        Finding(
                            "undeclared-ignorable-prefix",
                            part,
                            f"mc:Ignorable names {missing!r} with no "
                            "matching xmlns declaration in scope on that "
                            "element",
                        )
                    )
        elif event == "end":
            for prefix in declared_at_depth.pop():
                scope[prefix].pop()

    return examined


def text_survives(t: ET.Element, mode: str, parents: dict) -> bool:
    """True if `t` (an m:t) is not gated out by an ancestor w:ins/w:del
    under the given accept/reject direction. Walks the WHOLE ancestor
    chain, not just the enclosing math structure -- an m:t inside a
    paragraph that is itself wholly w:del'd from an outer edit is exactly
    as gone as one directly wrapped, and both must read as gone here."""
    gone_tag = MATH_GONE_MARK[mode]
    node = parents.get(t)
    while node is not None:
        if node.tag == gone_tag:
            return False
        node = parents.get(node)
    return True


def ctrl_marks_of(struct_elem: ET.Element) -> set:
    """Revision marks on a math structure's OWN m:ctrlPr, read from its own
    m:<tag>Pr child -- never a descendant's, since a nested structure's mark
    must not excuse its parent."""
    pr = struct_elem.find(M + local(struct_elem.tag) + "Pr")
    if pr is None:
        return set()
    ctrl = pr.find(M + "ctrlPr")
    if ctrl is None:
        return set()
    return {c.tag for c in ctrl.iter() if c.tag in (W + "ins", W + "del")}


def check_orphaned_math(
    root: ET.Element, part: str, findings: list, notes: list, parents: dict
) -> tuple:
    """Flag a math structure that renders as an empty placeholder box.

    A structure is ORPHANED, under a given accept/reject direction, when it
    contains at least one m:t, none of those m:t survive that direction,
    and its own m:ctrlPr carries no matching w:ins/w:del -- that is the
    defect, introduced by an edit that deleted/inserted the structure's
    runs without also marking the structure itself.

    A structure carrying no m:t at all is BLANK: an empty placeholder
    already present in the source, appended to `notes` for information and
    never treated as a finding -- conflating the two would flag every
    intentionally-empty placeholder a document already has.

    Checks both directions in one pass; returns (zones_examined,
    structs_examined).
    """
    zones = structs = 0
    for p in root.iter(W + "p"):
        ctx = "".join(t.text or "" for t in p.iter(W + "t"))[:60]
        for om in p.iter(M + "oMath"):
            zones += 1
            for tag in MATH_STRUCT_TAGS:
                for s in om.iter(M + tag):
                    structs += 1
                    ts = list(s.iter(M + "t"))
                    if not ts:
                        notes.append(
                            f"[blank-math] {part}: <m:{tag}> has no text "
                            "runs -- a placeholder already present in the "
                            f"source, not a defect (near {ctx!r})"
                        )
                        continue
                    marks = ctrl_marks_of(s)
                    for mode in ("accept", "reject"):
                        survives = any(
                            (t.text or "").strip()
                            for t in ts
                            if text_survives(t, mode, parents)
                        )
                        if survives or MATH_GONE_MARK[mode] in marks:
                            continue
                        findings.append(
                            Finding(
                                "orphaned-math",
                                part,
                                f"<m:{tag}> loses all its text under "
                                f"{mode} (every m:t sits inside "
                                f"{qualified(MATH_GONE_MARK[mode])}) but "
                                "its own m:ctrlPr is not marked "
                                f"{qualified(MATH_GONE_MARK[mode])}, so "
                                "Word renders an empty placeholder box "
                                f"under {mode} (near {ctx!r})",
                            )
                        )
    return zones, structs


def check_document(path: Path) -> tuple:
    """Run every intra-document check on one .docx. Returns (findings,
    stats-dict, reference_triples_for_this_doc, notes)."""
    findings: list = []
    notes: list = []
    parts_examined = 0
    parts_malformed = 0
    elements_examined = 0
    ids_examined = 0
    deltext_examined = 0
    ignorable_examined = 0
    math_zones_examined = 0
    math_structs_examined = 0
    id_seen: dict = {}
    all_triples: set = set()

    for name, data in iter_xml_parts(path):
        parts_examined += 1
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            parts_malformed += 1
            findings.append(Finding("malformed-xml", name, str(exc)))
            continue

        elements_examined += sum(1 for _ in root.iter())
        check_marker_in_rpr(root, name, findings)
        ids_examined += check_duplicate_ids(root, name, id_seen, findings)
        check_dual_rpr(root, name, findings)
        deltext_examined += check_orphan_deltext(root, name, findings)
        ignorable_examined += check_ignorable_prefixes(data, name, findings)
        all_triples |= nesting_triples(root)
        parents = parent_map_of(root)
        zones, structs = check_orphaned_math(root, name, findings, notes, parents)
        math_zones_examined += zones
        math_structs_examined += structs

    stats = {
        "parts_examined": parts_examined,
        "parts_malformed": parts_malformed,
        "elements_examined": elements_examined,
        "ids_examined": ids_examined,
        "deltext_examined": deltext_examined,
        "ignorable_examined": ignorable_examined,
        "triples_examined": len(all_triples),
        "math_zones_examined": math_zones_examined,
        "math_structs_examined": math_structs_examined,
    }
    return findings, stats, all_triples, notes


def check_against_reference(
    edited_triples: set, reference_triples: set, findings: list
) -> int:
    """Flag any nesting triple in the edited doc that never occurs in the
    reference. Returns the number of triples checked (i.e. len(edited_triples))."""
    novel = edited_triples - reference_triples
    for gp, p, c in sorted(novel, key=lambda t: (t[1], t[2], t[0] or "")):
        gp_desc = qualified(gp) if gp is not None else "(root)"
        findings.append(
            Finding(
                "novel-nesting",
                "(reference comparison)",
                f"<{gp_desc}> > <{qualified(p)}> > <{qualified(c)}> does not "
                "occur anywhere in the reference document",
            )
        )
    return len(edited_triples)


def report(path: Path, findings: list, stats: dict, notes: list) -> None:
    print(f"== {path} ==")
    print(
        f"  examined {stats['parts_examined']} part(s) "
        f"({stats['parts_malformed']} malformed), "
        f"{stats['elements_examined']} element(s), "
        f"{stats['ids_examined']} revision id(s), "
        f"{stats['deltext_examined']} w:delText element(s), "
        f"{stats['ignorable_examined']} mc:Ignorable declaration(s), "
        f"{stats['triples_examined']} nesting triple(s), "
        f"{stats['math_zones_examined']} math zone(s), "
        f"{stats['math_structs_examined']} math structure(s)"
    )
    for n in notes:
        print(f"  {n}")
    if not findings:
        print("  no findings")
        return
    for f in findings:
        print(f"  {f}")


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("docx", nargs="+", type=Path, help=".docx file(s) to check")
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="known-good .docx whose element nestings are ground truth",
    )
    args = parser.parse_args(argv)

    reference_triples = None
    reference_examined = 0
    if args.reference is not None:
        try:
            ref_findings, ref_stats, reference_triples, _ref_notes = check_document(
                args.reference
            )
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"ERROR: reference {args.reference} could not be opened: {exc}")
            return 1
        # An empty reference is worse than a silent pass: every triple in
        # the documents under test would then read as absent from it, so
        # the run would bury a real finding under a flood of false ones.
        if ref_stats["parts_examined"] == 0:
            print(
                f"ERROR: reference {args.reference} has no XML parts, so it "
                "is not usable as ground truth"
            )
            return 1
        reference_examined = ref_stats["triples_examined"]
        print(f"== reference: {args.reference} ==")
        print(
            f"  examined {ref_stats['parts_examined']} part(s), "
            f"{reference_examined} nesting triple(s) as ground truth"
        )
        if ref_findings:
            print("  (reference itself has findings -- treat it with suspicion):")
            for f in ref_findings:
                print(f"    {f}")
        print()

    any_findings = False
    for docx_path in args.docx:
        try:
            findings, stats, triples, notes = check_document(docx_path)
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"== {docx_path} ==")
            print(f"  ERROR: could not open as a zip package: {exc}")
            any_findings = True
            continue

        if reference_triples is not None:
            check_against_reference(triples, reference_triples, findings)

        # Zero parts means the package held nothing this tool can read, which
        # is not the same fact as a document that was read and found clean.
        # Reporting it as clean is the vacuous pass the stats line exists to
        # make visible, so it is a finding rather than a footnote.
        if stats["parts_examined"] == 0:
            findings.append(
                Finding(
                    "nothing-examined",
                    "(package)",
                    "no XML parts found -- this is not a .docx, or it is empty; "
                    "nothing was checked",
                )
            )
        report(docx_path, findings, stats, notes)
        if findings:
            any_findings = True
        print()

    return 1 if any_findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
