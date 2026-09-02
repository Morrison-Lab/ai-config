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

The `.rels` bullet above is right about the relationship form
and incomplete as a way to *find* links.
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
Tracked as [ai-config#2918](https://github.com/Morrison-Lab/ai-config/issues/2918),
since this is a reproducible defect in a helper we keep using
rather than a one-off observation.

Measured 2026-09-01 on a manuscript whose citations are Zotero `fldChar`/`instrText` field codes.
Running `merge_runs.py` alone, with no other edit, merged 942 runs.
Converting the result with `pandoc -t plain --track-changes=accept`
produced 211 diff lines against the same conversion of the untouched original:
citation markers detached from their sentences,
whole clauses reordered across paragraphs,
and some citation numbers dropped entirely.
One example: `modern ggplot2-based visualizations (15)` became `modern ggplot2`.

**Those counts and that example come from a private manuscript and are not reproducible from this repository.**
The recipe below is, on any `.docx` carrying field-code citations:

```bash
cp original.docx pristine.docx
python3 /mnt/skills/public/docx/scripts/merge_runs.py pristine.docx   # no other edit
pandoc -t plain --track-changes=accept original.docx -o before.txt
pandoc -t plain --track-changes=accept pristine.docx -o after.txt
diff before.txt after.txt
```

A non-empty diff is the defect: nothing was edited, so the two conversions should match.

The diagnosis matters as much as the fact.
The corruption is indistinguishable from "my edits broke the document",
so the natural response is to hunt through your own edits.
That same recipe is the cheap discriminator:
if the scrambling is already there on a copy you never touched, the helper is the cause.

Field codes are not rare.
Zotero, Mendeley, and EndNote citations, cross-references, table-of-contents entries,
and HYPERLINK fields are all field codes.

- **Do:** edit the pristine XML on any document containing field codes,
  and locate targets by walking `<w:r>` elements rather than merging runs first.
- **Do:** when a document looks scrambled after an edit session,
  run `merge_runs.py` on an untouched copy and diff that copy's
  `pandoc -t plain --track-changes=accept` output against the original's,
  per the recipe above.
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
XML that fails `xml.dom.minidom.parseString` at a byte offset in the middle of the edited region
(`parseString` rather than `parse`, since the edited XML is an in-memory string;
the skill's own `comment.py` uses `defusedxml.minidom.parseString` throughout).
Sorting by start offset **alone** cannot fix this,
because a zero-width insertion and a replacement sharing a start offset
need an explicit tie-break to order them (longer span first, say).
One rewrite per run makes the question moot,
which is why it is the recommendation rather than a tie-break rule
that has to be got right and kept right.

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

The reject-diff is not in the `docx` skill's documentation,
which recommends `validate.py --author` for the same failure mode instead.
Treat the two as independent checks rather than ranking them:
the reject-diff is format-level and keeps working when the validator fails for an unrelated reason,
which is exactly the situation the next paragraph describes.

Run that validator too, and **baseline it against the original first**.
Measured 2026-09-01: on this manuscript it reported 5 ID-uniqueness violations
in `word/documenttasks/documenttasks1.xml`,
and running it on the untouched file showed all 5 were pre-existing.
That count also comes from the private manuscript and is not reproducible here;
what transfers is the baselining step.
The validator does not skip the redlining check when an earlier one fails
--- `validate.py:161` reads `success = all([v.validate() for v in validators])`,
and the list comprehension is materialized, so every validator runs ---
and inside `validators/docx.py` only `validate_xml()` returns early,
while `validate_unique_ids()` sets `all_valid = False` and falls through.
What it does is exit non-zero on **any** validator's failure,
so a pre-existing ID collision reddens the whole run
and buries the redlining verdict you were actually asking for.

- **Do:** run both the accept-diff and the reject-diff,
  and baseline `validate.py` against the original before reading its output.
- **Don't:** read a `validate.py` failure as caused by your edits without that baseline.

## An edit that writes cleanly can still be silently dropped

A tracked edit has two failure modes, and only one of them is loud.
The loud one is malformed XML, which every check in this file already catches.
The quiet one is an edit that writes valid XML, parses, validates,
and then simply **is not there** in the accepted view.

Measured 2026-09-01, three times in one session on the same manuscript.
The sharpest case: a tracked prose rewrite applied to runs sitting inside a Zotero field region
wrote valid XML and passed `xml.dom.minidom.parseString`,
and the accepted view came back reading `"...across sites (12) (13)."`
--- the replacement text had vanished entirely,
leaving a sentence with no verb in it.
An inserted run inside a field region does not survive.
(That excerpt is from a private manuscript;
what transfers is the check below, which needs no particular document.)

The check is a diff rather than a parse, and it asks whether the change is there:

```bash
pandoc -t plain --track-changes=accept original.docx -o before.txt
pandoc -t plain --track-changes=accept edited.docx   -o after.txt
diff before.txt after.txt   # the intended change must APPEAR here
```

A clean parse says the file is well-formed.
It says nothing about whether Word will render what you wrote,
so the accepted-view diff is what shows whether an edit landed.
That is [`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md) again,
pointed the other way from the entry above:
there a derived view was read as the document,
here the document's own bytes were read as the rendering.

The corollary is a scope limit worth knowing before planning an edit pass.
**Text adjacent to a Zotero citation is not safely editable programmatically**,
because the surrounding runs may sit inside the field region.
And a citation's own target can only be changed in Zotero:
editing the rendered field result edits a cached rendering,
which reverts on the next field refresh.

- **Do:** diff the `--track-changes=accept` conversion after every tracked edit
  and confirm the intended change is **present**.
- **Do:** leave prose adjacent to a field-code citation alone,
  and route a citation change through Zotero rather than through the XML.
- **Don't:** read a successful write, a clean `parseString`, or a passing validator
  as evidence that the edit survived.
- **Don't:** edit the rendered result of a field code and expect it to persist.

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
