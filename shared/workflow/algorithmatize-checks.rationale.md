# Rationale: algorithmatize checks

The mechanism, evidence, and argument behind the rules in
[`algorithmatize-checks.md`](algorithmatize-checks.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

An LLM eyeballing a log, a diff, a state dump, or a rendered frame for a
property that has a numeric definition is the tell. The model's judgment on
such a check is slower, costlier, and less reliable than the two lines of
arithmetic that decide it exactly --- and unlike the model's read, the
instrument's verdict is reproducible, diffable across revisions, and wireable
into CI so the check runs on every change instead of only when someone thinks
to look.

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

## A threshold pinned to a current measurement needs its rate of change checked, not just its level

The section above is about a metric that will not discriminate anywhere.
This is about a metric that discriminates fine, and a threshold defined
*relative to it* --- a ratchet: cap the value a few hundred bytes, seconds,
or percentage points above wherever it sits today, so the check is green on
arrival and red on the next regression.

A ratchet's whole premise is that "today's measurement" is a stable
reference point.
That premise is a claim about the quantity's own **rate of change**, and
nothing about writing the ratchet tests it --- the check passes the moment
it is written, which reads as confirmation rather than as the one case the
premise was never asked to survive.

Compare that rate against the **interval the check actually has to survive
between measurements** --- a review round, a merge cadence, a day of
ordinary edits elsewhere in the file.
When the quantity moves by a meaningful fraction of the ratchet's own margin
within that interval, the check is red on the next unrelated change, on a
file nobody touched, for reasons the diff in front of the reviewer does not
explain.
That is not flakiness to route around; it is the ratchet reporting on
whichever PR happens to land within the window, rather than on the PR that
grew the quantity.

This is the same comparison
[`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s "Why serial
resolution structurally cannot converge" makes for a different pair of rates
--- there a base branch's merge interval against a review round, here a
measured quantity's growth against the same kind of interval --- and it is
worth reading as one instance of a general move: **before trusting a
threshold set relative to a snapshot, measure how fast the snapshot itself
moves, against the interval the threshold has to hold across.**

Where the two are close, a ratchet is unimplementable, not merely noisy.
The fix is not a wider margin --- a margin sized to survive today's rate
still expires on tomorrow's --- but a **round policy line**, stated as a
rule a reader can hold ("no file over 100 KB") rather than derived from
whatever the corpus happened to measure at write time.

Be exact about what that buys, because the tempting overclaim is that a
round line escapes the comparison.
It does not.
A round line is still a level, so the rate still eats its margin; what
changes is that the margin is **stated and deliberate** rather than an
artifact of when the threshold happened to be written, and that firing has
a known response rather than reading as an arbitrary failure.
A ratchet's margin is accidental and its firing is a surprise; a policy
line's margin is a decision and its firing is the decision arriving.
[`configurable-parameters`](../coding/configurable-parameters.md) already
argues for keeping such a line as a named, adjustable parameter rather than
a buried literal; this adds where the **value** of that parameter should
come from when the temptation is to derive it from a live measurement
instead.

(`Morrison-Lab/ai-config#1398`, 2026-08-12: a per-fragment size cap was first designed
as a ratchet, a few hundred bytes above the corpus's then-largest
auto-loaded fragment.
Measured over roughly two hours between filing and
implementing, `shared/workflow/ardi.md` grew 87,448 -> 93,326 bytes and
`shared/principles/fail-fast.md` grew 89,175 -> 91,835 bytes --- so a cap
pinned to that day's maximum would have gone red within a day on a PR that
never touched either file.
`Morrison-Lab/ai-config#1406` shipped a round 100,000-byte line with
several KB of runway over both, adding a `--fragment-cap` flag and its
rationale to the existing `scripts/check-context-closure.py` rather than
documenting it only here.

The sequel is the evidence for the paragraph above, and it arrived within
the day: #1406 merged at `14:43:53Z`, `Morrison-Lab/ai-config#1407` merged
nine minutes later carrying ordinary additions to both files, and by
`19:20Z` `ardi.md` stood at 95,681 bytes --- 4,319 of runway left, under a
day at the rates above.
So the round line did not escape the rate comparison, and was never going
to.
What it bought was a firing with a known answer: split case records out to
a `.cases.md` companion, which is what `Morrison-Lab/ai-config#1413` did,
merging at `2026-08-13T04:47:54Z`.
By then `ardi.md` had reached 98,655 bytes, leaving 1,345 of runway, and the
split returned it to 92,734 while `fail-fast.md` went 94,469 to 91,244.)

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

### Scale that from one reported input to a corpus of real ones

The rule above fixes the exact input that prompted the guard, and asks for
negative cases in the same pass so an over-blocking guard does not get switched
off.
Both halves run on your own imagination, which is the faculty already known to
be the problem here: you write the negative case for the over-block you can
foresee, and the over-block you cannot foresee gets no case at all.

Where the instrument's input is text that people actually write, that gap
closes cheaply.
Collect the real inputs it will meet --- the review bodies, the commit
messages, the log lines --- for a set whose right answer you independently know,
and run the instrument over all of them.
The corpus beats any number of authored cases for one reason: **you did not
choose its wording**, so it cannot share the blind spot that a case written by
whoever already understands the rule necessarily does.

Expect it to find failures in **both** directions, which is what an authored
suite does not.
An under-block it finds is a phrasing you would not have written --- a real
verdict worded a way the pattern does not reach, so it neither blocks nor
supersedes anything.
An over-block it finds is the more valuable of the two, because that direction
makes the gate unsatisfiable for a legitimate input and is therefore worse than
the under-block being fixed --- and it is the direction authored cases almost
never reach, since a case is written from the bug you already know about.
So re-run the corpus after every widening, not only once at the end.

The corpus also changes what you can report.
"Reproduces ground truth on N real inputs I did not author" is a claim a reader
can re-run; a suite total is a claim about cases you chose, which is the
provenance problem [`ardi`](ardi.md)'s whole-suite rule describes.

**A uniform result across the whole corpus is a fact about the harness, not
about the subject.**
The corpus earns its value from its members varying, so a verdict that does not
vary with them did not come from them.
All-mismatch is the easy version to catch, since it fails loudly --- but
failing loudly is only the safe direction, not a correct one, and the loudness
invites reading it as a real finding about the thing under test.
Check the comparison harness's own plumbing first: a ground-truth lookup keyed
by an identifier the harness derives from a filename is the usual culprit, and
a derivation that silently yields a wrong key produces exactly this signature.

Note the base rate while you are there.
Instrument bugs cluster in the checking code precisely because the checking
code is what nobody checks --- the subject under test has a suite, a reviewer,
and a guard, while the throwaway harness written to evaluate it has none of the
three, and is written fastest.

The section above asks for "a set whose right answer you independently know", and knowing it is usually the expensive part --- someone has to label the inputs, and a hand-labelled set is small and inherits its author's blind spot.

For one whole class of instrument the label comes for free, and the class is the common one: any instrument whose job is to **flag** something in text a CI check already gates.
That check is green on the default branch, so every in-scope file there is one CI accepts --- which makes any firing on that corpus a false positive **by construction**, needing no judgment and no labelling pass at all.
The corpus is also as large as the repository and was written by everyone who has ever committed to it, which is exactly the property the section above wants and cannot normally afford.

Note it is one-sided, and say so rather than overclaiming.
The green establishes that nothing there should fire, so it finds every false positive and no false negative --- a clean audit means the instrument does not over-report on today's corpus, and says nothing about what it misses.

**Ship the audit as a flag on the instrument, not as a one-off script.**
The whole value is that it re-runs: the table it audits will gain entries, and a check performed once is a claim about the day it ran.
Wiring it into the pre-push sweep turns the prose rationale that motivated the table into a standing predicate, per [`deterministic-tools`](../principles/deterministic-tools.md), and it is the step that makes the difference between having audited and having a guard.
Then confirm it fires: reintroduce one of the entries it removed and require the audit to fail.

**The audit has to enter at the instrument's own input, exactly as a negative control does.**
"A negative control must enter at the real input" below is stated for controls, and it governs the audit for the same reason --- an audit that queries the lookup table directly rather than calling the scanner's entry point bypasses every suppression the real path applies, so it reports collisions the shipped instrument would never have raised.
That failure is not the uniform-verdict one above: the result **varies** with the corpus and is simply wider than the truth, so nothing about it looks broken.

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

**That remedy has a precondition worth naming, because a comment gives no sign
of which side of it a claim sits on.**
Mutation decides an attribution whose subject is **your own code**, since you
can remove the part being credited.
A comment crediting the **runtime environment** --- what the kernel, the init
process, the shell, or the platform does --- has nothing in the diff to remove,
so mutation cannot reach it and only measuring the environment can.
Both are cause claims and both arrive in the same artifact, so discriminate on
whether the subject is something you can edit;
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A symptom that both
a mechanism and its opposite predict is evidence for neither" owns that case.

**Running the mutation is not the check, because the rule above asks WHETHER
the case flips and a comment can be wrong about WHICH WAY.**
Read the operative verbs: "confirm the behaviour **changes**", "confirming the
case **flips**".
Both are satisfied by any flip at all.
So a mutation can pass green while the prose beside it asserts the opposite
failure direction, and nothing in the round notices --- the rule was followed,
and following it was not enough.

The missing step is free, and it needs no re-derivation.
**A mutation's recorded before/after pair is itself a statement of the failure
direction**, already in machine-checkable form: an entry whose pair reads
`allow -> block` says the code *with* the clause allows and the code *without*
it refuses, so removing the clause over-blocks.
Read that pair back against the sentence, and a contradiction is visible by
looking.

Expect the two artifacts to sit in **different files**, which is most of why
nobody compares them.
The prose lives beside the code it explains and the mutation lives in the test
suite, so reading either one never brings the other into view --- and they
still ship in the same commit, by the same author, in the same sitting, so this
is not a stale note somebody left behind.
The comparison has to be sought; proximity will not supply it.

It matters more than an ordinary wrong sentence because
[`fail-fast`](../principles/fail-fast.md)'s safe-versus-dangerous asymmetry is
the thing that decides whether to accept a later request to loosen a guard.
A comment that labels an over-block as the lenient direction inverts that
judgment for the next editor, in the artifact written to guide them.

Two practical notes.
When a reviewer disputes an attribution, the disproof may already be sitting in
your own diff rather than needing a fresh experiment.
And check whether the direction claim was stated twice --- a rationale comment
and a fixture's docstring routinely carry the same sentence, so fixing the one
the reviewer quoted leaves the other standing, per
[`fail-fast`](../principles/fail-fast.md)'s partial-guard rule.

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

**"Stale" here means the earlier reading has been retired, which holds only
while one instrument has a before and an after.**
Where both revisions stay live at once --- a consumer pinning one while the
tool's default branch carries another --- the earlier figure is not obsolete
and the later one is not its correction.
See
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A re-measurement
with a different instrument is a second measurement, not a correction", which
owns that case.

## Publishing a command is not enough; it has to be the command you ran

The section above closes on "publish the command", and that rule is right.
Its failure mode sits one step inside it.
A diff can publish a command, satisfy the rule exactly as written, and publish
a **different** command from the one that produced the number.

The two copies are usually written minutes apart by the same author, and they
diverge because each is tuned for a different job.
The command you **run** is tuned against real data until it works, so a pattern
that over-matches gets tightened the first time it returns a wrong hit.
The command you **publish** is tuned to read well, so the same pattern gets
simplified for exposition, and nothing ever runs the simplified form.
One is tested against reality and the other is tested against nothing.

That inverts the usual reason a published command is wrong.
It is not that nobody checked it.
Somebody checked a near neighbour of it, carefully, and shipped the neighbour's
weaker sibling, so the diligence is real and lands one artifact away from where
it was needed.

The cost is worse than an ordinary unverified literal, which
[`ardi`](ardi.md) already covers under the rule that a literal is the part a
reader executes.
A published command carries the authority of whatever it illustrates, so a
reader inherits it as the prescribed form and reruns it indefinitely.
It also defeats the mechanizable check the section above proposes: re-running
the published command and comparing re-runs the weaker one, confirming the
published number with the published pattern, and never meeting the pattern that
actually produced it.

The check is a string comparison and costs nothing.
Before pushing, diff the command in your prose against the one in your shell
history or your own verification table.
Where they differ, the one you ran is the authority, because it is the only one
with evidence behind it.

This is also a DRY finding, per
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md):
two copies of one command, only one of them owned by anything that tests it.

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
single-sided form leaves exactly one alternative unreachable --- measured on
this corpus's own negation-prefix guard, each form mutated seven of eight and
silently no-opped on the opposite end.
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

