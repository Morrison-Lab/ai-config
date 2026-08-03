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

(Morrison-Lab/ai-config#1029:
`scripts/check-context-closure.py` reported the auto-loaded context closure
as 70 files and 803,950 bytes across review rounds.
A code-span regex regression that crossed newlines dropped the closure to 51 files
by swallowing 19 real imports;
no test failed,
and only the moved number caught it.
The same PR tried CommonMark's rule
that an unclosed fence runs to end of document.
On this corpus that dropped `CLAUDE.md` from 69 anchored imports to 50,
because same-length nested fences,
such as an outer triple-backtick fence wrapping an inner triple-backtick R fence,
made the outer closer look like a fresh unclosed opener.
The fix was to report the ambiguous fence
rather than silently consume the rest of the document.)

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

(2026-07-31, `ucdavis/bcs#503`: a spelling check could not run locally, and the
status report named `monotonicity` as the only newly-reachable word.
`monotonicity` passed; `unlabelled` failed --- a British spelling in prose
written minutes earlier.
A three-line pattern scan over the diff, needing nothing installed, then found
`unlabelled` **and** `neighbours` in one pass.
The user's correction was "no guessing".)

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

(2026-07-31, a guard against running heavy R jobs on a cluster's head node:
the reported command was
`R -e 'Sys.setenv(NOT_CRAN="true"); res <- devtools::test()'`.
Splitting on `;` left a fragment leading with `res` rather than an
interpreter, so the one command the hook existed to stop was the one it let
through.
A second bug in the same file had a comment asserting that a leading anchor
kept bare mentions from matching, which it did not -- `grep -rn
'devtools::test'` was blocked.
Neither surfaced from re-reading the code.
Both surfaced from tests, and the first only from the test that pasted the
reported line in unaltered.)

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

(2026-07-31, `ucdavis/bcs#539`: a three-step spelling check --- extract
candidates from the diff, drop those already present on a green `main`, look
the rest up in a dictionary --- reported 52 candidates, 3 unproven, 0 unknown,
and was called trustworthy on the strength of a control fed directly to the
dictionary step.
CI then failed on `SAS's`, a possessive added by the same commit the check had
just cleared.
Its extraction was `grep -oE '\b[a-z]{7,}\b'`: lowercase, seven or more
characters, no apostrophes, so the word was excluded on all three counts and
never became a candidate.
The filtering step was sound --- against green `main` it separated the four
possessives exactly, `arm's` 4 files, `manuscript's` 2, `simulation's` 6, and
`SAS's` 0 --- which is what makes the extraction the whole of the defect.)

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

(`Morrison-Lab/ai-config#1075`, 2026-08-03: the review of a new inject-only
`UserPromptSubmit` hook, `remind-learn-from-review.py`, found its
mechanism-discharge branch matched `memories?/`, `CLAUDE.md`, `/skills/`, and
`/shared/` --- roughly half the repo --- so an ordinary Address-fix edit
discharged the reminder by path match alone, with no check that a lesson had
been recorded, silencing the hook in its own home repo.
The fix scoped mechanism-discharge to `hooks/` and CI paths and required an
explicit learning signal.
The same `UMS_PATH` prefix already ships in `remind-ums-after-error.py`
(`memories?/|MEMORY\.md|CLAUDE\.md|/skills/|^skills/|/shared/|^shared/`,
commented "A write to any of these is a recorded learning"), so the proxy is
not hypothetical; whether its looser fire trigger there --- an error admission
rather than a finding whose fix edits those paths --- makes the coarse
discharge acceptable is the backstop-versus-fire-on-event judgment above.)

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

(Morrison-Lab/ai-config#1047 round 5, 2026-08-03: `claude-review` returned
"Ready for merge" with one non-blocking note --- the PR body said "the parser
is fuzzed for the no-throw invariant", but no fuzzing shipped.
The invariant is real: a parser crash prints a traceback into Bash.
Rather than delete the claim, `fuzz()` was shipped --- a `random.Random`-seeded
adversarial corpus driven through `split_segments` and the full predicate,
plus a subprocess smoke through `main()`.
The first non-vacuity probe injected a bug the `BACKSLASH_CONT` case also hit,
so the suite aborted on that case before `fuzz()` ran; a second probe targeting
an unterminated-quote-with-trailing-backslash shape the deterministic cases
never build was caught by `fuzz()` in isolation, while the real parser passed
4000 rounds.)

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
(Morrison-Lab/ai-config#1042, 2026-08-03: `hooks/no-unreviewed-pr.py`'s
discharge fired only when structural-identity, "last simple command", and
same-PR-scoping clauses all held, and a single regression case that two of the
three clauses each kept correct made reverting any one of them still pass; each
clause needed its own isolating case before the mutation test meant anything.)

## Limits

The rule targets *decidable* checks. Judgments of legibility, intent,
aesthetics, and prose accuracy stay with a human or model reviewer --- but even
these often decompose into a decidable core plus a smaller judgment (declare
the intended outcome as data, assert it mechanically, and review only the
framing). Prefer shrinking the judgment surface over automating a judgment
badly: an instrument with a mushy threshold that misfires trains everyone to
ignore it.

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
