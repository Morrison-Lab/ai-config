# Attributions are reader-visible

Credit a source where the document's readers can see it.
An HTML comment (`<!-- Source: ... -->`), a commit message,
or a PR description is not an attribution:
no reader of the rendered website, slides, handout or paper ever sees it.
Credit does not cure a copied passage, though: the text must be the author's own or a marked quotation ([`avoid-unintentional-plagiarism.md`](avoid-unintentional-plagiarism.md)).

Visible credit covers every outside source a reader would want to know about:

- the book or paper an item follows;
- another course's site, notes, or repository it was adapted from;
- the person whose lecture, notes or code it was adapted from.

When a source credits its own upstream,
carry that credit along,
so the chain reaches the reader rather than stopping one hop short.

## Never formally acknowledge the group's own work

"The group" means the maintainer (Ezra Morrison) and the members of the lab that maintains these repositories and manuals.
The group's own work is never credited.
That is work the group wrote, wherever it is stored:
the notes in the group's repositories
(Morrison-Lab and d-morrison, such as rme, lds, mds, pds and sds),
and the other works the group wrote alone or with others
(the UCD-SERG lab manual, the group's papers and packages).
Material that someone outside the group wrote is not the group's own work, even in those repositories.
The rule's full statement is PSW's
[Material from your own work](https://morrison-lab.github.io/psw/chapters/citations-evidence.html#material-from-your-own-work).
Two kinds of credit and citation stay:

- A person outside the group keeps their credit by name.
  For a reused co-written work, the work itself gets no credit, but each outside co-author is credited by name.
  Credit a person such as Kameron Decker Harris, Brian Hutchinson or Logan Sizemore by name when reusing their words or lectures.
- Ordinary citation stays:
  the group's published paper or released software cited as the original publication of a result or as a tool used,
  and a citation that a publisher's reuse terms require.

The maintainer gave two directives:

- 2026-10-05: "you don't have to give attributions for content taken from my other repos".
- 2026-10-16: "we need to stop self-citing", then "cross-refs between our repos are fine, but we shouldn't formally acknowledge borrowing content from ourselves like we do when we adapt content from others".

The rule covers a Source callout, an "adapted from" sentence,
and a bibliography entry for the group's own notes cited as the source of a definition or result.
For a result or definition, cite the original publication and, where one exists, a modern textbook instead,
and link the group's page as a cross-reference.

The rule covers only the hop from the group's own work to the page you write.
What a repository or work itself credits is still carried:
a book or paper it follows,
and any person outside the group whose lecture or notes it adapted,
since several of those repositories hold other authors' work
(lds credits its notes to Kameron Decker Harris, Brian Hutchinson and Logan Sizemore).
A link to a sister site that sends the reader to further reading
is a cross-reference, not an attribution, and is unaffected.

Leave a credit to the group's own work out of new work, and remove an existing one when you find it
(read as covering existing credits, since the 2026-10-16 directive says to stop self-citing;
the earlier rule, "do not strip one that already exists unless the maintainer asks", is superseded).
Keep the cross-reference link to the group's page.

- **Do:** credit the outside book, paper or person an item follows,
  even when it reached you through a sister repository.
- **Do:** write `[Mathematics for Data Science](https://morrison-lab.github.io/mds/...)` as a plain link, with no `[@key]` citation after it.
- **Do:** flag an existing credit to the group's own work for removal in review.
- **Don't:** report a credit to the group's own work as missing in review, or add one.

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

Follow PSW's [Adapting another course's material](https://morrison-lab.github.io/psw/chapters/citations-evidence.html#adapting-another-courses-material): the credit is set apart from running prose, never woven into it.
For a credit that holds more than a citation, such as the link, licence and changes for an adapted course page, the credit goes in a div, and in Quarto that div is a collapsed `.callout-note` titled "Source", which frames the credit and keeps it out of the way on the page.
Do not invent a separate attribution class or style it ad hoc (`.small .text-muted`);
the callout is the lab's one pattern for such credits.
Commentary about a source's history or notation is not a credit of this kind, and goes in a remark.

On a definition or result div whose credit is only a citation, the credit is the final line "Source: @key [locator]." inside the div.
Substantial source or history prose goes in a `#rem-source-` remark div (Ezra, 2026-10-15;
see [`quarto-remarks-vs-callouts`](quarto-remarks-vs-callouts.md)).

Where content lives in small included fragments, keep each credit in the same subfile as its item, not only at the top of the page, so the credit travels with the fragment when another site includes it:

```markdown
::: {#def-overfitting}
#### Overfitting

...

Source: @james2021islr2e [sec. 5.1].

:::
```

A collapsed callout goes inside the item's div, as its last block before the closing `:::`:

```markdown
::: {.callout-note collapse="true"}
#### Source

Adapted from [the course page](https://example.org/notes) under its licence, with the examples replaced.
:::
```

It differs from a `#rem-source-` remark in what it holds: the callout holds the credit's link, licence and changes, and the remark comments on the source's history or notation.

Cite books and papers through the bibliography (`@key [locator]`),
and link an outside site's rendered page at the item's anchor,
checking that the anchor exists and holds the text the credit points to.

## What stays in a comment

A comment remains the right place for maintainer-only notes
that are not attributions:
what was checked in a PDF,
a page number not yet verified,
or a wording edit made while porting.

- **Do:** end each item whose credit holds more than a citation (a link, a licence, a note of changes) with PSW's collapsed "Source" callout.
- **Do:** end an item whose credit is only a citation with a plain "Source:" line.
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
