# Manuscript float layout: figures, tables, and captions

These rules govern the layout of a manuscript prepared for journal submission,
whatever tool produces it --- Quarto, R Markdown, LaTeX, or Word.
They concern where figures and tables (the "floats") sit and how their captions render,
not the caption *syntax* of any one tool;
for Quarto's div syntax, see [`quarto-figure-captions`](quarto-figure-captions.md).
(Stated by the user, d-morrison, 2026-10-01.)

A reading copy, a website, or a preprint can still place floats near the text that cites them.
The rules below apply when the target is a journal submission,
where the journal's instructions to authors may ask for floats after the main text;
when a specific journal's instructions say otherwise, follow the journal.

## Main-text floats go at the end of the main manuscript

Put every main-text figure and table at the end of the main manuscript:
after the main text and the references,
and before the supplementary material.
The main text cites each float by number (`Figure 2`, `Table 1`);
the float itself does not appear inline.

In Quarto, place the float divs in a section after the bibliography,
which means positioning the references explicitly with a `::: {#refs}` div
rather than letting Quarto append them at the end of the document.

## A page break before the supplementary material

Insert a page break immediately before the supplementary-material header,
so the supplement starts on a fresh page and the boundary between main manuscript and supplement is unmistakable.
In Quarto, `{{< pagebreak >}}` emits a page break in PDF and DOCX output (and in HTML when printed).

## A caption stays on the same page as its float

Never leave a caption on a different page from its figure or table,
and do not let a caption split across a page break.
Fix both with page breaks **between** floats,
so each float starts on a page where it and its caption fit,
rather than by shrinking the float or cutting the caption.
The one unavoidable case is a float plus caption taller than a full page;
there, keep the float whole and let the caption continue onto the next page.

## Every float gets a numbered caption, rendered as a caption

Every figure and table carries a numbered caption (`Figure 1:`, `Table 2:`, `Supplementary Figure S4:`),
supplementary floats included.
An uncaptioned table is a defect even when its content is right.

The caption must render as a **caption**, not as a section heading.
A line such as `## Supplementary Figure S43: ...` produces a heading:
it shows up in the table of contents, takes heading styling,
is not attached to the float, and is not numbered by the cross-reference system ---
so it drifts out of sync with the real numbering as floats are added or moved.
In Quarto, the caption is the last paragraph of a `#fig-`/`#tbl-` div
(see [`quarto-figure-captions`](quarto-figure-captions.md));
the `crossref` options `fig-title` and `tbl-title` change only the caption's label word (for example, to "Supplementary Figure"),
`fig-prefix` and `tbl-prefix` change the same word in inline references,
and `S`-prefixed numbering needs a custom cross-reference type or a filter.
Either way, the number comes from the tool, never typed into a heading.

## Check these on the render, not the source

Every rule above is a property of the rendered page layout,
so none of them shows in a source diff or in a comparison of the rendered text and numbers.
Measured 2026-10-01 on a private manuscript render:
an uncaptioned two-column `kable` table passed a review that compared the rendered text and numbers against the expected values,
because the comparison covered the table's values,
and a missing caption or a misplaced float changes none of them.
When reviewing a manuscript render, page through it (or its PDF) and check layout explicitly:
float placement, page breaks, caption pagination, and that every float has a numbered caption.
This is the layout half of [`check-the-renders`](../workflow/check-the-renders.md).

- **Do:** put main-text figures and tables after the main text and references, and before the supplement, in a journal-submission manuscript.
- **Do:** insert a page break before the supplementary-material header.
- **Do:** insert page breaks between floats so each caption shares a page with its float.
- **Do:** give every figure and table, supplementary ones included, a numbered caption produced by the tool's caption mechanism.
- **Do:** check layout on the rendered document before calling a render reviewed.
- **Don't:** leave floats inline in a submission manuscript because the source was drafted that way.
- **Don't:** let the supplement header follow the last main-text float on the same page.
- **Don't:** accept a caption stranded on the next page, or split across a page break when a break between floats would avoid it.
- **Don't:** write a caption as a section heading (`## Supplementary Figure S43: ...`) or leave a table uncaptioned.
- **Don't:** treat a text-and-numbers comparison of the render as a layout review.
