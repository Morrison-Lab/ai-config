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

Seven distinct mechanisms can make a test pass against the reverted fix:

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
- **Rejected payload.**
  The sharpest form of the earlier-guard case:
  a parsing or validation layer in front of the code under test
  refuses the fixture outright, so nothing under test runs at all.
  It is likeliest when the defect is input-shaped,
  since the payload has to be malformed to reach the bug,
  and malformed is what the layer above rejects it for.

Those are test bugs,
not merely weak tests.
A suite with all seven can still be green,
and coverage can still report the lines as exercised.
Only the mutation answers whether the assertion depends on the fix.

- **Do:** mutate the exact fix and watch the new test fail before trusting it.
- **Do:** route the fixture through the real entry point
  and confirm it reaches the branch whose behaviour the test names.
- **Do:** make "the fixture arrived" an assertion in its own right ---
  a parse step's return value, a counter, a log line ---
  rather than a thing you satisfied yourself of once by reading the code.
- **Don't:** accept a test because it mentions the helper that changed,
  or because a coverage report marks the line covered.
- **Don't:** trust a test label as evidence of what the assertion checks.
- **Don't:** read a green guard as one whose subject ran.
  A payload rejected upstream and a working fix are the same observable.

### A predicate a fix adds needs mutation in both directions, not just reversion

The mutation above proves the fix is needed, by reverting it and watching the
predicate never fire.
That is one direction.
A predicate that decides between two outcomes --- admit or exclude, keep or
blank --- can also fail by firing on **more** than it should, and reverting
the fix cannot exercise that side at all: removing the predicate makes it
fire on *nothing*, never on *too much*.

The near-miss is running the revert-mutation, watching the new test fail,
and reading that as "mutation-tested."
It is mutation-tested in one direction.
The revert answers "does this catch the case it was written for," not "does
this also spare the cases it wasn't."

Two mutations answer the two questions, and neither substitutes for the
other:

- **Revert (under-inclusive).**
  Delete or disable the fix.
  The predicate should now fail to protect what it protects, and the test
  that catches the original bug should fail.
- **Over-broaden (over-inclusive).**
  Widen the predicate's trigger condition --- loosen a marker list, drop a
  qualifying clause, relax a proximity check --- and confirm a case that
  should survive now gets wrongly caught.
  This needs its own fixture, built to sit in the specific gap the widened
  predicate opens, not a generic input the narrower, correct predicate was
  never going to catch either way.

Each mutation catches exactly one side, and "run both directions" is easy
to over-generalize into a claim about the wrong side --- the version this
section shipped with the first time, until review caught it:

```
                        revert (fires on nothing)   over-broaden (fires on everything)
positive fixture        should now FAIL             should still pass
(bad input -> caught)
negative control        still passes                should now FAIL
(benign -> not caught)
```

A positive fixture is blind to over-broadening: it already expects to be
caught, so widening the predicate cannot break it.
A negative control is blind to revert, the opposite way: with the
predicate gone, nothing is caught, so a benign case stays correctly
un-caught whether the control ever sat on the predicate's real boundary or
not --- a well-targeted control and an inert one look identical under
revert.
Only over-broadening can tell them apart.
A control asserting a property of the fixture rather than of the predicate
is the extreme case of inert: it proves nothing under either mutation,
because it never runs the code under test at all.
That reads as rigor --- the comment above it usually says exactly what
property it is isolating --- which is what makes it the harder of the two
gaps to catch by reading rather than by mutating.

