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
Step 3 read "the whole `memories/` directory" at `3935bfff`, which meant the destination's,
so the dupe check ran to completion, found nothing,
and never looked at ai-config at all.

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

**The same failure has a same-repo sibling that needs no second repo at all: the wrong *directory*.**
The rule above turns on a routing decision between repos,
so it reads as a cross-repo rule and is filed under one.
The mechanism does not require two repos.
It requires only that some earlier decision fixed a location,
after which every later instruction is read relative to it.
Routing an item to a memory file does exactly that:
the destination is under `memories/`, so the dupe check searches `memories/`,
and a `shared/` fragment or a skill owning the same idea is never in view.
The check runs to completion and returns a clean, correctly-constructed zero.

It is worth separating because the remedy differs.
The cross-repo case is fixed by adding a corpus;
this one is fixed by widening within the corpus you are already in,
which no amount of care about *which repo* will prompt.
The corpus already owns the right query, in the sibling procedure ---
[`skill-builder`](../../skills/skill-builder/SKILL.md) step 0 greps `skills/ scripts/ hooks/ shared/ memories/ CLAUDE.md`,
where [`ums`](../../skills/ums/SKILL.md) step 3 read "the whole `memories/` directory" at `3935bfff` and stopped there.
`CLAUDE.md` names both procedures as the same trigger,
and their queries differed.

- **Do:** grep every directory the corpus spans, not the one the destination sits in.
- **Don't:** read "the whole `memories/` directory" as thorough --- the word doing the damage is `memories/`, not "whole".

