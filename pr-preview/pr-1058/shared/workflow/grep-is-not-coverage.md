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
