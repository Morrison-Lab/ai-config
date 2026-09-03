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
  years -> days) so it's dimensionally consistent with some internal
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

### An assertion whose two sides trace back to one call

This section's opening covers an assertion that cannot fail because its input is empty, and its first subsection covers a control the code under test undoes.
This is the third shape, and it is the only one that stays vacuous no matter what you feed it: the two sides of the comparison are the **same value**, reached under two names.
It is a property of the assertion's own shape, which is what separates it from [`fail-fast`](../principles/fail-fast.md)'s fifth cause of a vacuous zero --- there the assertion is fine and the subject's designed fallback is what cannot be separated from success.

It arrives through aliasing rather than through carelessness.
A function is refactored so the old name becomes a thin wrapper --- `f(x)` is now defined as `g(x)[0]` --- and a test that computed `scan` from the shipped path then asserts `scan == f(probe)`.
Read aloud, that is "the scan matches what the pre-change function produced", which is a real and valuable invariant.
Executed, it is `g(probe)[0] == g(probe)[0]`.
The wrapper is what hides it: at the call site the two names look like two implementations, and only the wrapper's one-line body says otherwise.

It is worse than the empty-collection shape because nothing about the test looks degenerate.
It has a non-trivial input, it exercises the real code, it takes time to run, and it appears in coverage.
A reintroduced design that had already been rejected on this branch changed behaviour on hundreds of bodies and passed the whole suite with this assertion watching it.

**The tell is syntactic, so look for it rather than reasoning about it:** an assertion in which both operands, expanded through every wrapper and alias, bottom out in one call with one argument.
Expand the wrappers on paper before trusting the assertion.

**The fix is to name the other side independently of the code under test.**
Pin the expected value against something the change cannot move: the base revision's own output (read from git, not from the current module), or a literal captured before the change.
Where a git read is available, assert both ways --- once against the base revision and once against a hard-coded expectation with no git dependency, so the invariant still runs in a shallow checkout where the base revision is absent.

- **Do:** expand every wrapper on both sides of an equality assertion and confirm the two sides can be produced by different code.
- **Do:** pin one side to a value obtained outside the module under test --- a base-revision read or a captured literal.
- **Do:** assert a git-dependent invariant a second way with no git dependency, so it does not silently skip in a shallow checkout.
- **Don't:** treat a wrapper and its delegate as two implementations;
  a one-line delegation makes them one.
- **Don't:** accept a suite's green as evidence an invariant holds until you have seen that invariant fail against a design it should reject.

(Measured 2026-08-28 on [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515).
`strip_cited_finding_vocab(x)` had become `strip_cited_finding_vocab_with_mask(x)[0]`, and the scan-identity test compared the shipped scan against `strip_cited_finding_vocab(probe)` --- the same call.
A previously-rejected design reintroduced deliberately passed all 299 tests.
Rewritten against the base revision, and again against a literal, the assertion fails on that design and the suite reached 303.)

### A test whose cases are GENERATED from the constant deletes its own coverage

The subsection below covers a test *gated on* a production constant, which degrades to a skip.
This is its sibling and it is quieter, because it degrades to nothing at all: the loop that generates the cases reads the same constant the cases pin.

```python
for kind in prod.NON_HUMAN_ORIGINS:            # generates one case per entry
    check(f"{kind} is excluded", classify({"origin": {"kind": kind}}) == EXCLUDED)
```

Empty the constant and the loop runs zero times.
The suite reports every remaining check passing, the totals barely move, and nothing is skipped --- so unlike the gated form, there is not even a `skipped` line to misread.
Measured: emptying that tuple left the suite fully green while every coordinator-relayed record became certifiable.

It is easy to write because it reads as the DRY form, and easy to miss in review for the same reason: a hand-written list beside a constant looks like duplication, and the duplication is the point.
Name the members in the test, then assert the constant contains them:

```python
for kind in ("channel", "peer", "coordinator"):     # literal, not derived
    check(f"{kind} is excluded", classify(...) == EXCLUDED)
    check(f"{kind} is in NON_HUMAN_ORIGINS", kind in prod.NON_HUMAN_ORIGINS)
```

The first assertion tests the behaviour;
the second tests that production still carries the entry.
Neither can be deleted by editing the constant alone.

**Two mutation-testing hazards travel with this**, both of which make a survivor and a kill look alike.