**There is a fourth outcome, and the differs-from-original assert above cannot
see it: a mutation that applies cleanly and is UNFAITHFUL.**
That assert reports `inapplicable` when the mutated artifact matches the
original, which is necessary and not sufficient.
A mutation can differ from the original, run to completion, and still not say
what its author wrote --- so the assert passes, the suite runs, and the harness
reports a plausible wrong number for a mutant nobody built.

The mechanism is escaping, and it appears whenever the mutation string is built
through a nested context rather than written out.
A doubled backslash inside a shell heredoc feeding Python collapses to a single
backslash before Python parses the literal, so `\\b` arrives as `\b` and becomes
a **backspace**.
A mutation meant to restore an older `pat == r"changes\s+requested\b"` guard
shape therefore generated a comparison string ending `\x08`, which can never
equal any member of the list it is compared against --- so the mutation silently
became "remove the guard entirely", and reported four failures where the
faithful mutation reports one.

Two properties make it worse than an ordinary typo.
The corruption is **selective**, so the string still reads correctly at a
glance: in that same literal `\\s` survived as a literal backslash-s while
`\\b` did not, because `\s` is not a valid Python escape and `\b` is.
And the interpreter's one diagnostic, `SyntaxWarning: invalid escape sequence`,
names `\s` --- the escape that **survived** --- rather than the one that broke,
so the only signal emitted points away from the defect.

