Never spend LLM reasoning on a check a deterministic algorithm can decide.
Whenever a verification, measurement, or classification step is decidable by
computation over data that is available (or cheaply instrumentable), build or
run the instrument and let the model consume its verdicts --- reserve model
judgment for the genuinely semantic remainder.

An LLM eyeballing a log, a diff, a state dump, or a rendered frame for a
property that has a numeric definition is the tell. The model's judgment on
such a check is slower, costlier, and less reliable than the two lines of
arithmetic that decide it exactly --- and unlike the model's read, the
instrument's verdict is reproducible, diffable across revisions, and wireable
into CI so the check runs on every change instead of only when someone thinks
to look.

Worked-example case records for the rules below live in
[`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md), moved out of the auto-loaded context.

## The procedure

1. **Name the property being checked.** If it has (or can be given) a precise
   definition over available data --- a threshold, an invariant, an expected
   state at a time, a comparison against a reference --- it is algorithmatizable.
2. **Check the data already exists** (a log, a transcript, an API field, a
   debug dump). If not, ask whether the system can be cheaply instrumented to
   emit it --- adding a machine-readable dump of internal state is usually a
   small, safe, render-only change, and it pays off on every future check.
3. **Write the instrument once, as a tool** (a script in the repo, a CI step),
   not as an inline throwaway --- the second use is where the payoff is.
   Thresholds come from the system's own constants, not magic numbers.
4. **Wire it to where the change happens** (CI on every PR, a pre-push check)
   so the check runs without anyone --- human or model --- remembering to run it.
5. **Let the model consume verdicts, not raw data.** The LLM's role shrinks to
   the semantic residue: is this legible, is the intent right, does the prose
   match --- plus deciding what new instruments are worth building.

## Tells that a check you're doing manually should be an instrument

- You (or a reviewer) re-derive the same numbers by hand on more than one
  occasion --- spacing, speeds, timings, counts, deltas.
- A review checklist item has words like "within", "never exceeds", "stays
  constant", "by tick/step/line N", "matches the reference".
- You compare two versions of an artifact and classify the differences by
  reading both --- when a metric computed on each side would classify most of
  them mechanically.
- A defect was caught by eye that a threshold over dumped state would have
  caught earlier and every time thereafter.
- You are about to write "the only X this could affect is Y" --- see the next
  section, which is that tell in its most reportable form.

## A holding-constant measurement is a regression test

When the instrument's purpose is to measure a real corpus property,
re-run it on that real corpus every round
and treat an unexpected movement as a defect until explained.
A unit test can cover the local branch
and still miss that the instrument's headline number moved,
because the number is an end-to-end invariant over the real input
rather than a property of one fixture.

The useful signal is not only a threshold failure.
A measurement meant to hold constant is itself a regression test:
same input, same code path, same count.
If the count changes,
either the corpus changed in a way you can name
or the instrument regressed.
Report both the before and after numbers,
and require the PR to explain the change before calling it clean.

The same rule decides what to do
when a spec-correct fix makes the real measurement worse.
A specification can define behaviour that is hostile to the corpus's actual
syntax mix,
especially when one construct nests inside another
in ways the spec does not model for this use.
Do not silently pick the spec or the corpus.
Report the ambiguity,
keep a regression test for the harmful interpretation,
and make the maintainer choose the policy.

- **Do:** re-run a measuring instrument on real input after every change,
  and treat movement in a supposed constant as a regression until explained.
- **Do:** when spec-correct behaviour worsens the real measurement,
  surface the ambiguity
  and protect against reintroducing the harmful interpretation.
- **Don't:** rely on fixture tests alone
  for an instrument whose output is a corpus-level count.
- **Don't:** apply a spec verbatim
  after the instrument shows it dropped real content.

## A metric that cannot discriminate over its whole range may be sharp over part of it

The section above assumes the measurement separates a healthy state from a
regressed one, and asks what to do when the number moves.
This is the case where it does not separate at all.
The reflex then is to call the metric unusable and either loosen its bound
until nothing can fail it, or drop the assertion outright.
Both answers discard a working instrument.

Ask instead which *part* of the measurement carries the signal.
The candidates are a sub-window, a phase, or an aggregate over samples rather
than any single sample, and the sub-range is frequently where the mechanism
actually acts --- a transient that forms early and is buried by whatever the
system does afterwards.

Note what the reflex gets right, since that is what makes it convincing.
"No bound works over the range I measured" can be true, and better supported
than the person reporting it realizes.
The error is one of **scope** rather than of measurement: it generalizes a fact
about one window into a fact about the metric.
That is a scope claim owing a check against the population, per
[`metacognitive-monitoring`](metacognitive-monitoring.md), and the same
overreach [`grep-is-not-coverage`](grep-is-not-coverage.md) describes for a
null result.

**The aggregate is the counter-intuitive half.**
When individual samples overlap between the healthy and regressed populations,
their **mean** can still separate cleanly.
So "no per-sample threshold exists" does not establish "no threshold exists" ---
those are different claims, and only the first was tested.
Gate the aggregate, and keep a looser per-sample bound as a backstop so one
blown sample cannot hide behind the good ones.

This is one of a family of transformations, and the corpus already carries
another: [`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s count delta,
where a predicate too noisy to report a *level* is sound reporting a *change*
because taking the difference cancels the baseline.
Sub-window, phase, aggregate, and delta are the same move --- find the
projection of the measurement on which the signal survives.

Two things keep the narrowed gate honest.
Say plainly which range it does **not** cover and why, since bounding the noisy
part anyway, at whatever number passes today, restores the silent pass that made
the original guard worthless.
And check the window is not vacuous --- that the mechanism under test genuinely
occurs inside it --- which is this file's own negative-control rule applied to a
window rather than to an input.

Where the range came from is worth asking too.
Measuring only over the window an existing test happened to use, then
generalizing from it, is
[`challenge-the-assignment`](challenge-the-assignment.md)'s failure with a
test's own constants in place of a brief: inherited parameters that were never
the thing under examination.

- **Do:** ask which window, phase, or aggregate carries the signal before
  concluding a metric is unusable.
- **Do:** gate the aggregate when samples overlap, with a looser per-sample
  bound as a backstop.
- **Do:** state which range the gate deliberately leaves unwatched, and why.
- **Don't:** read "no bound works over the range I measured" as "no bound
  works".
- **Don't:** loosen a bound until it cannot fail, or delete the assertion, as
  the first response to a metric that does not discriminate.
- **Don't:** treat a window inherited from an existing test as the metric's
  natural range.

## Never predict which case will fail; enumerate the class

The rule so far concerns checks you *perform*.
It has a second form that reaches further, because it survives into what you
*say*: predicting which member of a class will fail, in place of running the
enumeration.

The shape is a sentence like "the only new word this could flag is
`monotonicity`", or "the one file this could break is the parser".
It reads as the output of an analysis.
It is the output of an intuition, and the giveaway is that no command was run.

**A guess in a report is worse than reporting nothing**, which is why this is
worth a section of its own rather than a bullet.
Naming a single member implies the others were examined and cleared, so a gap
that is total gets recorded as narrow and understood.
The next reader --- often you, later --- then spends attention on the named
case and none on the rest.

So ask whether the class is enumerable by a command.
Usually it is, and usually the command needs less than the guess did: no
dictionary, no installed package, no network, just a pattern over the diff.
When it genuinely is not enumerable, say the class is unbounded and the check
did not run.
An honest "unverified" is worth more than a confident member, because it
leaves the gap the size it actually is.

Watch for the specific slip where sound reasoning about a **category** is
cashed in as a prediction about a **member**.
"CI's dictionary is more permissive than the local one" can be well evidenced
and still license nothing about which word will fail --- those are different
claims, and only the first had support.

- **Do:** enumerate with a command, and report what it examined.
- **Do:** say a check could not run, and name the class it would have covered.
- **Don't:** substitute "the only one that could fail is X" for running the
  check.
- **Don't:** let a supported claim about a category carry an unsupported one
  about a member.

## Test the instrument against the incident that prompted it, verbatim

Building an instrument in response to a specific failure is the usual path
into this rule.
When that is why it exists, the incident's **exact input** is test case
number one -- pasted in unaltered from wherever it was reported, not retyped
and not tidied.

Expect the first draft to fail it.
That is the whole reason to write the test, and it is worth saying plainly
because the failure feels impossible from the inside: you have just finished
designing against that very case.

You do not design against the incident, though.
You design against your **summary** of it, and the summary is what made the
rule statable in the first place -- so the abstraction that let you write the
guard is the same one that lets the guard miss.
The real input carries an env-var prefix, an assignment, a `;`, a wrapping
quote.
The summary carries none of those, and neither does the matcher.

Write the negative cases in the same pass, since a guard that blocks too much
gets switched off and then protects nothing.
Mentioning a thing is not doing it: a `grep` for the gated command, an `echo`
of it, and a doc quoting it all have to pass.

**Treat a comment claiming the matcher's scope as an untested assertion.**
A comment beside a regex saying it "only matches at the start of a command"
sits exactly where a reviewer stops asking, and it was written by the same
mental model that wrote the regex -- so the two agree with each other and
neither is evidence.
Only a test separates them.

This is the guard-shaped case of [`ardi`](ardi.md)'s rule that a regression
test must be seen to fail before it is believed.
The gap runs the other way here: there the test encodes the bug as intended
behaviour, while here the test is the only thing that can catch the mismatch
between the incident and your memory of it.

- **Do:** make the reported input test case number one, copied literally.
- **Do:** test that mentions, greps, and quotes of the gated command pass.
- **Don't:** validate a matcher by reading it -- a wrong one reads as correct.
- **Don't:** trust a comment describing what the pattern cannot match.

### An attribution claim in a guide-for-future-edits comment is settled by mutation, not by re-reading it

The section above governs a comment claiming *what* a matcher matches.
Its sharper cousin is a comment claiming *which* guard blocks *which* case ---
"the lookahead is what refuses a following lowercase word", "these two
characters were dropped to fix an over-split".
That is a **cause** claim in
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s sense, so its check
is not "does this read correctly" but "what else would explain the observed
behaviour" --- and here the answer is decidable, because you can remove the
named guard and watch whether the case actually flips.

A comment block written *to guide future edits* --- a map the next widening is
read against --- is the worst place for such a claim to sit unverified, on two
counts.
It reads as documentation rather than as a claim, so
[`fact-check-prose`](../writing/fact-check-prose.md) never fires on it.
And its whole function is to be trusted by the next editor, so a wrong
attribution there does not merely mislead, it *directs* the next edit at the
wrong guard.

Mutation settles it and argument does not, so run the mutation before writing
the attribution down, and again when a review disputes it.
Remove the clause you are crediting, re-run the case it supposedly handles, and
confirm the behaviour changes; if it does not, the credit is wrong however
plausible the reasoning.

- **Do:** verify a "which guard handles which case" comment by removing the
  guard and confirming the case flips, before committing the comment.
- **Do:** re-run that mutation when a reviewer disputes the attribution, rather
  than re-arguing it.
- **Don't:** treat a guide-for-future-edits comment as exempt from
  fact-checking because it is documentation --- it is a claim-bearing artifact.
- **Don't:** settle a mechanism attribution by plausible reasoning; a
  reasoned-but-wrong one reads exactly like a correct one.

(Morrison-Lab/gha#425, 2026-08-05: a `check-new-line-breaks.py`
sentence-boundary regex fix carried a comment block documenting which half of
the regex --- the closing-character class or the lookahead --- refused which
construct, kept as a map for future widenings.
Reasoned-but-wrong attributions in that block inverted the review across three
separate rounds (2, 4, 5), each a fresh factual inversion: an ellipsis
exclusion credited to the wrong guard, and gha#397's own history inverted from
"added characters to fix an under-split" to "dropped characters to fix an
over-split".
Each was decidable in one mutation --- remove the clause, re-run the case ---
and none was decidable by re-reading the comment.)

## A negative control must enter at the real input

The section above says to test a guard against the incident that prompted it.
This is the same demand made of any multi-stage instrument, and it fails in a
way that is harder to notice, because the control **works**.

An instrument is usually a pipeline: extract candidates, filter them, judge
what survives.
Feeding a known-bad case straight to the judging step proves that step and
nothing else --- while feeling like proof of the whole, since the instrument
does flag it, exactly as predicted.

So plant the failing case at the **real input**.
If the instrument reads a diff, put it in the diff.
If it reads a log, write the line into the log.
A control that skips extraction cannot detect an extraction that drops the
very class you care about, and extraction is the usual culprit precisely
because it looks like plumbing rather than logic.

State which stages your control travelled when you report the result.
"Clean, and the control exercised all three stages" is interpretable; "clean,
and the control failed as expected" is not, because it does not say where the
control entered.

- **Do:** inject the control at the instrument's real input, and let it travel
  the whole path.
- **Do:** name the stages the control covered alongside the clean result.
- **Don't:** hand the control to the stage you already trusted.
- **Don't:** call an instrument trustworthy on a control that skipped its
  weakest step.

## Widening an instrument invalidates every figure it produced, not only the one that exposed it

The section above ends where the control finally catches something.
This is about the next five minutes, which is where the correction goes wrong.

An instrument usually emits several figures at once --- a distinct count, an
occurrence count, a file count.
When one of them disagrees with a wider pattern, the disagreement arrives
attached to that single number, so the repair attaches itself to that number
too.
The others came off the same narrow pattern, on the same pass, and are wrong
for exactly the same reason.
Nothing points at them, because nothing disagreed about them.

What makes the partial repair feel finished is that **an assertion now
passes**.
Widening the pattern and updating the one figure it contradicted turns a
failing check green, and a green check is the strongest completion signal
available.
It is a signal about the figure that was checked, and it is silent about the
figures that were not.

So the trigger is the **widening**, not the discrepancy.
The moment a detector's pattern changes, every number that detector produced
is stale --- including the ones nobody re-measured, and the ones already
copied into a PR body, a changelog, or a table shipped in the repo.
Re-run the widened detector for all of them, in one pass, before any of them
are published.

**Two independent methods agreeing is not corroboration when both are narrow
in the same way.**
Two methods keyed on the same surface feature share a blind spot, so their
agreement measures the blind spot rather than the truth, and it arrives
looking like the strongest evidence in the room.
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "Matching
values is not matching roles" makes the same point about two *values* that
agree --- "treat a shared origin as grounds for more care, not as
corroboration" --- and it transfers to two *methods* unchanged.
The discriminating question is not whether the second method was run
independently, but whether it could have failed differently: a second pass
that keys on the same token shape will confirm the first pass's misses as
readily as its hits.

**A second, independent error hides in the same figure: summing two
quantities and labelling the total as one of them.**
Items redacted **in place** and items **deleted outright** are different
populations, and a total that adds them cannot be described as either.
The label is what makes this survive review, since a plausible number under a
plausible noun invites no arithmetic.
State the parts, then the total: "N pseudonymized in place plus M deleted, so
N+M sites in all" is checkable, and a single figure is not.

**The remedy is already corpus doctrine and was simply not applied.**
Publish the command that derives a count beside the count, per
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md).
A reader who inherits the deriving command re-derives when the pattern moves;
a reader who inherits a bare number cannot tell what measured it, or whether
anything still does.

