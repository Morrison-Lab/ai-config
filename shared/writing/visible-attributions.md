# Attributions are reader-visible

Credit a source where the document's readers can see it.
An HTML comment (`<!-- Source: ... -->`), a commit message,
or a PR description is not an attribution:
no reader of the rendered website, slides, handout or paper ever sees it.

This covers every source a reader would want to know about:

- the book or paper an item follows;
- the course site, notes, or repository it was adapted from;
- the person whose lecture, notes or code it was adapted from.

When the source credits its own upstream,
carry that credit along,
so the chain reaches the reader rather than stopping one hop short.

## Where the credit goes

Put it next to the content it credits,
not only in a page-level list,
so it travels with the content when a fragment is included elsewhere.
In Quarto, end the item's own div with a small, muted note:

```markdown
::: {#def-overfitting}
#### Overfitting

...

::: {.small .text-muted}
Source: adapted from the rme notes'
[definition of overfitting](https://morrison-lab.github.io/rme/chapters/predictor-selection.html#def-overfitting);
see also @james2021islr2e [sec. 5.1].
:::

:::
```

Cite books and papers through the bibliography (`@key [locator]`),
and link a site's rendered page at the item's anchor,
checking that the anchor exists and holds the text the credit points to.

## What stays in a comment

A comment remains the right place for maintainer-only notes
that are not attributions:
what was checked in a PDF,
a page number not yet verified,
or a wording edit made while porting.

- **Do:** end each adapted or sourced item with a visible "Source:" note.
- **Don't:** leave an attribution only in an HTML comment.

(Morrison-Lab/sds, 2026-10-05:
every item ported from rme or lds, or following ISLR or ESL,
carried its credit only in a `<!-- Source: ... -->` comment.
The owner's correction was that attributions should be reader-visible;
[sds#72](https://github.com/Morrison-Lab/sds/pull/72)
moved all 20 into visible notes.)