Two remedies, both cheap.
Build a mutant from a **raw literal**, or write the mutant source to a **file**,
rather than through a heredoc that re-escapes it; note that `repr()` of a raw
string does not reproduce a source line written as `r"..."`, which made a
different mutation in the same harness report `ANCHOR MISSING` instead --- a
vacuous row, but one that announces itself.
And **self-check the mutant against its own target**: assert that the value it
compares against is genuinely a member of the collection it is supposed to
match.
One `assert` catches this where the differs-from-original check cannot.

**A fifth outcome, which both asserts above pass: a mutation that substitutes a
DERIVED value for its source measures nothing, and scores a clean zero.**
The block above splits on whether the mutant *says what its author wrote*, and
its remedy is to build the mutant from a raw literal and assert that the value
it compares against is a real member of the set it names.
Neither reaches this case, because here the mutant says exactly what its author
wrote.
It is syntactically perfect, it differs from the original, it runs to
completion, and it is **semantically vacuous** --- the value substituted in is
computed *from* the value substituted out, so both sides of the mutation carry
the same ancestor and the behaviour cannot change.

The zero it reports is the dangerous part, because a zero from a mutation
harness has an established, reassuring meaning: no test distinguishes this
clause, so the clause is a candidate for the measured-dead treatment two blocks
below.
A vacuous mutant produces that same zero while establishing nothing at all, so
it does not merely fail to test the clause --- it argues, in the harness's own
vocabulary, that the clause is redundant.
That is the [`fail-fast`](../principles/fail-fast.md) figure where a check's
failure path and its pass path print the same thing, arriving at the one number
a reader is most likely to act on.

