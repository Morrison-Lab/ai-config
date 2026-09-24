#!/usr/bin/env python3
"""PreToolUse guard: a term-and-year pinned to a document nothing has read.

`shared/principles/dont-take-my-word-for-it.md` says investigate assertions
independently, and `hooks/flag-unread-commit-citation.py` is the instrument
for the commit-SHA case of that. This is the sibling for a different
artifact: a *document* whose provenance gets asserted from something other
than the document.

THE MEASUREMENT (2026-09-23, Morrison-Lab/mlg#20)
--------------------------------------------------
A vendored mirror of Stanford's CS229 course was split across two
repositories. Every README, both directory names (`cs229-stanford-2008`,
`cs229-see-2008`), three commit messages and four issue comments described
the material as "Autumn 2008".

No document said so. Checked afterwards, with `pdftotext`:

  * `practice-midterm.pdf` heads itself "CS 229, **Autumn 2007**".
  * All four problem sets and all four solution keys head themselves
    "CS 229, **Public Course**" and name no term at all.
  * The mirror's own course page names only the instructor; its sole `2007`
    and `2008` strings sit inside markup, never in visible text.

"Autumn 2008" came from the files' October 2008 *modification dates* --
evidence about when Stanford Engineering Everywhere published them, not
about which offering produced them -- and was then repeated as though a
source had stated it. An adversarial reviewer caught it by extracting the
PDF's own header, which is the check nobody had run.

WHAT IT CHECKS
--------------
    a Write/Edit/NotebookEdit whose new content
    (a) pins a term to a year -- "Autumn 2008", "Spring 2021"
    (b) AND names a document file (.pdf/.zip/.pptx/.docx/.epub/.djvu/.ps)
    (c) AND the transcript contains NO document-text-extraction command

All three are required. (a) alone fires on every course calendar in this
corpus ("Fall 2026 syllabus"); (b) is what turns a date into a claim *about
a document*; (c) is the part that says the claim cannot have come from the
document, because nothing in the session ever opened one.

WHY A TERM-AND-YEAR RATHER THAN ANY YEAR
------------------------------------------
A bare four-digit year is hopeless as a trigger: `2026-09-23`, `CC BY 3.0`,
`#3045` and "since 2008" all carry one, and this corpus is full of them. A
term word bound to a year is rare in ordinary prose and is almost always a
claim about *which offering* something belongs to -- exactly the class of
fact that lives inside a document or on its source page, and never in its
filename or its mtime.

WHY EXTRACTION AND NOT A WEB FETCH
------------------------------------
A `WebFetch` of the publisher's page is legitimate sourcing for a term, and
is deliberately NOT counted here. In the measured incident the session
fetched two course sites and still got the term wrong, because neither page
stated one -- so accepting a fetch as evidence would have suppressed this
warning on the very case it was built from. The cost is a false positive for
someone who sourced a term correctly from a web page; the message says to
answer that way, and it is one line.

WHY THIS WARNS RATHER THAN BLOCKS
-----------------------------------
Whether a term was sourced is not lexically decidable. The author may know
the offering first-hand (their own course), may have read the document in an
earlier session, or may be writing a term that is genuinely part of a proper
name. Blocking would refuse all three. The asymmetry also runs the right way
for warning: an unsourced provenance claim is cheap to check and expensive
to leave, because it propagates into directory names and gets repeated as
established fact -- which is what happened.

Scratch paths are exempt: a note-to-self in a scratchpad is not a durable
claim, and the incident's cost came entirely from the claim reaching
committed files.
"""
from __future__ import annotations

import json
import os
import re
import sys

# A term word bound to a year. `\s+` rather than `[ ]` so a line-wrapped
# "Autumn\n2008" still matches; semantic line breaks put one there often.
RX_TERM_YEAR = re.compile(
    r"\b(?:autumn|fall|winter|spring|summer)\s+(?:of\s+)?(?:19|20)\d{2}\b",
    re.I,
)

