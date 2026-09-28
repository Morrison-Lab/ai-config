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
may stand alone at the content-section level --- `## References`, a sibling
of the page's other `##` sections, never a `#` --- even though it never gets
a sibling of its own.
It closes the document instead of organizing it, so the "needs a sibling"
test does not apply to it.
This exception licenses a `##` at that level with no sibling; it says nothing
about the `# References` shape the paragraph above already rules out, which
stays wrong regardless of where in the document it sits.

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
  the old text instead of from a stable id.

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
Answer: yes --- as of 2026-09-28, before `Morrison-Lab/mds`#11's commit
`c21197a` fixed it, `_algebra.qmd` was exactly this shape: a lone
`## Elementary Algebra` wrapping every `### Equalities`, `### Inequalities`,
and so on.
Read this section's worked example as that history, not as mds's current
state.)

## Site navigation

The same test applies one level up, to a site's navbar instead of a page's
headings, and it is a test on **each** dropdown, not on whether the navbar
has any.
A dropdown is a grouping level, so it needs a sibling the same way a heading
does: a dropdown grouping several pages into a real topical section is fine,
and so are several such dropdowns side by side.
What fails the test is a dropdown with no sibling of its own kind --- a navbar
whose only items are "Home" plus one catch-all dropdown ("Notes",
"Chapters"), where that single dropdown groups *everything else on the
site* and divides nothing.
That is the lone-wrapper-heading defect one level up: a grouping level with
exactly one member.

It is not a fit problem, so "would a flat bar fit them all" is the wrong
question to ask about it.
A flat navbar, several topical dropdowns, and a sidebar are all fine
structures on their own terms; the defect is specifically a menu bar whose
*only* items are "Home" and a single everything-else dropdown, whatever the
reason given for it.

Prefer shortening a navbar item's label over reaching for a dropdown at all:
a navbar item's `text` can differ from the page's `title`, so a long page
title is never by itself a reason to hide a page behind a menu.

- **Do:** group pages into dropdowns that divide the site into real topical
  sections, with more than one such dropdown (or dropdowns alongside flat
  items) where that reflects the site's actual structure.
- **Do:** shorten an item's `text` before reaching for a dropdown menu.
- **Don't:** reduce the navbar to "Home" plus a single catch-all dropdown
  ("Notes", "Chapters") that groups everything else on the site --- that
  dropdown has no sibling and divides nothing, the same defect as a lone
  wrapper heading.
- **Don't:** treat a long page `title` as a reason to hide the page in a
  menu --- change the navbar `text` instead.

(User question, 2026-09-28: "since mds only has 'home' and 'notes' in the
menu bar, why not list each page of notes individually in the menu bar
instead of the notes drop down?
shouldn't we only use drop downs when the menu bar would be too cluttered
otherwise?"
Answer, refined after a follow-up clarification: "it's also ok to group
pages into sections with drop-down menus; we just don't want the only menu
bar items to be 'home' and 'chapters' etc" --- as of 2026-09-28, before
`Morrison-Lab/mds`#11's commit `18734ee` fixed it, `_quarto-website.yml`'s
`navbar.left` rendered as "Home | Notes" with a dropdown arrow, hiding six
page names --- Notation, Proof Writing, Algebra, Calculus, Linear Algebra,
Vector Calculus --- behind the site's only dropdown, exactly the one-member
grouping this section's test rejects.
Read this as that history, not as mds's current state.)

The same grouping test carries over to a sidebar's collapsible sections, not
just a navbar's dropdowns: group pages into a section only where the site's
topics actually fall into several such groups, and never collapse a sidebar
to a single catch-all section, the same defect a lone catch-all navbar
dropdown has.
A site can use dropdowns, a sidebar, or both for the same grouping --- the
test is about whether the grouping divides something, not about which
control renders it.
Groups, and the items within them, follow the same natural topic progression
as the rest of this section.

Showing the same grouping in both a sidebar and navbar dropdowns is fine, but
the two lists then have to be kept in step by hand --- Quarto does not derive
one from the other --- so mark each with a comment pointing at its
counterpart, for example `# keep in sync with navbar.left` beside the
sidebar's YAML and `# keep in sync with the sidebar` beside the navbar's, so
an edit to one is not missed in the other.

- **Do:** use a dropdown, a collapsible sidebar section, or both, wherever
  the site's pages fall into a real topical group, ordered by the same
  topic progression as the rest of the site.
- **Do:** mark a navbar dropdown and a sidebar section that mirror the same
  grouping with a comment pointing at each other, so an edit to one is not
  missed in the other.
- **Don't:** collapse a sidebar to a single catch-all section --- the same
  defect a single catch-all navbar dropdown has.
- **Don't:** let a mirrored sidebar section and navbar dropdown drift apart
  silently.

(User clarification, 2026-09-28: "if there's natural grouping, you can use
drop-downs to group them, both in sidebars and menu bars.")

### Order

Grouping is not the only question a navbar or sidebar raises --- once the
items and the groups are settled, their order is a separate question, and it
has the same answer as the rest of this document: derive it, don't inherit
it.
Menu and sidebar items, and the groups themselves, follow the natural
progression of topics, so each item comes after what it builds on.
Find that progression from the dependencies among the pages --- which page's
content a reader needs before another page's makes sense --- rather than from
the order the pages were created in or from the alphabet, neither of which
tracks what a reader needs first.

- **Do:** derive a menu's order, item by item and group by group, from the
  dependencies among the pages it lists, so each item comes after the
  content it builds on.
- **Don't:** order menu items by creation date or alphabetically and call
  that the natural order --- neither tracks what a reader needs first.

(Repo owner directive, 2026-09-28: "the ordering of items in the menu bars
should follow the natural progression of topics as much as possible."
Example, inferred: `Morrison-Lab/mds`'s navbar placed "Proof Writing" second
--- ahead of "Algebra", "Calculus", "Linear Algebra", and "Vector Calculus"
--- although the page's own worked example derives a linear-algebra result
(the hat matrix's idempotence) and links into `linear-algebra.qmd` for the
definitions and facts it uses, so a reader reached that example before the
page introducing the objects in it.
See `Morrison-Lab/mds`#13.)

## Page scope

The test above also runs in reverse, on a page instead of on a section
within it: a title, or a table of contents, can signal that a page is
carrying two topics instead of one --- a grouping that never earned its
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
  each other** --- each section stands alone; none of the later ones
  depends on an earlier one.

Splitting a page adds a navbar entry, so re-apply the navigation test above
after a split: group the new pages into topical dropdowns where that fits
the site's structure, and avoid reducing the navbar to a single catch-all
dropdown the way the test above rules out.
Where another site links to the page as a submodule, its `#id` anchors move
with the content that carries them, so every cross-page and cross-repo link
into the split page needs updating, not just the navbar entry.

- **Do:** split a page whose title joins two independent nouns with "and",
  or whose title is a vague catch-all, or whose sections do not build on
  each other.
- **Do:** re-check the navbar test above after a split, instead of assuming
  the new pages need a dropdown of their own.
- **Don't:** split a page merely because its title or table of contents is
  long --- check for independence, vagueness, or non-building sections
  first.
- **Don't:** rename or move a page's `#id` anchors during a split without
  updating every link, cross-repo included, that points at them.

(User question, 2026-09-28: "are long titles an indication that a page
might be better split into two topics?"
Answer: length is a weak signal; the three signals above are the reliable
ones.)
