# Quarto: put typed content in a div or callout wherever one fits

In Quarto lecture notes, books, and sites,
put every block of content that has a type into a div or callout of that type.
The box tells the reader what kind of thing they are reading
before they read it:
a reader skimming for the definition, the result, or the warning
can find it by its frame,
and a reader working through an argument can tell
the development from the asides.
Plain running prose is what is left over:
the connective narrative between typed blocks.

The rule applies in every repository and project with Quarto content,
not only the one where it was first stated.

## What gets a div

Use the matching construct for each kind of content,
and check every category rather than stopping at definitions.

- **Definitions**: `::: {#def-...}`.
  [`informal-definitions.md`](informal-definitions.md) is how a definition
  left in running prose is found and converted.
- **Theorems and other results**: `#thm-`, `#lem-`, `#cor-`, `#prp-`, `#cnj-`.
  A claim the text goes on to rely on is a result, even when it is stated casually.
- **Proofs**: `::: proof`, immediately after the result it proves.
- **Examples**: `#exm-`, after the definition or result they illustrate.
- **Exercises and their solutions**: `#exr-` and the repository's solution div
  (`::: solution`, or the `.sol` class that
  [`Morrison-Lab/gha`'s `student-qmd`](https://github.com/Morrison-Lab/gha/tree/main/student-qmd)
  removes from student copies).
- **Commentary on the math, warnings, hints and tips, notes, and optional material**:
  a remark or the matching callout type,
  chosen per [`quarto-remarks-vs-callouts.md`](quarto-remarks-vs-callouts.md).
- **Figures and tables**: `::: {#fig-...}` and `::: {#tbl-...}`,
  per [`quarto-figure-captions.md`](quarto-figure-captions.md).

## When no category fits, make one

A recurring kind of content with no matching category gets its own
div class or callout type, rather than being left as plain prose.
Examples are a "notation" box, a "key takeaway" summary,
a "connection to the book" pointer in notes that parallel a textbook,
or a "data" box describing a dataset's variables.

- Define it once in the project config, with its own color,
  so it is distinguishable from the existing types.
  What the config needs depends on the kind of type:
  - A **callout type** used as `::: {.callout-<type>}` needs a `custom-callout` entry
    (from the `coatless-quarto/custom-callout` extension).
  - A **theorem-like div** (framed like a definition)
    also needs a `callouty-theorem` entry,
    the way `Morrison-Lab/psw`'s `_quarto-website.yml` configures `remark`, `proof`, and `solution`.
  - A **plain div class** (`::: notation`) gets no frame from either extension,
    so it needs its own CSS rule.
- Style it in revealjs as well as HTML,
  per [`quarto-revealjs-div-styling.md`](quarto-revealjs-div-styling.md).
- Use it consistently: once the type exists,
  every block of that kind gets it.
- When the same new type would serve several repositories,
  add it to the shared templates
  ([`qwt`](https://github.com/Morrison-Lab/qwt),
  [`qbt`](https://github.com/Morrison-Lab/qbt),
  [`qmt`](https://github.com/Morrison-Lab/qmt))
  rather than to one site.

## Limits

- **Don't nest theorem-type divs.**
  A definition does not go inside a theorem, and no theorem-type div goes inside a remark;
  see [`divs-and-spans.md`](../../skills/quarto-authoring/references/divs-and-spans.md).
  Layout wrappers and callouts may still contain them.
  Two typed blocks sit side by side.
- **Don't box the narrative.**
  Prose that connects one typed block to the next,
  or that introduces a section, is not a typed block.
  The tie-breaker: a sentence about one specific block
  (its motivation, a synonym, a caveat) is a remark or callout attached to that block;
  a sentence that joins blocks or opens a section is narrative.
  A div around every paragraph makes the frames meaningless.
- **One type per box.**
  A block that mixes a definition with a warning about it
  becomes two blocks: the definition div, then the callout.

## Checking a page

When writing or reviewing a page, read each paragraph
and ask which category it belongs to.
A paragraph that states a definition, a result, a proof, an example, an exercise,
a warning, a hint, or a note, and is not already in the matching div, is a finding.
A paragraph that is a recurring kind with no category is a finding too:
the fix is a new custom type, per the section above.

- **Do:** put "A common mistake is to condition on a collider" in a `.callout-warning`.
- **Do:** put a three-line proof in a `::: proof` div, however short it is.
- **Do:** create a custom callout type for a recurring kind of block no category covers.
- **Don't:** convert a definition to a div and leave the result, the example,
  and the warning beside it in plain prose.
- **Don't:** wrap connective narrative in a div just to have one.

(Directive from the user, 2026-10-02:
"we want to put content into divs wherever feasible;
the div structure helps with reading",
"(not just definitions;
also theorems and other theoretic results, proofs, examples,
exercises, warnings, hints and tips, etc - everything that one of our div or callout
categories applies to, and everything you can think to create a custom callout or div for",
and "and this guidance applies to all our projects and repos, not just this one".
Tracked in Morrison-Lab/ai-config#4242.)