(Recorded 2026-09-03 on [ai-config#3060](https://github.com/Morrison-Lab/ai-config/pull/3060),
where a markdownlint entry was added to `memories/markdownlint.md`
while `shared/writing/semantic-line-breaks.md` already mentioned the same collision in three regions,
at `eb0cf15e` and unchanged at `3935bfff` (`origin/main` when this was measured):
`grep -n MD018` over that file returns five lines at each ref ---
274, 288, 295, 842 and 976 at `eb0cf15e`, and 274, 288, 295, 861 and 995 at `3935bfff` ---
of which the first three sit inside one bold-lead block with its own `Do`/`Don't` pair.
The checkable part is what the wider grep would have done.
`grep -ril "issue reference" memories/` returns three files at `3935bfff`,
and none of them is the owner,
because the owner is `shared/writing/semantic-line-breaks.md` and no search of `memories/` can reach it.
The ref matters, and is this fragment's own rule below ("A published count needs the ref and the flags it was measured with"):
the same query returns four at `eb0cf15e`, the commit that added the duplicate entry,
whose `memories/markdownlint.md` is the fourth hit.
At `5f2dab94`, #3060's head when this was measured, the count is still four,
but that fourth hit is now a stub whose body `1732000a` replaced with a cross-link ---
so the number outlived the thing it was measuring.
So this is not the old step 3 merely going unfollowed:
following it exactly, over the whole of `memories/`, still misses.
Note also why this section's own `Do` could not have caught it.
It reads "grep the ai-config corpus as well as the destination repo's docs,
**whenever step 2 routes an item anywhere other than ai-config**",
and this item was routed to ai-config, so its trigger never fires.)

## An unmerged PR is part of the corpus a citation can be corroborated against, and no default-branch search reaches it

The section above governs searching the wrong **repo**.
This one governs searching the wrong **branch state within the right repo**: a citation to content that ships only in an open PR, checked by grepping the default branch.

The null result here is not merely inconclusive --- it is guaranteed whether or not the cited content is genuine.
A search over the default branch cannot find content that has never been on the default branch, so the check answers a question the corroboration was never asking.
The failure reads as fabrication rather than as a scope error, because a clean, correctly-constructed zero-hit grep looks exactly like a search that covered the whole corpus.

**The fix belongs primarily to the author, not the searcher, because only the author controls which branch a citation actually lives on.**
When citing content that is not yet on the default branch, name the PR rather than (or in addition to) the file path, and state in the citation itself that the corroborating file is absent until that PR merges.
That converts an apparent dead end into an explained one, and it is the only fix that removes the false positive rather than merely shrinking it.

**A reader-side search of open PRs is worth running, and it is a mitigation rather than a remedy --- treat its null result as narrowing the question, not settling it.**
`gh pr list --state open --search "<term>"` or `gh search code` catches the common case, where the cited content sits in a PR someone opened.
It still misses a subject living on a branch nobody has opened a PR for, or in a PR that was closed and superseded, so a second null result is not proof either --- it is the same defect one level up, over a slightly wider population.
Stating the search this way matters: writing the search as *the* fix teaches the next reader to treat its null result as settling the question, which is the exact failure this section exists to prevent.

**Two independent parties running the same grep did not corroborate anything, because both searches keyed on the same surface.**
[`algorithmatize-checks.rationale.md`](algorithmatize-checks.rationale.md) already states the general form: "The discriminating question is not whether the second method was run independently, but whether it could have failed differently: a second pass that keys on the same token shape will confirm the first pass's misses as readily as its hits."
A second grep over the same default-branch tree cannot fail differently from the first;
it can only reproduce the first's dead end and make it feel doubly confirmed.

- **Do:** cite the PR, not just the file path, when the cited content lives only in an open PR --- and say the corroborating file is absent until merge.
- **Do:** search open PRs before concluding a citation is uncorroborated, but read a null result there as narrowing, not settling, the question.
- **Don't:** conclude a citation is fabricated from a default-branch grep alone, when the citation names or implies unmerged work.
- **Don't:** treat a second search that keys on the same population (the default branch, or the open-PR set) as independent corroboration of the first's null result.

(Morrison-Lab/ai-config#1864, 2026-08-21: `shared/workflow/verify-the-right-artifact.md` cited an incident about `skills/clean-git/SKILL.md` step 2 running a real `git worktree prune`.
The `claude-review` bot ([review comment 3834449057](https://github.com/Morrison-Lab/ai-config/pull/1864#discussion_r3834449057)) and a separate CLI session working the same PR each ran `grep -rn "worktree prune" skills/ shared/ memories/`, and both got the same three unrelated hits.
The incident was real --- ai-config#1849, [review comment 3834408153](https://github.com/Morrison-Lab/ai-config/pull/1849#discussion_r3834408153) --- but `clean-git` does not exist on the default branch;
it ships only in #1849, which was open at review time and remained open when this entry was written.
Resolved in [review comment 3834476527](https://github.com/Morrison-Lab/ai-config/pull/1864#discussion_r3834476527): "Your greps finding nothing is itself part of the record...
`clean-git` does not exist on `main`... so no search of `main` can corroborate the anecdote.")

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

## A claim that nothing exists owes its deriving command, even when no search ran

Every section above starts from a query that was actually run.
The commonest version of this failure runs no query at all.
You assert that nothing else touches a file, that no such sibling exists, that some construction is immune --- and the sentence goes out in confident phrasing that reads as already-checked, because nothing in it announces that the check was skipped rather than performed.

This fragment's own rule stops one step short of it.
Its opening Do/Don't block says to write "I did not find" rather than "there is no" **when the evidence is a search**, which is a precondition.
An assertion made with no search never meets that precondition, so the rule is loaded and matches nothing.
Derived at the time of writing:

```
$ grep -n "I did not find" shared/workflow/grep-is-not-coverage.md
39:- **Do:** say "I did not find" rather than "there is no", when the evidence is
```

It is also distinct from "Searching the wrong corpus is the same error with no grep in it" above, which is the nearest sibling and is narrower.
There a dupe check genuinely ran, correctly, over the wrong population.
Here nothing ran, so there is no query to critique and no null result to over-read --- only a sentence and the confidence it was written with.

**The failure is structural rather than a matter of care.**
That is the part worth stating, because the obvious remedy --- be more careful --- is the one the evidence rules out.
All four instances below were composed during careful work, and the fourth was committed inside the brief that commissioned this very entry, by someone actively thinking about the failure while writing about it.
A rule whose remedy is vigilance cannot survive that.

**The observable action is to paste the deriving command beside the claim**, in a brief, an issue body, a PR body, or a review comment --- the same discipline [`challenge-the-assignment`](challenge-the-assignment.md) already requires of a brief that asserts corpus state, extended to every artifact a negative claim gets published in.
The command is usually one line, and having to write it is the whole cost.

The three that settled these instances are the reusable part:

```
gh pr diff <N> --name-only     # what else touches this file
git --list-cmds=main,others    # what commands exist HERE (see the caveat below)
printf '%s' "$payload" | python3 hooks/<guard>.py   # what this code does
```

The second one carries a caveat the other two do not, and the case record below is where it came from: its output varies by git build, so it settles what exists on the machine you ran it on and nothing wider.

Note what the third one is for.
A claim that some code is immune to a bug class is a claim about behaviour, so no amount of reading settles it --- the probe does, and it is two lines.
[`self-review-fallback`](self-review-fallback.md)'s "Where a diff makes a claim about a TOOL's behaviour" section makes the same point for a diff under review.

- **Do:** run the deriving command before publishing a claim that something does not exist, and paste it beside the claim.
- **Do:** write what the command returned, so a reader can see which population the negative is about.
- **Do:** probe behaviour rather than reading it, when the claim is that some code cannot do something.
- **Do:** record the tool version beside a command whose output is build-dependent, since running it is necessary and not sufficient when the answer differs by environment.
- **Don't:** publish "nothing else", "no such", "immune", or "disjoint" on recollection --- confident phrasing is what makes such a claim read as checked.
- **Don't:** read this file's "say 'I did not find' rather than 'there is no'" rule as covering the case, since its precondition is that a search happened.

**No guard covers this, and one was built and measured before being rejected.**
The candidate was a warn-only hook over `gh issue create` and its siblings, firing on negative-existence phrasing in a body with no deriving query beside it.
Measured against 1,759 distinct bodies recovered from this machine's transcripts, a tightened matcher fired 40 times, and of 12 distinct fires read by hand 2 were genuine and 10 were not.
The reason is not tuning.
An issue body's genre is reporting findings, and a finding is routinely negative, so "the workaround does not exist" and "there was no breadcrumb" are conclusions the author had just derived --- textually identical to a guess, and frequently derived somewhere the body does not show.
[`remind-brief-premises.py`](../../hooks/remind-brief-premises.py) escapes this because it anchors on a corpus path, a rare token that is nearly always a real assertion, where negation is the ordinary vocabulary of a bug report.

The fourth instance closes the question.
"`grep-is-not-coverage.md` states this rule for a search result" is grammatically **positive**, so no negation matcher can see it at all, which means the class was never lexically negative to begin with.
The feature that matters is that the claim was underived, and that is not decidable from the text.
Building the guard anyway would trade one caught instance for roughly thirty wrong warnings on issue filings, against a corpus that makes filing near-unconditional --- which is [`deterministic-tools`](../principles/deterministic-tools.md)'s own warning that a misfiring guard gets switched off and takes the real cases with it.

(Morrison-Lab/ai-config#1979, 2026-08-22: four claims in one session, each cheap to verify and none verified before publishing.
"`shared/workflow/learn-from-review-findings.md` is disjoint from every open PR", written into a subagent brief --- false, since [#1911](https://github.com/Morrison-Lab/ai-config/pull/1911) touches it.
"Hooks that tokenize commands are immune to the entire bug class by construction", published in [#1967](https://github.com/Morrison-Lab/ai-config/issues/1967) --- false, since `sh -c "git push --force origin main"` draws no output at all from `hooks/no-clobbering-push.py`, where the same command unwrapped is denied.
The gap is filed as [#1973](https://github.com/Morrison-Lab/ai-config/issues/1973).
"Of `add|commit|apply|mv|rm`, only `commit` has real hyphenated siblings", published in [#1966](https://github.com/Morrison-Lab/ai-config/issues/1966) --- false on the machine it was asserted from, where `git --list-cmds=main,others` reports `add--interactive` under git 2.50.1 (Apple Git-155), whose exec-path still ships a `git-add--interactive`.
This PR's own review then ran the same command under git 2.55.0 and got no such entry, modern git having rewritten `add -i` in C and dropped the Perl dispatcher.
Both runs are honest, which makes this the sharpest of the four: the deriving command was necessary and **not sufficient**, because its answer is build-dependent and neither party could see that without running it in both places.
So pair such a command with the version it was run against, per [`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md).
And the characterization of this file quoted above, written into the brief asking for this section, which `hooks/remind-brief-premises.py` flagged as an unverified corpus assertion.
It happened to be true.
Its author did not know that when writing it, which is the whole of the point.)

## The sentence that CORRECTS an overclaim is where the next one gets written

The section above governs a negative existence claim published anywhere.
This one names the single site where that class is likeliest and least checked: the sentence that answers a review finding by narrowing a claim you already published.

The correcting commit is not a neutral place for a new claim to appear.
It is the place where a fresh claim draws the least scrutiny it will ever draw, and three separate mechanisms push in that direction at once.

**The corrective mood reads as rigor.**
Hedging, narrowing, conceding a limit are the opposite of overclaiming, so a sentence performing one of them does not present as an assertion needing evidence.
It presents as the evidence-respecting move.
That inversion is the whole difficulty: the check would fire on a confident sentence and does not fire on a modest one, while the modest one can be just as underived.

**The correction inherits the finding's credibility.**
The finding was checked --- somebody read the artifact and found the claim too strong --- and the answer arrives inside the same thread, minutes later, wearing the same subject matter.
The scrutiny that landed on the finding reads as covering the reply to it.
It does not.
Nobody has read the replacement against anything.

**It fails in the safe-sounding direction.**
An overclaim invites "prove it".
An underclaim invites nothing, because understating a guarantee sounds conservative, and a reader who suspects you of underselling your own work has no reason to make you derive it.
So the one claim shape that reliably attracts a demand for evidence is exactly the shape a correction is written to avoid.

The remedy does not change.
It is the section above's: run the deriving command, and paste it beside the claim.
What changes is knowing when to expect to need it, and the trigger is lexical enough to use rather than judge --- a **negative** written while conceding a limit.
"nothing asserts against it", "no test covers this", "nothing forbids", "only X closes that" are each a claim about a population, and each is one command away from being checked or refuted.

Three neighbouring rules sit close and none of them reaches this.

- [`learn-from-review-findings`](learn-from-review-findings.md)'s "A fix for a defect class is where a fresh instance of that class hides" is the nearest, and its residual-paragraph case runs the other way: there the fix names a residual and thereby **overstates** a survey nobody ran, and the remedy is to enumerate the class.
  Here the correction **understates** a guarantee, and the remedy is a single command rather than a survey.
- [`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A correction inherits its instrument" governs a replacement figure read off the same gauge as the original.
  That presupposes a gauge was used.
  Here none was, in either the claim or its correction.
- The same file's "A summary written above the account it summarizes escapes the re-read" keys on **position** --- a quantifier placed above the account it generalizes over.
  A correction is a claim about a population that lives somewhere else entirely, so nothing about where it sits marks it.

So the check to add is not a new kind of scrutiny but the existing one, pointed at a sentence that does not look like it needs any.

- **Do:** run the deriving command for any negative you write while narrowing a claim, and paste the command and its result beside it.
- **Do:** treat the reply to a review finding as unverified prose, separately from the finding that prompted it.
- **Don't:** read a hedge as self-evidently safe --- an understated guarantee is a claim about a population, and it can be as false as the overclaim it replaced.
- **Don't:** let the scrutiny a finding received stand in for scrutiny of the sentence answering it.

(Measured 2026-08-22 on [ai-config#1992](https://github.com/Morrison-Lab/ai-config/pull/1992), merged the same day as `593d25cc`.
Commit `fd929f52` claimed that making an argument required meant the unsafe call "cannot be spelled".
The PR's first review found that overclaimed, and commit `97402dea` corrected it --- writing, in the correcting sentence, that a caller passing `argv=[]` reaches the unguarded read "and nothing in that suite asserts against it".
No command was run for that.
An adversarial review of the correction ran one, and commit `a6a0860f` replaced the claim with the narrower true statement now on `main`: the value is asserted at every call site that exists, and nothing forbids a **new** call site spelling it.

Reproduced independently against [ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911), **unmerged** at the time of writing, at branch head `51be639e`:

```
$ python3 hooks/test-no-push-without-self-review.py hooks/no-push-without-self-review.py
All 169 cases passed
$ sed '817s/key, argv, env)/key, [], env)/' hooks/no-push-without-self-review.py \
    > hooks/mut-empty-argv.py
$ python3 hooks/test-no-push-without-self-review.py hooks/mut-empty-argv.py
FAIL (expected blocked=True, got False): an inline -c redirecting the DEFAULT remote is followed, not ignored
FAIL (expected blocked=True, got False): the sibling pushRemote key redirects the same way
2/169 cases failed
```

The call site is at line 912 in the revision `a6a0860f` cites and at 817 at that branch head, so take the site from a grep rather than from the line number.
The mutant has to live in `hooks/`, and the first run of it did not.
Written to the repo root, the same mutation fails 85 of 169, because the hook loads a sibling detector from its own directory --- [`algorithmatize-checks`](algorithmatize-checks.md)'s sixth mutation outcome, a mutant failing for a reason other than the mutation.
What exposes that is running an **unmutated** copy from the mutant's own location, and reading a shared failure as evidence about the location:

```
$ cp hooks/no-push-without-self-review.py ./ctl-root-copy.py
$ python3 hooks/test-no-push-without-self-review.py ./ctl-root-copy.py
85/169 cases failed
```

Identical to the mutant, so the 85 is the path and not the change.
Note which direction that control runs, since the intuitive reading is backwards: it is the control **failing** that attributes the failure elsewhere, and a passing control at some *other* location would have settled nothing.)

## An identifier search is evidence about the identifier, not about the thing it names

Every section above searches a corpus of prose for an idea, and the action a wrong null licenses there is authoring a duplicate.
The same defect reaches a search over a tree of code and assets, where the question is whether an entity is still used and the action a wrong null licenses is **deleting it**.

The mechanism is that such an entity carries two names at once.
It has a canonical identifier --- a citation key, a symbol, a package name, a route --- and it has a describable identity: an author and a title, a function's own words, a vendored directory, a constructed URL.
A region of the tree can reference it entirely by the second, and a region that references nothing by identifier will return zero for **every** identifier you could type, whether or not the entity is used there.
So the null is not weak evidence.
It is guaranteed over that region, the same way a default-branch grep is guaranteed over content that lives only in an open PR.

**Widening the identifier query cannot fix it, which is the near-miss to name.**
The natural response to a doubt is to run the same search again over more paths, or with a looser pattern, or after a fetch.
Each of those is a real improvement to a query that was going to return zero regardless, so each returns zero, and the repetition reads as convergence.
The query is not wrong.
It is about the wrong population.

**The remedy is a negative control over the search space, not a better query.**
Before reading a zero over some subtree as absence, confirm that the subtree contains at least one reference of the form you searched for.
Where it contains none, that subtree is unsearched rather than clean.
This is the same discipline [`batch-merge-and-resolve`](batch-merge-and-resolve.md) requires of a conflict sweep --- a zero matrix and a detector that never ran look identical --- applied to the region rather than to the instrument.
Then search the entity's attributes, which is the query the identifier search cannot substitute for: a surname, a title fragment, the string a config passes where an import would have named the symbol.

**Re-deriving a premise you distrust is what makes this land.**
Checking an old claim before acting on it is the corpus's own advice, so running the check supplies the sensation of having verified it.
The failure here was not skipping verification.
It was verifying thoroughly over a search space where the answer could only come out one way.

- **Do:** name which reference *form* a null covers, since an entity referenced by attribute is invisible to every search for its identifier.
- **Do:** run the negative control on each subtree --- confirm it holds at least one reference of the searched-for form --- and read a subtree holding none as unsearched.
- **Do:** derive a second query from the entity's own attributes before concluding it is unreferenced.
- **Don't:** read a zero over an identifier as evidence that the thing it names is unused.
- **Don't:** answer a doubt by re-running the identifier query over more paths or a looser pattern --- a search blind by construction returns the same zero however far it is widened.
- **Don't:** count having re-derived a stale premise as having derived it correctly;
  the second run inherits the first run's search space.

The same shape covers a symbol a config names as a string rather than importing, a file reached through a variable path, a dependency vendored rather than declared, and an endpoint called through a constructed URL.
[`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md)'s "Do not predict the branch name either" is the adjacent case and a weaker one: there the identifier is a **guess** that may happen to be right, whereas here the identifier is correct and still cannot appear.

(`ucdavis/bcs#514`, 2026-08-28: the issue reported the bibliography entry `klein2003survival` as cited nowhere and proposed deleting it, on the evidence of a grep for `@klein2003survival` across `vignettes/`, `R/`, `man/`, and `inst/docs/`.
The premise was re-derived a month later with `git grep -n klein2003survival` over the whole tree, which returned four hits and no citation, and the deletion was implemented and committed on the strength of it.
`inst/analyses/results/_sec-km.qmd` relies on that work twice in author-year prose, at line 4 for the Kaplan-Meier product-limit estimator and at line 53 for a section-level claim about Nelson-Aalen equivalence.
The whole-tree grep was wider than the issue's and just as blind: that subtree contains no Pandoc citations at all, and the file including it declares no `bibliography`, so no `@key` could have appeared there.
`grep -rniE 'moeschberger|Techniques for Censored'` finds it immediately.
An adversarial-reviewer subagent, dispatched before the push, caught the deletion.)

## A derived figure is supported by a source that never prints it

The section above searches for an entity under the wrong **name**, and its
remedy is a better query --- the surname instead of the citation key, the
title fragment instead of the symbol.
This section is the case where **no** query reaches the answer, because the
figure being checked was never in the source under any description.

A source can print the **inputs** while the citing claim quotes an **output**
computed from them: a normalization, a ratio, a sum, a percentage over counts,
a unit conversion.
Both are faithful to the source, and only one of them is searchable.
So a text search returns zero whether the attribution is sound or fabricated,
which makes the null not weak evidence but no evidence at all --- the same
guaranteed-either-way shape as a default-branch grep for content that lives
only in an open PR.

**The remedy is arithmetic rather than a query, which is exactly what the
section above cannot supply.**
Its bullets each name a search: attributes instead of identifiers, a negative
control confirming the subtree contains a reference of the form you searched
for.
Every one of them still returns zero here, because the negative control is
satisfied --- the source is full of numbers --- and the number you want is not
among them.
Running that remedy correctly and completely leaves you where you started,
with a second null that feels like corroboration.

So before asserting a numeric claim is unsupported, ask what the source would
have to print for the figure to be **derivable**, look for those quantities,
and compute.

**The stake is asymmetric, which is why this earns an extra step rather than a
hedge.**
Asserting misattribution is a public, hard-to-retract claim about someone
else's work, and it lands on an author who then has to disprove it.
The derivation is usually one arithmetic step and settles the question
outright.

- **Do:** ask which quantities would make the figure derivable, find those,
  and compute, before calling a citation unsupported.
- **Do:** record the derivation beside the claim, so the next reader is not
  sent back to the same fruitless search.
- **Don't:** read a text search's zero as evidence against a numeric claim ---
  a derived figure appears in no source that reports only its inputs.
- **Don't:** treat the attribute-search remedy above as covering this case; it
  prescribes a better query, and no query reaches a number the source never
  printed.

(`ucdavis/bcs`, 2026-08-28: the second encounter with this shape in one
session, and the first caught before it was published.
`R/symptom_probs.R` attributes a calibration target to Gangnon et al. (2015)
as "approximately 57% localized, 33% regional, 10% distant".
A research pass searched the paper's text, found none of those percentages,
and was about to file the citation as possibly misattributed.
The paper reports **rates** rather than a distribution: Table 1's 2010
"Without screening" column gives 129.7 localized, 74.3 regional, and 22.5
distant per 100,000, which normalized over the three invasive stages is
57.3 / 32.8 / 9.9.
The attribution was correct throughout, and the search failed only because the
package quotes a distribution the paper never computes.

The first encounter, earlier the same session, was not caught: a `git grep`
for a citation key returned nothing, and `ucdavis/bcs#514` asserted on that
evidence that a bibliography entry was unused.
That is the case the section above records, and the reason it exists --- so
this is a rule firing, matching nothing, and the same failure recurring in a
new surface hours later.

No instrument is proposed.
[`deterministic-tools`](../principles/deterministic-tools.md)'s bar is the
**third** occurrence, and this is the second, so recurrence is established and
building is not yet due.
The stronger reason is that the check is not decidable from the claim's text:
whether a figure is derivable requires arithmetic over an arbitrary source
document, so no matcher over the assertion can see it --- the same conclusion
the negative-existence section above reached about its own rejected guard.)

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

The general case is
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A sound
measurement does not license the claim standing next to it", which covers any
sound measurement followed by a claim it does not establish.
This fragment is the **null-result** instance of that shape, and the one worth
stating separately because a clean zero-hit result reads as thoroughness
rather than as evidence about a pattern.

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