A **malformed mutant** --- one that leaves the file unparseable --- produces no failures, because the suite never runs.
Counting `FAIL` lines then reports it as a survivor, and the natural response is to go write a test for a hole that does not exist.

**The exit status does not discriminate**, which is worth stating because it is the first remedy that comes to mind and it is the one this passage originally prescribed.
A suite that dies importing an unparseable module exits **1**, and so does a suite with a genuine failure --- so "treat anything outside `{0, 1}` as not applied" is a detector that cannot fire in the case it was written for.
It was wrong here for a full round, inside the section about detectors that cannot fire.

Key on the **pass count** instead, because that is the quantity a malformed mutant cannot produce:

| | exit | `FAIL` lines | passes |
|---|---|---|---|
| baseline | 0 | 0 | N |
| mutant killed | 1 | 1 or more | fewer than N |
| mutant **survives** | 0 | 0 | N |
| mutant **malformed** | 1 | 0 | none reported at all |

A survivor reproduces the baseline's pass count;
a malformed mutant reports no summary line, because the suite never reached one.
Record the baseline count before the run and require every mutant to reproduce it or fail --- anything else is "not applied", and should be re-applied rather than counted.

A **skip counted as a pass** hides a weakened run.
A case inert under some condition --- a permission test as root, a platform-specific path --- recorded via `check(name, True)` makes a suite that skipped it and a suite that ran it print the same total, so the difference between a full run and a partial one is invisible in the one number anybody reads.
Report skips in their own counter and exclude them from the pass count.

A **duplicated block counted as two passes** inflates the total in the opposite direction: a runner whose `check(name, condition)` keeps no registry of names re-runs a copy-pasted block's assertions a second time and reports a higher count, with nothing distinguishing that from genuine additional coverage.
`Morrison-Lab/ai-config#2725` measured this directly on `scripts/test_check_pr_fully_clean.py`: two checks each ran twice on `main`, inflating the reported total by exactly the duplicate's size, and it was caught only because a reviewer diffed two line ranges byte for byte while porting tests in a later PR --- not a check anyone runs by habit.
The pass count is routinely quoted in commit messages and reviews as evidence of coverage, which is exactly what makes a silently double-counted total worth naming as its own hazard alongside the two above.

