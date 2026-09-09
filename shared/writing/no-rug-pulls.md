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