**This is not mechanizable as a general hook, and saying so is the honest
answer** (per "Limits" below).
"A number in prose disagrees with a number derivable from the diff" is
decidable only once the deriving command is known, and a bare count in prose
is precisely the artifact that does not supply one --- so a general guard
would have to guess the derivation, and a guard that guesses is the mushy
threshold that trains everyone to ignore it.
What *is* mechanizable is the narrower case where the command has been
published beside the count, which is the remedy above: at that point a check
can re-run it and compare.
So the enforceable rule is "publish the command", not "verify the number".

- **Do:** re-derive every figure a detector produced when you widen it, in the
  same pass, before publishing any of them.
- **Do:** paste the deriving command beside each published count.
- **Do:** report a total as its parts when it sums distinct populations.
- **Don't:** re-derive only the figure whose mismatch exposed the gap --- that
  is the near-miss, and it feels like a complete correction because an
  assertion now passes.
- **Don't:** read two methods agreeing as confirmation without asking whether
  either could have failed differently.
- **Don't:** treat a figure already copied into a PR body, a changelog, or a
  shipped file as out of scope; those are the copies a reviewer will read.

## A reference frame chosen from the initial condition expires as the system moves

The section above is about an instrument that **changed**, leaving every figure
it had already produced stale with nothing pointing at them.
This is the mirror: the instrument never changes, and the **system** moves out
from under it.

