When reviewing code or prose --- including mathematical content (derivations,
proofs, restated formulas) --- check for redundant content that could be
consolidated, and question it rather than silently accepting duplication.
Redundancy is doubly costly: more to read, and more to keep in sync when one
copy changes and the other doesn't.

**The litmus test: only flag content as redundant when consolidating it would
lose nothing.** If removing one copy would drop a case, an edge condition, a
generality, or a distinct meaning, it is not redundant --- it's merely similar.
Flagging similar-but-distinct content as a duplicate recommends a merge that
loses something; that's a worse outcome than leaving the duplication alone.
Question the content, don't assume either way: check what each copy actually
covers before deciding whether one subsumes the other.

## What this looks like in each domain

- **Prose.** The same claim or explanation restated in two places --- a README
  section and a doc page saying the same thing in different words, two
  paragraphs in the same document making the same point --- that could become
  one statement plus a cross-reference to it.
- **Math.** A general formula and a separately derived special case that the
  general formula already covers; the same derivation carried out twice in
  different notation with no added insight; a theorem re-proved in place
  instead of cited. Consolidating here means stating the general result once
  and deriving the special case from it (or citing it), not deleting the
  special case's meaning if it actually adds a constraint the general form
  doesn't capture.
- **Code.** Duplicated logic across functions, files, or configuration that
  could be extracted into one shared unit without narrowing what either call
  site needs. Two functions that look alike but branch on genuinely different
  conditions are not this case --- extracting a shared unit there would need a
  parameter or flag for the branch, and that's a judgment call, not an
  automatic win.

## Applies at the scale of what's in front of you

This is a review-time check on the document or diff already being read, not a
mandate to sweep an entire corpus for duplication --- that's a separate,
larger job with its own tooling. When the redundancy found here turns out to
span more than the current diff (the same fact duplicated across many files,
the same procedure copied into several unrelated places), say so and route it
to `find-overlap` (or `consolidate-skills`/`consolidate-memory` for
skills/memories), rather than trying to fix everything found along the way in
the current review.

## Use the overlap instrument, not literal grep

A redundancy finding is exactly where phrase grep is most tempting, and where
it is least trustworthy.
This corpus uses semantic line breaks and inline markup, so a copied claim can
span a newline or differ only by backticks while still being the same prose.
Use the existing overlap instrument for the broad sweep:
`scripts/find-near-duplicates.py` ranks corpus pairs by normalized word
shingles and reports the number of units and pairs it examined.
Its default target set and top-pair threshold are tuned for near-duplicate
files, not for proving that a short copied run between long `shared/` files is
absent.
So treat it as the reusable starting point and corpus-wide reading list, not as
a clean-result certificate for a narrow review finding.
When the question is a narrower single-file audit, use the same algorithmic
shape with a run-reporting matcher:
normalize whitespace and markup on both sides, lower-case, compare word
n-grams, and report the examined scope and every overlapping run.

- **Do:** run `scripts/find-near-duplicates.py` for the broad candidate list,
  or run an equivalent normalized n-gram matcher that reports overlapping runs
  for the files under review.
- **Do:** report the examined files, pairs, or runs alongside any overlap found,
  then read the overlapping bodies before deciding whether consolidation loses
  nothing.
- **Don't:** use literal grep as evidence that no matching prose exists in a
  semantic-line-break corpus.
- **Don't:** treat `scripts/find-near-duplicates.py`'s default no-finding result
  as proof a short copied passage is absent from long shared files.
- **Don't:** treat a high shingle score as the disposition; it is a pointer to
  read, not a duplicate verdict.

(Morrison-Lab/ai-config#969, 2026-08-01: after review flagged one uncited
copy between `batch-merge-and-resolve.md` and `sync-with-main.md`, a
10-gram shingle sweep normalized backticks, asterisks, underscores, whitespace,
and case across `shared/workflow/`, `shared/writing/`, and
`shared/principles/`.
It found four overlapping runs: the flagged generalization, a second uncited
copy about `markdownlint`'s `blanks-around-lists` explanation that review had
missed, and two already-cited overlaps.
A literal grep for the `blanks-around-lists` wording in `sync-with-main.md`
returned nothing because the phrase crossed a semantic line break.)
