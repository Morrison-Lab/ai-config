#!/usr/bin/env python3
"""Run the docx skill's `merge_runs.py` without merging across field codes.

The `docx` skill's `merge_runs.py` merges any two adjacent runs with the same
`<w:rPr>`, and a field code's `begin`, `instrText`, `separate`, result and
`end` usually all qualify.  Merged into one run, the field is gone: pandoc
converts the paragraph to an empty line (ai-config#2918; the measurement is
in `memories/office-open-xml.md`, "`merge_runs.py` silently breaks field
codes").  Zotero, Mendeley and EndNote citations, cross-references, tables
of contents and HYPERLINK fields are all field codes.

This wrapper loads the skill's own script and changes one decision: a run
that holds a `w:fldChar`, `w:instrText` or `w:delInstrText` is never merged
with a neighbour.  Every other merge, and the command line, are the skill's.
The result runs between `separate` and `end` still merge with each other.
A field's instruction text stays split across its runs.

Usage (the same arguments as the skill's script):

    python3 scripts/docx-merge-runs-field-safe.py document.docx [-o out.docx]
    python3 scripts/docx-merge-runs-field-safe.py unpacked/

The skill's scripts directory is `$DOCX_SKILL_SCRIPTS`, or
`/mnt/skills/public/docx/scripts` when that is unset.  Before touching the
input, the wrapper runs the patched script on a one-field paragraph of its
own and exits 3 if the field's marker runs did not all survive, or if the
skill's script lost a function the wrapper uses: either means the skill
changed, so re-check ai-config#2918.
"""
import importlib
import os
import sys
import tempfile
from pathlib import Path
from xml.dom import minidom

DEFAULT_SKILL_SCRIPTS = "/mnt/skills/public/docx/scripts"
FIELD_TAGS = ("fldChar", "instrText", "delInstrText")
SKILL_CHANGED = 3
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PROBE = (
    f'<w:document xmlns:w="{W}"><w:body><w:p>'
    "<w:r><w:t>a</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    "<w:r><w:instrText> ADDIN X </w:instrText></w:r>"
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>(1</w:t></w:r><w:r><w:t>5)</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    "<w:r><w:t>b</w:t></w:r>"
    "</w:p></w:body></w:document>")


class SkillChanged(Exception):
    """The skill's script no longer behaves as the wrapper assumes."""


def has_field_marker(run):
    """True when a direct child of RUN is a field-code marker."""
    for child in run.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue
        name = child.localName or child.tagName
        if name.rsplit(":", 1)[-1] in FIELD_TAGS:
            return True
    return False


def load_patched(skill_scripts):
    """The skill's merge_runs module, with field-marker runs kept apart."""
    sys.path.insert(0, skill_scripts)
    module = importlib.import_module("merge_runs")
    names = ("_can_merge", "merge_runs", "main")
    missing = [n for n in names if not hasattr(module, n)]
    if missing:
        raise SkillChanged(f"{module.__file__} has no {', '.join(missing)}")
    original = module._can_merge

    def can_merge(run1, run2):
        if has_field_marker(run1) or has_field_marker(run2):
            return False
        return original(run1, run2)

    module._can_merge = can_merge
    return module


def self_check(module):
    """Raise SkillChanged unless the patch keeps PROBE's field intact."""
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp, "word", "document.xml")
        doc.parent.mkdir()
        doc.write_text(PROBE, encoding="utf-8")
        _, msg = module.merge_runs(tmp)
        runs = minidom.parse(str(doc)).getElementsByTagName("w:r")
    markers = [r for r in runs if has_field_marker(r)]
    if msg.startswith("Error") or len(markers) != 4 or len(runs) != 7:
        raise SkillChanged(
            f"the patched script left {len(markers)} of 4 field-marker runs "
            f"and {len(runs)} runs in all where 7 were expected ({msg})")


def main():
    skill_scripts = os.environ.get("DOCX_SKILL_SCRIPTS", DEFAULT_SKILL_SCRIPTS)
    try:
        module = load_patched(skill_scripts)
        self_check(module)
    except (ImportError, SkillChanged) as exc:
        print(f"docx-merge-runs-field-safe: {exc}; the docx skill changed, "
              "so re-check ai-config#2918 before merging runs", file=sys.stderr)
        return SKILL_CHANGED
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
