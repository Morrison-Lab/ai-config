A **forward reference** is any mention that points a reader ahead to
content they haven't reached yet --- a phrase like "as discussed below",
"in the following section", "we'll cover this later", or "as we'll see" ---
where the thing being pointed at genuinely comes later in reading order.
Good technical prose avoids these: they force the reader to hold an
unresolved pointer, and they're a common enough weakness that they're worth
a dedicated check, distinct from
[`definition-crossrefs.md`](definition-crossrefs.md)'s narrower check of
formal Quarto crossref-div ordering (`{#def-...}`, `{#thm-...}`, etc.) for
term and result definitions specifically. This fragment covers the general
case: **any** plain-text forward-pointing phrase, about **any** kind of
content (a section, a figure, a table, an argument, not just a formal
definition), in any prose --- READMEs, docs, papers, PR descriptions.

## The detection heuristic

The primary signal is the directional word itself --- below, later,
following, subsequently, further down, next (as in "the next section"),
afterward. Grep for these first; this is what actually catches the plain
examples above ("see below", "as discussed below", "we'll cover this
later", "in the following section") --- none of them name a section,
figure, or table explicitly, so a pattern that *requires* a paired
reference cue would miss all four:

```bash
rg -niE '\b(below|later|following|subsequently|further down|next|afterward)\b' <file>
```

A **stronger, higher-confidence subset**: a cross-reference or
named-content mention (`@sec-x`, "section", "figure", "table", "chapter")
paired with one of these words nearby is a self-declared forward
reference --- the author is explicitly telling the reader the target comes
later. Use this narrower pattern when the primary grep returns too many
idiom hits to triage one by one:

```bash
rg -niE '(@[a-z0-9_-]+|section|figure|table|chapter)[^.]{0,60}\b(below|later|following|subsequently|further down|next|afterward)\b' <file>
rg -niE '\b(below|later|following|subsequently|further down|next|afterward)\b[^.]{0,60}(@[a-z0-9_-]+|section|figure|table|chapter)' <file>
```

Treat every hit --- from either pattern --- as a **candidate**, not a
confirmed finding --- see the false positives below.

**Both patterns miss a whole class: an explicit numbered pointer inside a
sequential procedure.**
"per step 3", "see step 5", "as in step 2" carry no directional word at
all, so neither grep above fires --- yet in a numbered list the reader
follows in order, a pointer from step 2 to step 3 is exactly as unresolved
as an "as discussed below".
Add a pattern for it when the file contains an ordered procedure:

```bash
rg -niE '\b(per|see|as in|described in|from) (step|item|point) [0-9]+' <file>
```

The direction test is positional, not textual: compare the pointer's own
position to its target's.
A pointer from step 2 to step 3 is a forward reference; the same
`(step 3)` written in a section that *follows* step 3 --- an anti-patterns
list at the end of the document, say --- is a back-reference and fine.
Prefer deleting the pointer over rewording it: in a sequential procedure
the reader reaches the target anyway, so a step that states its own
mechanism in brief needs no cross-reference at all.
(ai-config#691: `ums`'s step 2 said "grep before writing, per step 3";
dropping the pointer left "grep before writing", which carries the
mechanism on its own, while the anti-patterns entry's own `(step 3)`
correctly stayed.)

## Confirming a hit

For each candidate, check two things:

1. **Is it actually a reference, not an idiom?** "Values below zero", "the
   below-threshold group", "below average" use "below" as a plain adjective
   or comparator, not a pointer to later content. Read the sentence; don't
   flag these.
2. **Does the target really come later?** Find what the phrase points at
   (a heading, a crossref target, a named figure/table). If it already
   precedes the mention, the wording is simply wrong (should say "above")
   but there's no forward-reference problem to fix structurally.

Only a hit that is (a) a genuine reference and (b) genuinely pointing
ahead is a forward reference to fix.

## Fixing a confirmed forward reference

Two options, in order of preference:

1. **Reorder.** Move the referenced content (the section, paragraph, div,
   figure, or table) earlier so it precedes the mention, then update the
   directional word ("below" → "above", or drop it if a working crossref
   link already carries the point). This is the strong fix: the reader
   never has to hold an unresolved pointer.
2. **Reword**, when reordering would break the document's narrative logic
   (e.g., a result genuinely depends on setup that must come first). Turn
   the vague pointer into a precise, working link (a real crossref or
   anchor) instead of a bare "below" --- this doesn't remove the forward
   reference, but at least lets the reader jump to it rather than search.
   Use this only when reordering is genuinely worse, not as a default
   shortcut.

## The roadmap exception

A deliberate scene-setting overview near the start of a document or
section ("this paper first covers X, then Y, then Z") is a conventional,
expected forward reference, not an error --- the reader isn't meant to
resolve it immediately, just to know what's coming. Scope this check to
places where the reader needs the pointed-at content *to understand the
current sentence*, not to a roadmap paragraph that's explicitly previewing
structure.

## Relationship to other checks

- **[`definition-crossrefs.md`](definition-crossrefs.md)** --- the special
  case of this same problem for formal term/result definitions via Quarto
  crossref divs. That check works by comparing div position to first
  mention directly; this one works by grepping for self-declared
  directional language. Run both: a definition can be forward-referenced
  without ever using the word "below" (a bare `@def-x` crossref with no
  signpost at all), which only `definition-crossrefs.md`'s ordering check
  catches.
- **[`informal-definitions.md`](informal-definitions.md)** --- a concept
  with no formal div of its own can't be crossref'd, which is exactly what
  pushes an author toward a forward-pointing phrase ("the definition
  below") instead of a working link in the first place. Fixing that
  check's findings often removes a forward reference for free.
- **[`challenge-ambiguous-terminology.md`](../workflow/challenge-ambiguous-terminology.md)**
  --- catches unclear terms; this check assumes the term is clear and
  instead verifies the reader has already been given whatever it's
  pointing at.
- **[`semantic-line-breaks.md`](semantic-line-breaks.md)** --- a sibling
  prose-quality check; both are the kind of finding worth raising as a
  suggestion during review of a prose diff.
