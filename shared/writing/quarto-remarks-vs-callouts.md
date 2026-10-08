# Quarto: remarks for commentary on the math, callouts for guidance to the reader

In lecture notes where every block sits in a typed div,
a reader should be able to tell from the box alone
whether a block is part of the mathematical development
or a sign by the road.
A remark and a callout look similar and are easy to swap,
so choose by what the content is about.
That every typed block belongs in a div in the first place
is [`quarto-divs-for-typed-content.md`](quarto-divs-for-typed-content.md)'s rule;
this file decides between two of the boxes.

## Which one

- **Remark** (`::: {.remark .notes}` for commentary kept off the slides,
  `::: remark` for commentary shown on them;
  a long paragraph gets a short `::: remark` and its detail in a `::: notes` div after it,
  per [`lecture-conventions`](lecture-conventions.md)):
  commentary on the mathematical content,
  attached to the definition, result or example just before it.
  Typical content:
  - synonyms and alternative notation
  - history and naming
  - scope limits ("the rigorous version also needs ...")
  - motivation ("this matters because ...")
  - pointers to other sources

  The test: the text is about the math,
  and it belongs to the item above it.
- **Callout** (`.callout-*`):
  guidance addressed to the reader
  that is not part of the mathematical development.
  - `.callout-warning` or `.callout-caution`: a common mistake or trap
  - `.callout-tip`: study or software advice, such as an R idiom
  - `.callout-important` or `.callout-note`:
    course logistics, or a note about the document itself
- **Collapsible callout** (`collapse="true"`):
  optional material a reader may skip,
  such as a long digression or an advanced aside.
  Proofs and solutions already fold through their own configuration.

A remark is never a container:
no theorem-type div goes inside it
(see `skills/quarto-authoring/references/divs-and-spans.md`).
A claim that needs a proof is a result div, not a remark;
a concrete instance is an example div.

- **Do:** put "Other sources write $A^c$ for $\neg A$" in a remark after the definition.
- **Do:** put "R's `var()` divides by $n - 1$, not $n$" in a `.callout-tip`.
- **Don't:** put a synonym or a historical note in a `.callout-note`.
- **Don't:** put a result, with or without its proof, in a remark.

## Style remarks like definitions

A remark is read alongside the definitions and results around it,
so it should look like them:
a minimal callout with only its colored left border,
no shaded title band (what the user called the "color bar"),
and no fold toggle.
With the `callouty-theorem` extension, the `remark` entry matches `def`:

```yaml
callouty-theorem:
  remark:
    override-title: false
    callout:
      type: remark
      appearance: minimal
```

`override-title: false` leaves the inline "*Remark*." label
as the only heading.
With `override-title: true`, the same label is repeated under a separate title band.
Keep a distinct `custom-callout` color for `remark`,
so remarks stay distinguishable from definitions.
The `qwt` template carries this configuration;
the lab's Quarto sites adopted it in Morrison-Lab/pds#29 and the matching PRs.

(Directives from the user, 2026-09-28:
"let's style remarks like definitions (not foldable, no color bar)?",
"(across all our quarto repos?)",
and "and when should we use remarks vs callouts?",
the last answered with "dyatb" (sic: the `daytb` keyword) to the proposal above.)
