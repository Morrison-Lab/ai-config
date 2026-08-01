When reviewing code that implements an algorithm, computation, math, or
statistics, check whether it's *right* --- not just styled well. Use domain
knowledge and, where checkable, an external source (the referenced paper, a
package's own docs, a spec) --- the same evidentiary bar
[`fact-check-prose.md`](../writing/fact-check-prose.md) applies. This is the
code counterpart to that fragment: it fact-checks claims and reasoning
written in prose; this one fact-checks the logic embedded in code itself.

## What to check

- **Strategic correctness (the chosen approach).** Is this the right
  algorithm or design for the problem? A correct-looking implementation of
  the wrong strategy still produces wrong or needlessly costly results ---
  a data structure with the wrong complexity for the expected scale, a
  statistical method whose assumptions don't hold for this data (e.g.
  treating clustered or correlated observations as independent), a
  concurrency strategy prone to races. Ask whether a standard, better-known
  approach exists for this problem that the diff doesn't use --- the review
  counterpart to [`prefer-packaged-functions.md`](prefer-packaged-functions.md),
  but at the level of the overall approach rather than a single function call.
- **Tactical correctness (the implementation).** Given the chosen strategy,
  does the code actually execute it correctly? Off-by-one errors, wrong
  comparison operators, sign errors, a formula transcribed incorrectly from
  a paper or spec, mismatched units or dimensions, incorrect edge-case or
  boundary handling, numerical instability (catastrophic cancellation,
  overflow/underflow).
  **A unit/scale conversion fix applied on the way into a computation needs
  the same check on the way out.** When a function rescales an input (e.g.
  years → days) so it's dimensionally consistent with some internal
  computation, any of that rescaled value that gets returned or reused
  downstream needs converting back --- otherwise fixing the input-side mismatch
  just moves the same bug to the output side. Check every quantity the
  rescaling touches, not just the one the original bug report named.
  (serocalculator#552: fixing a day/year mismatch on a function's *input*
  correctly rescaled an `age_range` parameter before use, but the resulting
  `age` column --- derived from that same rescaled range --- was returned
  unconverted, so it shipped ~365x too large; caught by a follow-up review
  round, not the same pass that fixed the input side.)
