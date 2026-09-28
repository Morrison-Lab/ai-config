A grouping level must earn its place: introducing one costs the reader a
level of nesting, and that cost is only repaid when the level actually
separates something from something else.
Headings are the clearest case, site navigation menus follow the same logic,
and a page's own scope is the inverse question --- the three sections below
are instances of one test, not three rules.

## Headings

Headings form an outline, and an outline entry only means something when it
has a sibling.
"1.1" implies "1.2" --- a numbered subsection with no peer at its own level
is not a subsection at all, it is the parent renumbered one level deeper.
The Markdown/Quarto analogue: a heading level is meaningful only when its
parent contains **at least two** headings at that level.
A lone child heading adds nesting without adding structure.
Either promote it into its parent (drop the heading, keep the prose) or drop
the parent and promote the lone child's own children up a level.

### The common case: a wrapper that restates the title

The shape that keeps recurring is a page whose YAML `title` already names the
topic, and whose entire body then sits under one `##` section restating it:
a page titled "Algebra" whose whole body sits under `## Elementary Algebra`,
with `### Equalities`, `### Inequalities`, and the rest of the real sections
nested a level below that.
The wrapper heading has no sibling --- there is no second `##` beside it --- so
it is not doing outline work, and it pushes every real section one level
deeper than it needs to be.

Drop the wrapper heading and promote its children (`### Equalities` becomes
`## Equalities`, and so on).
The page's actual sections --- which *do* have siblings --- become the
document's top level.

- **Do:** treat "does this level have a second heading beside it" as the test
  for whether a heading level belongs, the way "1.1" implies "1.2".
- **Do:** promote a lone child's contents and delete the wrapper heading that
  only restated the page or document title.
- **Don't:** nest real, multi-sibling sections one level deeper than they
  need to be, just because a solitary wrapper heading sits above them.
- **Don't:** read one first-level heading under the page title as normal
  Quarto structure without checking whether it has a sibling --- a single
  `#`/`##` wrapping the *whole* body is the wrapper case above, not an
  ordinary lead section.

### In a Quarto website or book chapter

The YAML `title` renders as the page's `<h1>`, so body sections start at
`##`.
Never skip a level (a `####` heading directly under a `#`, with no `##`/`###`
in between), and never place a higher-level heading as a peer *after*
lower-level content --- a `# References` heading following a run of `##`
sections reads as a step back up the outline, not a new top-level part.

**Exception:** a trailing, unnumbered References or Further-reading section
may stand alone at the same level as the page's content sections, even
though it never gets a sibling.
It closes the document rather than organizing it, so the "needs a sibling"
test does not apply to it.

### Preserve crossref ids and anchors when restructuring

In a repository whose fragments are included by other sites (this corpus's
own `d-morrison/rme`, `Morrison-Lab/mds`, `Morrison-Lab/sds`, and
`Morrison-Lab/pds` are all in that position), a heading's path and its
`#id` are load-bearing: renaming or dropping a heading can rename or drop
the anchor a host site or a `@crossref` depends on.

Keep explicit `{#sec-...}` ids on a heading when promoting or demoting it, and
check --- before merging --- that nothing still points at an id or an
auto-generated slug the restructuring removed:

- Grep the repo (and, where practical, a host site that includes it as a
  submodule) for the old heading's auto-generated anchor and any explicit
  `{#sec-...}` id near it.
- Where a heading carries no explicit id, promoting or demoting it changes
  Pandoc's auto-generated slug, which silently breaks any link built from
  the old text rather than from a stable id.

### In `revealjs` output, heading levels are slide boundaries

Quarto's `revealjs` format slices slides at `slide-level`, so a heading-level
change is also a slide-boundary change.
Dropping a wrapper heading can merge what used to be two slides into one;
promoting a lone child can split a slide that used to hold several sections.
After restructuring, re-render the deck and check it did not gain a
title-only slide --- the failure mode a promoted or demoted heading produces
most often.