- **Do:** write the members as literals in the test, and assert separately that the constant contains them.
- **Do:** compare each mutation run's PASS count against the baseline's, and treat a run that reports no count at all as "mutant not applied".
- **Don't:** discriminate on exit status --- a malformed mutant and a real failure both exit 1, so it cannot separate them.
- **Do:** count skips separately, so a weakened run and a full one differ in the totals.
- **Don't:** generate a test's cases from the value under test --- the DRY form is the defective one here.
- **Don't:** record a skip with `check(..., True)`; that is a pass asserting nothing.
- **Do:** have the check runner refuse a name it has already seen (`ai-config#2725`'s suggested fix), turning a silent duplicate into an immediate failure rather than an inflated count.
- **Don't:** treat a rising pass count as evidence of rising coverage without a name registry (or an equivalent dedup check) backing it.

(Measured 2026-08-28 on [ai-config#2539](https://github.com/Morrison-Lab/ai-config/pull/2539), where it occurred **twice in one file** against two different constants, the second after the first had been fixed --- which is why it is written down rather than noted.
A third instance in the same suite iterated the flag list, so dropping the flag that marks harness-injected records stayed green.
The malformed-mutant hazard was hit in the same session while checking these very fixes.)

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

### A sampling instrument's zero is a coverage statement unless the new arm's reach is reported

When a verification tool or change-time test
(such as a corpus-sampling parity diff or generator-based checker)
reports "0 regressions" or "0 widened, 0 narrowed",
confirm that the new code path or arm was actually **reached** during the run.

Three distinct mechanisms produce a false zero from a sampling instrument:

1. **Truncation before reaching the arm.**
   A generator that yields new cases after a truncation limit
   (such as an arm appended last in a generator subject to `--limit`)
   is cut off before any new cases execute.
2. **Strided sampling skipping the arm.**
   A sampling harness that selects every k-th item from a generated stream
   can skip a small, concentrated batch of newly added cases entirely.
3. **Earlier deciding branches.**
   An existing check that evaluates before the new mechanism
   (such as a prose verdict line preceding a structured payload)
   can resolve the case before control reaches the new branch.

In all three cases,
the resulting zero reports that the check did not run,
not that the code is correct.

- **Do:** report and assert the reach count
  (e.g., "reached N times out of M")
  for each arm of a generator or sampling instrument.
- **Do:** evaluate new generator arms unconditionally
  or append them after sampling limits and strides are applied,
  so no generated cases are skipped.
- **Don't:** read "0 differences" or "0 widened" as evidence of correctness
  when the execution count for the new branch was zero.

(Measured on PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736):
`scripts/check-verdict-scan-parity.py` reported 0 widened across multiple review rounds
because the structured payload arm was placed at index 241,920 where `--limit` truncated it,
skipped by strided sampling,
and bypassed by prose verdict checks,
hiding 1 accepted widening and 5 fail-closed narrowings.)

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

### A misleading test label also licenses a DELETION, which is the direction with no mutation available

The **Misleading label** entry above treats a test name that overstates its
assertion as a source of false confidence in a fix.
It runs the other way too, and that direction is the dangerous one, because the
remedy the list prescribes cannot be applied to it.
Mutating the fix is what exposes a test that does not depend on it.
There is no fix to mutate when the change under consideration is *removing*
code, and a suite that stays green is the entire evidence on offer.

The shape is a clause you judge redundant because a neighbouring pattern
appears to subsume it.
That judgment is about two patterns' **domains**, which is a claim, and the
green suite gets read as having checked it.
It has not: a suite proves the clause is untested, never that it is unreachable.

The specific miss worth naming is a near-subsumption --- a neighbour that covers
the anchored form of a case and not the free one.
A pattern rejecting a value that *begins* with a marker does not reach the same
marker mid-string, so the two look interchangeable on every example anyone
wrote down and differ on the case nobody did.

The consequence is easy to under-rate because nothing crashes.
An over-broad rule and a deleted clause both still return a verdict, so the
regression shows up as a **change of reason** rather than a failure: an
assertion about text that was never read, in place of the assertion about text
that was.
A caller reading only the pass/fail bit sees no difference at all.

- **Do:** state the two patterns' domains and produce an input inside one and
  outside the other, before deleting either as redundant.
- **Do:** read the assertion body rather than the test name, when a test is
  what persuades you a clause is dead.
- **Do:** diff the *reason* a check reports, not only its pass/fail bit, after
  removing a branch that produced one.
- **Don't:** read a green suite as evidence that a clause is unreachable ---
  it is evidence the clause is untested, which is the argument for a test
  rather than for a deletion.
- **Don't:** trust an anchored pattern to cover the unanchored case;
  `^marker` and `marker` agree on every example that starts with the marker.

### A subsumption proof over raw text must account for every transformation

When deleting a structured extraction check or parser term on the grounds that
it is "provably redundant" with a raw substring or regex match over the unparsed
body,
account for every transformation between raw text and parsed values.
This extends the near-subsumption hazard in `### A misleading test label also licenses a DELETION`
above from matching domains within one string to representations across decoding
transformations.

Decoders and parsers
(such as `json.loads` resolving `\u0061` Unicode escapes,
URL decoders resolving `%20`,
HTML/XML entity unescaping,
or case/whitespace normalizations)
convert raw representations into values that do not appear byte-for-byte in the
unparsed text.
A structured equality check `payload.get("commit_sha") == head_sha`
matches an escaped JSON string `"commit_sha": "\u0061bc1234..."`,
while raw substring checks on `head_sha` in the unparsed body fail to find it.
Deleting the structured check causes escaped or encoded payloads to fail closed.

- **Do:** construct adversarial test fixtures with escapes, encodings,
  and entity references before concluding a parsed-value check is subsumed
  by raw text search.
- **Do:** test decoded/escaped representations against the full verification
  pipeline.
- **Don't:** treat raw text and decoded structured values as interchangeable
  in redundancy proofs.

(Measured on PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736):
deleting a structured `commit_sha` check as "provably dead" made escaped JSON
review payloads fail closed as "no review posted" because raw substring
disjuncts could not see the escaped SHA.)

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

### Three ways an assertion passes without ever seeing the value it names

The vacuous modes above concern an assertion evaluated against an empty or self-satisfying collection.
These three concern an assertion evaluated against a **non-empty** stream that is not the stream the test claims to be reading.
Each looks like ordinary, specific coverage --- a named value, an anchored pattern, a real comparison --- and each passes against deliberately broken code.

