# Attributions are reader-visible

Credit a source where the document's readers can see it.
An HTML comment (`<!-- Source: ... -->`), a commit message,
or a PR description is not an attribution:
no reader of the rendered website, slides, handout or paper ever sees it.

This covers every outside source a reader would want to know about:

- the book or paper an item follows;
- another course's site, notes, or repository it was adapted from;
- the person whose lecture, notes or code it was adapted from.

When a source credits its own upstream,
carry that credit along,
so the chain reaches the reader rather than stopping one hop short.

## The maintainer's own repositories need not be credited

Content taken from the maintainer's own repositories
(Morrison-Lab and d-morrison, such as rme, lds, pds and sds)
does not have to be attributed to them
(user directive, 2026-10-05:
"you don't have to give attributions for content taken from my other repos").
The exemption covers only that hop.
What the repository itself credits is still carried:
a book or paper it follows,
and any person other than the maintainer whose lecture or notes it adapted,
since several of those repositories hold other authors' work
(lds, for one, credits its notes to Kameron Decker Harris and Brian Hutchinson).
A link to a sister site that sends the reader to further reading
is a cross-reference, not an attribution, and is unaffected.

The directive removes a requirement.
It does not forbid a credit.
So a sister-repository credit may be left out of new work,
but do not strip one that already exists unless the maintainer asks.

- **Do:** credit the outside book, paper or person an item follows,
  even when it reached you through a sister repository.
- **Don't:** report a missing sister-repository credit as a review finding,
  or delete an existing one unasked.

## Material written from scratch names no source

Material the maintainer's group wrote from scratch,
with no outside source behind it, has nothing to credit,
so it carries no source line, not even one saying it is new
(user directive, 2026-10-08:
"we don't need to state sources for material that we generated ourselves").
A line such as "Source: new for Fall 2026, written for Midterm 1",
in the text or in a comment, credits nobody;
leave it out, and remove it where you find one.
Material adapted from an outside source is not written from scratch,
however much it was reworded, and keeps its credit.
A note on where a worked example's numbers came from
("the counts are invented for hand computation",
or the library version that produced them)
is not a source line, and stays.

- **Do:** leave the source line off a question, example or section you wrote from scratch.
- **Don't:** add a "new for <term>" or "written for <assessment>" line as if it were a credit.

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

@james2021islr2e [sec. 5.1].
:::

:::
```

Cite books and papers through the bibliography (`@key [locator]`),
and link an outside site's rendered page at the item's anchor,
checking that the anchor exists and holds the text the credit points to.

## What stays in a comment

A comment remains the right place for maintainer-only notes
that are not attributions:
what was checked in a PDF,
a page number not yet verified,
or a wording edit made while porting.

- **Do:** end each item adapted from an outside source with PSW's collapsed "Source" callout.
- **Don't:** leave an attribution only in an HTML comment.

(Morrison-Lab/sds, 2026-10-05:
every item ported from rme or lds, or following ISLR or ESL,
carried its credit only in a `<!-- Source: ... -->` comment.
The maintainer's correction was that attributions should be reader-visible,
and in divs;
[sds#72](https://github.com/Morrison-Lab/sds/pull/72)
moved all 20 into PSW's Source callouts,
after a first attempt that invented an `.attribution` class
was caught for contradicting PSW.
Later the same day the maintainer added that credits to their own repositories are not needed,
pointing at one of the PR's rme credits,
so the PR's commit `714dd913` dropped its rme and lds credits,
and `aae43d26` kept those to ISLR, ESL, Dobson and the lecturers the lds notes credit.)

(Morrison-Lab/mlg, 2026-10-08:
23 questions in mlg's question bank ended their answers with
"Source: new for Fall 2026, written for ...",
and two more carried the same note in an HTML comment.
The maintainer pointed at one of them on
[mlg#67](https://github.com/Morrison-Lab/mlg/pull/67),
which removed all of them and kept the notes on where each question's numbers came from.)
