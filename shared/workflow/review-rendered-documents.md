# Review every page of a rendered document before calling it ready

A PR or MR that changes a rendered document is not ready, and is not mergeable under any grant, until someone has opened the rendered output at the current head and looked at every page.
This is a hard gate, not a guideline.
Green CI, a clean review verdict, and a correct source diff do not satisfy it, alone or together.

It extends [`check-the-renders`](check-the-renders.md), which covers websites and books, to documents whose deliverable is a file: Word (`.docx`), PDF, slides, a manuscript and its supplement, a report.
It stacks on the [`fully-clean`](fully-clean.md) criteria; neither satisfies the other.

## When it applies

The gate applies when the diff can change what a rendered document looks like.
That includes:

- the document source (`.qmd`, `.Rmd`, `.tex`, `.md` rendered to a document format);
- the code, data, or parameters that feed its tables, figures, or inline numbers;
- its templates, reference document (`reference-doc`), styles, CSL, bibliography, or render configuration.

When in doubt, it applies.
A PR whose only effect on the document is invisible (a comment in an R script that renders nothing) can say so in one line instead.

## Why

On 2026-10-01 and 2026-10-02, several manuscript MRs on the abridge project were reported ready, and some were merged, with a green pipeline and no one having opened the rendered Word document.
The pipeline proved the document rendered.
It did not prove the document was right: caption placement, table layout, page breaks, and figure order are visible only on the page.
The user's reaction was that treating those MRs as ready was insane, and the gates in this corpus allowed it, because `fully-clean`, `ardi`, and `mwc` looked only at CI and review verdicts.

## Procedure

1. **Render at the current head.**
   Use the repo's own render command.
   A render from an earlier commit is evidence about that commit only (see [`verify-the-right-artifact`](verify-the-right-artifact.md)).
2. **Convert to PDF**, if the output is not already PDF.
   Prefer the application the reader will use: Word for `.docx` (on macOS, Word's "Save as PDF" or a scripted export).
   When Word is not available, `soffice --headless --convert-to pdf <file>.docx` is acceptable, but say so: LibreOffice can paginate differently from Word, so page-break and caption-placement findings must be confirmed in Word before they are called fixed.
3. **Rasterize every page**, for example `pdftoppm -r 80 -png <file>.pdf pages/p`, and count the pages (`pdfinfo`).
4. **Look at every page image**, main document and supplement, in order.
   Not a sample, not the first few, not only the pages the diff touched: a change on page 3 can push a caption off page 17.
5. **Check each page** for:
   - a table running off the page or split badly;
   - a figure that is missing, cropped, blurry, or out of order;
   - a missing number or caption on any table or figure;
   - broken cross-references (`??`, `?@fig-`, `Table ?`), raw Markdown, code output, warnings, or `NA` cells;
   - any breach of the float and caption layout rules in the `manuscript-float-layout` fragment ([ai-config#4203](https://github.com/Morrison-Lab/ai-config/pull/4203));
   - anything else the document's own conventions require (for a manuscript, the [`manuscript`](../../skills/manuscript/SKILL.md) skill's checklist).
6. **Record the evidence** in a PR/MR comment: the commit the render came from, the converter used, the page count, that every page was viewed, and each finding with its page number.
   Post the independent reviewer's report from step 7 too, per [`adversarial-self-review`](adversarial-self-review.md#post-every-independent-review-on-the-pr-or-mr-it-reviewed).
   Fix the findings and repeat from step 1 on the new head.
7. **Get an independent referee read of this render** before handing it back to the user: a reviewer other than the session that made the revision reads every page, per [`adversarial-self-review`](adversarial-self-review.md#review-every-revision-before-it-goes-back-to-the-user).
8. **Only then** report the PR ready or treat it as mergeable.
   A push after the review invalidates it, exactly as it invalidates a review verdict.

## When you cannot view the pages

If the session cannot render, convert, or view images (a missing converter, a file it cannot reach, no image-reading tool), the gate is not met.
Say so plainly, name what blocked it, and ask the user to view the document or to unblock the step.
Never substitute a text extraction, a CI artifact's existence, or a source read for viewing the pages, and never describe the PR as ready while the gate is open.

- **Do:** open the rendered document at the current head, look at every page, and post the page-by-page evidence before calling the PR ready.
- **Do:** treat an unviewable render as a blocker you report, not a step you skip.
- **Don't:** call a document-producing PR ready, or merge it under `mwc` or any other grant, on green CI and a clean review alone.
- **Don't:** check only the pages the diff touched, or a render from an earlier commit.