The check is provenance, and it is one question per mutant: **can the
replacement vary independently of the thing it replaces?**
Where one is computed from the other --- a masked form of the same buffer, a
normalized copy, a filtered subset, a field read off the same object --- the
mutation is probing a shared ancestor and the answer is fixed before the suite
runs.
Trace the replacement back to its assignment rather than judging it by name;
two locals whose names suggest different stages of a pipeline are exactly the
pair most likely to be one derived from the other.

When the two are not independent, mutate somewhere that is.
The **call site** is usually the nearest such place, because it is where the
genuinely different input still exists before any derivation has been applied.

Read this as the same word "independent" the block below applies to a harness's
cross-check figure, moved one artifact over: there the second quantity must have
an origin the harness did not compute, and here the replacement must have an
origin the original did not compute.
Both fail silently, and both fail by comparing something against itself.

**A sixth outcome, and the only one that runs the other way: a mutant that
FAILS for a reason other than the mutation.**
The five above are all the same direction --- a mutant scores clean while
testing nothing, so the harness under-reports.
This one over-reports.
The mutant genuinely fails, the harness genuinely records a failure, and the
failure has nothing to do with the change that was made.

Every assert this section has accumulated passes here, because each of them
interrogates the **mutant** and this is a fact about the **environment**.
The artifact differs from the original, so the differs-from-original check
passes.
It says what its author wrote, so the faithfulness check passes.
Its replacement is independent of what it replaced, so the provenance check
passes.
And then the run dies on something none of them looked at.