The shape is a projection.
Measuring how much each of several candidates contributes to some effect, you
pick an axis to project onto, and you justify the choice from the state at the
start --- "the separation begins along +Y, so world X is the tangential
direction".
That justification is true at the first sample and at no later one.
Once the system has rotated 56 degrees, the axis chosen to isolate the
tangential channel is 83% **radial**, so the projection now reports mostly the
channel it was picked to exclude.

Nothing announces the change.
The projection keeps returning finite, confident, per-candidate numbers at
every sample, and a figure that has quietly changed meaning looks exactly like
one that has not.
The failure also runs the wrong way rather than merely adding noise.
The axis drifts into alignment with the radial channel, and a purely radial
candidate is precisely the kind that dominates a radial projection while
contributing nothing to the effect --- so the wrong candidate is
**amplified**, and the instrument returns a large, stable, wrong attribution.

Two remedies, and prefer the second.
Re-derive the frame at each sample rather than once at the start, so the axis
tracks the system it describes.
Better, attribute the **target quantity itself** instead of a projection
standing in for it: the effect under investigation was a change in bearing, and
`cross(r_hat, dr) / |r|` yields that directly, with no axis left to go stale.
A quantity computed directly cannot drift out of alignment with the question,
because it is the question.

- **Do:** state what a chosen frame, axis, or baseline is valid *at*, and
  re-derive it per sample when the system it describes moves.
