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

Worked-example case records for the rules below live in
[`forward-references.cases.md`](forward-references.cases.md), moved out of the auto-loaded context.

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

## Moving prose makes self-references stale

The same check fires after a file split or prose migration, even when the
reference was correct before the move.
Phrases like "this file", "the section below", "as noted above", and
"earlier in this" are relative to a source location, not to the concept being
moved.
A link checker cannot see them, because they are plain prose rather than
links.
A semantic-line-break or punctuation check cannot see them either, because the
sentence can be well formed and still point at content that stayed behind.

When moving a block between files or splitting a large memory file, grep the
moved block itself for locative self-references before committing.
For every hit, verify that the referenced content moved with it.
If it did not, replace the phrase with an explicit link or filename that stays
true after the split.
This is the prose-reference counterpart to
[`migrate-referenced-assets.md`](../workflow/migrate-referenced-assets.md):
there the thing that must move is an asset, while here it is the referent of a
self-reference.

- **Do:** scan moved prose for locative phrases such as `this file`, `above`,
  `below`, and `earlier in this`, then re-point each one after the move.
- **Do:** prefer an explicit file or section link over a relative phrase when
  the referenced content stayed in the source file.
- **Don't:** assume a self-reference survived because it was true before the
  split.
- **Don't:** rely on link checks for this class; the broken pointer is prose,
  not a link.

**Sweep the general directional pattern, not the literal phrases you expect.**
The self-review that verifies a move is where this check most often fails, and
it fails by grepping for the *specific* wording the mover happens to remember
--- `(below)`, `case below`, `per #N below` --- which is far narrower than the
ordinary `the X above` / `Y below` / `here` phrasing the real danglers wear.
Grep the general directional pattern instead, over both the moved content and
the prose left behind, since a stranded reference can sit on either side of the
split:

```bash
rg -niE '\b(above|below|here|earlier|later)\b|this (section|file)' <moved> <survivor>
```

Then classify each hit rather than trusting a zero count.
A hit that now points **across the split** --- at content that moved to a
different file --- is a dangling defect; fix it by naming the referent
explicitly --- name the target rather than counting to a position --- not by
flipping `above` to `below`.
A hit that stays **within its own block**, is **quoted** (prose describing the
very reference it quotes), or measures **elapsed time** ("minutes earlier", "a
round later") is correct and must be left.
The [`fix-forward-references`](../../skills/fix-forward-references/SKILL.md)
skill (alias `ffr`) runs exactly this sweep and is the right tool for it.

- **Do:** grep the general `\b(above|below|here|earlier|later)\b` pattern over
  both sides of a split, and classify each hit as cross-file (fix) or
  within-block/quoted/elapsed-time (leave).
- **Don't:** report "no dangling references" from a literal-phrase grep --- it
  is scoped to wording you already recalled, which is never where the misses
  are.
## Inserting prose makes a downstream back-reference stale

The section above covers the referrer *moving*.
The mirror case keeps the referrer still and changes what sits between it and
its target: you insert a section, and a **count-based back-reference** further
down --- "the two sections above", "the previous section", "as shown three
paragraphs up" --- now counts wrong.
Nothing about your insertion looks like it touched that later sentence, and it
did not; it changed the sentence's *referent* by displacing the sections it
counts.

This is the trigger [`sync-with-main.md`](../workflow/sync-with-main.md) names
for numbered subsections colliding at merge time --- "grep the file for any other place that names the
old numbering" --- but it fires during ordinary authoring, not just on a
merge, so an author inserting a section mid-file never thinks to consult a
merge-conflict rule.
It is also invisible to every mechanical check: a link checker sees no link, a
punctuation or line-break check sees a well-formed sentence, and the
directional-word grep above never fires --- its word list is exclusively
forward-pointing (`below`, `later`, `following`, ...), so a backward reference
like "above" is outside its alphabet regardless of whether the count is right.

So before landing an insertion, grep the file **below** the insertion point
for positional and count references, and re-verify each still resolves to what
it names.
The durable fix is to name the target sections rather than counting to them,
so the next insertion cannot silently invalidate the reference.

- **Do:** after inserting a section, grep the rest of the file for
  positional/count phrases (`sections above`, `the previous section`, `N
  paragraphs up`) and confirm each still counts correctly.
- **Do:** prefer naming the target ("the negative-control and incident-test
  sections") over counting to it, so an insertion cannot break the count.
- **Don't:** assume a back-reference survived your insertion because it was
  correct before and you did not touch its sentence.
- **Don't:** rely on the directional-word grep above to catch this --- its word
  list is exclusively forward-pointing and never sees a backward reference
  like "above" in the first place.

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
