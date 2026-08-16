A grep matches strings.
Coverage is a claim about concepts.
So a grep that returns nothing never entails that the corpus does not cover
something, and the step from one to the other is where the error lives.

The gap is easy to miss because the evidence is real and the command is
sound.
Running the grep feels like checking, and the null result is a genuine fact
about the pattern you typed --- it is only the *conclusion* that overreaches.
Nothing about a clean zero-hit result looks like a guess, which is why the
claim goes out with more confidence than a hedged one would.

What makes it worse than an ordinary wrong statement is the action it
licenses.
"The corpus does not cover this" is an argument for **writing something
new**, so the error does not merely sit there being wrong --- it produces a
duplicate fragment, a redundant skill, or a re-proposed rule, and the review
that catches it has to argue against work already done.

## The rule: report the query, not the conclusion

Write down what you searched and what came back, and let the reader draw the
inference:

> A grep for `hook|hooks.json|UserPromptSubmit` across `shared/`, `skills/`,
> and `CLAUDE.md` returned nothing.

That sentence is true, checkable, and shows its own limits --- a reader who
knows the corpus can see at a glance that the query was too narrow and say
so.
Compare:

> The corpus does not cover hooks.

Unfalsifiable from the outside, indistinguishable from a thorough search, and
false.

- **Do:** state the pattern, the paths searched, and the result.
- **Do:** say "I did not find" rather than "there is no", when the evidence is
  a search rather than a reading.
- **Don't:** convert a null result into a claim about what exists.
- **Don't:** propose new content on the strength of a phrase grep alone.

## Two things that make the null result cheaper to trust

**Pull before measuring.**
A grep against a stale checkout describes your disk, not the corpus.
This is the failure mode with no symptom: the command succeeds, the result is
clean, and the content you missed has been on `main` for weeks.
Fetch first, then search --- the same precondition
[`sync-with-main`](sync-with-main.md) sets for any measurement taken against
a moving base.

**Search by topic and filename, not only by phrase.**
A fragment covering a concept in different words is invisible to a phrase
grep.
[`find-overlap`](../../skills/find-overlap/SKILL.md)'s clustering step
measures this directly: `tidy` and `simplify`, its own canonical
same-idea pair, score **0.019** on phrase similarity, because they share an
idea and almost no wording.
So list the directories, read the titles, and grep for the stable part of the
concept rather than the volatile part.

The two mechanisms by which a well-intentioned grep misses text that is
genuinely present --- a wrong guessed spelling, and a phrase spanning a
semantic line break --- are already written up in
[`memories/debugging.md`](../../memories/debugging.md), under "An empty grep
for one spelling is not evidence the concept is absent".
Read that rather than re-deriving them; this fragment is about the inference
drawn from the null result, not about the query that produced it.

## Name the mechanism in the query, not the remedy you are about to prescribe

The section above improves how a query *matches*, and it assumes the query
already names the right concept.
Choosing which concept to name is a separate step, and it is the one that goes
wrong when the search is a dupe check for something you are about to write.

By then you already know the **remedy** you intend to prescribe, so the
remedy's words are the ones at hand.
The **mechanism** --- the thing that actually happens, which the entry is
about --- is the part you would have to stop and name.
So the query that forms itself is the remedy's, and that is the one query
guaranteed to miss the entry you most need to find.
A sibling written from the other side of the same mechanism prescribes a
**different** remedy, so it shares none of your vocabulary while being about
the identical thing.

That section's own advice to search by topic rather than only by phrase does
help here, and it stops one step short.
"Topic" is precisely what this failure gets wrong: while you are about to
write the remedy, the remedy *feels* like the topic.
The increment is naming which topic, not remembering to have one.

**Nothing about the result betrays it, and re-running the query more
carefully returns the same zero.**
This is not the wrong-spelling or line-break case
[`memories/debugging.md`](../../memories/debugging.md) covers, where a pattern
fails to match text that is genuinely present.
Here the pattern is correct and the grep works.
The remedy's words really are absent from the sibling entry, so there is no
matching bug to find and no better-constructed version of the same query that
would have hit it.
The command is sound, the null is true, and only the concept was wrong.

