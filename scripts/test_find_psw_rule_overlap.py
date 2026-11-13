#!/usr/bin/env python3
"""Tests for scripts/find-psw-rule-overlap.py (ai-config#5628).

Run: python3 scripts/test_find_psw_rule_overlap.py
"""
import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fpro", HERE / "find-psw-rule-overlap.py")
fpro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fpro)

FAILS = []


def check(name, got, want):
    ok = got == want
    print(("  ok      " if ok else "  FAIL    ") + name)
    if not ok:
        print(f"          got {got!r}, want {want!r}")
        FAILS.append(name)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = fpro.main(argv)
    return code, out.getvalue()


check("short quoted phrases are extracted, lower-cased, deduplicated",
      fpro.example_phrases('Avoid "Now" and "recently"; "now" again.'),
      ["now", "recently"])
check("a phrase over three words is skipped",
      fpro.example_phrases('"there are N consumers today" and "as of"'),
      ["as of"])
check("a one-letter phrase is skipped; apostrophes and hyphens are kept",
      fpro.example_phrases('"A" and "don\'t" and "state-of-the-art"'),
      ["don't", "state-of-the-art"])
check("a quoted code-like token is skipped",
      fpro.example_phrases('"tool_calls" and ", "'),
      [])

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    psw = root / "psw"
    (psw / "chapters").mkdir(parents=True)
    (psw / "_site").mkdir()
    (psw / "chapters" / "word-choice.qmd").write_text(
        'Do not write "now" or "currently".\nKnown issues.\n', encoding="utf-8")
    (psw / "_site" / "word-choice.md").write_text("now\n", encoding="utf-8")
    fragment = root / "frag.md"
    fragment.write_text('Say "as of" a date, not "now" or "nowadays".\n', encoding="utf-8")

    code, out = run([str(fragment), "--psw", str(psw)])
    check("a hit exits 0", code, 0)
    check("the hit names the file and line", "chapters/word-choice.qmd:1:" in out, True)
    check("whole-word match: 'now' does not match 'Known'", "word-choice.qmd:2" in out, False)
    check("build output is skipped", "_site" in out, False)
    check("the summary counts phrases", "1 of 3 phrase(s) found across 1 psw file(s)." in out, True)
    check("a line quoting the phrase is marked Q", "  Q chapters/word-choice.qmd:1:" in out, True)
    check("the quoting file is listed last", out.rstrip().endswith("chapters/word-choice.qmd: now"), True)
    (psw / "chapters" / "prose.qmd").write_text("We now see it.\n", encoding="utf-8")
    code, out = run([str(fragment), "--psw", str(psw)])
    check("a quoting hit sorts before an unquoted one",
          out.index("Q chapters/word-choice.qmd") < out.index("chapters/prose.qmd"), True)

    (psw / "chapters" / "case.qmd").write_text(
        "NOW is upper case.\nA now-ish word.\nWe don’t.\n", encoding="utf-8")
    code, out = run([str(fragment), "--psw", str(psw), "--max-lines", "9"])
    check("matching ignores case", "chapters/case.qmd:1:" in out, True)
    check("a hyphenated word is not a whole-word hit", "chapters/case.qmd:2:" in out, False)
    curly = root / "curly.md"
    curly.write_text('Avoid "don\'t".\n', encoding="utf-8")
    code, out = run([str(curly), "--psw", str(psw)])
    check("a curly apostrophe in psw matches a straight one", "chapters/case.qmd:3:" in out, True)
    code, out = run([str(fragment), "--psw", str(psw), "--max-lines", "1"])
    check("--max-lines caps the lines shown per phrase", out.count("\n    chapters/"), 0)
    check("--max-lines keeps the first (quoting) line", out.count("Q chapters/"), 1)

    nomatch = root / "nomatch.md"
    nomatch.write_text('Avoid "zebra".\n', encoding="utf-8")
    code, out = run([str(nomatch), "--psw", str(psw)])
    check("no match still exits 0", code, 0)
    check("no match reports zero phrases found", "0 of 1 phrase(s)" in out, True)
    code, out = run([str(nomatch), str(fragment), "--psw", str(psw)])
    check("several fragments pool their phrases", "of 4 phrase(s)" in out, True)
    check("a missing fragment file exits 2",
          run([str(root / "missing.md"), "--psw", str(psw)])[0], 2)
    bare = root / "bare"
    bare.mkdir()
    check("a psw directory with no prose files exits 2",
          run([str(fragment), "--psw", str(bare)])[0], 2)

    empty = root / "empty.md"
    empty.write_text("No quotes here.\n", encoding="utf-8")
    check("a fragment with no phrases exits 2",
          run([str(empty), "--psw", str(psw)])[0], 2)
    check("a missing psw directory exits 2",
          run([str(fragment), "--psw", str(root / "nope")])[0], 2)

if FAILS:
    print(f"{len(FAILS)} failure(s)")
    sys.exit(1)
print("all passed")