- **Do:** prefer computing the target quantity directly over projecting onto a
  proxy axis, wherever a direct expression exists.
- **Don't:** justify a fixed axis from the initial condition and then read
  late-run figures off it.
- **Don't:** read a large, stable per-candidate figure as a strong attribution;
  a stale frame produces exactly that.

## A reminder guard's discharge condition is a second matcher, and its failure is silence

The two sections above test a guard's *fire* condition: does the matcher catch
the reported input, and does a benign mention pass through as a negative case.
A guard that reminds rather than blocks carries a second matcher --- the
**discharge** condition, which decides the obligation was already met and the
reminder should stay quiet.
It fails in the opposite direction from the fire condition, and the two
failures do not cost the same.

An over-broad *fire* condition is noise: the reminder fires when it should not,
which is annoying and visible, so someone notices and narrows it.
An over-broad *discharge* condition is **silence**: the reminder never fires,
because every session looks already discharged.
Silence reads as compliance, so nothing prompts anyone to look --- the
[`fail-fast`](../principles/fail-fast.md) shape where the failure path and the
pass path print the same thing, here both printing nothing.

**A discharge scoped by file path cannot separate the obligation from adjacent
routine work that touches the same paths, and in the guard's own home repo that
routine work is everywhere.**
When the proxy for "a lesson was recorded" is a write to `memories/`,
`CLAUDE.md`, `skills/`, or `shared/`, the very act of *addressing* a review
finding --- editing one of those files to fix it --- satisfies the proxy, with
no lesson recorded.
Fixing the finding is not learning from it, but both write the same paths, so
the discharge cannot tell them apart.
The guard therefore goes dark in exactly the repo it ships to protect, while
working in every consumer repo where those paths are rarely touched.
So the adversarial test for a self-hosted guard's discharge is an ordinary,
unrelated edit **in its own repo**, run as a negative case beside the
fire-condition tests --- not the incident that prompted the guard.