The corpus's usual escape hatch does not reach it either.
[`challenge-redundant-content`](challenge-redundant-content.md) says to prefer
`scripts/find-near-duplicates.py` over literal grep, and that instrument does
score whole texts rather than one query --- but it enumerates its corpus with
`git ls-files`, so it compares **tracked** units against each other.
An entry that is not written yet has no text to shingle, so the instrument
cannot be pointed at it.

The substitution is one question, asked before the query is typed:
**what happens**, rather than **what I will tell people to do about it**.
Write the mechanism's nouns and verbs down first.
They are usually three or four words, and having to name them is the whole
cost.

- **Do:** derive the query from the mechanism the entry is about, and name
  that mechanism explicitly before searching.
- **Do:** report the mechanism terms searched alongside the remedy terms, so a
  reader can see which concept the null result is about.
- **Don't:** grep the vocabulary of the fix you are about to prescribe --- an
  entry prescribing a different fix for the same mechanism cannot match it.
- **Don't:** read a correctly-constructed query's zero as covering the
  concept; a sound query can be sound about the wrong thing.

(Morrison-Lab/ai-config#1522, 2026-08-16, review round 1: the PR added a
section on a squash merge orphaning a stacked PR, and its dupe check grepped
`"before merg|merging|check.*open"` --- the vocabulary of the fix it was about
to prescribe, which was to run `gh pr list --base` before merging.
It never searched the mechanism: squash, retarget, orphaned base, stacked.
`shared/workflow/use-existing-pr-branch.md`'s "A stacked PR reaches that
bloated state with no push of yours at all, and it announces itself as a merge
conflict" section was already on `main`, covering that same mechanism from the
dependent PR's side and prescribing a post-hoc rebuild rather than a pre-merge
check --- so it shared none of the remedy's vocabulary.
The reviewer named the cause in as many words, saying the cross-link "would
likely have surfaced during this PR's own dupe-check (which only grepped ...
and never searched for the underlying squash/retarget mechanism itself)".
The two sections stayed separate under that fragment's litmus test, since
consolidating would lose the split between a pre-merge obligation and a
post-hoc recovery.
What the missed search cost was the cross-link, which round 1 had to raise as
a finding and which landed in the fix commit answering it.)

## Searching the wrong corpus is the same error with no grep in it

Everything above assumes a grep ran and came back empty.
The failure that produces the same duplicate needs no grep at all: authoring a
**repo-local** memory in one repo, on a subject the cross-repo corpus already
covers, without ever searching that corpus.

The scoping is what hides it, and it is structural rather than careless.
Deciding where a learning belongs is a real step ---
[`ums`](../../skills/ums/SKILL.md) step 2 routes each item either to ai-config
or to the owning repo's own agent docs --- and once an item is routed to a repo
we own, every later instruction reads as relative to *that* repo.
Step 3's "grep the whole `memories/` directory" then means the destination's
`memories/`, so the dupe check runs to completion, finds nothing, and never
looked at ai-config at all.

The asymmetry is why this needs naming separately from the null-result case.
A repo-local memory in some other repo is precisely the place nobody thinks to
check ai-config from, because the ai-config corpus is not what that session is
working on.
So the duplicate lands where the check is least likely to be re-run, and it can
**contradict** the corpus rather than merely repeat it --- which is worse than
an ordinary duplicate, since a reader who later finds both has no way to tell
which one is current.

- **Do:** grep the ai-config corpus as well as the destination repo's docs,
  whenever step 2 routes an item anywhere other than ai-config.
- **Do:** search by topic and filename there too --- a file named for the
  subject settles it faster than any phrase.
- **Don't:** treat the routing decision as narrowing which corpus to search; it
  decides where the entry *lands*, not what already exists.
- **Don't:** author a repo-local entry that contradicts the corpus on the
  strength of never having looked.

