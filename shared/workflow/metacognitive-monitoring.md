Monitor your own claims as you make them.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`metacognitive-monitoring.rationale.md`](metacognitive-monitoring.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`metacognitive-monitoring.cases.md`](metacognitive-monitoring.cases.md), moved out of the auto-loaded context.

## Confidence is a warning sign, not a green light

The natural stopping rule for checking is feeling sure, and the article
reports that it runs the wrong way:

## Key on claim type, because confidence cannot be the trigger

If confidence is inversely related to accuracy, it cannot be what fires the
check.

- **State** --- is it green, is it pushed, does it exist, is it public.
  Re-query, never recall.
- **Scope** --- all, every, none, only, the whole corpus.
  Check the population rather than the sample that came to mind.
- **Cause** --- it failed because, this is flaky, that change broke it.
  Ask what else produces the same observation.
- **Inference** --- this measurement shows, therefore.
  State what the measurement establishes and what you are claiming as two
  sentences, and check the second is not wider than or beside the first.
- **An unexamined default** --- a flag, a template, a glob, a base ref.
  Name it and decide it, rather than inheriting it silently.

## A premise you were handed is still a claim

All five types above describe assertions **you** generate, so all five trigger
on the act of writing one.

- **Do:** restate a load-bearing premise explicitly and name what would
  falsify it, before building on it.
- **Do:** read a hedge in the user's own wording as a request for
  verification.
- **Don't:** treat "the user told me" as having checked -- it establishes what
  they believe, not what is true.
- **Don't:** report a classification built on an unverified premise without
  saying which premise it rests on.

**The source need not be the user, and a reviewer's finding is the variant this
section's own tell cannot catch.**

**Comprehension feels like verification from the inside.**

**Delegating the check feels like having made it.**

**The asymmetry inverts for a reviewer's incidental all-clear, which is the
shape that reaches code.**

- **Do:** compare an aside's evidence scope against its claim scope, since
  re-running true evidence confirms nothing about the wider claim.
- **Do:** write the case the evidence skipped before exempting a code path on
  the strength of the aside.
- **Don't:** treat attached evidence as making a claim checked --- it makes the
  narrow half checked and the general half more persuasive.
- **Don't:** read the conclusion-sound, particulars-unreliable rule above as
  covering this; here the particular is impeccable and the conclusion is not.

- **Do:** verify a finding's particulars before restating them as fact, even
  when its conclusion is obviously right.
- **Do:** name the check you ran, so a relayed finding stays distinguishable
  from a confirmed one.
- **Don't:** read a reviewer's flat, cited phrasing as evidence that anything
  was checked -- confidence is the house style of that genre, not a signal.
- **Don't:** count a dispatched verification as a completed one.

**A subagent's report arrives in the same position, and the bullet directly
above stops one step short of it.**

**You framed the question.**

**Its conclusion usually has a true neighbour.**

**The same asymmetry decides where to look in the delivered WORK, and there it
points at the deviation the agent flagged.**

- **Do:** review a delegated diff at the flagged deviation first, before the
  parts that merely followed the brief.
- **Do:** treat the rationale and the implementation as two claims, and check
  the second against the first.
- **Don't:** read a disclosed deviation as a handled one -- disclosure is where
  the review starts.
- **Don't:** stop at "the reasoning is sound"; that is a verdict on the
  sentence, not on the code.

- **Do:** run the deriving query before repeating a subagent's factual claim to
  a human, and name that query beside the claim.
- **Do:** re-derive the particulars specifically -- the count, the identifier,
  the error string -- even where the conclusion is obviously right.
- **Don't:** treat having read a report as having checked it.
- **Don't:** accept a check that confirms a true *neighbour* of the claim as
  confirming the claim.
- **Don't:** generalize this into distrusting subagents; the rule picks which
  **half** of a report to re-derive, not whether to use one.

**Verifying ONE particular from a report does not transfer to the one beside
it, and a reviewer confirming the checked half launders the unchecked one.**

- **Do:** count the independent claims in a report sentence before quoting it,
  and derive each one you intend to publish.
- **Do:** re-read a reviewer's confirmation for which claim it actually names,
  since it confirms the half you verified and is silent on its neighbour.
- **Don't:** let a real derivation against one particular stand in for the
  particular next to it --- adjacency in one sentence is not evidence.
