When reviewing prose, math, or code, check for unnecessary complexity ---
not just correctness or clarity of meaning. Flag content that is harder
to read, derive, or maintain than the problem requires, and propose a
concrete simpler equivalent rather than just naming the complexity.

This is a review-time check on content that already exists, not a
writing-time style default. [`plain-prose.md`](../writing/plain-prose.md)
and [`avoid-nesting.md`](../coding/avoid-nesting.md) shape a first draft;
this fragment catches complexity that survives those defaults anyway --- a
derivation that grew a special case nobody removed, an abstraction added
for a future need that never arrived, a paragraph that restates its own
point three times. Something can pass every write-time default and still
be more complex than the current problem needs.

## What to check

1. **Prose.** Look for circumlocution at the passage level: a point
   restated from multiple angles, a definition nested behind three
   qualifiers when one would do, a section that could be a sentence. This
   goes further than `plain-prose.md`'s per-sentence rules --- it asks
   whether the *passage as a whole* carries more words than its content
   needs, not just whether one sentence is tangled.
2. **Math.** Look for a derivation, proof, or notation more elaborate than
   the result requires: proving a general case when only a specific one is
   used, carrying an index or symbol the rest of the argument never needs,
   a multi-step derivation where a known identity or direct substitution
   gets there in fewer steps. This differs from `fact-check-prose.md`'s
   reasoning check --- that check asks whether each step *follows*; this
   one asks whether a *correct* derivation is also the *simplest* correct
   one.
3. **Code.** Look for convoluted control flow, an abstraction layer that
   adds indirection without earning it (a wrapper that only forwards to
   one callee, a config system built for variation the codebase never
   exercises), and redundant intermediate steps that don't change the
   result. This is broader than `avoid-nesting.md` (nested calls/
   definitions only), and it's a *standing review check* --- not
   `simplify`'s narrow dead-code-after-refactor sweep, and not `tidy`'s
   separate on-demand audit. Fold this into every normal review pass
   instead of waiting for either to be invoked.

## What to report

1. **What's overcomplicated**, with its location --- quote or point to the
   specific passage, derivation step, or code span.
2. **The concrete simplification**, not just the observation that
   something is complex --- show the simpler prose, notation, or code, or
   describe it precisely enough that the author can apply it without
   re-deriving it.
3. **Why nothing is lost** --- confirm the simplification keeps every
   feature, edge case, and precision the original carried; never trade
   correctness or an honest hedge for brevity.

Silence on a needlessly complex passage reads as "this is as simple as it
needs to be" --- don't let a correct-but-bloated derivation or a
three-layer wrapper through unchallenged just because it isn't wrong.

## Your own work: an idiom is not a workaround

The check applies to what you are about to build, not only to what you review.
The check slips most often at the word "workaround".
Call a language's idiomatic syntax a workaround,
and the label alone seems to license machinery to remove it.
Every agent briefed with that word then builds on it.

- **Do:** before building tooling to eliminate a construct,
  ask whether the construct is idiomatic in its ecosystem.
  Weigh the machinery the tooling adds against what it removes.
- **Do:** prefer the stock engine or tool plus the idiom,
  and fix any real side benefit of the tooling with its own plain fix.
- **Don't:** write "workaround" in a brief or PR for idiomatic syntax;
  name what the construct does instead, so the reader can judge it.
- **Don't:** spread new infrastructure to more files
  before someone has asked whether it was needed at all.

Measured case (Morrison-Lab/mln, 2026-09-28).
Julia chunks ran through JuliaCall's stock knitr engine,
which prints every top-level value.
So assignments ended in `;`, Julia's own idiom for suppressing display.
Briefs called the semicolons a workaround.
A custom 50-line knitr engine was merged to remove them
([mln#197](https://github.com/Morrison-Lab/mln/pull/197)),
and two more PRs were opened to spread it
([mln#202](https://github.com/Morrison-Lab/mln/pull/202),
[mln#205](https://github.com/Morrison-Lab/mln/pull/205)).
The user asked what was wrong with the semicolons.
Nothing was.
The engine's two real benefits had plain fixes:
CI already set `R_LD_LIBRARY_PATH` for a libunwind segfault,
and `global` in a loop handles soft scope.
The engine was dropped, and mln#202 and mln#205 were closed unmerged.
The same rule as [`dont-reinvent-wheel.md`](../principles/dont-reinvent-wheel.md), applied to your own work.

## Relationship to other rules

[`challenge-redundant-content.md`](challenge-redundant-content.md) covers a
related but distinct failure: the *same* content restated in two places
(duplication). This fragment covers a *single* passage being more
elaborate than its own content requires (verbosity), even with no
duplicate copy anywhere. "A point restated from multiple angles" here
means one passage circling its own point several ways, not the same point
appearing twice --- check both fragments on a substantive review, since a
paragraph can fail either, both, or neither.