(2026-08-05: a `git worktree remove` refusal on a worktree containing a
submodule was written into a `Lacaedemon/sparta` repo-local memory as `--force`
"does not help", asserting that git "declines this case unconditionally".
ai-config's own `memories/git-worktrees.md` --- a file named for that exact
topic --- already read "Fix: `git worktree remove --force <path>` removes it
cleanly", and had for some time.
No grep ran against it, because the entry was being authored in a different
repo.
One search would have settled the question with no measurement needed at all;
instead a reviewer had to challenge the claim and a measurement had to be taken
to disprove it.
The verification half of the same incident --- attempting the base form of a
command and generalizing to a flag never passed --- is recorded separately in
Morrison-Lab/ai-config#1174.)

## A non-null result has the same defect, when the hits go unenumerated

Everything above governs a grep that returns **nothing** and a conclusion
drawn from that silence.
The mirror failure returns **several** hits, and is worse in one respect: the
result is real evidence, so nothing about it invites the suspicion an empty
result eventually earns.

The mechanism is that a dupe check asks an **existence** question --- does the
corpus already cover this --- and a single hit answers it.
The search therefore terminates at the first match, which feels like success
rather than like stopping early.
You then read that one spot, decide how to extend it, and never look at the
second hit in the same file.

Two properties make this land hardest exactly where the corpus expects a dupe
check to run.
A long memory file or fragment can hold **two entries on adjacent aspects of
one concept**, written months apart, neither aware of the other.
And the second entry is usually framed differently from the first --- a
different content shape, a different surface, a different failure direction ---
which is precisely why it was written separately and precisely why it does not
read as a duplicate of the hit you already found.

So the cost is not a duplicate.
It is a **novelty claim**: you present as new something the corpus already
partly records, and the framing has to be walked back by a reviewer who read
further than you did.

The remedy is one word in the question.
Ask "where does the corpus cover this" rather than "does it", so the answer is
a list rather than a boolean, and read every hit in a file before deciding
what to add.
Report the hit **count per file**, not just which files matched --- a file that
matched twice for different reasons is invisible in a table that records only
which terms hit which paths.

- **Do:** enumerate every hit within a matching file, and read each one, before
  deciding whether to extend or add.
- **Do:** report hits per file, so a file matching twice is visible.
- **Don't:** treat the first match in a file as the entry to extend --- it is
  the first one your pattern happened to reach, not the most relevant.
- **Don't:** read a non-null result as exempt from this file's rule; the
  conclusion can overreach the evidence in either direction.

(Morrison-Lab/ai-config#1469, 2026-08-15, review round 1: a dupe check before
extending `memories/github-mcp-tools.md`'s angle-bracket-stripping entry
printed two matches in that one file --- the placeholder entry, and a second
one opening `- **The MCP write tools silently drop ... angle-bracket
autolinks`.
Cited by heading rather than by line number, since that file has grown since
and the numbers the grep printed no longer resolve.
The first was read and extended; the second was never opened.
It names `update_pull_request` outright, so the new entry's claim to be adding
"a third write surface" overstated what was new, and the reviewer caught it by
reading further down the same file.
The evidence was in the check's own output, which is what separates this from
a search that was never run.)

## A published count needs the ref and the flags it was measured with

The section above governs reading a dupe check's hits.
This governs **reporting** its count, and it needs no misreading at all: the
count is right, the reviewer's re-run is right, and they differ because the two
runs measured different trees.

A dupe check asks what the corpus held **before** this PR, so the merge-base is
the tree the claim is about.
A reviewer re-runs at the head, where the PR's own additions are present --- and
an addition can match the dupe-check pattern incidentally, so the PR falsifies
the count its own body reports.
Case sensitivity is a second axis, and it is worth stating even where it
changes nothing: in the case below the two flag settings agree at the
merge-base and differ at the head, so neither reading predicts the other.

**So the correction is not to update the figure.**
Raising it to match the head would make the claim *less* accurate, since the
extra hit is text this PR added rather than coverage the check should have
found.
What is missing is the **ref** and the **flags**, and stating both settles the
disagreement while leaving every number as it was.

Distinct from
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md)'s
count-above-a-block rule, whose subject sits in the same file and whose remedy
is an `awk`-bracketed re-derivation.
Here the subject is a query over several files, the count lives in a PR body,
and what falsifies it is the diff itself.

