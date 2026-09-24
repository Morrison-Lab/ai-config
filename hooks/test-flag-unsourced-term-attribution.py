#!/usr/bin/env python3
"""Tests for flag-unsourced-term-attribution.py.

Run: python3 hooks/test-flag-unsourced-term-attribution.py

The mutation checks at the bottom are the point: each of the guard's three
conditions is asserted to be load-bearing, so a later widening that drops one
fails here rather than silently turning the hook into a year detector.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "flag-unsourced-term-attribution.py")

FAILURES = []


def run(payload: dict, commands: list[str] | None = None) -> str:
    """Invoke the hook with a synthetic transcript; return its stdout."""
    tpath = ""
    tmp = None
    if commands is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        for c in commands:
            tmp.write(json.dumps({
                "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": c}},
                ]},
            }) + "\n")
        tmp.close()
        tpath = tmp.name
    payload = dict(payload)
    payload.setdefault("transcript_path", tpath)
    try:
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=30)
        return p.stdout.strip()
    finally:
        if tmp is not None:
            os.unlink(tmp.name)


def write(content: str, path: str = "/repo/README.md") -> dict:
    return {"tool_name": "Write",
            "tool_input": {"file_path": path, "content": content}}


def check(name: str, got: str, want_fire: bool) -> None:
    fired = bool(got)
    if fired != want_fire:
        FAILURES.append(
            f"{name}: expected {'fire' if want_fire else 'silence'}, "
            f"got {'fire' if fired else 'silence'}\n    stdout={got[:200]!r}")
    if fired:
        try:
            data = json.loads(got)
            if "systemMessage" not in data:
                FAILURES.append(f"{name}: missing 'systemMessage' in payload ({data})")
        except Exception as exc:
            FAILURES.append(f"{name}: stdout is not valid JSON ({exc})")


# ---------------------------------------------------------------- the case

INCIDENT = (
    "# CS229 practice midterm (Stanford, Autumn 2008)\n\n"
    "`practice-midterm.pdf` --- Andrew Ng, via Stanford Engineering "
    "Everywhere.\n"
)

check("the measured incident fires",
      run(write(INCIDENT), commands=["ls -la materials/", "du -sh ."]),
      True)

check("same content, but the session extracted text -> silent",
      run(write(INCIDENT),
          commands=["pdftotext -f 1 -l 1 practice-midterm.pdf -"]),
      False)

# ------------------------------------------------- each condition is needed

check("term+year but no document named -> silent",
      run(write("The Fall 2026 offering begins in September.")),
      False)

check("document named but no term+year -> silent",
      run(write("See `practice-midterm.pdf` for the format, retrieved "
                "2026-09-23.")),
      False)

check("a bare year next to a document is not enough -> silent",
      run(write("`Bishop-Pattern-Recognition-2006.pdf` was published in "
                "2006 by Springer.")),
      False)

# ------------------------------------------------------- extraction variants

for cmd in ("pdfinfo report.pdf",
            "unzip -p deck.pptx word/document.xml",
            "python3 -c \"import zlib; zlib.decompress(b'')\"",
            "qpdf --show-npages book.pdf",
            "strings notes.pdf | head"):
    check(f"extraction via {cmd.split()[0]} suppresses",
          run(write(INCIDENT), commands=[cmd]), False)

check("a bare `file` call does NOT suppress (metadata, not content)",
      run(write(INCIDENT), commands=["file practice-midterm.pdf"]), True)

check("a WebFetch-shaped command does NOT suppress",
      run(write(INCIDENT), commands=["curl -sSL https://cs229.stanford.edu/"]),
      True)

# ------------------------------------------------------------- tool coverage

check("Edit fires on new_string",
      run({"tool_name": "Edit",
           "tool_input": {"file_path": "/repo/a.md", "old_string": "x",
                          "new_string": INCIDENT}}, commands=[]),
      True)

check("Read is not an edit tool -> silent",
      run({"tool_name": "Read", "tool_input": {"file_path": "/repo/a.md"}}),
      False)

check("scratch path is exempt",
      run(write(INCIDENT, path="/private/tmp/scratchpad/notes.md"),
          commands=[]),
      False)

# ------------------------------------------------------------- robustness

check("line-wrapped term and year still fires",
      run(write("Published Autumn\n2008 --- see `ps1.pdf`."), commands=[]),
      True)

check("malformed stdin fails open", run({"tool_name": "Write"}), False)

p = subprocess.run([sys.executable, HOOK], input="not json",
                   capture_output=True, text=True, timeout=30)
if p.returncode != 0 or p.stdout.strip():
    FAILURES.append("non-JSON stdin: expected silent exit 0, got "
                    f"rc={p.returncode} stdout={p.stdout[:120]!r}")

check("missing transcript file fails open (no crash)",
      run(write(INCIDENT) | {"transcript_path": "/nonexistent/xyz.jsonl"}),
      True)

# --------------------------------------------------------- mutation checks
#
# Each asserts a DIFFERENT condition is load-bearing, by constructing the
# input that a hook missing that condition would mishandle. These are the
# tests that fail if someone later "simplifies" the guard.

MUTATIONS = [
    ("drop the document requirement -> fires on every course calendar",
     "The Fall 2026 course calendar lists twenty lectures.", False),
    ("drop the term requirement -> fires on an ordinary dated citation",
     "Retrieved 2026-09-23 from `ISLR2.pdf`.", False),
    ("drop the extraction check -> would fire even after checking",
     None, None),  # covered by the extraction-variant block above
]
for name, content, want in MUTATIONS:
    if content is None:
        continue
    check("mutation: " + name, run(write(content), commands=[]), want)

# ------------------------------------------------------------------ report

if FAILURES:
    print(f"FAIL ({len(FAILURES)})")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok")