The general shape is worth naming past this one paragraph: a quantifier
over a pair --- both, either, each of --- reads as symmetric and often is
not, and a sentence asserting it can be wrong in one direction while
sounding complete in both.
The table above cannot fail that way, because enumerating the cases forces
each one to be written down rather than assumed from the other.
[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
quantifier section covers checking one you already wrote against its
population; this is the authoring-side move --- reach for the enumeration
before the quantifier, for any claim over a pair whose two halves might
not behave the same way.

- **Do:** run both mutations --- revert, and over-broaden --- on every
  predicate a fix adds that decides between two outcomes.
- **Do:** build the over-broaden fixture to sit in the specific gap the
  wider predicate opens, since that is also the fixture a negative control
  needs to prove itself against.
- **Do:** confirm a negative control fails under the over-broaden mutation
  specifically, not only that the fixture contains what its comment
  claims.
- **Don't:** read "the revert-mutation failed" as mutation-tested; it is
  half of it.
- **Don't:** expect a negative control to fail under revert --- a benign
  case stays uncaught whether the predicate exists or not, so that
  direction cannot distinguish a real control from an inert one.
- **Don't:** trust a control whose assertion is about the fixture's
  contents rather than about what the predicate does with them.

(Morrison-Lab/ai-config#1862, 2026-08-21, two review rounds.
The PR added `is_non_review_notice()` to exclude bot workflow-status
notices from a review-item set.
Its precedence guard, meant to protect a genuine review from that
exclusion, used a 3-marker check while the admission gate it protected
used 6 --- a fallback self-review wide enough to be admitted was not wide
enough to be protected, and was silently excluded.
That is the over-inclusive direction of an exclusion predicate, and the
suite's own revert-mutation could not have found it: reverting the fix
removes the exclusion outright, it does not narrow the guard that is
supposed to spare genuine reviews from it.
The same round's "negative control" for the marker window substituted an
unrelated fixture rather than isolating the marker text; over-broadening
the marker list to absurd values still passed it, proving it was inert.
Both were reviewer findings.

Morrison-Lab/ai-config#1867: `blank_verdicts_citing_a_comment()` blanked a
not-clean verdict phrase whenever it sat near any comment permalink, with
no requirement that the surrounding text say the finding was resolved.
The suite held a "permalink, resolved" fixture and a "live finding, no
permalink" fixture --- never the combination, which is exactly what a live
finding re-raised with its own citation looks like.
A reviewer built that missing fixture and the phrase was wrongly blanked.)

(Measured 2026-08-21 on `Morrison-Lab/gha#576`, two more instances in
one review session.
A suite carried two cases meant to prove a check's fix.
Both passed with the fix reverted, because a different part of the
same new logic already made those specific inputs quiet --- the
Neighbouring-mechanism gap in "Mutate the fix, not only
the test" above.
The case that actually discriminated the fix was the opposite
polarity from what had been written: the suite held negative
controls, and what the fix needed was a positive fixture --- an input
that must be flagged and, under revert, was not.
See
[`algorithmatize-checks.md`](../workflow/algorithmatize-checks.md)'s
"When a mutation survives, the first hypothesis is that the mutation
was wrong" for the general form this instance is one of three of, all
on the same PR.)

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

## A signature change's caller set is derived by grep, never from the callers you can see

Adding or retyping a parameter on a shared function changes every call site at once, and the call sites are not a property of the file you are editing.
Another module in the same repo can load yours and call it while your file says nothing about it, so a careful and entirely correct reading of the code in front of you enumerates a strict **subset** of the population --- and does it in a way that feels like diligence, because the reasoning about each caller you did name was sound.

That is [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s scope claim in its most mechanical form.
"The callers" is a claim about a population, the population is one grep away, and per [`algorithmatize-checks`](../workflow/algorithmatize-checks.md) a decidable check does not get spent on reasoning.

**Key the grep on the call, not on the import.**
A module can be loaded dynamically --- `importlib.util.spec_from_file_location` is the usual Python form, and a script whose filename contains a hyphen can only be loaded that way --- so there is no `import <module>` line to find, and a grep for one returns nothing while reading exactly like a clean result.
Search for every function whose signature the change touched, not only the one you edited:

```bash
grep -rn '\.classify(\|\.collect(' --include='*.py' .
```

- **Do:** derive the caller set with a grep keyed on the call, before pushing a signature change.
- **Do:** grep for every function the change touched, since one edit usually moves more than one signature.
- **Do:** run the *importing* module's tests too, not only the edited module's.
- **Don't:** substitute reasoning about the callers you can name --- that enumerates the sample and reports it as the population.
- **Don't:** grep for the import statement and stop;
  a dynamically loaded module has no import line to match.

(Morrison-Lab/ai-config#1841, 2026-08-21: `classify()` in `scripts/check-install.py` gained a required `repo_roots: set[Path]` parameter.
The session hook and the CI job were both traced and both correct.
`scripts/check-harness-installs.py` loads the module through `spec_from_file_location` and calls `ci.classify()` and `ci.collect()`, was never searched for, and CI failed with `TypeError: 'PosixPath' object is not iterable`.)

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

(Morrison-Lab/ai-config#1762, 2026-08-20: a citation-stripping regex fix went through three review rounds.
Round 1 refuted the FIRST shipped claim --- "a genuine bold-labeled finding in parens is never blanked" (a co-occurring-wording gate) --- with a live finding that mentioned "the previous round" in its own text.
Round 2 refuted the SECOND shipped claim --- "a live finding does not describe itself that way" (adjacency alone) --- with a live finding re-raised across rounds using the identical citation syntax.
Only the THIRD version, which added an explicit resolution-wording requirement on top of adjacency, was approved ("Ready for merge"), with one narrow residual gap the reviewer explicitly judged non-blocking.
Both refuted claims were found by the reviewer executing a constructed counter-example, not by the author testing one first, despite this fragment's own execution-based verification section already existing in the corpus at the time either claim was written.)

## A comment beside a value you changed is part of the edit

Changing a literal --- a cap, a threshold, a timeout, a path, a flag --- edits every comment near it that states, computes from, or justifies that literal.
Read the neighbourhood before changing the value, and change the comment in the same commit.

The failure is easy to miss because nothing about it looks like an omission.
The changed line is correct, the diff is small and legible, and the surrounding comment is not in the diff at all, so a reader reviewing their own change sees only lines they meant to write.
What the reader does not see is the line that now contradicts them, and a stale comment is worse than no comment, because a reader trusts it exactly as much as the code.

Three things go stale at once, and they are worth separating because only the first is obvious.
The **stated value** is the visible half.
The **arithmetic derived from it** goes with it, so a comment reciting a product or a total is wrong by whatever factor the value moved.
The **justification** is the half that actually matters, because a comment explaining why a value was chosen frequently records a **prior incident** --- an outage, a resource exhaustion, a bug that motivated the limit.
Editing the value without reading that justification means changing a number whose reason you never learned, which is a different and larger mistake than leaving a stale sentence behind.

The corpus already states scoped versions of this and none of them fires here.
`memories/preferences.md` says to grep both code and comments when renaming a **concept**.
[`simplify`](../../skills/simplify/SKILL.md) calls a vestigial comment worse than none, as a cleanup pass rather than at edit time.
[`check-dependency-updates`](../../skills/check-dependency-updates/SKILL.md) says a stale comment beside a fresh SHA is its own bug, for **pinned dependencies** only.
The general case --- any literal, at the moment it is edited --- is what this section adds.

The condition is decidable from the diff alone, with no semantics: a literal leaves a changed line, and an unchanged comment line nearby still carries it.
So it is mechanized, per [`algorithmatize-checks`](../workflow/algorithmatize-checks.md), by `hooks/flag-stale-adjacent-comment.py`.
That guard **warns and never blocks**, because a comment quoting a value historically --- a changelog line, a "was N until ..." note --- is a real and common false positive it cannot distinguish from a stale assertion.
Reading the flagged comment is the whole of the response.
Confirming it is deliberately historical discharges the warning.

- **Do:** read the comment lines above and below a literal before changing it, and update them in the same commit.
- **Do:** treat a comment that justifies a value as a record of a past incident, and find out what happened before overriding it.
- **Do:** recompute any arithmetic a nearby comment derives from the value.
- **Don't:** read "my changed line is correct" as the change being finished --- the line that contradicts it is the one outside your diff.
- **Don't:** dismiss the hook's warning without reading the comment it names.
  The false-positive case is confirmed by reading, not by assuming.

(`ucdavis/bcs#679`, 2026-08-20: `#SBATCH --array=1-25%6` was raised to `%20` in `data-raw/ab507bs-imp.sbatch`.
The four comment lines directly above went untouched, so they still said 6, their stated 192G total was now wrong by more than a factor of three, and they still recorded the incident that had motivated the cap --- an unbounded array previously drained a node with an unkillable process stuck on network I/O.
Only the directive line was ever read.
An AI reviewer returned "Needs more work" on the contradiction.)

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

## A rationale can be false while the code it justifies is correct

The section above covers a docstring that is **true and incomplete**.
This is a related but distinct failure: a comment, docstring, or PR rationale
that is **explicitly false**, sitting beside code that works.
The contrast is omitted mechanism versus incorrect explanation, and it is
worth keeping sharp, because a rationale that merely *understates* how
something works belongs to that section rather than this one.

The pairing matters because the two are told apart only by checking, and
nothing about either one feels like a claim while you are writing it.
A rationale is written in the same breath as the code, from the same
understanding, and it inherits the code's air of having been verified ---
the code was tested, so the sentence about the code feels tested too.
It was not.
Tests exercise behaviour, and a rationale is a claim about *why* the behaviour
holds --- so an ordinary behavioural test can pass with the explanation still
false.

The failure has a signature worth learning:

- **The artifact is right, so nothing fails.**
  No check goes red and no output is wrong, so the defect is invisible to the
  behavioural checks a change normally runs.
- **The claim is checkable in seconds**, and usually by a command adjacent to
  what you already ran --- reading the function's documented defaults, grepping
  the file you cited, checking which commit introduced a line.
- **It survives review** unless a reader independently verifies the claim,
  because the natural review question is whether the code works.

**A rationale that reasons about defaults is particularly easy to get wrong**,
because the default is the thing you did not write and therefore did not think
about.
"Safe here, because the caller validates the input" is false when the caller
validates nothing and the safety comes from a filter further upstream ---
and note that the code is still safe, which is what makes it an instance of
this pattern rather than of a bug.
Deleting the sentence would leave a correct program; keeping it teaches the
next reader to protect the wrong invariant.
Read the signature and the call site rather than the intent.

The check is one question per justifying sentence:
**what command would show this false?**
If a command exists and takes seconds, run it before the sentence ships.
If none exists, the sentence is not a rationale but a guess, and should be
written as one.

- **Do:** run the deriving command for a rationale's factual claim --- the
  documented defaults, the introducing commit, the cited file's text --- and
  publish it beside the claim where the claim is load-bearing.
- **Do:** treat a sentence explaining *why* code is correct as unverified until
  checked, however thoroughly the code itself was tested.
- **Don't:** let a rationale inherit the code's credibility --- the tests
  covered the behaviour, never the explanation.
- **Don't:** reason about a call's semantics from its intent when its
  **defaults** decide them.

**Not decidable by a guard, though partly checkable by hand.**
The condition is "a sentence asserting why code behaves as it does is false",
and deciding it means evaluating the claim against the world, which no
transcript-scoped trigger can do.
A cue-word proxy --- `because`, `so that`, `rather than` --- would carry
unacceptable error in both directions: it fires on correct rationales that use
those words, and misses false ones that do not.
That is a claim about a *truth detector*, not about checkability in general.
The specific checks named above --- reading documented defaults, grepping a
cited file, finding the commit that introduced a line --- are exactly the
mechanical steps that settle individual instances, and they are why this is a
review question and a self-check rather than a guard.

(Measured 2026-08-21, three instances in one session, each caught by a
reviewer rather than by any check, and in each the artifact itself was
correct.
A fragment's prose about a hook attributed an omitted gate to "earlier fixes
rather than the original design", where `git log -S` put it in the hook's own
first PR, ai-config#1566 (ai-config#1860).
The gate was real and the hook was right; only the sentence about where it
came from was wrong.
`fully-clean.md` said a checker "annotates duplicated names automatically",
where it annotates only the lines it reports, never a passing one ---
which was the very case the passage illustrated (ai-config#1870).
And a PR rationale justified a reword by saying "the same entry already uses
the long form", where the entry used the abbreviation (ucdavis/bcs#725).

A fourth candidate was dropped on review, and the reason is instructive.
An R helper's comment claimed it used R's own regex engine "rather than
reimplementing the matching and risking a divergence", while calling `grepl()`
with defaults that are case-sensitive POSIX ERE, against `.Rbuildignore`
patterns that Writing R Extensions specifies as Perl-like and
case-insensitive (ucdavis/bcs#720).
That looks like this section's pattern and is not: the **code** diverged from
the semantics it was implementing, so the artifact was not correct, and the
sentence stayed arguably true while omitting which mode was selected ---
which is the preceding section's failure, not this one's.
The test of membership is whether the artifact would still be right once the
sentence were deleted.)

## A reported digit finer than its Monte Carlo error is a claim about precision

A simulation estimate arrives with a standard error, and the number of digits
you print asserts that the estimate resolves them.
It usually does not, and the check is arithmetic: compare each reported digit
against the MCSE sitting in the same table you read the estimate from.

**Where a closed form exists, it supplies the values and the simulation
validates it.**
The two answer different questions.
The simulation establishes *that* a derivation describes the system; once it
does, the derivation supplies the numbers, because it carries no Monte Carlo
error and the estimate does.
Reporting the estimate at that point throws away precision the derivation
already gave you, and rounds noise into the last digit as though it were
signal.

The instinct that produces this is worth naming, because it sounds like
rigour: a measurement feels more honest than an argument, since it came from
the system rather than from reasoning about the system.
That is true of *whether* the relation holds and false of *what its values
are*.

Look for the closed form before reaching for replicates, too.
A generator assembled from standard pieces --- a beta-binomial draw, a
mixture, a deterministic map --- usually has one by construction, and finding
it is cheaper than the simulation that would estimate it.

- **Do:** compare every reported digit against its own MCSE before publishing.
- **Do:** report derived values and cite the measurement as corroboration,
  once a closed form fits.
- **Do:** ask whether the quantity has a closed form before designing a
  simulation to estimate it.
- **Don't:** round a noisy estimate to three digits because it is "what was
  measured" --- the rounding asserts a precision the estimate does not have.
- **Don't:** treat a measurement as the more conservative choice; where a
  derivation is available, it is the less precise one.

(Measured on
[ucdavis/matt.contracts#2](https://github.com/ucdavis/matt.contracts/pull/2),
2026-08-23.
A generator's realized ICC was reported as 0.011 / 0.018 / 0.032 from 12
replicates.
The relation is exactly derivable ---
`((1-p)/(2-p)) * (rho + (1-rho)/m)`, which is `0.0037234 + 0.1452128*rho` at
the parameters in use --- and three published figures were wrong against it:
0.032 for 0.032766, and ratios of 4.5 and 6.2 for 4.552 and 6.104.
The ICC estimate behind the first of those was `0.032131` on 12 replicates,
with a Monte Carlo standard error of `0.00087`, against a derived `0.032766`.
The estimate therefore sat 0.73 standard errors from the derived value ---
squarely inside its own noise, and unable to discriminate 0.032 from 0.033 in
either direction.
The two ratios are functions of that same estimate and inherit the problem.
The standard error was in the same table the estimate was read from.
Tracked as
[ai-config#2028](https://github.com/Morrison-Lab/ai-config/issues/2028).)

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

## When a fix changes what code COMPUTES, sweep everything that DESCRIBES it

The section above covers a literal and the comment beside it, and mechanizes
that with a ten-line window in one file.
The commoner and costlier version is wider on both axes: a fix changes what a
value *means*, and every place that describes the old meaning survives ---
docstrings hundreds of lines away, a user-facing message template, a catalog
row in `README.md`, sibling prose in other directories.

**It recurs across rounds of one review**, which is the tell.
The description sites are not one set: fixing the ones you remember leaves the
ones you did not, so each round closes some and reveals more, and each round
feels like the last one.

Measured on [ai-config#1884](https://github.com/Morrison-Lab/ai-config/pull/1884),
2026-08-21, where the same defect was filed three times:

| round | fixed | still describing the old behaviour |
| --- | --- | --- |
| 3 | the comparison (`HEAD` -> the pushed ref) | the warning's label, the docstring's classification table, the `README.md` row |
| 5 | the warning's label | the remediation *commands* in the same message |
| 6 | the remediation commands | the same-branch test underneath them |

Every intermediate state had correct code, a green suite, and a description
that contradicted it.
The reviewer's own summary of round 5 named it exactly: the label was fixed
"precisely because" of the case at hand, "but the sibling block ... never got
the same treatment".

**Advice is behaviour when a reader runs it**, which is what raises this above
tidiness.
Round 5's stale text was not a comment: it was the remediation the guard printed,
and following it literally would have merged the wrong branch.
A description that a reader *acts on* is a second implementation of the same
logic, and it needs the same fix.

**Derive the sites, do not recall them.**
The population is every occurrence of the old concept, so grep for it rather
than revisiting the places you remember writing:

```bash
git grep -n "HEAD" -- hooks/ shared/ skills/ README.md CLAUDE.md AGENTS.md
```

Then ask of each hit whether it asserts the behaviour you just changed.
This is [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
scope claim applied to your own diff: check the population, do not recall it.

**Assert the message, not just the verdict.**
A suite that checks only *whether* a guard fires cannot see *what it says*, so
a wrong message survives every green run.
Where output is advice, pin its content --- ai-config#1884's `LABEL_EXPECT`
asserts both the label and the emitted commands, and the mutation clauses that
revert each one flip a case rather than nothing.

- **Do:** grep for the old concept across the whole repo after changing what a
  value means, and re-read every hit.
- **Do:** treat a printed remediation as code, and test its content.
- **Do:** expect several rounds when a reviewer files this once --- the sites
  you did not fix are the ones you did not remember.
- **Don't:** read "the computation is right now" as the change being finished.
- **Don't:** rely on an adjacent-comment guard for this; its window is ten
  lines and one file, and these sites are neither.

## Replacing a mechanism: enumerate what the OLD one handled, not what the new one adds

Swapping one implementation for another is not the same review problem as writing one.
The new code gets read on its own merits and looks better, because it *is* better along the axis that motivated the swap.
The set of cases the old one handled and the new one does not is absent from the replacement by construction, so reading the new code cannot surface it.

The tell is a justification that enumerates **only the gains**.
A comment or commit message listing three ways the replacement is superior, with nothing about what it gives up, is not a summary of the trade.
It is one side of a ledger presented as the whole.
It reads as thorough precisely because it is specific.

So derive the old one's coverage from the old one's own source and check each case against the new one.
Where the code being replaced is itself a pattern, that pattern is the enumeration: a regex's alternations, a table's keys, a dispatch dict's entries.
Turn each entry into a test case, so the coverage claim is asserted and not merely reasoned about.

The enumeration disappears from the working tree when the change lands, which is what makes the loss feel permanent --- but it is still in history.
`git show <pre-change-commit>:<path>` prints it.
Finding that sha is the only fiddly part, and it is worth saying plainly that it is **not** always the commit before the PR: a replacement landing mid-PR has its own predecessor inside the same branch.
Derive it rather than assuming.
`git log --oneline -- <path>` names the commits that touched the file, and the one before the swap is the one to read --- but check how the repo merges before trusting that list, because a squash-merging repo collapses a PR to a single commit and the mid-PR predecessors never appear in it.
Where that is the case, reach them by sha through the PR's own ref, which a default clone does not fetch --- and note that fetching it is only half the route.
`git fetch origin refs/pull/<n>/head` writes `FETCH_HEAD` and no persistent ref, and a bare `git log --oneline -- <path>` still walks `HEAD`, so it lists the same squash it listed before.
Name the ref you just fetched: `git log --oneline FETCH_HEAD -- <path>`.
Fetch into a durable ref (`refs/pull/*/head:refs/remotes/pr/*`) if you want it to survive the next fetch.

This is [`check-purpose-before-reusing`](../workflow/check-purpose-before-reusing.md)'s "mirror failure" section pointed at a **replacement** rather than at a sibling.
That one governs a new check written *beside* an existing one, where the guards to mine are still in the tree.
Here they are in the diff's own deleted lines.
[`challenge-redundant-content`](../workflow/challenge-redundant-content.md)'s "inverse failure" section is the third case, where consolidation *gains* a trigger rather than losing one.

Measured 2026-08-22 on [ai-config#1932](https://github.com/Morrison-Lab/ai-config/pull/1932).
A regex push-detector in a `PreToolUse` hook --- at the time of writing on that PR's branch rather than on `main` --- was replaced by the shell-parsed detector from a sibling hook, correctly, on the DRW grounds the replacing comment itself cited.
That comment block named three cases the new detector handled better --- `git -C <dir> push`, `git -c k=v push`, and excluding the two forms that re-head nothing --- and none of the cases it dropped.
The deleted `KEYWORD_PREFIX` alternation had covered twelve shell prefixes, and the deleted `GIT_PROG` pattern had covered an unexpanded `$GIT` or `${GIT}` program token.
The detector stopped recognizing those forms, so a push written that way was not treated as a push at all and passed the guard unexamined --- among them a `for ... do` retry loop, an `if !` or `while !` guard, a brace group, a bare `!`, and a `sudo` prefix.
Later rounds restored them, and the restoring comment says outright that dropping them "was a REGRESSION rather than a simplification".
The alternation listing all twelve was in the deleted lines the whole time.

- **Do:** read the replaced code for its case list, and check the replacement against each one.
- **Do:** add a test per entry in that list, so the recovered cases are asserted and not argued.
- **Do:** derive the pre-change sha from the file's own history where the repo's merge style preserves it, and from the PR ref where it does not --- never assuming it is the PR's base.
- **Do:** state what the swap gives up alongside what it gains, even when the answer is nothing --- an explicit "nothing" is checkable and an omission is not.
- **Don't:** accept a justification that lists only improvements.
  The cases it is silent about are the ones nobody will look for.
- **Don't:** read a passing suite as covering the difference.
  The suite was written against the old behaviour's *intent* rather than its edges, so a dropped case usually has no test until you write one.