**Location is the usual culprit, and mutation is what puts you in a strange
one.**
A mutant is normally written to a scratch directory, because that is how you
avoid editing the real artifact --- so the act of being careful is what moves
the run.
Three things change with it, none of them announced: a resource resolved
relative to the working directory is no longer there, an interpreter picked up
from a different `PATH` may be a different version, and the scratch directory
goes on the front of the module search path, where an unrelated file can shadow
a standard-library name.

Measured on one machine, 2026-08-09, with an **unmutated** copy of
`ucdavis/bcs#614`'s `.github/scripts/detect-redaction-diff.py` --- the same
script whose vacuous self-test
[`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md)
records --- placed in `/tmp` and run from there:

| run | outcome |
|---|---|
| unmutated copy, from the repo root | self-test passes |
| unmutated copy, from `/tmp` | `error: .gitleaks.toml not found` |
| `python3 -c "import inspect"`, from `/tmp` | executes a stray `/tmp/inspect.py` |
| the machine's default `python3` | 3.10, while the script requires 3.11+ |

Three independent ways for a run in that directory to fail, none of them a
mutation, and each producing a traceback that reads like a real finding.

**The discriminator is an unmutated copy run from the same location**, and it
costs one command.
A mutant that fails where its unmutated twin also fails has told you about the
location.
A mutant that fails where its twin passes has told you about the mutation.
Nothing short of that separates them, because the mutant's own traceback names
whatever broke first rather than whatever you changed.

Read this as [`ardi`](ardi.md)'s "seen to fail" rule completed: that rule
requires a test to be **seen to fail**, and this one requires it to be seen to
fail **for its own stated reason**.
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s "Mutate the fix,
not only the test" already asks for exactly that, and enumerates six mechanisms
--- all six of which are ways a mutant wrongly *passes*.
This is the direction that list does not carry.

**A seventh outcome belongs to the MATRIX rather than to any mutant: a real
failure reported under the wrong mutation's name.**
The six above each interrogate one mutant --- did the edit apply, does it say
what its author wrote, is its replacement independent of what it replaced, did
it fail for its own reason.
A matrix runs several in sequence, and sequence is a property none of those
checks can see.

Observed directly, and stated as an observation because the mechanism was never
pinned down.
A five-mutation matrix run in **one shared scratch directory** --- copy the
files once, mutate, run, restore, repeat --- reported mutation M3's row as
failing a test belonging to M2's clause.
Two runs disagreed with it: the identical mutation run alone named the right
test, and the harness's own mechanism reproduced in a fresh directory named the
right test too.
Nothing beyond that was established, so do not infer a cause from it.
What is established is that the shared directory produced the misattribution
and a fresh one per mutation did not.

Note that every discriminator above passes here, the sixth outcome's included.
An unmutated control was run and passed, so "a mutant that fails where its twin
also fails has told you about the location" does not fire --- the location is
fine and the **sequence** is not.
The row also reported a genuine failure, so nothing keyed on *whether* a
mutation was caught would flag it either, the block below's totals cross-check
included.
Only the name is wrong, and the name is the whole of what a seen-to-fail table
publishes.

The remedy is to remove the failure mode rather than to find it.
Give each mutation its own fresh directory.
That is one `mkdtemp` per row against an open-ended investigation into shared
state, and it ends with the mode gone rather than explained --- which is worth
paying for because a mutation matrix is **evidence you publish**, so a harness
bug inside it is indistinguishable from a finding about the tests, exactly as
the block below says of any harness's own output.

Distinguish it from the suite-level trap higher up, which is the same
misattribution one axis over: there a *sibling test case* in the same run
aborts first, so the catch is credited to the wrong test; here the name belongs
to a *sibling mutation* in another row of the same matrix.

**One more belongs to the matrix, and it is not an outcome but the matrix's own
PASS CONDITION: a case that flipped for a reason other than the clause.**
Every outcome above asks whether a mutation applied, was faithful, or was
credited to the right row.
This asks what a row has to observe before scoring itself caught, and "did any
case fail" is the wrong answer.

The three remedies already on this page all shape the mutation or the input,
and none of them checks what the row concluded.
The suite-level trap says to aim the fault where the deterministic cases cannot
reach it.
The AND-clause rule says to construct an input where only the target clause
keeps the result correct.
The harness rule says to assert the artifact actually changed.
A matrix can satisfy all three and still score a row on the wrong case,
because every one of them is a precondition and none is an acceptance test.

**The gap opens wherever the clauses are STAGES rather than conjuncts, which
the AND-clause rule does not reach.**
That rule assumes the clauses are evaluated together, so an input reaching the
guard reaches every clause.
A staged matcher rejects a case at the first stage that fails, so a case
written for a late clause can be dropped early and never exercise the clause at
all.
Mutating that clause then changes nothing for its own case, while an unrelated
case flips for its own unrelated reason and the row reports caught.

The distinguishing feature is that this failure **inflates** the matrix.
An unmeasured clause reads as a measured one, so the matrix's own summary line
argues that coverage is complete, which is the one claim it cannot support.
That puts it alongside the inapplicable-mutation case rather than beside an
ordinary miss: both convert an absence of evidence into a positive report, and
both are the [`fail-fast`](../principles/fail-fast.md) figure where a check's
failure path and its pass path print the same thing.

The fix is one assertion per row and costs nothing to run: name the case that
must catch this mutation, and fail the row when a different case is the one
that flipped.
It is also self-diagnosing, since the row that fails names the case that was
supposed to catch it, which is exactly the case whose construction is wrong.

(`Morrison-Lab/ai-config#1528`, 2026-08-16, a `Stop` guard for a quoted phrase
attributed to a file that does not contain it.
The first draft of its test suite reported every clause caught.
Adding the per-mutation named case turned **7 of 11 clauses** from caught to
unmeasured: their cases were being rejected at the attribution-cue stage,
several clauses before the one each was written for.
The cases were rebuilt around the matrix rather than the matrix relaxed, and
the merged suite runs 16 cases against 12 clause mutations.)

