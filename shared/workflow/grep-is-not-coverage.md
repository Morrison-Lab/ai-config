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

## Where this fires

The skills whose workflows run exactly this grep, and whose next step is to
author something:

- [`skill-builder`](../../skills/skill-builder/SKILL.md) step 0, deciding
  whether an existing skill should be extended instead.
- [`ums`](../../skills/ums/SKILL.md) step 3, deciding whether a learning is
  already recorded.
- [`find-overlap`](../../skills/find-overlap/SKILL.md), whose whole premise
  is that phrase matching under-detects.

In each, the null result is an input to a judgment, never the judgment
itself.

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
