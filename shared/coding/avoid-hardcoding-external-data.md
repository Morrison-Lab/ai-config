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

**A softened count is still a pinned count.**
The rule that refreshing a drifted list only resets the clock has a
near-miss.
The move it does not rule out is replacing the figure with a vaguer version
of itself --- "on the order of 90K+ tokens across the ~60 files in it" in
place of "~74-92K tokens across 59 files".
Hedging acknowledges the imprecision and changes nothing about the mechanism,
so the substitution reads as careful while drifting on the same schedule:
a tree can shrink past "90K+" as easily as it grew past an exact figure.

The tell is that such a sentence has to describe its own restraint.
A form needing a clause like "a count this sentence deliberately does not
pin" pinned one, or it would have nothing to disclaim.
The pointer form needs no such clause, because it names the query rather
than an answer.

Hedging is the wrong answer whether or not the figure has a source.
What the source decides is which right answer applies, and the discriminator
is whether a *source can be named* rather than whether a command exists.
A figure whose source is nameable --- a directory, an API, a lockfile --- gets
the pointer.
A count of the items in the block directly beneath it names nothing, so it
gets dropped or re-derived instead, per
[a count in the prose above a block](#a-count-in-the-prose-above-a-block-is-the-same-duplicate-one-line-away).

- **Do:** replace a figure the filesystem or an API enumerates with the
  command that derives it.
- **Don't:** hedge such a figure and keep it --- an approximation drifts on
  the same schedule the exact value did.

(Measured on `ucdavis/bcs`#750, 2026-08-27.
A hedged draft was rejected in review before it was pushed, in a change whose
own commit message cited this fragment.
The shipped text splits along exactly the line above: the *file* count became
`find .ai-config/shared -name '*.md' | wc -l`, and the *token* figure, which
no command enumerates, was dropped rather than hedged.)

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
  than something to settle by recollection.

  **Scope that command to the block, not to the whole file.**
  A file-wide `grep -c` is right only while the pattern happens to match
  nothing outside the block, which is a property of the file today rather
  than of the command.
  An unrelated edit that adds one matching line anywhere else silently
  inflates the count, so the instrument acquires exactly the failure mode it
  was reached for to prevent.
  Bracket the block with two unique anchors instead:

```bash
awk '/^Four reads settle it/,/^An identical tree/' shared/workflow/claim-pr.md |
  grep -c '^git '
```

Count list items, bullets, or numbered steps the same way.
Two habits keep the range honest.
Confirm each anchor matches exactly once (`grep -c` on the anchor itself)
before trusting it, since a repeated start anchor makes an `awk` range
restart and silently widen.
And run the range once without the counting stage, to see that the lines it
selects are the ones you meant.

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

### A qualitative generalization above a block goes unchecked where a count would be re-derived

The section above governs a **count** stated above the block it counts, and its remedy is to drop the count or re-derive it by command.
A qualitative claim over the same block is the same shape, and it slips past that remedy entirely, because it carries no number to re-derive.

A count invites verification because it is obviously a number someone must have measured, and a stale one reads as a typo waiting to be caught.
A qualitative claim --- "always", "independently of", "in every case", "the same in both" --- carries no such tell.
It reads as characterization rather than as a checkable fact, so it survives review exactly where a count would not.

The check is not "re-derive the number" --- there is none --- but "read the introducing sentence against the block", applied here to the sentence a table or block sits directly beneath.

- **Do:** re-read a lead-in sentence against its block for what it generalizes or quantifies, not only for a stated count.
- **Do:** treat "always", "independently of", "in every case", "the same in both" as tells that a claim needs checking against the data beneath it.
- **Don't:** assume a qualitative lead-in is safe because it carries no number that could go stale.

(Morrison-Lab/ai-config#1543, 2026-08-16, review round 1: a new section in `shared/workflow/grep-is-not-coverage.md` opened "Case sensitivity moves the number again, independently of the ref." directly above its own case record's table, which showed the two flag settings agreeing at the merge-base and differing only at the head --- the opposite of ref-independent.
Every number in the table had been re-derived by command before publishing;
the sentence generalizing about it had not been checked against it at all, because it carried no number to re-derive.
Fixed in `b02e3ff`.)

### A suite's pass count is a liability twice over when written as an expectation

The sections above govern a claim about a block the same file carries --- a count of its items, or a generalization over them.
A **test-suite pass count** --- a total written into a comment above the helper it describes, or into a commit message --- looks like the same defect and is worse.
It has two independent ways of going wrong, and each is mistaken for the other.

The number moves with the **suite**, so any added or removed case falsifies it on a schedule nobody watches.
That much it shares with the counts above.

What makes it expensive rather than untidy is the second failure, which those counts cannot have: a suite can report a total one short of the written one **without anything having changed**, because one case flaked.
The comment then supplies an exact expectation for the reader to miss, and the first hypothesis they form is about the code.
A comment with no number would have prompted nothing.

**The diagnosis that follows is where this compounds**, because the count is a plausible-looking anchor and invites an explanation for the discrepancy rather than a check of the premise.
Any difference between the two runs will do --- a different checkout, a different working directory --- and such an explanation is unfalsifiable from the numbers alone.
So the written count first manufactures a regression and then supplies a wrong cause for it.
A run one short of a written total is a flake until shown otherwise, and the way to see that is the failing test's **name**, which a total conceals by construction.

**Assert the property, not the number.**
"Every case still passes with the helper neutered" is checkable, cannot go stale, and says what the observation was for.
The total says only how big the suite was that day.
Where the count is genuinely load-bearing, make it a test rather than a sentence.

**This rules out one tense and not the other.**
A count inside a case record is evidence about a past run and keeps its literal, which is the boundary
[the section on text that records what was observed](#where-the-rule-stops-text-that-records-what-was-observed)
draws with the same tense-and-mood test.
What this section rules out is the forward form: a count written as what a future reader should expect to see.

- **Do:** state the property a run demonstrated, and leave the total out of a forward-looking comment.
- **Do:** keep an exact total inside an evidentiary record, naming the tree and the command it was measured on.
- **Don't:** write a suite total into a comment or commit message as a baseline for someone to compare against.
- **Don't:** read a total one short of a written expectation as a regression, before checking whether the expectation was ever a stable number.
- **Don't:** explain a discrepancy between two totals by naming a difference between the two runs.
  That hypothesis fits any pair of numbers and tests nothing.

(Measured on [Morrison-Lab/ai-config#3100](https://github.com/Morrison-Lab/ai-config/pull/3100), merged 2026-09-03.
A comment in `scripts/test_check_review_body.py` read "754 pass with the helper neutered", and the same figure went into a commit message.
The figure counted a *different* file's suite, `scripts/test_check_pr_fully_clean.py`, which is half the point: the number was written where nothing regenerates it and nothing names what it counts.
That suite carries wall-clock assertions that intermittently miss a one-second budget
([#3127](https://github.com/Morrison-Lab/ai-config/issues/3127)), so a run comes back one short.
The baked count had that flake read as a regression.
The revision after it then misattributed the flake to the checkout, saying in effect that both readings were right because the worktree and a scratch copy of it disagreed by one.
They did not.
The flake was the same in either location, and that explanation was retracted a revision later.

The other half of the point is that the total really is environment-dependent, and three successive attempts named the wrong cause.
Measured 2026-09-03 on `origin/main`, `python3 scripts/test_check_pr_fully_clean.py` reports `754 passed, 0 failed` in an ordinary checkout and `753 passed, 0 failed` under `GIT_DIR=/nonexistent`.
The suite fetches a prior revision of the checker with `git show`, trying `origin/main` first, and emits one extra case only when some revision resolves.
So the total turns on whether that ref is reachable, not on where the tree sits: a `git archive` export reports 753 and a depth-1 clone reports 754, because the shallow clone still has `origin/main`.

That is the discriminator, and it was one command away throughout.
What the three wrong explanations share is that none of them varied an input.
The first two named whatever differed between the two runs already performed --- the code change, then the checkout's location.
The third, written while this entry was being drafted, went further and denied that 754 had ever been a real reading, on the strength of an archive measured in place of a checkout, which is
[`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)'s substitution exactly.
A count that varies with the environment offers an explanation for every pair of numbers, and every one of them is unfalsifiable until someone changes one thing and re-runs.
The text that shipped gives no count as an expectation, and says why.)

## Where the rule stops: text that records what was observed

Everything above pushes toward replacing a literal with whatever owns it.
There is one boundary it must not cross, and a consistency sweep is precisely
the operation that crosses it without noticing.

Text that **asserts what was observed** is not configuration.
A command someone actually ran, the output it actually produced, and the
conditions a measurement was actually taken under are claims about the past,
and their literals are the evidence for those claims.
Parameterizing them does not generalize the record.
It falsifies it, in the name of consistency, and leaves no trace that anything
was changed.

Three forms, each of which looks exactly like the hard-coding this fragment
bans:

- **A command that was executed.**
  `git worktree add /tmp/wt-ums main` reports a run.
  Rewriting it to `<default-branch>` asserts a run that never happened.
- **A verbatim error string.**
  `fatal: invalid reference: origin/main` is what the tool printed.
  A reader matches it against their own terminal, so a parameterized version
  matches nothing and stops being findable.
- **The conditions of a measurement.**
  A sentence saying the runs used a repo whose default branch is literally
  `main` states the scope of the result.
  It is usually the sentence that explains why the measurement did not surface
  the bug.

The tell is tense and mood rather than syntax.
Prescriptive text tells a reader what to do next, and should name the
parameter.
Evidentiary text says what happened, and should keep the literal.
One file routinely carries both, so decide occurrence by occurrence.

[`ascii-punctuation-in-source`](ascii-punctuation-in-source.md) records the
same over-application for punctuation, where a whole-file replace turned a
one-line finding into a 104-line diff.
The failure there is scope, and the diff is still true.
Here the rewritten text becomes false, which no diff size reveals.

- **Do:** parameterize the occurrences that instruct, and leave the ones that
  record.
- **Do:** decide per occurrence in a file that carries both, reading each one's
  surrounding sentence.
- **Don't:** run a whole-file replace over a literal that also appears inside
  quoted commands, quoted output, or a statement of measurement conditions.
- **Don't:** treat an unparameterized literal inside a case record as a defect
  left behind -- there it is the evidence.

(Morrison-Lab/ai-config#1008, merged 2026-08-01 as `3eb15a4`: it parameterized
the base branch to `<default-branch>` across `skills/gip/SKILL.md` and
`memories/preferences.md`, and stopped at three places on purpose.
`memories/preferences.md` keeps `git worktree add /tmp/wt-ums main` and the
scores measured with it, and closes that block by saying those runs "used a
repo whose default branch is literally `main`, which is why they are written
that way here and why they did not surface the hard-coding".
`skills/gip/SKILL.md` keeps `fatal: invalid reference: origin/main` as the
error a reader will actually see.
Both files state their reasoning in place --- `preferences.md` in the sentence
quoted above, `gip/SKILL.md` at the line that says hard-coding "fails with
`fatal: invalid reference: origin/main` on any repo whose default is named
otherwise".
So the judgment was written down, and a sweep still re-flagged them, because an
in-file rationale is not something a `grep` for `main` can consult.
That is the transferable part: recording *why* an instance is exempt protects a
reader, not a mechanical sweep, and the two need different affordances.)
