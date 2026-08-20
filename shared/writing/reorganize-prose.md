When writing or editing prose, rearranging is part of the edit, not a separate
permission to seek.
A section, subsection, paragraph, or sentence may move --- within the document
you were asked to touch, and in a multi-document repo (a website, a book, a
manuscript, a docs site), **across** documents --- whenever moving it makes the
prose you are writing more straightforward or removes a defect that staying
put would leave in place.

This is the standing case for the remedy several review-side rules already
prefer over a local patch.
[`forward-references.md`](forward-references.md) names reordering "the strong
fix" for a forward-pointing phrase, ahead of rewording it into a working link.
[`challenge-redundant-content.md`](../workflow/challenge-redundant-content.md)
asks whether two copies could consolidate into one.
Related content stranded across distant sections or distant files is the
third shape: nothing points at it as broken, but a reader assembling the full
picture has to hold pieces from several places in mind at once, which a single
reordering pass can fix outright.

## What licenses a move

Three motivating cases, and the list is illustrative rather than exhaustive:

- **A forward reference.** The content a sentence points ahead to can move
  earlier instead of the sentence being reworded around a dangling pointer.
- **Duplicate content.** Two passages saying the same thing can collapse to
  one, with the surviving copy placed wherever it is first needed.
- **Related content split across distant locations.** A concept explained in
  one section and used three sections (or three files) away reads better with
  the explanation moved next to its first real use, or with both pulled
  together under one heading.

## Cross-document scope

In a multi-document repo, the same three cases can span files rather than
sections: a Quarto book's chapter, a docs site's page, a manuscript's section.
Content drafted in the file that happened to be open is not anchored there by
that fact alone --- if it is more at home in a different document, moving it
there is in scope for the same edit, not a separate restructuring project to
propose first.

## What a move has to preserve

Relocating prose is authorship, not a no-op, for exactly the reason
[`ascii-punctuation-in-source.md`](../coding/ascii-punctuation-in-source.md)
gives for a section moved between files: "the diff cannot tell a move from an
authoring pass, and neither can a reviewer." Everything that rule and its
neighbors already require of moved prose still applies here; this fragment
grants the move, it does not exempt it from what a move costs.

- **Self-references go stale.** "This section", "as noted above", "earlier in
  this file" are relative to where the text used to live.
  [`forward-references.md`](forward-references.md)'s "Moving prose makes
  self-references stale" section is the sweep to run --- grep the moved block
  (and, for a cross-file move, the survivor left behind) for locative and
  directional phrases, and re-point or delete every one that no longer
  resolves.
  **A phrase grep only catches the instances that quote their target.**
  A reference can allude to a moved rule in its own words --- "the UMS rule
  above", naming no heading --- and a grep keyed on the target's wording
  finds nothing to match.
  Once a reviewer (or a self-sweep) has found more than one instance of this
  defect in a moved block, stop pattern-matching and read the block end to
  end, checking each `above`/`below`/`bullet`/`section`/`rule` reference's
  actual target by hand --- the site list for this defect class is derived by
  reading, not by grep, because it is defined by what a sentence refers to
  rather than by what string it contains.
  See [`address-every-comment.cases.md`](../workflow/address-every-comment.cases.md),
  "A defect whose surface form varies defeats a phrase grep", for the case
  this generalizes from --- a quoted-heading grep sweep still left two more
  rounds' worth of differently-worded instances for reviewers to find.