**Generalize past mutation: a harness needs a self-check against a quantity it
did not compute.**
A harness bug and a real finding are indistinguishable from the harness's own
output, because both arrive as a number the harness produced.
What separates them is a second quantity with an independent origin --- the
suite's own reported failure count, the corpus's own ground truth, the figure a
different tool reports over the same input.
A section-derived failure count that over-counted by a constant was caught only
because the harness compared its own total against the total the suite itself
printed and said `HARNESS DISAGREES`.
A ground-truth extractor using `rfind("Verdict")` landed on prose *discussing*
verdicts and blamed the classifier for three mismatches that were its own.
Neither is visible to a harness that only reports what it computed.
This is the negative-control rule below aimed at the harness's arithmetic rather
than at its input: a control proves the instrument can fire, and a cross-check
proves the number it produced is the number it meant.

**A component that stops failing under mutation is a question, not a cleanup.**
Adding a new, stronger guard alongside older ones routinely leaves one of the
old components **dead** against the suite: mutate it away and nothing fails,
because the new guard already catches every case the suite holds for it.
The reading that suggests itself is that the old component is now redundant, and
deleting it is the tidy move.

That is wrong, and wrong in the fail-open direction, because what the suite just
reported is a fact about **its own coverage** rather than about the component's
necessity.
So invert the question.
Ask where the dead component is *still* load-bearing, looking specifically for
an input the newer guard cannot see.
The search either finds a real case --- in which case the component stays and
the suite gains the case it was missing --- or it comes back empty and you
delete on evidence instead of by inference.

Sequence is the part that is easy to miss: adding the new guard is what *creates*
the dead component, so the moment a mutation score drops to zero is the moment to
look, not a later tidying pass.

