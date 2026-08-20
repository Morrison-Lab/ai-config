When reviewing code that implements an algorithm, computation, math, or
statistics, check whether it's *right* --- not just styled well. Use domain
knowledge and, where checkable, an external source (the referenced paper, a
package's own docs, a spec) --- the same evidentiary bar
[`fact-check-prose.md`](../writing/fact-check-prose.md) applies. This is the
code counterpart to that fragment: it fact-checks claims and reasoning
written in prose; this one fact-checks the logic embedded in code itself.

Worked-example case records for the rules below live in
[`fact-check-code-logic.cases.md`](fact-check-code-logic.cases.md), moved out of the auto-loaded context.

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
  **When one parser construct becomes tolerant of a condition,
  audit its siblings for the same condition.**
  A regex or parser that handles CRLF, indentation, escaping,
  or blank-line boundaries in one construct
  makes the file *look* tolerant of that condition.
  That appearance is dangerous if sibling constructs still hard-code
  the old assumption.
  Grep for every construct that consumes the same syntax class,
  not only the one a reviewer named,
  and add fixtures that move the measurement in both directions.
  A missed sibling can create either a false inclusion or a false exclusion,
  so a one-sided test is not enough.

  - **Do:** grep for every sibling parser construct
    when one construct gains tolerance for a syntax condition.
  - **Do:** add fixtures that prove the tolerance works in each direction
    the measurement can move.
  - **Don't:** treat one CRLF-aware or indentation-aware regex
    as evidence the file is tolerant as a whole.
  - **Don't:** test only the construct the reviewer named
    when neighbouring constructs parse the same text.

  (Morrison-Lab/ai-config#1029:
  round 5 made `_ANCHORED_IMPORT_RE` tolerant of CRLF,
  but round 7 found fence closers and span blank-line bounds still LF-only.
  The remaining two defects moved the context-closure measurement
  in opposite directions,
  so the earlier CRLF-looking code hid both.)
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

### A test gated on a production constant loses coverage when that constant moves

Everything above concerns an assertion that cannot fail **today**.
This one asserts perfectly well today and stops running later, because its
**applicability** was derived from a production value rather than from the
property under test.

The shape is a guard around the case rather than inside it:

```python
ALLOWLISTED = set(prod.KNOWN_UNREGISTERED)   # sourced from the real constant

if ALLOWLISTED:
    check_every_entry_is_still_unregistered()
    check_no_entry_is_stale()
```

That is right while the constant has members, and the constant is usually one
declared to shrink --- an allowlist, a deprecation set, a known-failures list,
whose own comment says it should only ever get smaller.
So the coverage disappears **exactly when the feature is next edited**, since
emptying the constant is the edit everyone is working toward.

Two things separate this from the vacuous assertion above.
Its failure is in the **future** rather than at authoring time, so no
mutation, no negative control, and no failing-run evidence taken today can
show it --- every one of those checks passes, correctly, on a populated
constant.
And it degrades to a **skip** rather than to a false pass, which reads as
information rather than as a gap: a suite reporting `2 skipped` looks like it
is telling you something, and what it is telling you is that the code path is
now exercised by nothing.

Inject a synthetic value so the case always runs, and keep one case against
the real constant so the two questions stay separate:

```python
def test_allowlist_hygiene_synthetic():
    check_every_entry_is_still_unregistered({"fake-entry"})   # always runs

def test_allowlist_hygiene_live():
    check_every_entry_is_still_unregistered(prod.KNOWN_UNREGISTERED)
```

The synthetic case tests the **logic**, which does not depend on how many
entries production currently has.
The live case tests the **corpus**, and is allowed to be vacuous once the
constant empties, because that is the state it exists to confirm.

- **Do:** derive a test's applicability from the property under test, and feed
  the production constant in as data rather than as a gate.
- **Do:** ask, of any `if <constant>:` wrapping a test body, what the suite
  covers once that constant reaches its intended value.
- **Don't:** read a skip as coverage --- it reports that the case did not run,
  which is the same outcome as not having written it.
- **Don't:** treat a passing mutation test as clearing this; a populated
  constant makes every check today report correctly.

(Morrison-Lab/ai-config#1507, 2026-08-16: three allowlist-hygiene cases in
`scripts/test_check_hook_catalog.py` ran under `if ALLOWLISTED:`, sourcing
`ALLOWLISTED` from the script's real `KNOWN_UNREGISTERED`, whose own comment
says it "should only ever shrink".
A reviewer caught that emptying it --- the declared goal --- would silently
retire all three.
Tracked as
[#1519](https://github.com/Morrison-Lab/ai-config/issues/1519).)

### Mutate the fix, not only the test

The rule above says a regression test must be seen to fail.
The cheapest way to make that routine is mutation testing:
temporarily revert, delete, or corrupt the exact fix,
then run the new test and require it to fail for the intended reason.
Reading the test is not a substitute.
A vacuous test usually looks targeted,
because it was written from the same mental model that produced the fix.

Six distinct mechanisms can make a test pass against the reverted fix:

- **Wrong entry point.**
  The test calls a helper directly,
  while the bug lives in the caller or parser path that feeds it.
- **Earlier guard.**
  The fixture is caught by a pre-existing check
  before it reaches the branch the new test claims to exercise.
- **Neighbouring mechanism.**
  Another rule strips or rewrites the fixture incidentally,
  so the assertion passes for the wrong reason.
- **Boundary fixture.**
  The fixture sits on a line or span boundary
  where existing syntax rules already make the changed behaviour irrelevant.
- **Wrong expectation.**
  The asserted behaviour contradicts the specification,
  so the test protects a bug rather than the fix.
- **Misleading label.**
  The test name or comment says one property is under test
  while the assertion checks another.

Those are test bugs,
not merely weak tests.
A suite with all six can still be green,
and coverage can still report the lines as exercised.
Only the mutation answers whether the assertion depends on the fix.

- **Do:** mutate the exact fix and watch the new test fail before trusting it.
- **Do:** route the fixture through the real entry point
  and confirm it reaches the branch whose behaviour the test names.
- **Don't:** accept a test because it mentions the helper that changed,
  or because a coverage report marks the line covered.
- **Don't:** trust a test label as evidence of what the assertion checks.

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

## A "safe because X never happens" comment needs its own counter-example before it ships

When a fix's safety rests on a claim that some input shape "never" happens or "is not realistic phrasing" --- a live finding won't describe itself this way, a user never types that --- construct the counter-example yourself and run it through the actual code before writing the comment, not after a reviewer does it for you.
The claim reads as reasoning, but it is a factual assertion about a population of possible inputs, and "I can't think of a case" is not the same evidence as "I tried to construct one and it didn't work."

The tell is a comment or docstring asserting "X is not realistic" or "this never happens in practice" sitting beside the exact regex or conditional whose safety depends entirely on that claim being true.
That is checkable, by this fragment's own ["run the claim instead of reasoning about it"](#when-the-runtime-is-available-run-the-claim-instead-of-reasoning-about-it) section above --- the difference here is which claim to run: not "what does this return", but "can I construct an input that breaks the thing I just asserted can't happen."

A single refutation is a normal review finding.
What makes it worth a rule of its own is a SECOND refutation of the same underlying ambiguity on the same fix, because that is the signal the first counter-example didn't generalize from --- a narrower patch closed the one case found without closing the *class* the case belonged to.

- **Do:** for every "X never happens" / "not realistic phrasing" safety claim in a comment, write the adversarial counter-example and execute the actual function against it before shipping.
- **Do:** treat a second reviewer refutation of the same underlying ambiguity as a signal to search for the general class of counter-example, not just patch the specific instance found.
- **Don't:** ship a safety claim in a comment that was reasoned about but never executed against an adversarial input.
- **Don't:** treat one fixed counter-example as proof the class is exhausted --- the next one can share its shape exactly.

(Morrison-Lab/ai-config#1762, 2026-08-20: a citation-stripping regex fix shipped two consecutive safety claims in the same docstring --- first that a live finding "does not describe itself that way" [adjacency alone], then, after that was refuted, that adjacency plus co-occurring wording was sufficient.
An external reviewer refuted both by constructing and executing a counter-example, in two separate review rounds on the same PR, despite this fragment's own execution-based verification section already existing in the corpus at the time either comment was written.)

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

## A docstring that explains why, but not how, misattributes the mechanism

A docstring can be entirely correct and still hide a dead parameter, if it states the *reason* a behaviour holds without saying *how* the code produces it.
A reader --- including the author, in self-review --- fills the gap with whatever is nearest at hand, and the nearest thing is usually a parameter sitting right there in the signature.

The shape: a function takes a parameter the body never reads, and a comment or docstring above it explains a real, correct fact that sounds like it depends on that parameter.
"The root file is excluded because `--root-char-cap` already governs it" is true.
It does not say the exclusion is implemented by checking depth, so a reader credits the unused `root` argument with doing the excluding, when a `depth > 0` filter elsewhere does the actual work.
Nothing about the sentence is false, which is what makes it survive review: there is no wrong claim to catch, only a mechanism the sentence never names.

This is not the same failure as [`reuse-docs-and-args.md`](reuse-docs-and-args.md)'s doc-reuse rules, which are about a docstring going stale relative to the code it describes.
Here the docstring is accurate throughout --- the gap is that it explains a fact instead of a mechanism, and an unrelated parameter absorbs the explanation by proximity.

The check is to ask, of every sentence justifying a behaviour, whether it names the line, branch, or filter that produces it.
A sentence that would still read true with the parameter deleted is explaining the *why*, not the *how*, and the parameter it sits beside is a candidate for being unused.

- **Do:** state the mechanism a docstring is invoked to justify --- the actual line, branch, or filter --- not only the reason the behaviour is correct.
- **Do:** check whether a nearby parameter is actually read by the code the docstring describes, whenever the docstring explains a fact rather than a mechanism.
- **Don't:** treat a docstring as covering a parameter's purpose merely because it explains something true about the parameter's neighbourhood.
- **Don't:** read "the docstring makes sense" as evidence a parameter is used --- a correct sentence can justify behaviour that a different part of the function actually implements.

(Morrison-Lab/ai-config#1406: `render_fragment_caps(files, root, cap)` carried a docstring reading "The root file is excluded because `--root-char-cap` already governs it," and `root` was never referenced in the function body --- the exclusion was a `depth > 0` filter.
Caught as a non-blocking review note.
Restating the docstring to name the depth filter made the parameter visibly redundant, and it was removed.)

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
