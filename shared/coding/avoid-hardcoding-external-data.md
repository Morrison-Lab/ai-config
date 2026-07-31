Avoid hard-coding data that already has a reliable external source of truth ---
a version number, a package list, a dependency's release date, a set of
downstream consumers, a schema, an enum's valid values. Read or generate it
from that source instead of copying a snapshot into the codebase:

- **Versions and pins.** Don't retype a dependency's version in prose or a
  second config file when a lockfile, `DESCRIPTION`, or manifest already
  states it --- reference that file, or generate the mention from it.
- **Generated lists.** A list of consumers, plugins, or registered items that
  the source system can enumerate (an API, a directory scan, a registry)
  should be produced by querying that system, not maintained by hand
  alongside it.
- **Cross-file duplication.** When the same fact must appear in two places
  (a usage example and a reference doc, a schema and its example), generate
  the second from the first, or have CI check they agree, rather than
  trusting two hand-edited copies to stay in sync.

## Prose enumerations count, and they are the ones that rot unnoticed

The "generated lists" bullet reads as being about code, and the rule is
easiest to break in a sentence.
An enumeration written into documentation --- "the rules below (A, B, C,
...)" --- is a hand-maintained copy of a directory listing, and it has no
generator, no test, and no linter behind it.
Nothing fails when the directory grows; the sentence simply becomes wrong
and stays wrong, while still reading as authoritative.

When a prose list mirrors something the filesystem or an API already
enumerates, prefer a pointer to the source over the list: "every fragment
under `shared/coding/`" cannot drift, while a parenthetical naming seven of
them silently can.
Keep an explicit list only where the *selection* is the point --- a curated
subset, an ordering that matters --- and then say that it is a selection, so
a reader knows not to trust it as complete.

**Fixing a drifted list by refreshing it only resets the clock.**
The list will drift again on the next addition, by exactly the same
mechanism.
Replace it with the pointer instead, and treat "this needs updating again"
as the signal that it should not have been a list.
(ai-config#774, 2026-07-28: `CLAUDE.md`'s KISS section enumerated the
coding rules beneath it and had reached 7 of the 13 files then in
`shared/coding/`, having silently missed six additions.
The PR was adding four more.
Refreshing the parenthetical to 17 entries would have been wrong again
within weeks, so it became "every fragment under `shared/coding/`, indexed
by the principle it serves in the catalog above".)

This is conditioned on the external source being **reliably available** ---
don't add a network fetch or a fragile dependency where a static value would
do. A constant that has no external owner (a magic number intrinsic to the
algorithm, a default chosen by this project) is not "hard-coded data" in this
sense --- it is just a value. The target is duplicated *ownership* of a fact:
if updating the external source should have updated this value too, and
didn't, that is the bug this guidance prevents.

### A count in the prose above a block is the same duplicate, one line away

The section above describes a list mirroring something *elsewhere* --- a
directory the sentence cannot see, drifting over weeks as files land.
The tighter case is a count of the items in the block directly beneath it:
"Three reads settle it", above three commands.
Same defect, since the count is a hand-maintained copy of something the block
already enumerates.
What differs is who invalidates it and when.
Nobody adding a file to some other directory breaks this one.
**You** break it, in the same review round, by fixing the block the count
describes.

Two things keep it out of view at exactly that moment.

The count was **correct when written**, so it was never a mistake to notice
and carry forward --- it became false only when the block gained a command.
And a review finding points at the block, so correcting the block feels like
the whole action.
The sentence introducing it is not part of what the reviewer flagged, so
nothing prompts a re-read.

The second is that adjacency reads as safe.
A count of items in a distant file is obviously fragile, and that visible
fragility is what makes anyone check it.
A count one line above the thing it counts feels like it cannot drift, since
both are on the screen at once --- which is precisely why nobody looks at the
prose while editing the block.

**The remedy above does not transfer, so do not reach for it.**
That section says to replace the list with a pointer to its source, and a
count has no source to point at: "every fragment under `shared/coding/`"
works because a directory can be named, whereas the number three cannot be
delegated to anything.
Two options that do work:

- **Drop the count.**
  The block is immediately below, so "These reads settle it" loses nothing a
  reader could not get by looking down.
  This is the better answer whenever the number carries no argument.
- **Re-derive it mechanically before pushing**, when the number is doing real
  work in the sentence.
  One command decides it exactly, which makes this an
  [`algorithmatize-checks`](../workflow/algorithmatize-checks.md) case rather
  than something to settle by recollection:

```bash
grep -c '^git ' shared/workflow/claim-pr.md
```

Count list items, bullets, or numbered steps the same way for a block of
those.

- **Do:** re-read the sentence introducing a block whenever a review finding
  changes what is in that block.
- **Do:** delete a count the neighbouring block already states, and re-derive
  by command any count you keep.
- **Don't:** treat a fix to the block as complete because the finding named
  only the block.
- **Don't:** read adjacency as protection --- the nearest duplicate is the one
  your own edit falsifies first.

(Morrison-Lab/ai-config#975, 2026-07-31: a new section in
`shared/workflow/claim-pr.md` opened "Three reads settle it before you touch
anything:" above a fenced block of `git` commands.
Review round 1 correctly found the block needed a fourth command, and that
fix is what made the preamble false.
Round 2 flagged the stale count, fixed in `42214b0` as "Four reads settle it
before you touch anything:".)