- **Math and statistics embedded in code.** When code implements a formula,
  statistical test, or model, verify it against its source (a paper, a
  textbook, a package's reference implementation, a spec) with the same
  rigor `fact-check-prose.md` applies to a derivation --- don't assume a
  formula is right because the code compiles and runs. Re-derive or
  spot-check by hand, or construct a small worked example with a known
  answer and compare it against the code's output.

## Check tests the same way, especially for assertions that cannot fail

A test is code, so it gets the same correctness scrutiny as the code it
guards --- and it has a failure mode of its own: **a vacuous assertion**,
one that passes no matter what the implementation does. That is worse than
no test, because it reads as coverage in a diff and in a coverage report.

The common shape is an assertion over a collection that the test also
expects to be empty. In R, `any(logical(0))` is `FALSE` and
`all(logical(0))` is `TRUE`, so both of these always pass when `out` is
`character(0)`:

```r
expect_false(any(grepl("bad", out)))
expect_true(all(nzchar(out)))
```

The same trap exists everywhere: a loop-based check over an empty list, a
`for` assertion with no iterations, a filter that matches nothing before
the assertion runs. Python's `all([])` is `True` for the same reason.

Two ways out, in order of preference:

1. **Give the assertion real content to run against**, so it actually
   evaluates --- add an element to the input that survives to the output.
   This keeps the check and makes it meaningful.
2. **Delete it**, when a sibling assertion already covers every failure
   mode it was meant to catch. A redundant assertion is not harmful, but a
   vacuous one misleads.

**Then prove the test fails against the unfixed code.** Temporarily revert
the fix (or introduce the specific defect the test targets), confirm the
test fails with the message you expect, and restore. A test written after
the fix has never once been observed failing, so nothing yet establishes
that it can. Quote the observed failure in the PR --- it converts "I added a
test" into evidence.

### The proof step has its own vacuous mode

The remedy above is itself a piece of code that can fail to do anything, and
it fails in the same direction as the assertion it was meant to validate.
The mechanism: you impose the failure condition from outside, and **the code
under test re-establishes it internally**, so the state you were trying to
create never exists.

```sh
PATH=/usr/bin:/bin ./wrapper     # meant to starve a binary lookup
```

If `wrapper` prepends its own directory to `PATH` before looking anything up
--- a reasonable thing to do, since a GUI-launched process may not inherit a
login shell's `PATH` --- then the restriction is overwritten before the guard
runs.
The guard never fires and the script exits 0.

That is worse than an ordinary vacuous assertion, because it launders an
untested guard into a verified one during the very step added to prevent that.
It also carries the [`fail-fast`](../principles/fail-fast.md) signature: the
failure path and the pass path produce the same observable.

- **The tell.** A "should fail" run and a "should pass" run print the same
  thing and exit the same way.
  A negative control that is indistinguishable from the positive case proved
  nothing.
- **The check.** Before trusting the control, grep the code under test for
  assignments to whatever you are controlling --- `PATH`, an env var, a config
  path, the clock.
  One grep usually settles it.
- **The fix.** Assert the guard's *own* message and exit status rather than a
  bare exit code, and impose the condition somewhere the code cannot undo:
  strip the overriding line into a copy under test, or set the override
  variable the code itself consults.

- **Do:** confirm a negative control produces a *different* observable than
  the passing case, before believing what it proves.
- **Don't:** conclude a guard works because a run you expected to trip it
  exited cleanly.

In review, flag an assertion whose expected value makes it unfalsifiable,
and ask for the failing-run evidence when a PR claims a test covers a
specific regression.
Read that evidence rather than accepting its presence: a quoted run that
exits cleanly is the vacuous-control shape above, not a proof, so the
failing output has to look *different* from the passing output.
(d-morrison/altdoc#43: an ordering-constraint test
asserted `expect_false(any(grepl("_GITHUB", out)))` while also expecting
`out` to be `character(0)`, so it could never fail; fixed by adding an
input line that survives substitution, then verified by swapping the two
source lines into the wrong order and watching both assertions fail on the
resulting `"* [GitHub](_GITHUB)"` residue.)

## When the runtime is available, run the claim instead of reasoning about it

Every check above can be done by reading.
Most of them can be *settled* by execution, and when the language runtime is
present in the session, execution is both cheaper and stronger than the
careful reading it replaces.
This is [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)
pointed at your own diff: a claim about what a function returns is decidable
by calling it, so calling it is the check.

The claims worth executing are the ones that feel too settled to bother
with --- what a call returns on an edge input, which of two forms errors, a
printed value quoted in a comment or a doc.
Confidence is not the filter, because a claim you are confident about is
exactly the one you will publish without support.
So the filter is simply: *is this checkable here, right now?*
Install the package if it is missing rather than downgrading the claim to a
hedge; one `install.packages()` usually costs less than a review round.

Two habits make it pay off beyond the one check:

- **Paste the verified output into the fragment or comment**, so the next
  reader inherits the evidence rather than re-deriving it.
- **Say what you ran and what version you ran it on.** Behaviour is
  version-dependent, so "verified on rlang 1.3.0" survives contact with a
  future reader in a way "verified" does not --- the same reasoning
  [`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md)
  applies to prose.

(ai-config#774, 2026-07-28: a fragment stated that R's `[[` errors on a
missing name in a list, offered as the strict counterpart to `[`.
The book's own out-of-bounds table contradicted it, and one call settled it
--- on R 4.6.1, `list(a = 1)[["b"]]` returns `NULL`, and only an
out-of-bounds *integer* index errors.
Stamping the version here is the habit this section asks for, not a hedge
about base R: `[[` is about as stable as R gets, and recording what you ran
it on costs a parenthetical either way.
The stamp is worth least exactly where you are most sure, which is why it
is easiest to skip there.
The claim had been written precisely because it felt obvious.
The same pass executed the other five behavioural claims in the diff, all of
which held, and the reviewer independently confirmed each one --- so the
cost of being wrong here was one wrong sentence caught before review rather
than a finding.)

## Matching values is not matching roles

When checking whether our code follows a reference implementation, confirm the
matched quantity plays the **same role** in both systems.
Equal values are not agreement.

The failure is a `grep` for a constant that finds it in the reference and
stops there.
Two things make it more persuasive than an ordinary bad lookup.
A matching number feels like *verification* rather than inference, so the
check feels finished the moment the grep returns.
And the coincidence is often structural rather than lucky: when both
quantities derive from the same underlying schedule, geometry, or protocol,
they are *bound* to share values while meaning different things --- which is
exactly when this error is likeliest and least visible.

Read what surrounds the match rather than the match alone.
One line of context usually names the role: the comment above it, the
assignment target, the procedure it feeds.
Then state the role in the finding, since "the reference uses 18 months to
filter exams and we use it as a readout horizon" is falsifiable while "the
reference uses 18 months too" is not.

Be most careful when the match *confirms* something already decided.
A coincidence that agrees with the expected answer gets less scrutiny than a
surprising one, and it arrives at the moment it will be acted on.

- **Do:** name what the number does in each system before reporting agreement.
- **Do:** treat a shared origin as grounds for more care, not as corroboration.
- **Don't:** conclude one implementation follows another because a constant
  appears in both.
- **Don't:** relax the check because the match supports a decision already
  taken.

(2026-07-31, `ucdavis/bcs#539`: R constants of 18 and 30 months were reported
as following the SAS, on the strength of finding both numbers in the SAS
source.
The SAS comment one line up reads "ignore a diagnostic exam if the difference
between this diagnostic examdate and the previous examdate is outside the
annual screening window 11-18 months" --- exam eligibility, not an estimation
horizon.
Both quantities derive from the same screening schedule, which is why they
coincide.
Withdrawn the following round, when review also found the R constants live in
simulation-validation code the real pipeline never calls.)

## What to report

For each issue found, state:

1. **Whether it's strategic or tactical.** The fix differs: a strategic
   mistake needs a different approach; a tactical mistake needs a
   correction within the existing approach. Don't file "the algorithm is
   wrong" when the algorithm is right and only a line of it is wrong, or
   vice versa.
2. **The specific line or function**, and what's wrong with it.
3. **The basis for the judgment** --- cite the source checked (a paper, a
   spec, a package's reference implementation, a hand-worked example) so
   the finding can be verified without re-deriving it.

Distinguish blocking correctness issues from optional "there's a better
approach" suggestions, and don't let a plausible-looking implementation pass
unchecked just because it runs without error.
