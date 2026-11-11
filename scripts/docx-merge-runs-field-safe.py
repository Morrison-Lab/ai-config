#!/usr/bin/env python3
"""Run the docx skill's `merge_runs.py` without merging across field codes.

The `docx` skill's `merge_runs.py` merges any two adjacent runs with the same
`<w:rPr>`, and a field code's `begin`, `instrText`, `separate`, result and
`end` usually all qualify.  Merged into one run, the field is gone: pandoc
converts the paragraph to an empty line, and Word drops or reorders the
citation (ai-config#2918; the measurement is in `memories/office-open-xml.md`,
"`merge_runs.py` silently breaks field codes").  Zotero, Mendeley and EndNote
citations, cross-references, tables of contents and HYPERLINK fields are all
field codes.

This wrapper loads the skill's own script and changes one decision: a run
that holds a `w:fldChar`, `w:instrText` or `w:delInstrText` is never merged
with a neighbour.  Every other merge, and the command line, are the skill's.
The result runs between `separate` and `end` still merge with each other,
since the field markers around them stay put.

Usage (the same arguments as the skill's script):

    python3 scripts/docx-merge-runs-field-safe.py document.docx [-o out.docx]
    python3 scripts/docx-merge-runs-field-safe.py unpacked/

The skill's scripts directory is `$DOCX_SKILL_SCRIPTS`, or
`/mnt/skills/public/docx/scripts` when that is unset.  The wrapper exits 2,
before touching any file, if the skill's script no longer has the
`_can_merge` and `main` functions it patches.
"""
import importlib
import os
import sys

DEFAULT_SKILL_SCRIPTS = "/mnt/skills/public/docx/scripts"
FIELD_TAGS = ("fldChar", "instrText", "delInstrText")


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
    missing = [n for n in ("_can_merge", "main") if not hasattr(module, n)]
    if missing:
        raise AttributeError(
            f"{module.__file__} has no {', '.join(missing)}; the docx skill "
            "changed, so re-check ai-config#2918 before merging runs")
    original = module._can_merge

    def can_merge(run1, run2):
        if has_field_marker(run1) or has_field_marker(run2):
            return False
        return original(run1, run2)

    module._can_merge = can_merge
    return module


def main():
    skill_scripts = os.environ.get("DOCX_SKILL_SCRIPTS", DEFAULT_SKILL_SCRIPTS)
    try:
        module = load_patched(skill_scripts)
    except (ImportError, AttributeError) as exc:
        print(f"docx-merge-runs-field-safe: {exc}", file=sys.stderr)
        return 2
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
