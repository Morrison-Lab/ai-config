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

## A regex simulating accept/reject over `document.xml` is not a parser of the format, and OMML deletes prove it

Verifying *existing* tracked changes (ones you did not make, and want to
confirm the effect of) by writing a regex that matches `<w:ins>`/`<w:del>`
wrappers and simulates stripping or keeping them is a plausible-looking
shortcut around the pandoc conversions below.
It produced a confident, wrong conclusion once: a regex-based accept/reject
simulation over `word/document.xml` reported that a tracked edit had inverted
an equation, when re-checking with `xml.etree.ElementTree` showed the edit was
correct all along.

The cause is specific to math, and it is worse than a single missed shape:
**two different nestings both occur**, and a document is free to use either.
Outside a math run, Word marks a deletion by **wrapping** the run in a
`<w:del>` element, which is exactly the shape a regex can match.
Inside an OMML (`<m:oMath>`) region, the marker can sit in either of two
places.
Measured 2026-09-09 on a real redlined manuscript: 54 `<w:del>` and 53
`<w:ins>` elements inside `m:oMath`, every one an **empty** element on the
path `w:del < w:rPr < m:r < m:oMath` --- a deletion flagged in the run's own
**properties**, a sibling of `m:t` rather than a wrapper around it.
[`plutext/docx4j` issue #348](https://github.com/plutext/docx4j/issues/348)
documents the other shape for the parallel case (`w:ins`, which OOXML always
treats as `w:del`'s sibling in the same content-model choice): a **wrapper**
element, itself a child of `m:r`, enclosing both `<w:rPr>` and `<m:t>` ---
`<m:r><w:ins w:id="1" w:author="..." w:date="...">`
`<w:rPr>...</w:rPr><m:t>A=π</m:t></w:ins></m:r>` in that issue's own
example, which docx4j's then-current unmarshaller did not expect and dropped
entirely, leaving an empty `<m:r/>`.
So the same deletion can be marked by an empty flag inside the run
properties, or by a wrapper that contains the run properties and the text --
and which one a given document uses is not predictable from outside.
A wrapper-matching regex misses the properties-flag shape entirely, or,
worse, matches an unrelated enclosing element in the wrapper shape and
swallows an arbitrary span.
Nothing about the regex's failure looks like a failure: it returns a
plausible span either way.

The general point is not "write a better regex".
A regex matches **strings**; which of the two OMML nestings marks a given
deletion is a **structural** fact about which element sits under, or wraps,
which -- and a parser has to check both shapes, since neither markup nor a
regex can tell you in advance which one a document chose.
This is [`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)'s
argument in the specific shape it takes for a serialized format: a
hand-rolled simulation of the format's rules is an adjacent artifact to the
format's actual rules, and simulating it thoroughly is still simulating the
wrong thing.

- **Do:** parse `document.xml` with a real XML library
  (`xml.etree.ElementTree`, `defusedxml`) before drawing any conclusion about
  what a tracked change does, math content included.
- **Do:** check for a `<w:del>`/`<w:ins>` in **both** shapes when the run sits
  inside `<m:oMath>` --- an empty one as a `<w:rPr>` child, and a wrapper one
  enclosing `<w:rPr>`/`<m:t>` --- rather than assuming a document uses only
  one.
- **Don't:** treat a regex-based accept/reject simulation as a substitute for
  a parse, however well it matches on ordinary prose --- it is verified only
  against prose, not against math.
- **Don't:** trust a regex-derived verdict about a tracked change without
  cross-checking it against the pandoc conversions in the next section, which
  read the format through its own real parser.

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

**2nd occurrence of the missing-wrapper failure, this time authored by an edit
rather than found in one already there --- confirming the reject-diff is the
check that catches it, not just a hypothetical.**
An edit split a run with `run_text.split(anchor, 1)` and wrote back only the
head plus the new `<w:ins>` insertion, silently dropping the tail instead of
wrapping it in a `<w:del>`.
The accept-diff looked perfect, because the accepted view never shows what a
deletion removed.
Simulating **reject** is what exposed it: the original sentence was gone from
both conversions, unrecoverable, and the mangled remnant read
"It is the product**t** (the incidence rate...)" --- so the reject-diff was
non-empty exactly as this section's bullet predicts, and that is the one
comparison a forward-only (accept-only) check cannot perform.

The transferable shape, beyond this format: for any mechanism that is
supposed to be reversible --- tracked changes, a migration's down step, a
feature flag's off path --- the forward direction is the one a normal test
run exercises, so the reverse direction is where silent data loss hides.
Verifying the forward result looking right says nothing about whether the
reverse path still recovers the original; only running the reverse path does.

- **Do:** simulate the reverse path of any reversible edit before trusting
  the forward result, not only when the forward result looks suspicious.
- **Don't:** read a clean accept-diff as evidence the edit is
  non-destructive --- an accept-diff cannot see content a `<w:del>` never
  wrapped, because there is nothing there for accept to keep.

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

**The same accept-diff also settles a reviewer's finding, not only an author's self-check.**
Word's "All Markup" display shows a tracked insertion and the deletion it replaces at once, which reads exactly like a stray duplicate to a reviewer who has not resolved the changes --- run the accept-mode extraction before reporting a finding about content that shows up only in that view.
[`verify-the-right-artifact`](../shared/workflow/verify-the-right-artifact.md)'s "A tracked-change DISPLAY VIEW, standing in for the resolved document a finding means" section carries the general shape and a measured case.

## A tracked change's `w:author` decides who made it, not the size of the diff

In a redlined document written by more than one person,
measuring how much text changed in a paragraph is not the same claim as
measuring who changed it --- and it is easy to conflate the two, because a
paragraph carrying insertions and deletions reads as "edited", and the
nearest edit session in memory is the available explanation for whose it was.
That is [`metacognitive-monitoring`](../shared/workflow/metacognitive-monitoring.md)'s
**cause** claim type in a docx-specific shape: proximity to the observed
effect stands in for a check of what actually produced it.

Measured 2026-09-09: tallying inserted and deleted characters per paragraph
in a redlined supplement showed heavy edit density in one section, and the
paragraph having many edits was read as evidence of having authored them.
Reading the `w:author` attribute on the `<w:ins>`/`<w:del>` elements in that
same section showed every one of those insertions carried a different name
and a date three weeks earlier --- the document's own student author, in
a paragraph the reviewing edits never touched.
"This paragraph contains insertions" and "I made those insertions" are
different claims, and only `w:author` (with `w:date` for a tie-break when
two authors both touched a run) settles the second, in a document more than
one person has edited.

The check is a query rather than a diff: tally `(tag, author, date)` per
paragraph --- `<w:ins>`/`<w:del>` count grouped by `w:author` --- rather than
a paragraph-level character count with no author dimension at all.

```python
import defusedxml.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
tree = ET.parse("word/document.xml")
for p in tree.iter(f"{W}p"):
    for tag in (f"{W}ins", f"{W}del"):
        for el in p.iter(tag):
            print(tag, el.get(f"{W}author"), el.get(f"{W}date"))
```

- **Do:** tally tracked-change elements by `(tag, author, date)` before
  attributing a paragraph's edits to yourself or to anyone else.
- **Do:** treat a character-count or edit-density measurement as evidence
  that a paragraph changed, never as evidence of who changed it.
- **Don't:** offer to revert, or otherwise act on, content whose authorship
  you inferred from proximity rather than read from `w:author`.

## A hand-built accept/reject simulator is itself an unverified instrument until it passes a negative control

The two pandoc diffs above work because pandoc is a real, independently
tested parser of the format.
Writing your own accept/reject renderer --- to check a specific structural
question pandoc's plain-text output can't answer, say --- forfeits that, and
the replacement needs the same scrutiny any new instrument does per
[`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md): a
freshly built checker is exactly as trustworthy as its own testing, and
"trustworthy because I wrote it carefully" is not testing.

Measured 2026-09-09: a renderer built to simulate accept and reject over
`word/document.xml` collected every `<w:t>` node in one pass and every
`<w:delText>` node in a second pass, then reassembled each in document
order **within its own pass** --- so on the reject path, every deleted
string was appended after every kept string, landing at the end of the
paragraph instead of back in its original position.
The output looked exactly like real data loss: a sentence reassembled as
"terms: the participant-level log-likelihoods to be summed.
ach biomarker retains..." with the deleted text relocated and mangled to
look like a missing fragment.
The document was fine.
The instrument was broken, and its false report was nearly acted on as a
finding.

The general shape is worth carrying past this one bug: a checker's false
**negative** here --- reporting a defect that is not there --- is not the
safe direction the way it usually is.
It reads as a rigorous, structural finding rather than a guess, so it invites
a "fix" to already-correct content, which is strictly worse than the false
positive (a real problem missed) everyone instinctively worries about.

What would have caught it immediately is the negative control this corpus
already prescribes for any new instrument: run the harness against the
document's own **known-good prior version** and require a clean result
before trusting anything it reports on the version under test.
Rewriting the renderer to walk `document.xml`'s children in document order,
rather than collecting node types in separate passes, made reject
byte-identical to the original --- which is what a working instrument looks
like on a negative control, and the reading the broken one had been
imitating.

- **Do:** run a hand-built docx verification harness against a known-good
  document first, and require a clean (no-op) result, before trusting any
  finding it reports on a document under test.
- **Do:** prefer pandoc's own accept/reject conversion (the section above)
  whenever it can answer the question, since it needs no such control of
  your own.
- **Don't:** treat a harness's own careful construction as a substitute for
  testing it --- an instrument built to check an artifact is itself an
  unchecked artifact.
- **Don't:** act on a structural-looking finding (a harness's reject-diff,
  a parser's reported span) before confirming the harness itself is sound.

## Read `word/comments.xml` before proposing a new review comment

Proposing to add a review comment without first reading the document's
**existing** comments is the same dupe-check gap
[`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md) and
[`issue-first`](../shared/workflow/issue-first.md) describe for a memory
entry or a tracker issue, in a docx-specific shape: a document's
`word/comments.xml` is the population to search before authoring new
content, not just the paragraph text you happen to be looking at.

Measured 2026-09-09: after telling a document's author that a new comment
would be added raising three concerns about a confidence-interval
construction, opening `word/comments.xml` showed comment id 209, already
present from an earlier review pass on the same document, raising the same
three concerns in more specific terms --- citing an issue number and noting
that both manuscript intervals came from two-biomarker fits.
The corpus-wide dupe-check had been run diligently in the same session;
the document-local one, over an artifact already open, had not.

- **Do:** read `word/comments.xml` (or the skill's comment-listing helper)
  before proposing or drafting a new comment on a document already carrying
  review history.
- **Don't:** treat "I have not seen this concern in the paragraph text" as
  having checked whether it was already raised --- a comment lives in
  `comments.xml`, not in the run you are reading.

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

## Writing a NEW OMML tracked-change marker: wrap `w:rPr`, don't put the marker inside it

The "A regex simulating accept/reject..." section above is about *reading* tracked changes someone else already made;
this is about *writing* a new one by hand, and it is a different mistake with a different fix.

Writing a fresh `w:ins`/`w:del` marker for an OMML (`<m:oMath>`) run as a **child** of that run's own `<w:rPr>` produced markup Word refused outright ("Word found unreadable content ...
Do you want to recover the contents"):

```xml
<m:r><w:rPr><w:ins w:id="9301" w:author="..." w:date="..."/><w:rFonts .../></w:rPr><m:t>x</m:t></m:r>
```

`CT_RPr` has no `w:ins`/`w:del` child.
The shape that opens correctly, confirmed against the *same* document's own pre-existing, Word-authored tracked changes, **wraps** the run properties and the text instead:

```xml
<m:r><w:del w:id="9" w:author="..." w:date="..."><w:rPr>...</w:rPr><m:t>x</m:t></w:del></m:r>
<m:ctrlPr><w:del w:id="10" w:author="..." w:date="..."><w:rPr>...</w:rPr></w:del></m:ctrlPr>
```

The one place a marker legitimately sits **inside** a `w:rPr` is when that `w:rPr`'s own parent is `w:pPr` --- `CT_ParaRPr`, the inserted/deleted paragraph-mark case.
That single exception is the whole of it: everywhere else, `w:ins`/`w:del` wraps `w:rPr` and the content, rather than sitting inside it.

**The cause was a direction-ambiguous note, and the fix is to quote the source instead of describing its shape.**
An earlier note in this same file measured 54 `<w:del>` and 53 `<w:ins>`
elements on the path `w:del < w:rPr < m:r < m:oMath` --- see its "A regex simulating accept/reject..." section above, which is the entry that notation comes from.
A "path" written as a chain of tag names carries no marked direction: read one way it says the marker sits *inside* the properties, read the other way it says the marker *wraps* them, and nothing in the four bare names decides which.
That note was read in the wrong direction when used as a template for writing brand-new markers, and the nesting came out inverted.

The reading that inverted it is not obviously wrong on its face, which is what makes the notation worthless rather than merely imprecise: the same sentence in that earlier entry also calls the measured element "a sibling of `m:t`", language that describes a marker sitting *alongside* the run's content rather than one level deeper inside its properties.
A path expression and a prose description of the same structure disagreeing about what "inside" means is the ambiguity, not a one-off misreading of a clear note --- and it is left as an open question here (not resolved, since it is not independently re-checkable from this repository) whether that earlier 54/53 measurement was itself affected by the same ambiguity, or describes a genuinely different shape.
What is independently confirmed, from this document's own markup and from Word's refusal to open the alternative, is the wrapping shape above.

The durable fix is the one this incident's own working notes reached for independently: don't describe a nesting relationship as a nameless chain of tags.
Quote the literal snippet from the source file instead.
A quoted snippet carries its own direction --- the wrapping element is visibly the one with the opening and closing tags on the outside --- where a path notation has to be interpreted.

- **Do:** write `w:ins`/`w:del` as the element that wraps `w:rPr` and the run's text, for any OMML run outside a paragraph mark.
- **Do:** treat `w:pPr`'s own `w:rPr` as the sole exception where a marker legitimately sits inside `w:rPr` rather than around it.
- **Do:** record a structural finding as a literal quoted snippet, not as a chain of tag names --- a snippet's own opening/closing tags carry the direction that a path notation strips out.
- **Don't:** infer a marker's correct position from a "path" note without also confirming which way that note's author meant it to read.
- **Don't:** treat a document's OWN pre-existing tracked changes as safe to skip checking against --- they are the ground truth for what that document's markup generator actually produces, and confirming an edit against a note *about* them is a weaker check than confirming it against a literal example pulled from the file itself.

(Measured 2026-09-09 on a manuscript resubmission.
The invalid shape was introduced by hand while adding new tracked-change markers to an OMML equation, propagated through five successive delivered copies (75 malformed elements in the first, 92 by the fifth) because the verification in use --- a pandoc-style accept/reject text diff over `word/document.xml` --- cannot see a markup-validity defect at all;
see [`shared/workflow/verify-the-right-artifact.md`](../shared/workflow/verify-the-right-artifact.md)'s "A content diff verifies WHAT CHANGED, not whether the markup is valid" section for why.
`scripts/check-docx-tracked-changes.py` in this repo is the structural checker that would have caught it before delivery.)

## Re-serializing an OOXML part with a generic XML library drops prefix bindings, not prefix-shaped text

A second, independent defect turned up in the same manuscript, in a different part: `word/comments.xml` had been rebuilt by an XML library (ElementTree/lxml) and came out carrying `mc:Ignorable="w14 w15 w16se w16cid w16 w16cex w16sdtdh w16sdtfl w16du wp14"` on its root element while declaring **none** of those ten namespace prefixes.
[Markup Compatibility (ECMA-376 Part 3)](https://ecma-international.org/publications-and-standards/standards/ecma-376/) requires every prefix an `mc:Ignorable` attribute names to be declared in scope on that same element.
Word refused the part;
the three Word-authored sibling parts (`commentsExtended.xml`, `commentsIds.xml`, `commentsExtensible.xml`) each declared the full ten-prefix set, which is what made the missing one noticeable at all.

The mechanism generalizes past `mc:Ignorable` specifically, and it is worth naming on its own: a generic XML library reserializes a document's actual `xmlns:*` **declarations** faithfully (or regenerates its own, differently named, `ns0:`/`ns1:`-style prefixes for whatever it still uses), but it has no way to know that a prefix also appears as plain **text** inside some attribute's *value* -- `mc:Ignorable`'s value is a whitespace-separated list of prefix names, which to a generic serializer is just a string, not a reference to anything.
So the round-trip preserves the string and can silently stop preserving the binding that string depends on, and nothing in that round-trip errors: the attribute is still there, spelled exactly as before, and the file still opens as XML.
It only breaks under the schema this specific attribute's semantics impose, which no general-purpose XML library enforces.

The repair was to rebuild the affected root using a Word-authored sibling part's own `nsmap` and `mc:Ignorable` value as the template, rather than trying to patch the broken one in place.

- **Do:** treat any attribute whose value is a whitespace- or comma-separated list of namespace prefixes (`mc:Ignorable`, `mc:ProcessContent`'s `PreserveAttributes`, and their relatives) as a second reference to check after a re-serialization, separately from checking that the element's own tag and normal attributes survived.
- **Do:** compare a re-serialized part's namespace declarations against an untouched Word-authored sibling part when one exists, rather than reasoning about what the library "should" have preserved.
- **Don't:** assume a generic XML library's round-trip is content-preserving for a prefix that only appears inside an attribute's text -- the serializer's namespace handling cannot see it there.
- **Don't:** trust `ElementTree.fromstring()`'s parsed tree to answer "which prefixes are declared in scope here" -- it discards prefix bindings once parsed, keeping only resolved `{uri}local` names;
  checking `mc:Ignorable` against them needs a re-parse that tracks namespace events directly (see `scripts/check-docx-tracked-changes.py`'s `check_ignorable_prefixes`).

(Measured 2026-09-09, same manuscript and session as the OMML entry above.
`scripts/check-docx-tracked-changes.py` in this repo implements the check this incident argues for.)

## A math structure's ctrlPr must be marked separately from its runs, or accepting/rejecting leaves an empty box

The two entries above cover markup *validity* -- whether the XML is legal at all.
This one is a *rendering* defect in perfectly well-formed markup: a math structure whose runs are correctly tracked-change-marked, but whose own container is not, so it survives the edit as an empty placeholder box.

OOXML math structures Word renders slot-by-slot regardless of content --- `m:sSup`'s base (`m:e`) and exponent (`m:sup`), `m:f`'s numerator and denominator, and similarly `m:sSub`, `m:sSubSup`, `m:sPre`, `m:d`, `m:nary`, `m:func`, `m:rad`, `m:limLow`, `m:limUpp`, `m:groupChr`, `m:bar`, `m:acc`, `m:eqArr`, `m:box`, `m:borderBox`, `m:phant`, `m:m` (matrix).
Each carries an `m:<tag>Pr` child holding an `m:ctrlPr`, and that `ctrlPr` carries the **structure's own** revision mark, independent of whatever marks sit on the runs inside it:

```xml
<m:sSup>
  <m:sSupPr><m:ctrlPr><w:del w:id="10" w:author="..." w:date="..."><w:rPr>...</w:rPr></w:del></m:ctrlPr></m:sSupPr>
  <m:e><m:r><w:del w:id="11" ...><w:rPr>.../><m:t>x</m:t></w:del></m:r></m:e>
  <m:sup><m:r><w:del w:id="12" ...><w:rPr>.../><m:t>2</m:t></w:del></m:r></m:sup>
</m:sSup>
```

Deleting every run inside a structure without also marking its `ctrlPr` `w:del` leaves the structure itself un-deleted: accepting the change removes all the text and Word still draws the (now empty) base/exponent box, because the box is a property of the structure, not of its text.
The mirror case: a structure built entirely from `w:ins` runs whose `ctrlPr` is not marked `w:ins` leaves the same empty box on **rejection**.

This is measured as Word's own convention, not invented: a real hand-edited document in this same manuscript carried 3 `m:ctrlPr` elements marked `w:ins` and 6 marked `w:del`, on structures whose own runs carried the matching mark independently.
Word marks both -- the structure's `ctrlPr` and its runs' text -- as two separate facts about the same edit.

The 19-tag list above is the complete set, confirmed against the raw `shared-math.xsd` schema (every `complexType` ending `Pr` checked for a `ctrlPr` child) rather than trusted from a hand-written enumeration -- the first version of this list, and of the check it documents, missed `m:m` (the matrix element), caught by a review on the PR that introduced both (Morrison-Lab/ai-config#3423).
That same schema search found one more `ctrlPr` location, deliberately left out of the list above: `CT_OMathArg` (the type of `m:e`, used for every argument slot -- a structure's base, its numerator, a matrix cell, ...) also carries an optional `ctrlPr`, as a direct sibling of its own content rather than nested inside an `<x>Pr` wrapper the way every structure above is.
That is a different revision-tracking surface -- most plausibly per-argument insertion/deletion in a variable-arity construct like a matrix row, rather than the fixed-slot empty-box defect this entry is about -- with a different wrapper shape needing its own traversal code, so it is tracked separately rather than folded into the tag list here (Morrison-Lab/ai-config#3429).

Nothing existing catches an unmarked `ctrlPr`.
An accept/reject text diff can't see it, because an empty placeholder box carries no text to diff.
It is also independent of the structural-validity checks two entries up: the markup here is entirely legal, it simply renders wrong.

- **Do:** when deleting/inserting every run inside a math structure by hand, mark that structure's own `m:<tag>Pr/m:ctrlPr` with the same direction, as a second edit distinct from marking the runs.
- **Do:** distinguish a structure that lost all its text to an edit (a defect, if its `ctrlPr` is unmarked) from one that carries no text at all in either direction (a blank placeholder already in the source, not a defect) --- conflating the two produces a report dominated by noise.
- **Don't:** assume marking a structure's runs is sufficient;
  the structure's own container needs its own mark.
- **Don't:** trust a content/text diff to catch this --- an empty box renders no text, so there is nothing for a text diff to see.

(Measured 2026-09-09, same manuscript as the two entries above.
`scripts/check-docx-tracked-changes.py`'s `check_orphaned_math` implements the check this convention argues for -- built from a working draft, then extended into that script's existing per-part check pipeline, checking both accept and reject in one pass.
Reproduced against four real deliveries of the same manuscript: one carrying exactly one orphaned `m:sSup` under accept, one carrying exactly one orphaned `m:sSub` under reject (present since the first delivery, fixed only in the next), and the final two both clean under both directions.)

## `m:oMathPara` does not claim its own line; the surrounding `w:br` elements do

`m:oMathPara` marks an equation as display math, but that markup alone does not put it on its own line.
Two ordinary line breaks, each its own run, do that work:

```xml
<w:r><w:br/></w:r>
<m:oMathPara>
  <m:oMath>
    ...
    <m:r><w:br/></m:r>
  </m:oMath>
</m:oMathPara>
```

A `<w:r><w:br/></w:r>` immediately **before** the `m:oMathPara` breaks the introducing prose onto its own line.
A closing `<m:r><w:br/></m:r>` as the **last child of `m:oMath`** breaks the equation off from whatever prose follows it.
The two breaks are independent: either can be present while the other is missing, and each omission produces a different symptom (the prose runs into the equation, or the equation runs into what follows) with the same underlying markup otherwise unchanged.

Neither omission has anything to do with whether `m:oMathPara` was the right choice.
The equation is still correctly display either way, so "this equation runs into its neighbouring prose" does not by itself say whether the fix is converting to inline or adding the missing break --- reading the two break positions is what decides it.
This is a *rendering* gap distinct from the ctrlPr entry above: that one is about a structure's own container losing its revision mark;
this one is about a correctly-marked display equation missing the plain line breaks that put it on its own line, and the two can be checked independently.

- **Do:** check both `w:br` positions --- immediately before the `m:oMathPara`, and as the last child of `m:oMath` --- before concluding a running-together equation has the wrong display/inline form.
- **Do:** treat the two breaks as independently omittable, so confirming one is present says nothing about the other.
- **Don't:** convert a correctly-display equation to inline as the fix for prose running into it;
  that discards a correct choice without repairing the missing break, and the equation will still run into whatever follows it if the closing break is also missing.

(Measured 2026-09-09, same manuscript and session as the entries above.
Three new equations, each correctly authored as display, were missing one or both of these breaks;
two further equations elsewhere in the same document had the identical gap, unnoticed until a per-file checker counted display equations against their break requirements.
Five equations in total, missing seven breaks between them (three missing one side, two missing both) --- the same tally [`shared/writing/math-derivation-steps.md`](../shared/writing/math-derivation-steps.md)'s "Choose display or inline, deliberately" section records, which also carries the display-versus-inline decision this defect is easy to mistake for.)