- **The harness merges the streams.**
  A runner that captures stdout and stderr into one buffer lets any log line, progress message, or warning satisfy an anchored grep meant for the program's *output*.
  The assertion is specific, the pattern is anchored, and the value it matched was written by the logger.
  Check what the harness captures before trusting any assertion over captured text, and assert against the stream you mean by capturing them separately.
- **Two values are emitted as one field.**
  When a formatter concatenates two variables with no separator, a test asserting on the combined field cannot distinguish them, so a defect that swaps, drops, or duplicates one of the two leaves the assertion intact.
  Assert on the parsed fields, or on a separator the format guarantees --- not on a substring of the joined line.
- **A subsequence match cannot see an appended item.**
  An `in_order`-style assertion checks that the named items appear in that relative order.
  Extra content between them, and extra content after the last of them, satisfies it by construction --- so a test written to pin an output's shape is blind to anything the code appends.
  Pair every ordering assertion with a length or exact-set assertion, or the ordering check is a lower bound and nothing more.

The general form: **name the stream, the field, and the completeness the assertion actually constrains**, and check that each is the one the test is about.
All three failures survive the "does it read as coverage" glance precisely because the assertion names a real, specific value --- what is wrong is the haystack, not the needle.

(Measured 2026-09-03 across nine review rounds on one PR, several of which found a real defect in the previous round's fix.
Four separate times a suite passed against code broken on purpose.
A fifth shape from the same PR --- asserting a value is PRESENT on the failure path without asserting it ABSENT on the success path --- is the positive-fixture-without-negative-control case that "A predicate a fix adds needs mutation in both directions" above already covers;
counted as a recurrence of that entry rather than written again here.)

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

**An illustration you invented is the one claim that never prompts the check.**
Everything above is a claim you set out to verify.
An example is different: it is chosen to make something you already believe concrete, so it inherits that belief's verification in the writing and is never checked on its own.
The rule being true is not evidence about the instance, and an instance picked to demonstrate a rule can turn out to be a **counterexample** to it.

That is worse than an ordinary slip, because a wrong example names the wrong failure mode and the surrounding argument then reasons from it.
A reader takes the example as the concrete case and the prose as its generalization, so a false example redirects the conclusions drawn near it.
Where a mechanism has more than one outcome, pick the example showing the **dominant** one, and say which outcome it shows.

Distinct from [`examples-are-scanned`](../writing/examples-are-scanned.md), where the example's claim is correct and a checker matches a **token** the prose is discussing.
Here the claim itself is wrong, so re-reading cannot catch it and only running it can.

- **Do:** execute an illustrative example --- in a comment, a docstring, or prose --- before shipping it, on the same terms as any other claim.
- **Do:** re-read the surrounding argument after checking one, since a corrected example can invert the point it was supporting.
- **Don't:** let an example inherit the verification of the rule it illustrates.
- **Don't:** generalize from one member of a class to the class --- checking U+201C and then writing "a smart quote" is the same unchecked step, one level up.

(Morrison-Lab/ai-config#2086, 2026-08-23: a pre-push draft comment offered "a smart quote in a PR title, an emoji in a check-run name" as inputs that would raise under cp1252.
Both were wrong in the same direction, and the draft was corrected before reaching a commit --- `git show 36268396:scripts/check-pr-fully-clean.py` carries the corrected wording --- so this is a draft error the process caught rather than a shipped one.
Measured: cp1252 leaves five bytes undefined, `0x81`, `0x8D`, `0x8F`, `0x90`, `0x9D`, so U+1F600 (`f0 9f 98 80`) mojibakes silently while U+1F44D (`f0 9f 91 8d`) raises on `0x8D`.
The draft named the rare outcome as though it were the common one, inverting its own argument for why `errors="replace"` was the wrong fix: silent corruption is the dominant case, and `errors="replace"` preserves exactly that.
The first draft of *this entry* then generalized from U+201C to "a smart quote", which an adversarial review refuted by measurement: U+201C (`e2 80 9c`) decodes silently and U+201D (`e2 80 9d`) raises, `0x9D` being one of the five.
Recording that second step because it is the same error at one remove, committed while documenting why not to.)

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

## Changing which exception a function RAISES is a signature change that fails silently

The section above derives a **parameter** change's caller set by grep.
The exception a function raises belongs to the same interface and needs the same grep, and it is the more dangerous of the two because of how the two fail.