How tight the discharge must be depends on what the guard is for.
A coarse discharge is tolerable for a **defensive backstop**, where a missed
fire only forfeits a nag and the real signal lives elsewhere.
It is a defect for a guard meant to **fire on one specific event**, where a
missed fire is the whole failure.
Decide which kind the guard is before choosing how loose the discharge can be.

- **Do:** test a reminder guard's discharge against a benign, unrelated edit in
  its own home repo, as a negative case alongside the fire-condition tests.
- **Do:** scope a load-bearing discharge to the artifact the obligation
  actually produces (a `hooks/`/CI path, an explicit signal), not to a path
  prefix the home repo edits routinely.
- **Don't:** treat a write to a broad path prefix as proof the obligation was
  met --- in the home repo that prefix matches almost every edit.
- **Don't:** read a reminder's silence as evidence the obligation is being met;
  an over-broad discharge produces the same silence as a repo full of compliant
  sessions.

## A review flagging an overclaimed check is a prompt to build it, not to soften the claim

The sections above are about an instrument you already decided to build.
This is about the moment a reviewer tells you one is missing --- and the
softer, wrong way out of it.

The shape is a description, a docstring, or a PR body asserting a property was
verified ("the parser is fuzzed", "inputs are validated", "the migration is
idempotent") when the verification was ad hoc manual work during development
and nothing repeatable shipped.
A reviewer flags the mismatch: the prose reads as if a committed test covers
it, and none does.

The tempting disposition is to delete the claim, since that makes the prose
accurate in one edit.
It is the wrong one whenever the property is **real and cheap to guard**,
because deleting the sentence throws away exactly the check this whole
principle says to build.
The manual verification you did once is the ad hoc check; the reviewer has
just handed you the recurrence signal that turns it into an instrument.
So make the claim true instead --- ship the committed, repeatable guard the
prose already describes --- and the finding resolves by addition rather than
by retraction.

Prefer deletion only when the property is not worth a standing check: a
one-off characteristic of this diff, or an invariant no future change could
plausibly break.
Say which it is, rather than defaulting to whichever edit is smaller.

**Then prove the new guard is non-vacuous by isolating the injected fault to a
shape only it reaches.**
This is [`ardi`](ardi.md)'s "seen to fail" rule with a suite-level trap: when
the guard ships into a shared test file, an injected fault that an *existing*
deterministic case also reaches makes that earlier case abort the suite first,
so you have demonstrated the old test catches it, not the new one.
Target the fault at an input the deterministic cases never build, or run the
new guard in isolation, before believing it catches what it claims.

- **Do:** ship the committed guard the prose describes when the property is
  real, so the finding resolves by addition.
- **Do:** state plainly when a property is a genuine one-off, and delete the
  claim then.
- **Do:** isolate a non-vacuity fault to a shape only the new guard reaches,
  or run it alone, so the failure is attributed to the right test.
- **Don't:** default to deleting an overclaiming sentence because it is the
  smaller edit --- that discards the instrument the finding asked for.
- **Don't:** read a suite that aborts on an injected fault as proof the *new*
  guard caught it; an earlier case may have.

**A guard whose condition ANDs several clauses masks its own mutation test the
same way, one level in.**
The suite-level trap above is a *sibling test case* aborting first; this is a
*sibling clause* in the very condition you are mutating.
When a guard reads `if a and b and c`, reverting clause `b` alone still passes
any regression case that clause `a` or `c` also keeps correct --- so the
mutation looks covered when it is not, a false negative that hides an untested
clause.
Construct a test that isolates each clause: an input where *only* that clause
keeps the result correct, so reverting it is the one change that flips the
outcome.
Then mutation-check each clause separately, per [`ardi`](ardi.md)'s "seen to
fail" rule applied clause by clause rather than once for the whole condition.

**The harness that performs those mutations needs the same scrutiny, because a
mutation it could not apply looks exactly like one the tests caught.**
The rule above assumes each clause can actually be removed.
When the clauses are alternatives inside one regex and the harness drops one by
deleting a delimiter-joined token, the token is present for the interior
alternatives and absent at one end, so that end is never mutated at all --- and
a harness that scores "no failure observed" as a pass reports the unmutated
clause as verified.

Which end depends on which side of the token the delimiter sits, and either
single-sided form leaves exactly one alternative unreachable.
Measured on this corpus's own
`\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't)\s+` prefix guard, dropping
`<alt>|` mutated seven of eight and silently no-opped on the last (`can't`,
followed by `)`), while dropping `|<alt>` mutated seven of eight and no-opped
on the first (`not`, preceded by `(?:`).
A naive string replacement is the wrong instrument for this regardless, since
one alternative can be a substring of another; split the alternation and rebuild
it without the member instead.

The transferable half is not the regex detail.
It is that a mutation harness has three outcomes, not two --- caught, missed,
and **inapplicable** --- and collapsing the third into the first is the
[`fail-fast`](../principles/fail-fast.md) figure where a check's failure path
and its pass path print the same thing.
Make the harness assert that the mutated artifact actually differs from the
original before it runs anything, and report the case as inapplicable when it
does not.

- **Do:** verify each mutation changed the artifact before scoring its result,
  and surface an inapplicable mutation as its own outcome.
- **Do:** rebuild an alternation from its parsed members when mutating one, so
  position and substring overlap cannot silently no-op the edit.
- **Don't:** score "the tests still passed" as a pass without knowing the
  mutation applied --- an unmutated clause passes for the wrong reason.
- **Don't:** trust a single-sided delimiter token to reach every alternative;
  it reaches every one but the end the delimiter is missing from.

## Limits

The rule targets *decidable* checks. Judgments of legibility, intent,
aesthetics, and prose accuracy stay with a human or model reviewer --- but even
these often decompose into a decidable core plus a smaller judgment (declare
the intended outcome as data, assert it mechanically, and review only the
framing). Prefer shrinking the judgment surface over automating a judgment
badly: an instrument with a mushy threshold that misfires trains everyone to
ignore it.
Read that as an argument for finding the range over which the threshold is
sharp, not as licence to abandon the instrument --- see "A metric that cannot
discriminate over its whole range may be sharp over part of it" above.

This generalizes the narrower habit of turning repeated manual verifications
into CI checks: that is the CI-shaped instance; this rule also covers one-off
investigations, review procedures, and any place model reasoning substitutes
for arithmetic. It is a different axis from multi-agent orchestration
([`when-to-orchestrate`](when-to-orchestrate.md)): orchestration parallelizes
model reasoning across subagents, while this rule removes model reasoning from
checks that never needed it --- apply this rule first, then orchestrate
whatever judgment remains.

## Apply this to writing a memory bullet, not just to runtime checks

The rule targets checks a system performs, but a UMS/memory bullet that
documents *how to tell X from Y* is itself a check --- and the same
tell applies: don't write down whatever fuzzy method you happened to use
live in the moment (eyeballing wording, matching timing) without first
asking whether a mechanical signal already exists in the data. Drafting a
memory is a natural moment to *notice* an available instrument even when
none was used at the time --- go back and check before finalizing the
bullet, the same way a reviewer would flag a manual check that should be
automated. (`ai-config#688`: a first-draft bullet on detecting self-echoed
PR replies said to match body text and timing --- both fuzzy --- when
every reply already carried a mechanical, unambiguous marker, the Claude
Code attribution footer, sitting unused in the same data. Caught only when
asked directly why the sharper signal hadn't been the first idea.)
