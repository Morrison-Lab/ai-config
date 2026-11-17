#!/usr/bin/env python3
"""Test docx-merge-runs-field-safe.py (ai-config#2918).

Run:  python3 scripts/test_docx_merge_runs_field_safe.py

Part 1 runs everywhere, against stand-in `merge_runs` modules: the patched
decision, and the exit before any input is touched when the skill's script
lost a function or stopped consulting `_can_merge`.
Part 2 runs the real docx skill end to end on the paragraph
`memories/office-open-xml.md` measured, when the skill is installed
(`$DOCX_SKILL_SCRIPTS`, else `/mnt/skills/public/docx/scripts`), and says
plainly when it is not.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.dom import minidom

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "docx-merge-runs-field-safe.py"
passes = failures = 0


def check(name, cond):
    global passes, failures
    passes += bool(cond)
    failures += not cond
    print(("PASS: " if cond else "FAIL: ") + name)


spec = importlib.util.spec_from_file_location("field_safe", WRAPPER)
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
W = wrapper.W


def runs_of(body):
    doc = minidom.parseString(f'<w:p xmlns:w="{W}">{body}</w:p>')
    return doc.getElementsByTagName("w:r")


# --- Part 1: stand-in modules ----------------------------------------------
r_text, r_fld, r_instr, r_plain = runs_of(
    "<w:r><w:t>a</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    "<w:r><w:instrText>ADDIN ZOTERO</w:instrText></w:r>"
    "<w:r><w:t>b</w:t></w:r>")
check("a fldChar run is a field marker", wrapper.has_field_marker(r_fld))
check("an instrText run is a field marker", wrapper.has_field_marker(r_instr))
check("a text run is not a field marker", not wrapper.has_field_marker(r_text))

with tempfile.TemporaryDirectory() as tmp:
    Path(tmp, "merge_runs.py").write_text(
        "def _can_merge(a, b):\n    return True\n"
        "def merge_runs(d):\n    return 0, ''\ndef main():\n    pass\n",
        encoding="utf-8")
    sys.modules.pop("merge_runs", None)
    module = wrapper.load_patched(tmp)
    check("text runs still merge", module._can_merge(r_text, r_plain))
    check("text never merges into begin", not module._can_merge(r_text, r_fld))
    check("begin never merges into instrText", not module._can_merge(r_fld, r_instr))

COLLAPSE = (  # a skill that merges everything without asking _can_merge
    "def _can_merge(a, b):\n    return True\n"
    "def merge_runs(d):\n"
    "    p = __import__('pathlib').Path(d, 'word', 'document.xml')\n"
    f"    p.write_text('<w:document xmlns:w=\"{W}\"><w:body><w:p>"
    "<w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>')\n"
    "    return 6, 'Merged 6 runs'\n"
    "def main():\n    open(__import__('sys').argv[1], 'w').write('touched')\n")
for name, source in [("lost _can_merge", "def main():\n    pass\n"),
                     ("stopped consulting _can_merge", COLLAPSE)]:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "merge_runs.py").write_text(source, encoding="utf-8")
        target = Path(tmp, "in.docx")
        target.write_text("original", encoding="utf-8")
        res = subprocess.run([sys.executable, str(WRAPPER), str(target)],
                             env={**os.environ, "DOCX_SKILL_SCRIPTS": tmp},
                             capture_output=True, encoding="utf-8")
        check(f"exits 3 when the skill {name}",
              res.returncode == 3 and "#2918" in res.stderr)
        check(f"leaves the input untouched when the skill {name}",
              target.read_text(encoding="utf-8") == "original")

# --- Part 2: the real skill, end to end ------------------------------------
SKILL = Path(os.environ.get("DOCX_SKILL_SCRIPTS", "/mnt/skills/public/docx/scripts"))
PARA = (
    "<w:r><w:t xml:space=\"preserve\">modern ggplot2-based visualizations </w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>(1</w:t></w:r><w:r><w:t>5)</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    "<w:r><w:t xml:space=\"preserve\"> and more text after.</w:t></w:r>")
CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"


def write_docx(path):
    parts = {
        "[Content_Types].xml":
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="{CT}"/></Types>',
        "_rels/.rels":
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{REL}" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body><w:p>{PARA}</w:p></w:body></w:document>',
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in parts.items():
            zf.writestr(name, text)


def plain(path):
    return subprocess.run(["pandoc", "-t", "plain", "--track-changes=accept", str(path)],
                          capture_output=True, encoding="utf-8", check=True).stdout.strip()


def run_counts(path):
    """(field-marker runs, all runs) in PATH's word/document.xml."""
    with zipfile.ZipFile(path) as zf:
        runs = minidom.parseString(zf.read("word/document.xml")).getElementsByTagName("w:r")
    return sum(wrapper.has_field_marker(r) for r in runs), len(runs)


if not (SKILL / "merge_runs.py").is_file():
    print(f"NOT RUN: part 2 needs the docx skill at {SKILL}")
elif shutil.which("pandoc") is None:
    print("NOT RUN: part 2 needs pandoc on PATH")
else:
    with tempfile.TemporaryDirectory() as tmp:
        original, unsafe, safe = (Path(tmp, n) for n in ("o.docx", "u.docx", "s.docx"))
        for path in (original, unsafe, safe):
            write_docx(path)
        subprocess.run([sys.executable, str(SKILL / "merge_runs.py"), str(unsafe)],
                       cwd=SKILL, capture_output=True, check=True)
        subprocess.run([sys.executable, str(WRAPPER), str(safe)],
                       capture_output=True, check=True)
        before = plain(original)
        check("the fixture converts to its text", "(15)" in before)
        check("control: the skill's script merges the field markers",
              run_counts(unsafe)[0] < 4 and plain(unsafe) != before)
        check("the wrapper keeps all four field-marker runs", run_counts(safe)[0] == 4)
        check("the wrapper still merges the two result runs", run_counts(safe)[1] == 7)
        check("the wrapper keeps the paragraph's text", plain(safe) == before)

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