# A document the claim could be about. Deliberately not a generic path
# pattern: the point is a file whose CONTENT states its own provenance.
RX_DOCUMENT = re.compile(
    r"[\w./-]+\.(?:pdf|ps|djvu|epub|zip|pptx|docx|doc|odt)\b",
    re.I,
)

# Commands that read a document's text. `strings` is included because it is
# the fallback when nothing better is installed; a bare `file` is NOT, since
# it reports type and page-tree metadata rather than content -- in the
# measured incident `file` was run and reported "3 pages" for a 1098-page
# book, which is precisely the metadata-instead-of-content confusion this
# guard exists to interrupt.
RX_EXTRACT = re.compile(
    r"""\b(?:
          pdftotext | pdfinfo | pdfgrep | pdftk | qpdf | mutool
        | antiword | catdoc | textutil | docx2txt | odt2txt
        | pdfplumber | PyPDF\d* | pypdf | fitz | pymupdf
        | unzip\s+-p
        | zlib\.decompress
        | libreoffice[^\n]{0,40}--convert-to
        | soffice[^\n]{0,40}--convert-to
        | strings\b[^\n]{0,80}\.(?:pdf|docx?|pptx?|zip)
    )""",
    re.I | re.X,
)

SCRATCH = ("/tmp/", "/private/tmp/", "/var/folders/", "scratchpad")


def _content(tool: str, ti: dict) -> str:
    """The text this call would write, across the three edit tools."""
    if tool == "Write":
        return str(ti.get("content") or "")
    if tool == "Edit":
        return str(ti.get("new_string") or "")
    if tool == "NotebookEdit":
        return str(ti.get("new_source") or "")
    return ""


def _transcript_text(path: str) -> str:
    """Every Bash command string the transcript records, concatenated."""
    if not path or not os.path.exists(path):
        return ""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "command" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") or {}
                for block in msg.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    ti = block.get("input") or {}
                    if isinstance(ti, dict) and ti.get("command"):
                        out.append(str(ti["command"]))
    except Exception:
        return ""
    return "\n".join(out)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open

    tool = payload.get("tool_name") or ""
    if tool not in ("Write", "Edit", "NotebookEdit"):
        return 0

    ti = payload.get("tool_input") or {}
    target = str(ti.get("file_path") or ti.get("notebook_path") or "")
    if any(s in target for s in SCRATCH):
        return 0

    content = _content(tool, ti)
    if not content:
        return 0

    hit = RX_TERM_YEAR.search(content)
    if not hit:
        return 0
    doc = RX_DOCUMENT.search(content)
    if not doc:
        return 0

    if RX_EXTRACT.search(_transcript_text(payload.get("transcript_path") or "")):
        return 0

    phrase = hit.group(0).strip()
    named = doc.group(0)
    print(json.dumps({"systemMessage": (
        f'This writes "{phrase}" alongside `{named}`, and no command in this '
        "transcript has extracted text from any document (pdftotext, "
        "pdfinfo, unzip -p, strings). A term and year say which offering a "
        "document belongs to -- a fact that lives inside the document or on "
        "its source page, never in its filename or its modification date.\n\n"
        "Measured 2026-09-23 (Morrison-Lab/mlg#20): a vendored CS229 mirror "
        'was labelled "Autumn 2008" across two repositories, two directory '
        "names, three commit messages and four issue comments. The year came "
        "from the files' October 2008 mtimes. The practice midterm's own "
        'header reads "CS 229, Autumn 2007"; every problem set and solution '
        'key reads "CS 229, Public Course" and names no term at all.\n\n'
        f"Run `pdftotext -f 1 -l 1 {named} -` (or the equivalent) and quote "
        "what it returns. If you sourced the term from the publisher's page "
        "rather than the file, or you know the offering first-hand, say so "
        "and carry on -- this is a reminder, not a refusal."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