- **Don't:** reach for the true-neighbour or reachable-half rules here; both
  particulars are independent, and both were one command away.

**A hedge you attach for one audience is owed to the other, and writing it
once is the tell.**

- **Do:** treat writing "verify this" into a brief as a trigger to qualify the
  same claim wherever else you have just stated it.
- **Do:** name the field or query a state claim rests on, so the reader can
  fail it the way the agent would.
- **Don't:** let a claim reach the user unqualified because the copy sent to an
  agent carried the hedge.
- **Don't:** read having delegated the check as having qualified the claim;
  that is the dispatched-verification bullet above, one audience over.

## An action you recommend is a claim about state

The five types above fire on an assertion, and the section above extends them
to a premise you were handed.

- **Do:** re-query an artifact's state immediately before recommending an
  action on it, exactly as you would before asserting that state.
- **Do:** name the query and when it ran, so a reader can tell a fresh read
  from a recited one.
- **Don't:** treat a recommendation as exempt because it contains no status
  word.
- **Don't:** build one from the recap's own status table, however recently
  that table was assembled.

## Calling your own note stale is a state claim about that note

The section above finds a state claim hidden inside a recommendation.

- **Do:** open the file before saying it is stale, and quote the line you
  believe is wrong.
- **Do:** treat an index, summary, or description line as a pointer only --- it
  routinely omits the exact fact in dispute.
- **Don't:** infer a stored fact from where a repo lives, from a naming
  convention, or from anything else obvious enough to feel like it excuses the
  read.
- **Don't:** offer "my note is stale" as the explanation for a failure you have
  not diagnosed yet; that is a second unchecked claim, invented to account for
  the first.

## Question the answer that arrives without deliberation

This is distinct from the confidence point above, and harder to catch.

## The moment is composition time

A rule with no moment attached is read only by whoever was already careful.

## Illusions of knowing have an exact software form