- **A downstream count or position reference can silently break**, even
  though you touched neither its sentence nor its file.
  [`forward-references.md`](forward-references.md)'s "Inserting prose makes a
  downstream back-reference stale" section covers the mechanism: content
  inserted or removed ahead of a count-based pointer ("the two sections
  above", "the previous chapter") changes what that pointer resolves to.
  Prefer naming a target over counting to it, in prose you touch either way.
- **Line-level checks are diff-scoped, so a moved line is a line you just
  wrote.**
  [`ascii-punctuation-in-source.md`](../coding/ascii-punctuation-in-source.md)
  and [`semantic-line-breaks.md`](semantic-line-breaks.md) both judge added
  lines, and a relocation adds every line it touches --- there is no
  grandfathering for content that merely changed address.
  Bring a moved block into compliance with both on the way, the same as any
  other line you add.
- **Referenced assets move with their content.**
  [`migrate-referenced-assets.md`](../workflow/migrate-referenced-assets.md)
  covers images, data files, and anything else a moved passage embeds by
  relative path --- grep for them and confirm each exists at the destination,
  since a missing local asset frequently degrades silently in HTML and fails
  loudly (and late) in a PDF render.
- **Prove nothing was lost, and nothing was gained by accident.**
  A whitespace- and markup-normalized word-level comparison between the
  pre-move and post-move text, run in both directions, is what
  [`ascii-punctuation-in-source.md`](../coding/ascii-punctuation-in-source.md)
  and [`fail-fast.md`](../principles/fail-fast.md)'s "third pattern direction"
  both point to for this: a one-sided "did anything go missing" diff cannot
  see a token the move itself introduced, such as a diff header or stray
  marker a mechanical extraction leaked into the result.

  **That proof cannot stand in for the self-reference sweep above, and it is
  the substitution to expect** --- the word comparison is the more rigorous
  of the two, it runs in both directions, and it returns a clean verdict, so
  having run it makes the softer-sounding grep feel already covered.
  It is not, and the reason is structural rather than a matter of thoroughness:
  a preservation check tests **membership** in the union of the results, while
  a pointer's correctness is a **relational** property of where its target sits
  relative to it.
  A split leaves both the pointer and its target present somewhere, so the
  comparison reports nothing lost --- correctly --- while every "see below"
  whose target went to the sibling file now resolves to nothing.
  The two checks are independent, and only one of them can see this.
- **A line's "pre-existing" status is a fact about a destination, not about a
  file.**
  A line that has sat in the source file for months is an **added** line in the
  file a split creates, so every line-level rule --- banned glyphs, one
  sentence per line, house punctuation --- applies to it there.
  The trap is that both halves of a split feel like the same file, so a scan
  run on the survivor, where the lines genuinely are pre-existing and
  genuinely are out of scope, reads as having covered the move.
  Scan each destination separately, and treat a relocated line by where it is
  landing rather than by where it has been.
- **A multi-document move can break navigation and cross-file crossrefs.**
  A Quarto sidebar, table of contents, or `_quarto.yml` entry that named the
  section by its old location may need updating, and a crossref id
  (`{#sec-...}`, `{#def-...}`) used from another file has to keep resolving
  after the move --- check with the project's own render or a link-check pass
  rather than assuming project-wide unique ids make this automatic.

## The sweep needs a trigger, and the split now has a mechanical one

Everything above says *what* a move has to preserve.
None of it says *when* to check, and
[`skill-checklists.md`](../workflow/skill-checklists.md) is explicit that a
checklist with no stated pause point is read only by whoever was already
careful.

That gap used to cost little, because relocating prose was an occasional and
deliberate act, prepared for by whoever chose it.
It is no longer.
`scripts/check-context-closure.py` enforces a 100,000-byte cap on every
non-root auto-loaded fragment, and it fails rather than warns, so a fragment
that grows past the line forces a `.cases.md` split on whoever happens to be
editing it that day.
The split now arrives as a red check mid-task rather than as a plan.

So the observable pause point is **the cap check failing**, and that check's
own remediation message names the sweep and the deriving command, so a mover
meets both at the moment the split is decided rather than having to recall a
rule in a different file.

**What earns the split this treatment is that no other instrument here can
see what it breaks.**
The bullet above notes that line-level checks are diff-scoped, so a moved
line is a line you just wrote.
The complement is the half that hides the defect: the thing that line
*refers to* is content that did **not** move, so it appears in the diff as
unchanged context or not at all.
A reviewer reading the diff closely therefore sees the pointer and never sees
what it points at, and `check-links.py` is no help either, since a positional
reference is prose rather than a link.

The remedy is unchanged and already written down --- fix each hit by naming
its referent, per
[`forward-references.md`](forward-references.md)'s "Sweep the general
directional pattern" section, rather than by flipping the direction or
repointing at the file the content stayed in.
A name survives the next reorganisation and a pointer survives only until the
file it names moves.
Note that this is the rule failing to *fire* rather than the rule being
incomplete, which is why the fix is a trigger rather than another statement
of it.

## Do and don't

- **Do:** move a section, paragraph, or sentence --- within a file or across
  files in a multi-document repo --- when doing so removes a forward
  reference, a duplicate, or a split between related content, as part of the
  prose edit already in front of you.
- **Do:** run the self-reference and back-reference sweeps, the line-level
  checks, the asset migration check, and a bidirectional content-preservation
  diff on anything you relocate.
- **Don't:** treat a section as anchored to its current file or position
  merely because that is where it was originally drafted.
- **Don't:** relocate content and stop at "the words are all still there
  somewhere" --- a move that breaks a self-reference, a count-based
  back-reference, or a cross-file crossref is a defect the move introduced,
  not a pre-existing one.
- **Do:** run the directional sweep over both the companion and the fragment
  when a cap breach forces a `.cases.md` split, before opening the PR ---
  the failing check is the pause point, not a topic to remember.
- **Do:** treat a single stranded reference a reviewer names as one member of
  a class, and derive the rest, per
  [`address-every-comment.md`](../workflow/address-every-comment.md).
- **Don't:** rely on reading the diff to surface a stranded reference --- the
  moved line is in the diff and the content it refers to is not.
- **Don't:** read a green `check-links.py` as covering this; the broken
  pointer is prose, so no link check can reach it.

## Relationship to other rules

- [`forward-references.md`](forward-references.md) is the specific case this
  fragment generalizes: its "reorder" remedy, its two staleness sections, and
  its roadmap exception all still apply --- read it for the mechanics.
- [`challenge-redundant-content.md`](../workflow/challenge-redundant-content.md)
  supplies the litmus test for whether two passages are duplicates worth
  consolidating in the first place, before this fragment's "where do they go
  once consolidated" question is even live.
- [`definition-crossrefs.md`](definition-crossrefs.md) is the formal-div
  version of "content split from its first use": a definition div that
  follows its own first mention is fixed by moving the div, exactly as this
  fragment licenses.
- [`migrate-referenced-assets.md`](../workflow/migrate-referenced-assets.md)
  is the asset-specific half of "what a move has to preserve," cited above.

(`Morrison-Lab/ai-config#1413`, merged 2026-08-13 as `65d8886d`: a cap-forced
split moved case records out of two fragments ---
`shared/workflow/ardi.md` 98,655 to 92,734 bytes, and
`shared/principles/fail-fast.md` 94,469 to 91,244 --- into their `.cases.md`
companions.
Review found one stranded positional reference, `the checks below` in
`ardi.cases.md`, whose Do/Don't list had stayed in `ardi.md`.
Deriving the class found two more in `fail-fast.cases.md`, both missed by the
reviewer's enumeration: `the rate-limit truncation above` and
`in both forms above`.
All three carried `above` or `below`, so
[`forward-references.md`](forward-references.md)'s general directional
pattern would have flagged every one of them as a candidate --- the sweep was
complete and was simply never run, which is the argument for attaching it to
the failing check rather than restating it.
Fixed in `fd5cd1a5` by naming each subject.
The two fragments sat at 92,734 and 91,244 bytes on `main` as of 2026-08-13,
against the 100,000-byte cap, so the same split recurs within days at the
growth rate that produced this one.)

(User directive, 2026-08-09: "when writing and editing prose, you can
rearrange sections (and subsections, paragraphs, sentences, etc) of the
larger document to improve the flow... in multi-document repos (for example
websites), you can also rearrange content across documents when helpful.")