Adding a genuinely **required** parameter fails loudly at the call site, on an arity mismatch.
The section above's own case was quieter than that and still red: `classify()` kept five parameters and *retyped* one, so nothing mismatched at the call site and the `TypeError` surfaced several frames inside the callee, in CI.
An optional parameter with a default, or a reordering of same-typed positionals, is quieter again.
So "parameter changes are loud" is a spectrum, and what follows is the end of it that has no red at all: an exception-type change raises nothing anywhere.
Where a handler upstream already catches the new type, the error is routed into whatever that handler does next --- and a handler that returns a default, returns `None`, or logs and continues is the code that carries on.
So the change lands green, and the failure it was meant to report stops being reported.

**The direction is what makes it worth a rule of its own.**
This edit is typically made *to improve* error handling --- replacing an incidental `AttributeError` with an explicit `raise RuntimeError("...")` that names the problem.
It therefore reads as a strict improvement and attracts less scrutiny than a change that looks risky, while its actual effect can be to make the error **quieter** than the incidental one it replaced.
That effect depends entirely on how *narrow* the enclosing handlers are, which is the thing to look up rather than assume.
Against a narrow `except RuntimeError` the incidental `AttributeError` would have escaped and the explicit one does not, so the change really does make it quieter.
Against a broad `except Exception` the two are indistinguishable and the change buys nothing either way.
Measured here on 2026-08-23, the broad form is the overwhelming majority --- 138 of the 140 hits below --- so assuming the narrow case is the wrong default.

Derive the handler set before claiming the change makes anything louder, and note that **base classes catch too**:

```bash
grep -rnE 'except \(?[A-Za-z_, ]*RuntimeError|except (Exception|BaseException)\b|^[[:space:]]*except[[:space:]]*:' \
  --include='*.py' .
```

The narrow form is the trap, and it is the one that comes to mind.
Measured in this repo on 2026-08-23, `grep -rn 'except RuntimeError'` returns **2** hits where the form above returns **140** --- because `except Exception`, `except (RuntimeError, OSError)`, and a bare `except:` all catch a `RuntimeError` while none of them matches the literal string `except RuntimeError`.
A grep keyed on the type name is therefore a grep for the handlers that happen to *name* it, which is the same sample-for-population substitution the section above warns about.

That broader form is broader and still not exhaustive, so report it as what it examined rather than as the population: it misses `except(Exception):` with no space, two-space spellings, a tuple split across lines, and a dotted `except errors.RuntimeError:`.
None of those occurs in a `RuntimeError`-catching form in this repo today, which is why the 140 stands here and is not a general guarantee.

Then read what each hit does with it.
A handler that re-raises or exits is fine.
One that returns a default, returns `None`, or records a status and carries on is the case this rule is about.

The same-file case of this check is decidable, so it is being built rather than
left to judgment: Morrison-Lab/ai-config#2105 specifies an instrument flagging a
`raise` whose exception type a caller in the same file already catches.
The cross-file case stays a reading task, since it turns on what each handler
then does.

- **Do:** grep for handlers of the NEW exception type before changing what a function raises.
- **Do:** read each handler's body, since only the ones that swallow matter.
- **Do:** reach for an exception the enclosing handlers do not catch when the point of the change is to stop something being swallowed --- `SystemExit` derives from `BaseException`, so `except Exception` misses it --- and confirm that from the grep rather than assuming it, since a bare `except:` and `except BaseException` do catch it.
- **Don't:** count an explicit `raise` as louder than the incidental error it replaced.
  That is a claim about the handlers, not about the raise.
- **Don't:** read a green suite as evidence, since the swallowing path is the one that does not fail.

(Morrison-Lab/ai-config#2086, 2026-08-23: a fix for a Windows cp1252 decode bug replaced an `AttributeError` from `None.strip()` with an explicit `raise RuntimeError(...)`, to name the decode failure rather than leave it incidental.
`_resolve_run_head_sha` in `scripts/check-pr-fully-clean.py` wraps its `run_cmd` call in `except RuntimeError: return None`, so the explicit error was swallowed and the caller went on to append `No review comment has been posted evaluating HEAD SHA ...`.
That is exit 1 **with** a `  - ` finding bullet --- exactly the shape [`fully-clean`](../workflow/fully-clean.md)'s crash test, `rc==1` plus the absence of bullets, cannot tell apart from a genuine verdict.
The `AttributeError` it replaced had escaped that catch and was at least loud.
An adversarial self-review caught it before merge.
The shipped fix calls `die()`, whose `SystemExit` no `except RuntimeError` intercepts.)

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