Distinct too from the nearest sibling, in
[`ardi.cases.md`](ardi.cases.md), where a figure "correct at the head it ran on"
went stale because a later commit moved the head.
That one says re-derive, because the right tree kept moving.
This one says the right tree does **not** move --- a dupe check's tree is fixed
at the merge-base by what the claim is about --- so re-deriving at the head
answers a different question rather than a fresher version of the same one.
[`ardi`](ardi.md)'s pre-push checklist already requires every number in the body
to be "re-derived by command rather than re-read, run at this push rather than
carried from the last one".
Read literally that is right, and read quickly it points the wrong way here: "at
this push" is about not carrying a **stale** figure forward, and a dupe-check
count is one you *should* carry, because the merge-base it was measured at has
not moved.
Re-run it each push if you like --- against the merge-base, not against the tree
the push produced.

- **Do:** publish the ref, the flags, and the paths beside a dupe-check count,
  rather than the count alone.
- **Do:** measure a dupe check at the merge-base, since that is the tree an
  "already covered" claim is about.
- **Don't:** re-run at the head and "correct" the body to match --- that imports
  your own additions into a claim about what preceded them.
- **Don't:** read a reviewer's differing count as a disagreement about the
  corpus until you have checked whether it is a disagreement about the tree.

(Morrison-Lab/ai-config#1536, 2026-08-16, review round 1: the body reported its
dupe check as "6 hits, all in the sections above", and the reviewer re-ran the
same query and got **7**, filing it as a non-blocking miscount.
The query was `calibrat|against the real corpus|real corpus|false positive` over
`shared/workflow/algorithmatize-checks.{md,rationale.md}` and
`shared/principles/fail-fast.{md,rationale.md}`.
Re-derived, every figure was correct about a different tree:

| tree | flags | hits |
| --- | --- | ---: |
| merge-base `f6805489` | case-sensitive | 6 |
| merge-base `f6805489` | `-i` | 6 |
| head `ab88c2b7` | case-sensitive | 7 |
| head `ab88c2b7` | `-i` | 8 |

The seventh hit is `Its false positives are therefore not incidental` and the
eighth is `False positives after the narrowing were 0`, both `+` lines of that
PR's own diff in `shared/principles/fail-fast.rationale.md`.
The reviewer had itself noted the extra match was "inside this same PR's own new
FIRE-condition addition", so both parties held the evidence and neither drew the
conclusion that the count needed a ref rather than a correction.
The fix stated the ref and the flags and changed no number.)

## Where this fires

The skills whose workflows run exactly this grep, and whose next step is to
author something:

- [`skill-builder`](../../skills/skill-builder/SKILL.md) step 0, deciding
  whether an existing skill should be extended instead.
- [`ums`](../../skills/ums/SKILL.md) step 3, deciding whether a learning is
  already recorded.
- [`find-overlap`](../../skills/find-overlap/SKILL.md), whose whole premise
  is that phrase matching under-detects.

In each, the grep's result is an input to a judgment, never the judgment
itself --- and that holds in both directions, since these three sites are
also where the non-null under-read above happens.
The incident recorded there was a `ums` step-3 dupe check, so the same list
covers a search that found nothing and a search that found two things and
read one.

## Relationship to other rules

[`report-mistakes-proactively`](report-mistakes-proactively.md)'s dupe-check
step and
[`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md)
both ask you to search before adding.
This fragment governs how to *report* what that search found.
[`challenge-redundant-content`](challenge-redundant-content.md) is the
review-side counterpart, for the duplicate that gets written anyway.

(Morrison-Lab/ai-config#950, 2026-07-30: three claims of the form "the corpus
does not cover this" were made in one session on the evidence of a phrase
grep returning nothing.
All three were wrong.
"ai-config does not ship hooks" --- it does, in a top-level `hooks/`, and the
grep had run against a checkout 27 commits behind.
"The corpus frames reprexes only as communication, never as diagnosis" ---
`skills/reprexes/SKILL.md` opens by telling you to extract a reproduction and
"iterate candidate fixes on *that*", and fires "when debugging a bug whose
cause isn't obvious after a first look".
That is the diagnostic framing, and the word "diagnosis" appears nowhere in
the file --- so a grep for it returns clean, which is the false negative this
fragment is about, reproduced while writing this fragment.
The third re-proposed an already-covered delegation rule.
None of the three greps was badly written; each conclusion simply did not
follow from its evidence.)
