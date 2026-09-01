# Office Open XML (`.docx` / `.xlsx`): editing committed and redlined documents

Satellite of [`tools.md`](tools.md), split at the 1250-line gate (ai-config#694 pattern).

`.docx`/`.xlsx` are zip archives, so every entry here is about editing the XML inside one directly.
The `docx` skill's helper scripts are the other route,
and several entries below are about where those helpers and their documentation diverge from what the files actually do.

## Editing committed content

- To strip or edit content (for example, remove a sensitive link from a committed Word doc):
  `unzip` the file, edit `word/document.xml` for body text,
  and edit `word/_rels/document.xml.rels` for hyperlink **targets**.
  A clickable URL's address lives in the `.rels` `Target`, not just the visible `<w:t>` text,
  so delete both the `<w:hyperlink r:id="rIdN">...</w:hyperlink>` element
  and its matching `<Relationship Id="rIdN" ... Target="...">` to remove link and address.
- Re-zip from the extracted dir: `zip -r -X out.docx '[Content_Types].xml' _rels docProps word`
  (plus `customXml` if present).
  Verify with `unzip -t out.docx` and re-extract plus grep
  to confirm the removed strings are gone before committing.
  (Done on ucdavis/bcs#237 to strip an internal SharePoint URL and a server reference from a to-do doc.)

## A hyperlink can live in the rels file **or** in a field code, so the rels listing is not the whole set

The entry above is right about the relationship form and incomplete as a way to *find* links.
Word stores hyperlinks two ways:
as a relationship (`word/_rels/document.xml.rels`, with `TargetMode="External"`),
and as a `fldChar` HYPERLINK **field code** inline in `word/document.xml`.
Enumerating the rels file is the obvious check and sees only the first kind.

Measured 2026-09-01 on a manuscript resubmission:
a Shiny-app link was absent from the rels listing and absent from pandoc's markdown output,
and I concluded from those two readings that it had been deleted.
It was present the whole time as a field-code hyperlink,
found only by grepping `word/document.xml` for the URL itself.
The wrong conclusion had already been written into a draft review finding before the grep ran.

This is the general failure in
[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)
wearing a document-specific shape:
a converted or derived view of a document is an adjacent artifact,
and thorough checking of it is still checking the wrong thing.

- **Do:** grep `word/document.xml` directly for a URL or string before concluding it is absent.
- **Don't:** treat the rels listing, or pandoc's output, as the document's full contents.

## `merge_runs.py` silently breaks field codes

As of 2026-09-01 the `docx` skill documents `merge_runs.py` as merging adjacent identically-formatted runs
in `word/document.xml` "without changing content or rendering",
and lists it in the standard edit recipe.
That claim does not hold for a document whose citations are field codes.

Measured 2026-09-01 on a manuscript whose citations are Zotero `fldChar`/`instrText` field codes.
Running `merge_runs.py` alone, with no other edit, merged 942 runs.
Converting the result with `pandoc -t plain --track-changes=accept`
produced 211 diff lines against the same conversion of the untouched original:
citation markers detached from their sentences,
whole clauses reordered across paragraphs,
and some citation numbers dropped entirely.
One example: `modern ggplot2-based visualizations (15)` became `modern ggplot2`.

The diagnosis matters as much as the fact.
The corruption is indistinguishable from "my edits broke the document",
so the natural response is to hunt through your own edits.
The cheap discriminator is to run `merge_runs.py` on a **pristine** copy and diff that against the original:
if the scrambling is already there, the helper is the cause.

Field codes are not rare.
Zotero, Mendeley, and EndNote citations, cross-references, table-of-contents entries,
and HYPERLINK fields are all field codes.

- **Do:** edit the pristine XML on any document containing field codes,
  and locate targets by walking `<w:r>` elements rather than merging runs first.
- **Do:** diff `merge_runs.py` on a pristine copy against the original
  when a document looks scrambled after an edit session.
- **Don't:** run `merge_runs.py` as a reflexive first step
  because the skill lists it in the standard edit recipe.

## Edit by run index, not by character span

Working on pristine XML means a target phrase is often split across several runs,
which is what makes the run-merging step tempting.
A run-index edit model handles the split directly and avoids a second, subtler bug.

The workable pattern:

1. Build a list of `(start, end, run_xml)` for every `<w:r>` once,
   plus each run's concatenated `<w:t>` text.
2. Find targets by run index, with an optional context window to disambiguate repeated phrases.
3. Collect at most one rewrite per run, plus optional before/after insertions.
4. Splice changed runs back **from the end of the document forward**.

A comment range spanning several runs is then
`commentRangeStart` before run `i`,
and `commentRangeEnd` plus `commentReference` after run `j`.

The bug this avoids came from the obvious alternative.
An earlier version collected `(start, end, replacement)` edits and sorted them back-to-front.
When a tracked replacement `(s, e, rep)` and a zero-width comment-marker insertion `(s, s, ins)`
shared a start offset,
applying the insertion first invalidated the replacement's offsets and produced mismatched tags:
XML that fails `xml.dom.minidom.parse` at a byte offset in the middle of the edited region.
Sorting cannot fix this, because the two edits are not disjoint.
One rewrite per run makes the overlap structurally impossible.

- **Do:** key edits to run indices and rewrite each run at most once.
- **Don't:** collect overlapping `(start, end)` span edits
  and rely on sort order to keep them disjoint.

## Two pandoc diffs verify a redlined docx, and they answer different questions

Run both on every redlined document, against the original and the output:

- `pandoc -t plain --track-changes=accept`, diffed,
  shows exactly what the edits **do**.
  It should contain only the intended changes.
- `pandoc -t plain --track-changes=reject`, diffed,
  should be **empty**.
  A non-empty reject-diff means something was changed without a `<w:ins>`/`<w:del>` wrapper,
  which is the failure mode that is invisible in Word's accepted view.

The reject-diff is the load-bearing one and is not in the `docx` skill's documentation,
which recommends `validate.py --author` instead.

Run that validator too, and **baseline it against the original first**.
Measured 2026-09-01: on this manuscript it exited on 5 ID-uniqueness violations
in `word/documenttasks/documenttasks1.xml` before it ever reached the redlining check,
and running it on the untouched file showed all 5 were pre-existing.
A validator that stops early reports a failure about the document rather than about your edits.

- **Do:** run both the accept-diff and the reject-diff,
  and baseline `validate.py` against the original before reading its output.
- **Don't:** read a `validate.py` failure as caused by your edits without that baseline.

## LibreOffice can refuse a file outright, so a PDF render is not always available

`soffice --convert-to pdf` refused one of these manuscripts with
`source file could not be loaded`,
with a writable `HOME` and with an explicit `--outdir`.
Measured 2026-09-01.

Visual confirmation through a rendered PDF is therefore not guaranteed,
and XML-level evidence has to stand on its own.
That is workable, since the XML **is** the document and the PDF would be a rendering of it,
but it is worth knowing before planning a workflow around the `docx` skill's
"render it and look at it" step.

- **Do:** plan a docx workflow so its verification is XML-level and pandoc-level,
  treating a PDF render as a bonus.
- **Don't:** assume `soffice --convert-to pdf` will load any `.docx` you can otherwise edit.