## A comment asserting the state of ANOTHER artifact is a claim with an expiry across commits

A comment asserting facts about *another* file, prompt format, or test expectation
(such as "prompts render the payload 3 spaces in",
"this field was removed as provably dead in helper X")
is a cross-artifact claim.
In a multi-commit PR where designs iterate across review rounds,
modifying the referenced file immediately expires the comment in the other file.

Because the comment is in a different file from the code change,
single-file adjacent-comment linters (e.g. `hooks/flag-stale-adjacent-comment.py`,
which checks a 10-line window in the modified file)
cannot flag it,
and the diff of the modifying commit does not contain it.
Worse,
a stale test comment pointing readers away from the test pinning a restored feature
actively misleads reviewers.

- **Do:** grep for cross-artifact references, format descriptions,
  and justification comments across the repository when updating a shared data
  format or reversing a prior round's deletion.
- **Do:** audit explanatory comments in test files when restoring logic
  that an earlier commit removed.
- **Don't:** rely on 10-line adjacent-comment hooks to catch stale claims about
  other files.

(Measured on PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736)
commit `c725c449`:
after restoring `commit_sha` in `scripts/check-pr-fully-clean.py`
and making reviewer payloads flush-left,
comments in `scripts/test_check_pr_fully_clean.py`
and `scripts/lib/review_payload.py`
still asserted the old, opposite states.)

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

## A comment describing HOW a mechanism works survives the mechanism, and a superset replacement leaves no test able to catch it

The section above covers a fix that changes what code *computes*, where the remedy is to grep for the old concept across the repo.
This is the case that remedy does not reach: a fix that changes *how* a mechanism works --- a narrower scan widened, a shared helper given a second caller and then only one, a data structure retired --- while the comment documenting the old design stays in place, worded exactly as it was.

**Nothing turns red.**
The widened mechanism is a superset of the one it replaced: every assertion the old design satisfied, the new one satisfies too, plus more.
So the suite that passed before the change passes after it, and it passes identically whether the nearby comment was updated or not.
Only a reader notices, and a reader is exactly who consults the comment *before* touching the mechanism it describes --- which means the miss is most costly at precisely the moment it matters.

