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


def check_document(path: Path) -> tuple:
    """Run every intra-document check on one .docx. Returns (findings,
    stats-dict, reference_triples_for_this_doc)."""
    findings: list = []
    parts_examined = 0
    parts_malformed = 0
    elements_examined = 0
    ids_examined = 0
    deltext_examined = 0
    ignorable_examined = 0
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

    stats = {
        "parts_examined": parts_examined,
        "parts_malformed": parts_malformed,
        "elements_examined": elements_examined,
        "ids_examined": ids_examined,
        "deltext_examined": deltext_examined,
        "ignorable_examined": ignorable_examined,
        "triples_examined": len(all_triples),
    }
    return findings, stats, all_triples


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


def report(path: Path, findings: list, stats: dict) -> None:
    print(f"== {path} ==")
    print(
        f"  examined {stats['parts_examined']} part(s) "
        f"({stats['parts_malformed']} malformed), "
        f"{stats['elements_examined']} element(s), "
        f"{stats['ids_examined']} revision id(s), "
        f"{stats['deltext_examined']} w:delText element(s), "
        f"{stats['ignorable_examined']} mc:Ignorable declaration(s), "
        f"{stats['triples_examined']} nesting triple(s)"
    )
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
            ref_findings, ref_stats, reference_triples = check_document(
                args.reference
            )
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"ERROR: reference {args.reference} could not be opened: {exc}")
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
            findings, stats, triples = check_document(docx_path)
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
        report(docx_path, findings, stats)
        if findings:
            any_findings = True
        print()

    return 1 if any_findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
