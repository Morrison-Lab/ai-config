Never spend LLM reasoning on a check a deterministic algorithm can decide.
Whenever a verification, measurement, or classification step is decidable by
computation over data that is available (or cheaply instrumentable), build or
run the instrument and let the model consume its verdicts --- reserve model
judgment for the genuinely semantic remainder.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`algorithmatize-checks.rationale.md`](algorithmatize-checks.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

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

**The aggregate is the counter-intuitive half.**

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

## A threshold pinned to a current measurement needs its rate of change checked, not just its level

The section above is about a metric that will not discriminate anywhere.

- **Do:** before setting a threshold relative to a current measurement,
  measure that quantity's rate of change and compare it against the
  interval the check must survive between reads.
- **Do:** replace an unworkable ratchet with a round policy line carrying
  stated runway, rather than a tighter one.
- **Don't:** read a ratchet passing at the moment it is written as evidence
  the reference point it is pinned to is stable.
- **Don't:** treat a check that goes red on an untouched file as flaky ---
  read it as the reference point having moved faster than the margin.

## Never predict which case will fail; enumerate the class

The rule so far concerns checks you *perform*.

**A guess in a report is worse than reporting nothing**, which is why this is
worth a section of its own rather than a bullet.

- **Do:** enumerate with a command, and report what it examined.
- **Do:** say a check could not run, and name the class it would have covered.
- **Don't:** substitute "the only one that could fail is X" for running the
  check.
- **Don't:** let a supported claim about a category carry an unsupported one
  about a member.

## Test the instrument against the incident that prompted it, verbatim

Building an instrument in response to a specific failure is the usual path
into this rule.

**Treat a comment claiming the matcher's scope as an untested assertion.**

- **Do:** make the reported input test case number one, copied literally.
- **Do:** test that mentions, greps, and quotes of the gated command pass.
- **Don't:** validate a matcher by reading it -- a wrong one reads as correct.
- **Don't:** trust a comment describing what the pattern cannot match.

### Scale that from one reported input to a corpus of real ones

The rule above fixes the exact input that prompted the guard, and asks for
negative cases in the same pass so an over-blocking guard does not get switched
off.

**A uniform result across the whole corpus is a fact about the harness, not
about the subject.**

- **Do:** run a text-consuming classifier over a corpus of real inputs whose
  ground truth you know independently, before reporting it correct.
- **Do:** re-run that corpus after every widening, and treat a newly
  over-blocked legitimate input as the more urgent of the two directions.
- **Do:** read a corpus-wide uniform verdict as a harness bug until the
  harness's own plumbing has been checked.
- **Don't:** substitute more authored cases for real ones --- they inherit the
  understanding that produced the bug.
- **Don't:** treat a harness's loud failure as evidence that it works; the safe
  direction is still the wrong answer.

#### A green check on the default branch is a free labelled corpus

The section above asks for "a set whose right answer you independently know", and knowing it is usually the expensive part --- someone has to label the inputs, and a hand-labelled set is small and inherits its author's blind spot.

**Ship the audit as a flag on the instrument, not as a one-off script.**

**The audit has to enter at the instrument's own input, exactly as a negative control does.**

- **Do:** take a CI check's green on the default branch as ground truth that nothing in scope there should fire, and audit against that corpus.
- **Do:** ship the audit as a flag on the instrument, wire it into the pre-push sweep, and see it fail on a reintroduced entry.
- **Do:** run the audit through the instrument's own entry point with its real configuration.
- **Don't:** read a clean audit as evidence about false negatives --- the green is one-sided.
- **Don't:** reimplement the instrument's lookup inside the audit; that measures the table rather than the tool.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A green check on the default branch is a free labelled corpus".

### An attribution claim in a guide-for-future-edits comment is settled by mutation, not by re-reading it

The section above governs a comment claiming *what* a matcher matches.

**That remedy has a precondition worth naming, because a comment gives no sign
of which side of it a claim sits on.**

- **Do:** verify a "which guard handles which case" comment by removing the
  guard and confirming the case flips, before committing the comment.
- **Do:** measure instead of mutating when the comment credits the environment
  rather than a clause you wrote.
- **Do:** re-run that mutation when a reviewer disputes the attribution, rather
  than re-arguing it.
- **Don't:** treat a guide-for-future-edits comment as exempt from
  fact-checking because it is documentation --- it is a claim-bearing artifact.
- **Don't:** settle a mechanism attribution by plausible reasoning; a
  reasoned-but-wrong one reads exactly like a correct one.

**Running the mutation is not the check, because the rule above asks WHETHER
the case flips and a comment can be wrong about WHICH WAY.**

- **Do:** read a mutation's before/after pair back against the prose it
  supports, in the commit that ships both.
- **Do:** state a direction in the vocabulary the pair uses --- over-block or
  fail-open --- so the sentence and the fixture are comparable at a glance.
- **Do:** grep for the direction claim once one instance is wrong; it is
  usually written down more than once.
- **Don't:** count a green mutation as having verified the attribution --- it
  establishes that something flipped, which is the weaker half.
- **Don't:** reach for a fresh experiment when a reviewer disputes a direction
  before checking whether your own fixtures already record it.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A mutation whose recorded direction contradicted the comment beside it".

## A negative control must enter at the real input

The section above says to test a guard against the incident that prompted it.

- **Do:** inject the control at the instrument's real input, and let it travel
  the whole path.
- **Do:** name the stages the control covered alongside the clean result.
- **Don't:** hand the control to the stage you already trusted.
- **Don't:** call an instrument trustworthy on a control that skipped its
  weakest step.

## Widening an instrument invalidates every figure it produced, not only the one that exposed it

The section above ends where the control finally catches something.

**Two independent methods agreeing is not corroboration when both are narrow
in the same way.**

**A second, independent error hides in the same figure: summing two
quantities and labelling the total as one of them.**

**The remedy is already corpus doctrine and was simply not applied.**

**This is not mechanizable as a general hook, and saying so is the honest
answer** (per "Limits" below).

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

**"Stale" here means the earlier reading has been retired, which holds only
while one instrument has a before and an after.**

## Publishing a command is not enough; it has to be the command you ran

The section above closes on "publish the command", and that rule is right.

- **Do:** paste the command you actually ran, verbatim, rather than a tidied
  restatement of it.
- **Do:** diff a prescribed command against your own verification command
  before pushing, and treat any difference as the prose being wrong.
- **Don't:** simplify a published command for readability without re-running
  the simplified form and confirming it still gives the same answer.
- **Don't:** read "I published a command" as discharging the rule above; that
  rule is discharged by publishing *that* command.

## An instrument's own exit code is not the gate; find what CI actually runs

The two sections above govern the command you publish.
This one governs the command you *believe*, and it is the cheaper mistake to
make because running the right script feels like having checked.

A repo can ship a checker that reports a finding and still exits `0`, because
it was designed to advise rather than block.
Separately, a **test** can pin the same property as a hard fact, and CI can run
that test.
Reading the script's exit code then answers "does the script complain?" when
the question you are actually asking is "does CI pass?" --- and the two answers
differ precisely when the property is one somebody cared enough to pin.

The failure direction is the bad one.
The script exits `0`, the local check looks green, and the gate is discovered
by a red PR rather than by the pre-push sweep that was supposed to prevent it.
Nothing in the script's output hints that a second consumer exists.

So resolve the question against the workflow rather than against the tool:
read the job's step list and run **what it runs**, tests included, instead of
picking the script whose name matches the property.

- **Do:** enumerate the CI job's steps and run that set, rather than the one
  script that seems to cover the check.
- **Do:** treat an advisory script and a test pinning the same property as two
  different instruments with two different verdicts.
- **Don't:** read a `0` from a purpose-built checker as "CI will pass" --- it
  reports only that *that* script is satisfied.
- **Don't:** conclude a threshold is advisory from the exit code of the script
  that measures it.

(Measured 2026-08-19 on ai-config.
`scripts/check-memory-file-size.py` exits `0` while printing that
`memories/github-actions.md` was over its 1200-line threshold, so the crossing
was reported here as advisory and pushed.
`validate` went red on both parallel runs: `scripts/test_check_memory_file_size.py`
carries `# The real corpus must stay under the shipped default, or the check
ships red` and asserts it directly, and `validate.yml` runs that test.
The whole local `validate` job was then run before the fixing push, which is
what this section is asking for.)

## A reference frame chosen from the initial condition expires as the system moves

The section above is about an instrument that **changed**, leaving every figure
it had already produced stale with nothing pointing at them.

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

**A discharge scoped by file path cannot separate the obligation from adjacent
routine work that touches the same paths, and in the guard's own home repo that
routine work is everywhere.**

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

**Then prove the new guard is non-vacuous by isolating the injected fault to a
shape only it reaches.**

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

**The harness that performs those mutations needs the same scrutiny, because a
mutation it could not apply looks exactly like one the tests caught.**

- **Do:** verify each mutation changed the artifact before scoring its result,
  and surface an inapplicable mutation as its own outcome.
- **Do:** rebuild an alternation from its parsed members when mutating one, so
  position and substring overlap cannot silently no-op the edit.
- **Don't:** score "the tests still passed" as a pass without knowing the
  mutation applied --- an unmutated clause passes for the wrong reason.
- **Don't:** trust a single-sided delimiter token to reach every alternative;
  it reaches every one but the end the delimiter is missing from.

**There is a fourth outcome, and the differs-from-original assert above cannot
see it: a mutation that applies cleanly and is UNFAITHFUL.**

- **Do:** assert the mutant is faithful --- that what it compares against is a
  real member of the set it names --- on top of asserting it differs from the
  original.
- **Do:** build a mutation from a raw literal or a written file, not through a
  nested-escaping heredoc.
- **Don't:** read `SyntaxWarning: invalid escape sequence` as naming the broken
  escape; it names a surviving sibling, and the corrupted one is silent.
- **Don't:** treat "the artifact changed" as "the intended mutation applied" ---
  a corrupted mutant differs from the original too.

**A fifth outcome, which both asserts above pass: a mutation that substitutes a
DERIVED value for its source measures nothing, and scores a clean zero.**

- **Do:** trace a mutant's replacement to its assignment and confirm it is not
  derived from the value it replaces, before recording the mutation's score.
- **Do:** mutate the call site, or wherever the undeepened input still exists,
  when the two candidate values inside the function are not independent.
- **Do:** treat a zero from a mutant you have not provenance-checked as
  unmeasured rather than as evidence of redundancy.
- **Don't:** read "the mutation applied, and the mutant is faithful" as "the
  mutation tested something" --- both asserts above pass on a vacuous mutant.
- **Don't:** pick a replacement by name similarity; the names that read as
  sibling stages of a pipeline are the ones most likely to be ancestor and
  descendant.

**A sixth outcome, and the only one that runs the other way: a mutant that
FAILS for a reason other than the mutation.**

**Location is the usual culprit, and mutation is what puts you in a strange
one.**

**The discriminator is an unmutated copy run from the same location**, and it
costs one command.

- **Do:** run an unmutated copy from the mutant's own location, and treat a
  shared failure as evidence about the location rather than the mutation.
- **Do:** read the mutant's failure message against the change you made, and
  distrust any failure that does not name it.
- **Don't:** score a mutant as caught because the harness recorded a non-zero
  exit --- the asserts above all inspect the mutant, and none inspects where it
  ran.
- **Don't:** treat moving the mutant to a scratch directory as inert; it
  changes the working directory, the module search path, and possibly the
  interpreter, all silently.

**A seventh outcome belongs to the MATRIX rather than to any mutant: a real
failure reported under the wrong mutation's name.**

- **Do:** run each mutation in its own fresh scratch directory, rather than a
  shared one restored between rows.
- **Do:** re-run a surprising row alone before believing it --- an isolated run
  is the cheapest second opinion a matrix has.
- **Don't:** read a matrix's per-row test names as attributable because its
  control passed and its counts look right; misattribution moves the name and
  leaves both intact.
- **Don't:** spend the round diagnosing shared harness state when isolation
  deletes the failure mode outright.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A shared scratch directory reporting one mutation's failure under another's
name".

**One more belongs to the matrix, and it is not an outcome but the matrix's own
PASS CONDITION: a case that flipped for a reason other than the clause.**

Every outcome above asks whether a mutation applied, was faithful, or was
credited to the right row.
This asks what a row has to observe before scoring itself caught, and "did any
case fail" is the wrong answer.
Where the clauses run in sequence rather than as one condition, an earlier
stage can reject the case written for a later clause before that clause is
ever reached, so mutating it changes nothing for its own case while an
unrelated case flips and the row reports caught.

- **Do:** designate, per mutation, the one case that must catch it, and score
  the row on that case failing rather than on any case failing.
- **Do:** read a case that survives a mutation aimed at a clause it never
  reaches as an unmeasured clause rather than a robust one.
- **Don't:** accept "some case flipped" as "the case written for this clause
  flipped" --- those come apart wherever the clauses are stages.
- **Don't:** infer coverage from a matrix whose rows all read caught; the count
  is a fact about the rows, and only the identity check makes it one about the
  clauses.

**Generalize past mutation: a harness needs a self-check against a quantity it
did not compute.**

- **Do:** have a harness compare at least one figure against a quantity produced
  by something other than itself, and fail loudly on disagreement.
- **Don't:** debug the artifact first when a harness reports a uniform or
  otherwise surprising result across a corpus whose members vary --- suspect the
  harness.

**A component that stops failing under mutation is a question, not a cleanup.**

- **Do:** treat a zero mutation score on an existing component as a missing test
  case, until a search for its remaining role comes back empty.
- **Do:** run that search at the moment the score drops, since the guard you
  just added is what made the component look redundant.
- **Don't:** delete a component because mutating it no longer fails the suite
  --- that is the suite describing itself, not the component.

**When the artifact is a GUARD, an empty search is still not licence to delete.**

- **Do:** record a measured-dead guard component in a comment naming the
  measurement, and flag its removal as a separate reviewable simplification.
- **Do:** treat a suite the current round is fixing as unusable evidence about
  what that suite's guard no longer needs.
- **Don't:** delete a redundant path in a guard on suite evidence alone --- for
  ordinary code a wrong deletion costs a failure, and for a guard it costs a
  silent fail-open.
- **Don't:** read this as licence to keep every dead branch; the exemption is
  for guards, where the failure mode is silence, not for code generally.

**The dual of those two sections: a case labelled NON-DISCRIMINATING is a claim
about the current clause set, not about the case.**

**Such a label is worse than no label, because it instructs the next reader not
to count the case.**

- **Do:** re-run the mutation matrix over previously-excluded cases whenever a
  clause is added, and correct each label the new matrix falsifies.
- **Do:** name in the label the clause set it was measured against, so a later
  reader reads a measurement with an expiry rather than a verdict.
- **Don't:** read a non-discriminating label as a property of the case; it
  records a measurement against the clauses that existed when it was taken.
- **Don't:** drop an excluded case as dead weight on the strength of its own
  label, without re-running the matrix that produced that label.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A case labelled non-discriminating is a claim about the current clause set".

## Limits

The rule targets *decidable* checks. Judgments of legibility, intent,
aesthetics, and prose accuracy stay with a human or model reviewer --- but even
these often decompose into a decidable core plus a smaller judgment (declare
the intended outcome as data, assert it mechanically, and review only the
framing). Prefer shrinking the judgment surface over automating a judgment
badly: an instrument with a mushy threshold that misfires trains everyone to
ignore it.

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
every reply already carried a mechanical marker, the Claude
Code attribution footer, sitting unused in the same data. Caught only when
asked directly why the sharper signal hadn't been the first idea.)

## Anchor the discharge as carefully as the trigger --- the discharge is the more expensive half

A guard built from a transcript scan usually has two matchers: one that decides it should **fire**, and one that decides it is already **discharged**.
The instinct is to spend the care on the trigger, because that is the one whose false positives are visible.
That instinct is backwards.

**A false trigger usually costs one note.
A false discharge costs every remaining warning in the session, always.**
The qualifier is load-bearing, and the case record here breaches it.
A trigger is evaluated per event, so a wrong answer is normally wrong once --- but a trigger that matches *durable* transcript content re-matches on every later turn, which is why `no-unshipped-commit.py` fires permanently rather than once.
So the asymmetry is not that a trigger cannot fire forever.
It is that a discharge fires forever *by design*: it is the matcher whose whole job is to set state, so a wrong answer there is unrecoverable rather than merely repeated.
The discharge sets that *state*: once something in the transcript looks like the check was run, the guard is silent from then on, and its silence is indistinguishable from compliance.
That is the failure [`deterministic-tools`](../principles/deterministic-tools.md) warns about --- an instrument that has stopped measuring reports the same thing as an instrument reporting all-clear.

Measured 2026-08-20 on [ai-config#1749](https://github.com/Morrison-Lab/ai-config/pull/1749), which was open at the time of writing --- so the file below is described as that PR proposed it, not as something `main` carries.
`warn-pr-create-without-dupe-check.py`, in the state that PR put it in, anchored its trigger to a command position and carried a docstring paragraph explaining why --- this corpus quotes `gh pr create` constantly, so a substring matcher would fire on every reply citing the rule.
Its discharge, in the same file, was a bare substring search:

```
echo 'run gh pr list first'                     discharged=True
git commit -m 'mention gh pr view here'         discharged=True
heredoc body containing gh pr list --repo o/r   discharged=True
```

The reviewer's sharpest observation was that the hook's own reminder text names `gh pr list --repo <owner>/<repo>` --- so the guard told the user to run the command that would have disarmed it.

**Command-position anchoring is not sufficient on its own, because a heredoc body is full of line starts.**
`^` matches inside quoted prose, so a fenced reproduction block in a PR comment satisfies the anchor.
`hooks/no-unshipped-commit.py` has exactly this shape and fires permanently once a heredoc quotes a commit command ([#1775](https://github.com/Morrison-Lab/ai-config/issues/1775)).

**The machinery already exists, which makes this a [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) finding too.**
`hooks/no-unauthorized-merge.py` solved the same problem across six review rounds, and carries `mask_heredocs` plus its `LEAD`/`PERMISSIVE_LEAD` pair for precisely this reason --- [`check-purpose-before-reusing`](check-purpose-before-reusing.md) records the rounds.
Two newer hooks each re-derived a weaker version instead of reusing it.

- **Do:** apply the same anchoring and the same heredoc masking to every matcher in a guard, including the discharge.
- **Do:** reuse `no-unauthorized-merge.py`'s masking rather than re-deriving it, and say so when you deliberately do not.
- **Do:** test the discharge against prose that quotes it, exactly as the trigger is tested.
- **Don't:** reason about the trigger's self-reference trap and leave its sibling unexamined --- writing the paragraph is what makes the omission feel handled.
- **Don't:** treat a command-position anchor as covering quoted text;
  strip heredoc bodies first.