Three confirmed instances from one PR, `Morrison-Lab/ai-config#2668` (`_strip_posted_aside`'s re-raise veto, `scripts/check-pr-fully-clean.py`): a block above `_RERAISE_VOCAB` said the veto scans "the containing sentence BACKWARD and its containing paragraph FORWARD" after the scan had moved to the whole containing section in both directions;
a block above `_SENTENCE_END_RE` said the regex was "shared by the citation-aside veto and the negated-resolution guard" after the veto stopped using it (it moved to bisecting heading positions, leaving `_sentence_start_before` with exactly one caller);
and a third comment still named `_paragraph_starts` and `_paragraph_ends`, two variables a later commit in the same PR had already deleted.
All three were caught, but not by the suite: the third was a reviewer's non-blocking nit in the PR's own final review round and still shipped as-is (no fix for it existed to lose), while the first two were never raised in any of #2668's review rounds at all.
All three surfaced only in a later retrospective sweep, `Morrison-Lab/ai-config#2722`, and were fixed in the follow-up PR it produced, `#2726`.

**The sweep method matters more than the instance count.**
Two successive attempts at collecting these each missed at least one, because grepping for the vocabulary of the comments written in the *current* round finds those comments and misses ones written earlier in different words --- "shared by" and "scans ... backward ... forward" do not share a token with each other, let alone with whatever a third, older comment happened to say.
The sweep that worked instead enumerated the *mechanisms* (the re-raise veto, the shared regex, the paragraph-bound variables) and read every comment touching each one, structurally rather than lexically.
This sharpens the "derive the sites, do not recall them: grep for it" prescription in the section above: grep is the right instrument when the *sites* are unknown but the *word* naming the changed concept is stable;
it is the wrong one when the word itself has drifted across rounds, because the search inherits the same blind spot as recall did.

**Record why the abandoned design was abandoned, not only what replaced it.**
A comment that says "the veto scans the whole containing section" is already accurate, but it gives a future reader no reason not to narrow it back to a sentence-and-paragraph window --- the exact design this PR spent several rounds proving unsafe.
Naming the failure the narrower version had is what stops it from being reintroduced.

- **Do:** when a fix replaces *how* a mechanism works, enumerate the mechanisms touched and read every comment referencing each one --- not just the comments using the new round's own vocabulary.
- **Do:** state, in the updated comment, why the retired narrower design was unsafe --- not only what the current one does.
- **Don't:** trust a green suite as evidence a mechanism-describing comment is current;
  a superset replacement passes every old assertion by construction, comment or no comment.
- **Don't:** grep for the concept's *current* name and call the sweep complete --- an older comment describing the same mechanism in different words is invisible to that search.

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

**A generalization loses properties of the matching FORM, which the case list does not contain.**
The section above says to derive the old mechanism's coverage from its own source, and that where the replaced code is a pattern, "that pattern is the enumeration: a regex's alternations, a table's keys, a dispatch dict's entries".
That instruction is right and it is not sufficient, because the second occurrence lost something the enumeration never held.

Replacing a four-name alternation with a structural regex is the case:

```
<(task-notification|system-reminder|wake|command-name)\b     the old one
<[A-Za-z][A-Za-z0-9_-]*(?:\s[^>]*)?>                         the new one
```

Every one of the four names still matches, so enumerating them --- exactly as prescribed --- reports full coverage.
What went missing is the `\b`: the old form matched on a word boundary and so needed no closing `>`, while the new one requires one.
A truncated opener stopped being recognized, and the resulting fail-open was found by a reviewer rather than by the coverage check.

The asymmetry is worth naming.
An enumeration's **entries** are visible in the deleted lines, so the prescribed check finds them.
Its **form** --- an anchor, a flag, a boundary, a greediness, a case sensitivity --- is a property of how the entries are matched, and it survives no entry-by-entry comparison, because each entry passes.
A generalization is exactly the change most likely to alter the form while preserving every entry, so the two directions of scrutiny are complementary rather than redundant.

Read the two patterns side by side and ask what the old one accepted that the new one does not, rather than which of its cases the new one still covers.
The question is answerable by execution: run both over a corpus that includes malformed and truncated inputs, and diff the accepted sets, per Pattern 15's base-parity rule in [`mistake-patterns`](../../memories/mistake-patterns.md).

- **Do:** diff the old and new patterns for anchors, boundaries, flags and greediness, not only for the cases they enumerate.
- **Do:** feed both the malformed inputs, since a form difference shows on inputs no entry describes.
- **Don't:** read "every old entry still matches" as coverage --- that is the check a generalization passes by construction.

(Measured 2026-08-28 on [ai-config#2539](https://github.com/Morrison-Lab/ai-config/pull/2539).
The generalization was itself the fix for a prior fail-open, and it shipped with the four names checked and the boundary unexamined.
It became the tenth certification fail-open of that PR, and the reviewer's reproducer was one line: a tag opener with no closing bracket anywhere in the block.)

## Two literals for one concept drift apart inside a single session

When two separate regexes, literals, or parsers match the same syntax or concept
(such as harvesting a token at one site and scanning for trailing content
after that token at another),
modifying one site in response to a review finding causes them to drift apart.

A relaxed matcher accepts an input that the second matcher rejects,
causing unexpected `None` dereferences, missed checks, or silent inconsistencies.

- **Do:** hoist duplicate literals or regexes for the same concept into a single
  shared constant or helper, or assert their identity.
- **Don't:** maintain two separate regex literals for the same concept across
  multiple checks in the same file.

(Measured on PR [#2736](https://github.com/Morrison-Lab/ai-config/pull/2736)
commit `5dfd3883`:
`parse_review_verdict` in `scripts/pre-push-review.py` used two separate regexes
for `Reviewed-Commit:`;
loosening one to accept bold and spaced formatting while replacing the other with
a line scan caused `last_fp` to stay `None` on loosened inputs,
raising an `AttributeError`.
This is the single-constant counterpart to the sibling-audit rule in
[What to check](#what-to-check) above
("When one parser construct becomes tolerant of a condition, audit its siblings for the same condition"):
where that rule prescribes sweeping distinct constructs that parse the same syntax class,
this one prescribes eliminating duplicate literals for the exact same construct outright.)

