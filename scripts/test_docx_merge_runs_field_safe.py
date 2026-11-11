#!/usr/bin/env python3
"""Test docx-merge-runs-field-safe.py (ai-config#2918).

Run:  python3 scripts/test_docx_merge_runs_field_safe.py

Part 1 runs everywhere: the patched `_can_merge` against a stand-in
`merge_runs` module, which proves the wrapper's own decision.
Part 2 runs the real docx skill end to end on the one-paragraph document
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
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
passes = failures = 0


def check(name, cond):
    global passes, failures
    passes += bool(cond)
    failures += not cond
    print(("PASS: " if cond else "FAIL: ") + name)


def load_wrapper():
    spec = importlib.util.spec_from_file_location("field_safe", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runs_of(body):
    doc = minidom.parseString(f'<w:p xmlns:w="{W}">{body}</w:p>')
    return doc.getElementsByTagName("w:r")


# --- Part 1: the decision, against a stand-in module -----------------------
wrapper = load_wrapper()
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
        "def _can_merge(a, b):\n    return True\n\ndef main():\n    pass\n",
        encoding="utf-8")
    sys.modules.pop("merge_runs", None)
    module = wrapper.load_patched(tmp)
    check("text runs still merge", module._can_merge(r_text, r_plain))
    check("text never merges into begin", not module._can_merge(r_text, r_fld))
    check("begin never merges into instrText", not module._can_merge(r_fld, r_instr))

with tempfile.TemporaryDirectory() as tmp:
    Path(tmp, "merge_runs.py").write_text("def main():\n    pass\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(WRAPPER), "x.docx"],
                         env={**os.environ, "DOCX_SKILL_SCRIPTS": tmp},
                         capture_output=True, encoding="utf-8")
    check("exits 2 when the skill lost _can_merge",
          res.returncode == 2 and "_can_merge" in res.stderr)

# --- Part 2: the real skill, end to end ------------------------------------
SKILL = Path(os.environ.get("DOCX_SKILL_SCRIPTS", "/mnt/skills/public/docx/scripts"))
PARA = (
    "<w:r><w:t xml:space=\"preserve\">modern ggplot2-based visualizations </w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>(15)</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    "<w:r><w:t xml:space=\"preserve\"> and more text after.</w:t></w:r>")


def write_docx(path):
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml":
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body><w:p>{PARA}</w:p></w:body></w:document>',
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in parts.items():
            zf.writestr(name, text)


def plain(path):
    return subprocess.run(["pandoc", "-t", "plain", "--track-changes=accept", str(path)],
                          capture_output=True, encoding="utf-8", check=True).stdout.strip()


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
        check("control: the skill's script alone loses the paragraph",
              plain(unsafe) != before)
        check("the wrapper keeps the paragraph", plain(safe) == before)

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