The [Wikipedia article](https://en.wikipedia.org/wiki/Metacognition) notes that
"students often mistake a lack of effort for understanding when evaluating
themselves and their overall knowledge of a concept".

## Verification of the reachable half does not transfer to the unreachable half

The section above concerns one claim whose supporting command was narrower than
it looked.

- **Do:** mark which claims are measured and which are recalled, and cite the
  recalled ones.
- **Do:** date a claim about a third-party platform, since its defaults move.
- **Don't:** let a rigorously verified section lend its tone to an adjacent
  unverified one.

## Search for the artifact instead of arguing about whether it would exist

The section above concerns an instrument you ran whose scope you did not check.

- **Do:** convert a mechanism question into a search for its artifact --- a
  comment, a file, a row, a log line --- before reasoning about it.
- **Do:** treat "nobody has ever observed X" as stronger than any argument that
  X should occur.
- **Don't:** accept reviewer agreement as evidence for a mechanism claim; a
  reviewer checks the argument you gave, not the record you did not consult.
- **Don't:** let the future tense of the claim hide that the answer is already
  in the past.

## Ask whether a candidate can produce the effect at all, before measuring how much it does

The section above says to stop reasoning and go look for the artifact.

**A symmetry you find striking is worth asking what it implies.**

- **Do:** ask whether a candidate can produce the effect at all before building
  anything to measure how much of it that candidate produces.
- **Do:** state the constraint that rules a candidate out --- a conservation
  law, a symmetry, a geometry --- so a reader can refute it with one
  counterexample.
- **Do:** ask what a striking regularity in the data is the signature of,
  before reading it as support.
- **Don't:** treat an instrumented measurement as the rigorous option when a
  free structural check settles the same question.
- **Don't:** confuse a decidable constraint with a plausible mechanism story;
  the section above bans the second, not the first.

## A symptom that both a mechanism and its opposite predict is evidence for neither

The two sections above are a pair, and this is the case they leave between
them.

**Inferring a permanent state from an immediate one is the commonest shape.**

**A comment justifying a design choice is where such a claim goes unchecked
longest.**

**Mutation is the remedy for the neighbouring case and is unavailable for this
one.**

- **Do:** name what the opposite mechanism would have produced, and treat a
  matching prediction as meaning nothing has been tested yet.
- **Do:** measure the environment directly when a comment appeals to its
  behaviour, and timestamp the result, per
  [`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md).
- **Do:** extend the observation window before inferring that a state is
  permanent.
- **Don't:** read a symptom as confirming the mechanism you inferred from it
  --- that is the same evidence twice, not a check.
- **Don't:** reach for mutation on a claim about the runtime environment; there
  is nothing to mutate, and finding that out reads as the claim being
  unfalsifiable rather than as the wrong instrument.
- **Don't:** treat a comment as fact-checked because the code it explains
  works.

See [`metacognitive-monitoring.cases.md`](metacognitive-monitoring.cases.md),
"A symptom that both a mechanism and its opposite predict".

## Read the artifact that failed, not the one beside it

The section above governs a symptom that two opposite mechanisms both predict.
This governs a cause read off the **wrong artifact** entirely --- the failing
step's neighbour, the sibling job, the log line above the error.

The pull is structural rather than careless.
A failure is usually surrounded by context cheaper to reach than the failure
itself: a neighbouring step's env block prints in full where the failing step's
own output needs another fetch, so the adjacent artifact is what you meet
first.
And it frequently contains something anomalous, because a neighbour of a broken
thing is often a little odd for its own reasons --- which reads as
corroboration rather than as coincidence.

What makes this worse than an ordinary guess is that the resulting claim
carries a specific, checkable-looking particular lifted from a real artifact.
"The PR-number variable was empty" is not vague.
It names a variable, a value, and a place it was observed, so it survives
scrutiny a vaguer guess would not --- and every one of those particulars is
true of a step that did not fail.

One question settles it, asked before the claim is written: **is this
observation from the thing that failed?**
Where it is not, the claim is a hypothesis rather than a finding, and it stays
labelled one until the failing artifact's own output is read.

- **Do:** read the failing step's own output before naming a cause, however
  suggestive a neighbour's looks.
- **Do:** label a cause drawn from adjacent evidence as a hypothesis, and name
  the artifact it came from.
- **Don't:** treat an anomaly in a sibling artifact as the cause of a failure
  in this one --- proximity is not evidence.
- **Don't:** read a specific-sounding particular as verification; the
  specificity is inherited from the artifact you did read, not from the one you
  are explaining.

See [`metacognitive-monitoring.cases.md`](metacognitive-monitoring.cases.md),
"A cause read off the step next to the one that failed".

The same substitution happens to claims that are not about a failure's cause
at all --- about what a plugin contains, where a file is read from, whether a
mechanism runs --- where nothing frames a neighbour as a neighbour and this
section does not fire.
[`verify-the-right-artifact`](verify-the-right-artifact.md) is the general
case, and names the shapes the substitution takes.

## A correction inherits its instrument, so a second reading is not a check

"Illusions of knowing" above concerns a **single** reading whose scope went
unexamined.

### The tell

Unusually mechanical, and observable in the sentence being composed:

### Which contradiction fires it

Not every changed number.

### Why no instrument decides this

Worth stating plainly, per
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits", so nobody builds
the guard and then switches it off.

- **Do:** cross-check with a different source of truth before publishing a
  figure that contradicts one you already published.
- **Do:** name the mechanism that explains the change, and treat being unable to
  name one as evidence the instrument is the problem.
- **Don't:** count a sibling command that reads the same field as a second
  opinion.
- **Don't:** let the act of retracting stand in for having verified the
  replacement --- a correction is a claim, and it carries its instrument with it.

## A retraction is only as good as the instrument's reach

The section above concerns a second reading from the **same command**, where
the gauge is shared and so proves nothing.

- **Do:** ask what a positive result would have looked like, and where it would
  have appeared, before treating a null result as grounds to withdraw a claim.
- **Do:** state the scope a check covered when reporting it, so a reader can
  see what it could not have reached.
- **Don't:** retract on silence from an instrument whose input excluded the
  evidence --- soundness is not reach.
- **Don't:** read the effort of correcting yourself as evidence that the
  correction is right.

## "Unresolved between two sources" is a place to stop checking, not a finding

The section above is one instrument read twice.

- **Do:** before writing "unresolved" or "disputed" between two sources,
  name one more check that would decide it, and try it if it is cheap.
- **Do:** treat a lopsided sample (two calls returning X, one returning Y) as
  a reason to suspect the outlier, not as license to average the disagreement
  away by calling it unresolved.
- **Don't:** report a two-source disagreement as a fact about the world
  before it is a fact about how much you looked.
- **Don't:** let the *number* of sources you already checked stand in for
  whether a decisive one remains unchecked.

## A re-measurement with a different instrument is a second measurement, not a correction

"A correction inherits its instrument" above governs two readings of the
**same** instrument, and its remedy is to reach for a different source of
truth.

### Sharpening that section's own test

It already asks the right question and stops one word short.

### Why it evades the checks

Retracting your own figure is the most rigorous-feeling thing available, so
the replacement inherits credibility the original has just lost.

### When both revisions are live, neither figure retires

The commonest case has no stale reading in it at all.

**This is the boundary with
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Widening an instrument
invalidates every figure it produced".**

- **Do:** ask whether two disagreeing figures came from the same revision of
  the instrument, before framing the later one as a correction.
- **Do:** label a published figure with the revision that produced it, and
  publish both when both revisions are live.
- **Do:** require the mechanism explaining a change to be a mechanism in the
  world --- a change in the detector explains the disagreement, not the
  quantity.
- **Don't:** publish a re-measurement from a different instrument as a
  correction; that reports a correct figure as an error, to everyone the first
  figure reached.
- **Don't:** let a caption naming the instrument stand in for naming it in the
  claim --- the caption is not the part that gets quoted.

See [`metacognitive-monitoring.cases.md`](metacognitive-monitoring.cases.md),
"A re-measurement with a different instrument".

## A sound measurement does not license the claim standing next to it

The two sections above both concern a reading that was narrower than it looked
--- a scope left unexamined, or an instrument whose input could not have held
the evidence.
This concerns a measurement that is entirely sound, correctly scoped, and
correctly read, followed by a sentence asserting something it does not
establish.
The evidence is real.
The step from the evidence to the claim is what fails, and nothing in the
surrounding paragraph marks that step as having been taken.

**The near-miss: having measured something makes the whole surrounding
paragraph feel measured.**
The measurement is usually the expensive part, so the diligence behind it is
genuine and recent, and the sentences written just afterwards inherit its tone
whether or not they inherit its support.
That is the reachable-half inversion above at sentence scale rather than at
document scale --- and here the neighbouring claim need not be a *wider*
version of the measured one.
It is routinely a different proposition altogether: a mechanism verified and an
instance asserted, a provenance verified along one axis and reported along
another, a difference measured and a direction concluded.

**The overreach has no preferred direction, so watching for over-confidence
misses half of it.**
It reaches toward confidence when the neighbouring claim flatters the work, and
toward alarm when the claim condemns it.
A measurement showing two inputs differ can license a retraction exactly as
easily as an approval, and the half that arrives as a retraction is dressed as
rigour.

**The test is two sentences written side by side.**
State what the measurement establishes.
State the claim.
Then check that the claim is neither wider than the first sentence nor beside
it:

> The measurement establishes that `findGlobals()` drops namespace-qualified
> call heads.
> The claim is that a particular directory contains bare `map()` calls relying
> on the standalone import.

Set out that way the gap is visible with no further checking, because the two
sentences have different subjects.
Composing them is cheap, and it is the whole of the remedy --- what defeats
every other check here is that such a claim never presents itself as
unsupported.

**Where the two subjects are the same kind of thing, the test reduces to naming
the population, and the widening is usually one word.**
`git branch -r --contains <sha>` enumerates the **branches** containing a
commit, correctly and completely.
Reporting that as no **ref** containing it silently enlarges the population to
a superset --- one whose excluded members, `refs/pull/<N>/head` among them, are
exactly the ones the question turned on.
So write the population your command actually enumerated into the same sentence
as the claim.
"No branch contains it" and "no ref contains it" differ by one word, and the
first is the one you measured.

That makes this the **scope** claim type's composition-time counterpart rather
than a rival to it.
Scope says to check the population instead of recalling it, and assumes the
population in the claim is the one you meant.
This fires when the command's population and the sentence's population are two
different sets, and the sentence never names either.

**A test suite is the commonest place to meet the population gap, because the
tool reports two of its three numbers.**
"43 pass, 0 fail" can be exactly accurate and still not say the suite passes,
when 15 tests skipped and the skipped set holds the one your change broke.
So report `SKIP` alongside `PASS` and `FAIL`, always, and treat a non-zero skip
count as an unmeasured population rather than as a footnote.

The reason the skips happen deserves its own look, because it is usually a flag
you added for an unrelated reason.
`R_PROFILE_USER=/dev/null` bypasses renv, which changes which packages are
available, which changes which tests execute --- and none of that is visible at
the call site or in the number that comes back.
Any "skip the environment setup" flag can do this: a `--no-config`, a bare
interpreter, a container built without the optional extras.
Each shrinks what is being measured without shrinking the figure reported, and
each makes the run faster, so the habit reinforces itself.

- **Do:** write what the measurement establishes and what you are claiming as
  two separate sentences, and confirm the second does not reach past the first.
- **Do:** measure the illustrating instance separately whenever a verified
  mechanism is illustrated by one, since the mechanism's evidence says nothing
  about which files exhibit it.
- **Do:** name the axis a provenance or freshness check covered, because such a
  check usually settles one axis and is silent about the others.
- **Do:** write the population your command enumerated into the sentence that
  reports it --- branches rather than refs, tracked files rather than files,
  open PRs rather than PRs.
- **Do:** report a test run's skip count in the same sentence as its pass and
  fail counts, and say what a non-zero one excluded.
- **Do:** ask what an environment-bypassing flag removes from the run before
  citing that run as verification.
- **Don't:** let a real measurement lend its credibility to the sentence
  standing next to it --- adjacency in a paragraph is not support.
- **Don't:** treat a retraction as exempt.
  Concluding that something is *wrong* from a measurement that established only
  a *difference* is this same overreach pointed the other way.
- **Don't:** read a correct, complete enumeration as covering the superset it
  sits inside --- completeness is a property of the population the command
  took, not of the one your sentence names.
- **Don't:** cite a green test run whose skip count you did not read --- a
  suite where roughly a quarter of the tests never executed (15 of 58) has
  not reported that they pass.
- **Don't:** treat [`grep-is-not-coverage`](grep-is-not-coverage.md) as a
  rival rule here.
  That fragment is the **null-result** instance of this shape --- a zero-hit
  search read as evidence about a pattern --- so it is the sharper tool when
  the measurement returned nothing, and this section is the general form.
  Instance 4 is itself a null result, so both reach it.
  Finding a positive result read as a neighbouring fact is the case only this
  section covers.

See [`metacognitive-monitoring.cases.md`](metacognitive-monitoring.cases.md),
"Five sound measurements, five claims beside them".

## Writing is the instrument, when the claim can be wrong

The article establishes that self-assessment is unreliable and that confidence
points the wrong way.

**Not all writing tests, and the kind that does not is the kind that feels most
like work.**

## Stripping is the part that tests

Lamport says writing reveals fuzzy thinking, and the section above says to
write the thing that can be wrong.

## Do and don't

- **Do:** classify each assertion as state, scope, cause, inference, or default
  before it goes out, and re-measure any that is not from this turn.
- **Do:** name the falsifying command beside a claim, and run it when it is
  cheap.
- **Do:** treat a fluent, undeliberated answer as owing an alternative you can
  name and reject.
- **Do:** write the claim that can be wrong --- a specification, a prediction, a
  precise statement of mechanism --- early enough that being wrong still costs
  little.
- **Don't:** treat a polished retrospective as evidence that thinking happened;
  a summary of settled conclusions cannot fail, so it cannot test anything.
- **Do:** strip a brief, issue, or PR body after writing it, asking of each
  element whether the task actually depends on it.
- **Don't:** mistake a complete document for a tested one --- completeness is
  satisfied by adding, and adding tests nothing.
- **Don't:** use confidence as the signal to stop checking --- it runs the
  wrong way.
- **Don't:** read a command's output as settling a question without checking
  what that command's scope actually was.
- **Don't:** let a recap's overall accuracy vouch for an individual cell in it.
- **Don't:** publish a figure contradicting one you already published without
  reading a different source of truth --- the second reading of one instrument
  is not a check on the first.

## Relationship to neighbouring rules

- [`algorithmatize-checks`](algorithmatize-checks.md) says to build the
  instrument rather than reason.