**When the artifact is a GUARD, an empty search is still not licence to delete.**
The branch above ends by deleting on evidence once the search for a remaining
role comes back empty.
That holds for ordinary code, where a wrong deletion surfaces as a failure.
It does not hold for a guard, because the costs are asymmetric: a redundant path
costs a few characters, while removing one that was load-bearing fails **open**,
and a guard that fails open is silent by construction.

The asymmetry sharpens when the suite is itself the thing under suspicion.
A round whose whole subject is that a guard's suite had been incomplete cannot
then cite that suite as evidence a component is unnecessary --- the search came
back empty using the very instrument the round is correcting.
So the emptier the result looks, the more it is worth asking which of the two
things it actually measured.

Report the measurement instead of acting on it.
Keep the component, record in its own comment that it is measured dead and by
what, and say plainly that removing it is a reviewable simplification rather
than a bug fix.
That hands the human a decision they can make on wider evidence than the suite,
which is the disposition
[`report-mistakes-proactively`](report-mistakes-proactively.md) already
prescribes for anything noticed but out of scope --- and it keeps the finding
visible instead of resolving it silently in the fail-open direction.

**The dual of those two sections: a case labelled NON-DISCRIMINATING is a claim
about the current clause set, not about the case.**
Both sections above track a clause whose mutation score falls to zero.
A case's score can rise from zero just as quietly, and the label asserting it
cannot is the artifact that goes stale.

A mutation matrix runs against the clauses that exist when it runs, so a case
failing under none of them really is non-discriminating at that moment, and
labelling it so is honest rather than sloppy.
Adding a clause changes the matrix underneath the label.
The case can become the only one that fails under some mutation while nothing
announces the change: the case keeps passing, the suite stays green, and the
label reads as settled precisely because it was true when written.

**Such a label is worse than no label, because it instructs the next reader not
to count the case.**
An unlabelled case is at least weighed on its merits.
A case marked "not evidence" is pre-excluded from the count, so a later
simplification pass can drop it as dead weight --- taking with it the only input
that separates a specific wrong fix from the right one.
That is [`fail-fast`](../principles/fail-fast.md)'s partial guard reading as
coverage, arriving through a comment rather than through a code path.

The same reasoning covers any **exclusion annotation** on a test or a check:
`skip`, `xfail`, "known-vacuous", "kept for documentation".
Each one asserts a relationship between a case and the code, and the code moves.

The remedy is a trigger rather than more care, and it is the trigger the
dead-component section already uses one direction over: growth in the clause set
is the moment to look.
Re-run the matrix over the cases previously labelled non-discriminating, and
rewrite every label the new matrix falsifies.

## A required-subset assertion is not an inventory-pinning test

**A test that loops a hand-written table and asserts each entry is present in
a production list looks like it pins that list.**
It pins only the listed entries as a required subset of the production
collection.
The assertion never reads what else that collection holds, so it confirms the
named entries are present somewhere inside it and nothing more.

The overclaim usually sits in the docstring, since that is the sentence
describing the test's *purpose* rather than what the assertion compares.
"Pins the deny list" and "confirms every required rule is present" read as one
claim, and only the second is what a subset assertion checks.
The gap stays invisible until something is deleted, because a subset assertion
cannot fail on an addition, and cannot fail on the deletion of anything except
one of its own named members.

Set equality, asserted in both directions, is the fix where the test's purpose
is to pin an inventory: every required entry is present, and nothing present
is unaccounted for by the table.
The second direction is what turns the table from a sample into an inventory.
A production entry added with no matching table entry then fails the suite
immediately, rather than silently widening the gap between what the table
claims to pin and what the collection actually holds.

That qualifier is doing work.
A subset assertion is the right shape for a test that deliberately samples ---
a few representative entries whose presence matters, over a collection
expected to grow.
The defect is a sampling assertion described as an inventory one, not the
assertion form itself.

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

That case record originally called the footer *unambiguous*, and
[`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md) has since
qualified it: the footer separates an agent post from a **human** one, and
does not separate this session from a peer agent session.
The lesson here is unaffected, because it is about *noticing* an available
mechanical signal rather than about how much that signal proves --- but note
the pair, since "mechanical" and "sufficient" are different properties and
this section is only ever arguing the first.
