Don't write "rug-pulls": present a model, claim, or picture, and then a
sentence or two later retract or replace it.
Every individual sentence in a rug-pull can be true, cited, and checked ---
the defect is in the order, not in any one claim.

## The tells

Treat these as a prompt to check the structure, not as banned strings:

- "X.
  However, the implementation actually Y."
- "In principle X; in practice Y."
- Any sentence whose entire job is to withdraw the one before it.

## Why it passes every check this corpus has

A fact-check confirms each sentence is accurate.
A read-through confirms the paragraph flows.
Neither inspects the thing the rug-pull actually costs: the model the reader
built while reading the first half, and had to discard reading the second.
No existing check in this corpus --- [`fact-check-prose`](fact-check-prose.md),
[`ai-tells`](ai-tells.md), [`plain-prose`](plain-prose.md) --- looks at
*order* across sentences the way this rule has to.

## The near-miss: autobiography instead of exposition

A rug-pull is the natural shape to write when you discovered the facts in
that order.
You started from the idealized model, found the correction, and the prose
narrates that path --- which reads, to the person who wrote it, as a
complete and honest account.
It is: an honest account of the *author's* path to the fact, not an
exposition of the fact for a reader who has not made that journey and does
not need to retrace it.
That is what makes it survive self-review --- nothing about a true,
well-cited, fluently-ordered paragraph looks like a defect from the inside.

## The fix: lead with what is true of the subject

Write the thing that is actually the case first, in full, and present the
alternative --- the idealization, the in-progress work, the historical
approach --- afterward, framed as an extension or as future work.
Do not soften the retraction; remove it, by reordering.

## The exception

Presenting a wrong model first is legitimate when the **reader** already
holds it, and the passage exists to correct that specific belief.
The discriminator is whose model it was: the reader's, walked in with, not
the author's, arrived at during drafting.
A paragraph correcting a documented misconception is not a rug-pull; a
paragraph correcting the author's own first draft, in front of the reader,
is.

- **Do:** lead with what the software, method, or system actually does or
  is, in full, before presenting an idealization, a prior approach, or
  planned work as an alternative.
- **Do:** write the alternative as an extension or as future work, not as a
  correction to something just asserted.
- **Do:** present a wrong model first when the **reader** is known to hold
  it already and the passage exists to correct that belief.
- **Don't:** narrate the order facts were discovered in as though it were
  the right order to present them --- the reader did not make that journey
  and does not need to retrace it.
- **Don't:** soften a rug-pull's retraction sentence; reorder instead, so
  there is nothing left to soften.

## The same failure stretched across revisions: a persisted comment narrating its own edit history

Everything above is about order **within one passage**, read once.
The identical failure recurs across **revisions of one persisted artifact**
--- a Word review comment, a PR reply --- edited in place over successive
builds, where each rewrite narrates what changed instead of stating what is
now true: "Confirmed by the author: the manuscript's intervals use the
naive variance, and this comment no longer asks a question," or
"Withdrawing part of an earlier note here, which claimed..."

The diagnosis is the same one this fragment already gives for the
single-passage case: it is autobiography, not exposition.
The rewrite narrates the comment's own path from question to resolution,
which reads as a complete and honest account to whoever wrote it and is
exactly the wrong content for whoever reads the comment now.
A reader opening a comment thread wants its current state, not a changelog
of the comment itself --- the intervening builds are not information they
need to retrace.

This is the third site this exact principle has landed on, and naming the
other two is more useful than restating the argument a third time.
[`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)'s
"Re-reading each round does not fix it" section gives the same remedy for a
PR body: organize around invariants and an append-only history rather than
around how the change currently works, because a body describing the
mechanism goes stale on every round while one recording present state does
not.
[`ums`](../../skills/ums/SKILL.md)'s anti-patterns list the mirror case for
a memory entry: "patching a sentence the entry's point does not need, round
after round," where the fix is to delete the narrating prose rather than
repair it.
A Word comment and a PR reply are the same shape again --- a persisted
artifact edited across time --- so the remedy carries over unchanged.

Two forms discharge it, matching what each surface allows.
Where the surface supports a reply (a PR comment thread, a review-comment
reply chain), **reply to the earlier comment as a new one** rather than
overwriting it --- the append-only form, which is what the PR-body section
above recommends where restructuring is possible at all.
Where the surface has no reply and only an editable body (a Word comment
tied to a document range), **overwrite it with the present fact and drop
the history** --- state what is now true, with no sentence describing what
the comment used to say or how it changed.

- **Do:** reply to an existing comment as a new comment when the surface
  supports it, rather than rewriting the original in place.
- **Do:** when only in-place editing is available, replace the comment's
  text with the present fact and nothing else.
- **Don't:** write a rewritten comment that narrates its own edit history
  ("no longer asks a question," "withdrawing part of an earlier note") ---
  that is this fragment's rug-pull, persisted across revisions instead of
  compressed into one passage.
- **Don't:** treat this as specific to Word comments; the same rule covers
  a PR review reply and any other persisted, editable annotation.

(User directive, 2026-09-09, reviewing a manuscript supplement: "please stop
including unnecessary past-version-referential comments like 'Confirmed by
the author: the manuscript's intervals use the naive variance, and this
comment no longer asks a question.'
either reply to the previous comment instead of overwriting it, or just
forget the past and just focus on the present and future."
The comments being edited in place, across successive builds, each carried a
line narrating what had just changed in the comment itself.)

(User directive, 2026-09-09, reviewing a manuscript supplement: "apply this
principle throughout your edits to the manuscript files; minimize
'rug-pulls' like the one you had written."
The specific instance: a section on multiple-biomarker likelihoods presented
the idealized joint factorization first, with its equation, and only then
said the released software (v1.4.1) computes something else --- a composite
likelihood.
Every sentence was accurate; the structure still built a model for the
reader to discard, and buried what the software does behind what it does
not do.
The user's diagnosis named the general failure directly: "what you did was
an example of not keeping the prose as simple and straightforward as
possible."
The fix led with v1.4.1's actual composite likelihood, written out in full,
and presented the joint estimator afterward as development-version,
in-progress work.)
