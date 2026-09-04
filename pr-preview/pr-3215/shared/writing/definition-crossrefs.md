When reviewing prose that defines technical terms or named results via
formal cross-reference divs --- Quarto's theorem-like div syntax
(`::: {#def-...}`, `{#thm-...}`, `{#lem-...}`, `{#cor-...}`, `{#prp-...}`,
`{#cnj-...}`, `{#exm-...}`, `{#exr-...}`) or an equivalent
glossary/definition-list convention --- check each of the following for
every mention:

- **Hyperlinked on first mention.** The first place a technical term or
  named result appears in running prose should link to the div that
  defines or states it --- a Quarto crossref (`@def-token-budget`,
  `@thm-cauchy-schwarz`) or an explicit markdown link to the div's anchor.
  A bare mention of a term the reader hasn't been given a definition for
  forces them to search instead of click.
- **No hand-written type word in front of the crossref.**
  Quarto emits the type name as part of a theorem-family crossref, so
  `@def-hessian` already renders as "Definition 5".
  Writing `Definition @def-hessian` therefore renders as
  "Definition Definition 5", and the doubling hits every member of the
  family: `Proposition @prp-x` renders as "Proposition Proposition 4",
  `Theorem @thm-x` as "Theorem Theorem 1".
  Write the bare `@def-hessian` and let Quarto supply the word.
  It renders capitalized, so a parenthesized or sentence-initial mention
  reads correctly with no prefix of your own --- `(@def-hessian)` renders
  as "(Definition 5)", and `of @prp-x` as "of Proposition 4".
- **No forward references.** The definition/theorem/lemma/etc. div itself
  must appear **before** its first mention in reading order --- earlier in
  the same document, not later. A crossref pointing at a div the reader
  hasn't reached yet is a forward reference.

Scope note: "same document" means the single rendered file this checklist
runs against. In a multi-file Quarto book, a term defined in a later
chapter and referenced from an earlier one is a forward reference from the
reader's perspective too, but checking reading order across chapter files
is out of scope here --- flag that case manually when reviewing a book-level
diff.

## What to check

- For each technical term or named result mentioned in the prose, find its
  defining div (if one exists) and confirm the first mention is a working
  crossref/link to it, not bare text.
- For each definition/theorem/etc. div, confirm it precedes --- in document
  reading order --- every place that references it, whether a prose mention
  or a crossref used elsewhere in the same document.
- A term or result mentioned but never defined anywhere in the document is
  a separate gap from ordering: flag it as missing a definition entirely,
  not just as a forward reference. If the term actually *was* stated with
  definitional precision somewhere in the prose --- just not inside a
  formal div --- that's [`informal-definitions.md`](informal-definitions.md)'s
  case specifically, not this one.
- Grep the source for a type word immediately preceding a theorem-family
  crossref, which is the whole of the doubling check and needs no
  judgment:

  ```bash
  grep -nEi '(definition|theorem|lemma|corollary|proposition|conjecture|example|exercise) +@(def|thm|lem|cor|prp|cnj|exm|exr)-' <file>.qmd
  ```

  Derive the site list rather than fixing the flagged line, since the habit
  produces the same collision at every mention.

## What to report

For each violation, name the term or result, the mention's location, and
one of:

- **Missing crossref** --- the mention is bare text; add a link to the
  defining div.
- **Forward reference** --- the div is at `<location>`, after the mention
  at `<location>`; move the div earlier, or restructure so the definition
  precedes its use.
- **Undefined term** --- the term is mentioned but no div defines it
  anywhere in the document; add the missing definition.
- **Doubled type word** --- the mention writes the type name in front of a
  crossref that already supplies it; drop the hand-written word.

## Relationship to other checks

- **[`informal-definitions.md`](informal-definitions.md)** --- runs before
  this check, conceptually: it catches a concept stated with definitional
  precision that never became a formal div at all (or rides along inside a
  *different* concept's div), which is exactly the "undefined term" case
  above when the "definition" is sitting in plain prose rather than
  missing outright.
- **[`forward-references.md`](forward-references.md)** --- the general case
  of this same problem: any plain-text forward-pointing phrase ("below",
  "later", "in the following section") about any kind of content, not just
  a formal definition/theorem div. That check's grep-for-directional-word
  heuristic won't catch a bare `@def-x` crossref with no signpost word at
  all --- this check's direct div-position comparison is what catches that
  case. Run both on a diff that touches definitions.
- **[`check-rendered-refs`](../../skills/check-rendered-refs/SKILL.md)**
  (`crr`) is a post-render check: does `@def-x` resolve at all, without
  leaking `?@def-x` or `**key?**` into the built HTML. This check runs
  earlier, on the source prose itself: even a crossref that will resolve
  cleanly can still target the wrong spot (no link at all) or point
  backward at content that hasn't appeared yet.
- **[`challenge-ambiguous-terminology.md`](../workflow/challenge-ambiguous-terminology.md)**
  catches terms whose *meaning* is unresolved; this check assumes the
  meaning is fine and instead verifies the *link and its ordering* --- a
  resolved term can still be unlinked or defined too late.

## The doubling survives every check that already runs

The linking and ordering checks above are decidable from the source: a
mention is linked or it is not, and a div precedes a mention or it does not.
The doubled type word is decidable from the source too --- the grep above
settles it outright --- but only for a reader who already knows to look.
`Definition @def-hessian` is a well-formed crossref that resolves, numbers
correctly, and leaks no `?@` marker, so every check that asks whether a
reference *worked* reports clean, and the defect shows up only on the page.

That is why it survives a review round rather than being caught in one.
An automated reviewer reads the diff, and the diff shows a sentence that
looks like ordinary prose introducing a reference.

- **Do:** write the bare `@def-x` and let Quarto emit the type name.
- **Do:** read the rendered page, or run the grep above over the source,
  before calling a crossref pass clean.
- **Don't:** write `Definition @def-x`, `Proposition @prp-x`, or
  `Theorem @thm-x` --- Quarto supplies the word, so yours doubles it.
- **Don't:** read a clean `check-rendered-refs` scan as covering this; that
  scan answers whether the reference resolved, and a doubled type word is a
  reference that resolved perfectly.

(`UCD-SERG/serocalculator`
[#654](https://github.com/UCD-SERG/serocalculator/pull/654), 2026-08-08/09: a
methodology vignette formalizing statistical definitions into theorem-style
divs wrote the type word in front of 25 crossrefs, so the rendered page read
"Definition Definition 5", "Proposition Proposition 4", and "Theorem Theorem
1".
Two automated review rounds came back clean over them, because the source is
well formed and every reference resolved.
Fixed by dropping the hand-written word at all 25 sites.)