(User question, 2026-09-28, on
<https://morrison-lab.github.io/mds/pr-preview/pr-11/algebra.html>: "has only
one first-level header; should the header levels for that page be adjusted?
in general, don't headers only make sense in a document when there are
multiple at the same level (nested within the prior level)?"
Answer: yes.)

## Site navigation

The same test applies one level up, to a site's navbar rather than to a
page's headings: a dropdown groups several pages under one label, and that
grouping earns its place only when a flat bar would not fit.

List pages as top-level navbar items by default.
Add a dropdown menu only when the flat list of top-level items would be too
cluttered to fit --- typically at desktop width, since that is where a wide
navbar actually runs out of room.
Prefer shortening a navbar item's label over reaching for a dropdown: a
navbar item's `text` can differ from the page's `title`, so a long page title
does not by itself justify hiding the page behind a menu.

Quarto already collapses the navbar into a hamburger menu below its
responsive breakpoint, so a dropdown buys nothing for narrow screens --- the
only question worth asking is whether the *desktop* bar has room.

- **Do:** list each page as its own top-level navbar entry when the bar has
  room for them.
- **Do:** shorten an item's `text` before reaching for a dropdown menu.
- **Don't:** collapse a handful of short page names into a dropdown "for
  tidiness" when a flat bar would still fit.
- **Don't:** treat a long page `title` as a reason to hide the page in a
  menu --- change the navbar `text` instead.

(User question, 2026-09-28: "since mds only has 'home' and 'notes' in the
menu bar, why not list each page of notes individually in the menu bar
instead of the notes drop down?
shouldn't we only use drop downs when the menu bar would be too cluttered
otherwise?"
Answer: yes --- see `Morrison-Lab/mds`'s `_quarto-website.yml`, whose
`navbar.left` renders as "Home | Notes" with a dropdown arrow, hiding six
short page names --- Notation, Proof Writing, Algebra, Calculus, Linear
Algebra, Vector Calculus --- behind a menu that this section's test would
keep at the top level instead.)

## Page scope

The test above also runs in reverse, on a page rather than on a section
within it: a title, or a table of contents, can signal that a page is
carrying two topics rather than one --- a grouping that never earned its
place because it should not exist at all.

Length alone is a weak signal.
A long title naming one concept ("Maximum Likelihood Inference") is fine,
and near-synonyms joined by "and" ("Exploratory and Descriptive Methods")
call for a shorter title, not a split.
Three signals are reliable instead:

- **A title joining two nouns with "and", where neither part depends on the
  other.**
  "Key Distributions and the CLT" names two topics that do not need each
  other.
  "Variance and Covariance" is one topic under a compound name, because
  $\mathrm{Var}(X) = \mathrm{Cov}(X, X)$ --- the second term is a special
  case of the first, not an independent one.
- **A vague catch-all title**, such as "Basic Statistical Methods", that
  names no specific concept a reader could look up.
- **A table of contents with many top-level sections that do not build on
  each other** --- each section standing alone rather than the later ones
  depending on the earlier ones.

Splitting a page adds a navbar entry, so re-apply the navigation test above
after a split: past what a flat bar can hold, group the new pages by topic or
move them to a sidebar rather than defaulting straight to a dropdown.
Where another site links to the page as a submodule, its `#id` anchors move
with the content that carries them, so every cross-page and cross-repo link
into the split page needs updating, not just the navbar entry.

- **Do:** split a page whose title joins two independent nouns with "and",
  or whose title is a vague catch-all, or whose sections do not build on
  each other.
- **Do:** re-check the navbar test above after a split, rather than
  defaulting to a dropdown for the new pages.
- **Don't:** split a page merely because its title or table of contents is
  long --- check for independence, vagueness, or non-building sections
  first.
- **Don't:** rename or move a page's `#id` anchors during a split without
  updating every link, cross-repo included, that points at them.

(User question, 2026-09-28: "are long titles an indication that a page
might be better split into two topics?"
Answer: length is a weak signal; the three signals above are the reliable
ones.)
