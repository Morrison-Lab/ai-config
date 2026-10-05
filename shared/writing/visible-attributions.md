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

Follow PSW's
[Adapting another course's material](https://morrison-lab.github.io/psw/chapters/citations-evidence.html#adapting-another-courses-material):
the credit goes in a div, never in running prose,
and in Quarto that div is a collapsed `.callout-note` titled "Source",
which frames the credit and keeps it out of the way on the page.
Do not invent a separate attribution class or style it ad hoc
(`.small .text-muted`); the callout is the lab's one pattern.

Where content lives in small included fragments,
put the callout at the end of each item's own div,
not only at the top of the page,
so the credit travels with the fragment when another site includes it:

```markdown
::: {#def-overfitting}
#### Overfitting

...

::: {.callout-note collapse="true"}
#### Source

Adapted from the rme notes'
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

- **Do:** end each adapted or sourced item with PSW's collapsed "Source" callout.
- **Don't:** leave an attribution only in an HTML comment.

(Morrison-Lab/sds, 2026-10-05:
every item ported from rme or lds, or following ISLR or ESL,
carried its credit only in a `<!-- Source: ... -->` comment.
The owner's correction was that attributions should be reader-visible,
and in divs;
[sds#72](https://github.com/Morrison-Lab/sds/pull/72)
moved all 20 into PSW's Source callouts,
after a first attempt that invented an `.attribution` class
was caught for contradicting PSW.)
