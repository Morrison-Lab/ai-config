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

## "At what moment was this true?" is one question wearing three disguises

A **cause** claim gets asked what else explains it, and a **state** claim gets
re-queried.
Neither fires on a claim that was true when you learned it and false when you
wrote it down, because nothing about such a sentence looks unchecked --- you
did check, and the check has since expired.

Three shapes recur, and the reason they need naming together is that fixing one
does not make the next visible.
Each looks like a different kind of problem:

- **A citation to something not yet merged.**
  Reads as a merge-order question, so the remedy that comes to mind is
  sequencing or draft-gating.
- **A citation to something already merged.**
  Reads as a stale-fact question, so the remedy that comes to mind is a
  timestamp.
- **A citation to a branch in a state that branch has already left.**
  Reads as a which-commit question, and is the least visible of the three,
  because the PR number still resolves and the PR is still open.

They are one question --- *at what moment was this true?* --- and answering it
about the repository is not the same as answering it about the artifact you
cited.
A hedge naming `main` ("described as that PR proposed it, not as something
`main` carries") is precise about the wrong axis: it guards the repository's
state while saying nothing about whether the cited branch still looks like
that.

The cheap check is to write the moment into the sentence rather than reasoning
about it.
A claim carrying a date, a commit, or "as of" is one a later reader can falsify.
A claim carrying a PR number alone is not, because the number keeps resolving
long after the content moves.

- **Do:** name the moment --- a commit, a date, or "the first draft of" --- in
  any sentence describing code you do not control.
- **Do:** ask when a claim was true, separately from whether it was true.
- **Don't:** treat a hedge about `main` as covering the branch you cited.
- **Don't:** read having fixed one staleness finding as evidence the others are
  a different problem.

(Morrison-Lab/ai-config#1777, 2026-08-20/21: three rounds, one class.
Round 1 flagged a citation to unmerged #1749; round 2 a citation to
`no-unshipped-commit.py` whose fix, #1807, had merged four hours before the
citing commit; round 3 the same #1749 example, whose branch had anchored its
discharge in `911f0ea8` at 11:40 --- eight minutes before that section's first
commit at 11:48.
Each was fixed on its own terms and none of the fixes generalized.)

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

## A removal proposal's premise is about the substitute, not about the artifact you are acting on

The section above is keyed on the **object** of the recommendation: re-query
the artifact's state before recommending an action on it.
That check is sound and it cannot reach a proposal to remove, forbid, or
replace something, because such a proposal's load-bearing premise is not about
its object at all.
It is about the **substitute** --- the path that would carry the work once the
object is gone.

So the check passes and the premise stays unchecked.
Re-querying the object confirms exactly what you already believed, which
supplies the sensation of having verified while the claim that decides whether
the proposal is safe was never opened.
[`verify-the-right-artifact`](verify-the-right-artifact.md) names that shape in
its opening paragraph: "It is thorough verification of the wrong object."

Two things make it worse than the same claim stated plainly.
The premise rides in a subordinate clause --- "drop the allowance, so the
pre-written file is the only path" --- while the main clause is a
recommendation, so a reader's attention goes to whether the change is a good
idea rather than to whether the second half is true.
And removal is the one direction with no soft failure: a proposal that adds
something on a false premise is merely useless, whereas one that removes a
capability whose replacement does not exist converts a fix into a regression,
invisible until the capability is gone.

- **Do:** open the artifact that would supply the substitute before proposing
  to remove, forbid, or replace something, and cite the file and line.
- **Do:** read a proposal's subordinate clauses as claims, since that is where
  a removal's premises live.
- **Don't:** count re-querying the object as having checked the proposal ---
  for a removal those are different artifacts.
- **Don't:** read "this is only a suggestion" as lowering the bar; a proposal
  acted on is a change, and its premise is not re-checked at the moment it is
  carried out.

(`Morrison-Lab/gha#543`, 2026-08-21.
The reviewer was exhausting its permission budget retrying variants of
`gh pr diff ... > /tmp/pr.diff`, each denied as a compound command.
The proposal made twice on that issue was to drop `Bash(gh pr diff:*)` from the
reviewer's allowlist, so that the pre-written diff file would be the only path
left.
The allowlist was exactly as believed, so re-querying it would have confirmed
the proposal rather than refuting it.
Reading `.github/actions/run-claude-review-attempt/action.yml` --- the
substitute --- showed there was no pre-written diff file: the harness saves a
command's output to a file only *after* the bare call succeeds, so removing the
allowance would have starved the reviewer of the diff entirely.
`Morrison-Lab/gha#567` supplied the file instead and left the allowance in
place.

The first draft of this entry, in `Morrison-Lab/ai-config#1861`, opened by
calling this a shape "no rule in this file or its neighbours currently
watches".
The section directly above it already did, and the reviewer found it.
That is the same error one level up --- a corpus-gap claim asserted rather than
derived, which
[`grep-is-not-coverage`](grep-is-not-coverage.md) exists to prevent --- so the
entry is written here, as a narrowing of that section, rather than elsewhere as
a new one.)

## "This change is only reformatting" is a scope claim about your own diff

The claim-type list above names **only** as a scope word, and the commonest
"only" an author writes is about their own diff: this is just a re-wrap, no
prose meaning changed, purely mechanical.
It reads as a description rather than an assertion, which is why nothing fires
on it.
It is the same shape as any other scope claim and it is cheaply decidable, so
derive it.

**The obvious command does not decide it.**
`git diff -w` ignores whitespace *within* a line, and re-wrapping moves words
*between* lines, so a genuine re-wrap still shows as changed content.
Measured on the commit below, `git diff -w` returned 57 lines, and it would
have returned a non-empty diff for a faithful re-wrap too.
Using it here produces a false positive on the ordinary case, which is the kind
of detector that gets switched off.

**Comparing the normalized word stream does decide it**, because re-wrapping
preserves the sequence of words and an edit does not:

```python
def words(sha, path):
    t = subprocess.run(["git", "show", f"{sha}:{path}"],
                       capture_output=True, text=True, encoding="utf-8").stdout
    return re.split(r"\s+", t.strip())

words(before, path) == words(after, path)   # True iff a pure re-wrap
```

Run the negative control first, per
[`batch-merge-and-resolve`](batch-merge-and-resolve.md): a `textwrap.wrap()`
re-flow of one sentence must compare **True**.
Without that, an always-False comparison is indistinguishable from a working
detector.

**It is a fast negative rather than a proof.**
A True result licenses the claim.
A False result means look, not that the claim is wrong --- a re-wrap that also
fixes a typo compares False and is still fairly called trivial.

- **Do:** compare the word streams before writing "only reformatting", and say
  what the comparison returned.
- **Do:** run the re-wrap control first, so a False result means something.
- **Don't:** reach for `git diff -w` for this --- it cannot separate a re-wrap
  from an edit, which is the entire question.
- **Don't:** treat a description of your own diff as exempt because you wrote
  it; authorship is what makes the scope feel already known.

(Measured 2026-08-24 on
[#2092](https://github.com/Morrison-Lab/ai-config/pull/2092).
A commit was pushed reformatting a block to one sentence per line, described as
altering no prose meaning.
It also shifted two clauses from first person to third-person passive, which a
reviewer caught.
The word-stream comparison returns False with 37 differing tokens, and the
control returns True.
Tracked as
[#2109](https://github.com/Morrison-Lab/ai-config/issues/2109).)

## Calling your own note stale is a state claim about that note

The two sections above find a state claim hidden inside a recommendation.

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

**An observed absence is only as strong as its sample, and a sample you
MEASURED is the one least likely to get checked.**
The bullet above says a record of nobody observing X outranks any argument that
X should occur.
That holds when the record covers the population, and the bullet says nothing
about what to do when it covers a slice.

The **Scope** claim-type at the top of this fragment already prescribes
checking the population "rather than the sample that came to mind", which
points at recall.
This is the harder case, because the sample did not come to mind.
It was measured.
Four artifacts were queried, four came back empty, and a universal claim was
written from them --- so every instinct the Scope rule trains had already
fired, and the remedy it prescribes felt like it had already been applied.

The bias is what survives the measurement, and it is invisible from inside the
sample by construction.
Ask what the sampled items have in common that the population does not, and
whether that shared property is itself what produces the absence.
Where it is, each further empty observation adds nothing.
A filter that excludes the whole sample excludes the next member of it too, so
the evidence feels like it is accumulating while its weight stays exactly
where it started.

The cheap discriminator is a **second axis** that the population varies along
and the sample does not.
Cost and duration are the two measured below, and they worked because a run
that exits early spends almost nothing, so the trace it leaves differs in kind
from a broken path rather than in degree.
Where every sampled item sits at one end of such an axis, the sample is a
slice, and the claim that can be supported is about the slice.

**A bounded query prints no denominator, which is the gap in the rule that
would otherwise cover this.**
[`deterministic-tools`](../principles/deterministic-tools.md)'s "Read the scope
an instrument prints" is the standing remedy.
It contemplates the unprinted case --- "a printed denominator nobody checked is
worth no more than one that was never printed" --- and prescribes nothing for
it, which is the gap here rather than an oversight there.
`gh run list --limit 5` prints no denominator at all.
It returns exactly as many rows as you asked for, so a truncated answer and a
complete one are the same shape on screen, and the bound was your own choice
rather than something the output announced.

So the tell is the flag rather than the output: `--limit N`, `head -N`, `-n N`,
a first page.
The deriving query raises the bound and groups, which manufactures the
denominator the tool declines to print --- `gh run list --limit 200` with
`group_by(.conclusion)` reports how many were examined beside how many matched,
which is what [`fail-fast`](../principles/fail-fast.md) asks of any check.

Raise it until the total **stops changing**, rather than to a number that
sounds generous.
A run that comes back with exactly 200 rows has told you only that the
population is at least 200, which is the same non-answer `--limit 5` gave,
one order of magnitude along.
State the window whenever you cannot raise it far enough to settle it.
"None of the five most recent" is a claim you measured, and "never" is not.

**The sharpest instance is the one where every sampled item was verified and
correct.**
The two above were samples that were too small and unchecked.
In the third, a reviewer tested three items at real cost, found all three
behaved exactly as the text claimed, and endorsed a universal that was false.
The reason is the sample frame: the three items it tested were the three the
claim itself had listed, so the author of the claim had chosen the evidence
that would check it.

That is why the test cannot be "verify your examples".
Verifying them is what happened.
A quantifier needs evidence of its own, and the examples in the text are the
one sample that can never supply it.
Where a claim says "whatever it starts with", the check is to enumerate the
cases the text did not name.

**A sample a program took has a shared property nobody chose, and the property is the mechanism that took it.**
The instances above are samples a person selected, so asking what the items have in common is a question about judgment.
A programmatic cap makes it a question about code, and the answer is usually sitting in one call.

`itertools.islice(generated, n)` over a generator returns a **contiguous prefix** of whatever order that generator emits.
Where the generator is a nested product over several axes --- the outer loop varying a preamble, the inner loops varying everything the check is about --- a prefix holds one value of the slowest axis and every value of the fastest.
So the sample is not small, it is narrow, and it is narrow along exactly the axis the outer loop varies.
Nothing in the run announces this: the count is large, the items are genuinely distinct, and the cap was a deliberate choice about runtime.

The symptom is a capped run that reports itself blind.
A negative control that fires on the full corpus finds nothing under the cap, because the shape it detects is generated by an outer-axis value the prefix never reaches.
Read that as evidence about the sampling, not as evidence about the corpus --- and note it is the same reading the paragraphs above prescribe, arriving in a form where "what do the sampled items share" has a mechanical answer.

The fix is to take a **stride** across the product space rather than a prefix, so every axis is varied within the cap.
The arithmetic that gets this wrong lives in [`python.md`](../../memories/python.md) and is not restated here;
what belongs here is the reading, which is that a capped figure and a swept figure answer different questions and a run that does not say which it took cannot be quoted as either.

The blind-prefix **length** is a measurement, so it expires like any other, and re-deriving it before quoting it is the cheap part.
The expensive part is not mistaking *why* such a figure went wrong.
Widening a generator reorders it, which is [`algorithmatize-checks`](algorithmatize-checks.md)'s "widening an instrument invalidates every figure it produced" applied to a sampling bound --- but a blind reading can equally come from a control that fired on nothing, and the two look identical from the figure alone.
Establish which before citing either, since the remedies differ: re-derive for the first, repair the control's patch point for the second.
The axis structure is what you can quote freely, since the outermost axis stays outermost.

(Measured 2026-08-28 on `scripts/check-verdict-scan-parity.py`, shipped by [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515) and recorded here while preparing [ai-config#2529](https://github.com/Morrison-Lab/ai-config/pull/2529).
A "first 8,000 are blind" figure was first read as decay from #2515's own widening of that corpus, 221,184 bodies to 1,693,440.
Recovering the branch through `refs/pull/2515/head` refuted that: the claim entered with `936aea2`, the widening commit itself, so it never faced the smaller corpus.
Measured at `936aea2` against `936aea2^`, the dead control reports 0 divergences over the first 8,000 and the repaired control reports 120 over the identical corpus.
The real first divergence sits at prefix index 485.
Tracked for the source comment as [ai-config#2532](https://github.com/Morrison-Lab/ai-config/issues/2532).)

- **Do:** name what the sampled items share, before generalizing from their shared emptiness.
- **Do:** ask how a capped sample was *taken*, and read a contiguous prefix over a nested product as a slice of the outer axis rather than a sample of the whole.
- **Do:** re-derive a blind-prefix or coverage bound whenever the population it was measured against changes, and quote the axis structure rather than the bound when you cannot.
- **Do:** raise the bound until the answer stops changing, or carry the window into the sentence.
- **Do:** sample along a second axis --- one large item beside four small ones --- rather than adding a fifth of the same kind.
- **Do:** scope the claim to what was measured, keeping "these four produced none" distinct from "none has ever".
- **Do:** enumerate the cases a quantified claim did NOT list, since the ones it listed were chosen by whoever wrote the claim.
- **Don't:** read a query returning exactly `--limit N` rows as a complete answer --- that is precisely what a truncated one looks like.
- **Don't:** cap a generated corpus with a contiguous prefix;
  that fixes the slowest-varying axis and hides every shape it produces.
- **Don't:** read repeated absence as accumulating evidence when a single filter would explain every observation at once.
- **Don't:** treat a sample you measured as exempt from the Scope check, because measuring it is what makes that check feel already performed.
- **Don't:** read a reviewer's endorsement of a universal as evidence for it when the reviewer checked the claim's own examples.

(The three instances below, all 2026-08-24, all in one session, on three different agents.
The falsifications and figures are measured.
The second-axis remedy and the sample-frame reading are inferred from them.

**One.**
On `UCD-SERG/ucd-serg.github.io`, PRs 94, 95, 97 and 106 carried no
`claude-review` comment, and that repo's issue #105 was told "no successful
claude-review run in this repo has ever posted one".
A run on PR #111 posted a real review hours later.

The cheap-run signature is what the sample missed.
Across five `pull_request` runs on the `chore/gha-claude-agent` branch, all
`success` with `is_error: false`, one posted and four were silent.
The posting run took 250.4s, 9 turns, $1.0797 and 7 denials.
Cost figures were recorded for three of the four silent runs --- 27.9s at
$0.1733, 14.5s at $0.0520, and 11.5s at $0.0810, one denial each --- and not
for the fourth, which is also the one left unattributed below.
Duration and cost agree, and either would have served: a run under roughly 30
seconds or 20 cents examined nothing.
That is the transferable part, and it is a claim about five runs on one branch
rather than about the repo.

**Why each silent run was silent is a separate question, and the first answer
reached for was wrong.**
"Every sampled PR was small, and small is the class the eligibility gate
filters" is an inferred mechanism, and reaching for the branch's final size to
refute it is the same substitution one level down.
PR #111 ends at +172/-33, and no run read that.
Each run read the head it was triggered on, and those differ: the 16:19:10 run
saw an **empty** commit at +0/-0, the 16:37:08 and 16:38:16 runs saw
+109/-33, and only the 16:56:56 run saw +172/-33.
So the size hypothesis is not refuted wholesale --- it is entirely consistent
with the first run, and inconsistent with the last, which was silent on the
largest head of the four.
That is what a per-run reading buys and a merged-diff reading hides, which is
[`verify-the-right-artifact`](verify-the-right-artifact.md)'s substitution of a
neighbour for the target, inside a section arguing against exactly that.

The timeline attributes the runs directly, which settles it without the size
argument at all.
`gh api repos/UCD-SERG/ucd-serg.github.io/issues/111/timeline` shows #111
created as a **draft** at 16:19:07Z and marked ready for review at 16:38:13Z,
so the runs at 16:19:10 and 16:37:08 met a draft, and the run at 16:56:56 met a
PR already carrying the 16:50:49 review.
Those are two different early exits, neither of them about size.
The run at 16:38:16, three seconds after ready, stays **unattributed** ---
recorded as such rather than assigned to whichever branch would round out the
story.
A competing exit also goes unexamined by the size explanation: the plugin's
step 6 drops findings scoring under 80 and says not to proceed when none
qualify, which produces silence from a run that did examine the diff.

So the correct statement is narrower than the one first written.
The cheap-run signature separates a full pipeline from an early exit, which
step-1 branch fires varies per run, several are verifiable from the PR's state
at run time, and one is not attributable at all.
The class claim survives untouched, since the original sample was still four
small PRs read as a universal.

**Two**, on the same repo, and recorded secondhand from the agent that made it
rather than re-derived here.
`gh run list --limit 5` over that repo's lint workflow showed no successful
run, and "never executed once" went into a PR body, a commit message, and a
self-review.
The real population was 25 runs, one of them a success.

**Three.**
On ai-config PR #2142, a diff claimed a CI gate flags a two-sentence line
"whatever the second one starts with".
The repo's own review run tested the three opener forms the diff had listed ---
lowercase, uppercase, backtick --- found all three behaved as written, and
concluded every checkable assertion matched.
An adversarial reviewer tested outside that list and found the gate's
`classify_line` --- in `check-new-line-breaks/check-new-line-breaks.py` in a
[`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha) checkout, not in this
repo --- returns `None` for a parenthesis or a digit opener, so an unbroken
two-sentence line passes there.
Reproduced independently against that script.
That gate behaviour is recorded on ai-config#2142, which is where it was
found; the sampling lesson drawn from it is what ai-config#2149 tracks.)

## A risk claim that appears after the decision is rationalization

The **cause** claim-type at the top of this fragment asks what else explains an
observation.
This is the case with no observation in it at all.
[`fact-check-prose`](../writing/fact-check-prose.md)'s "Check that a stated
trigger actually fired" owns the general locus --- a justification is a factual
claim and gets fact-checked like one --- and the increment here is that
**ordering** is the discriminator, which no prior site makes.

A decision gets made on good evidence.
The justification then acquires a failure mode nobody measured --- a mechanism
that would supposedly bite if the decision went the other way --- and that
mechanism quietly escalates the claim, from "this is unnecessary" to "this
would break every run".
Both sentences sit in the same paragraph, written in the same pass, and the
finished prose gives no sign which of them came first.

The tell is positional, which is what makes it checkable: **a risk claim that
appears AFTER the decision it supports.**
Evidence gathered before a decision is reasoning.
A mechanism produced after one is rationalization, and the two read identically
once the paragraph is finished.

Ask of any such claim whether you would have predicted it before choosing, and
whether anything was actually run to confirm it.
Where the answer to both is no, either measure it or delete it.
The decision almost always still stands on the evidence that genuinely produced
it, so the invented mechanism is load-bearing for nothing while being false by
default.

- **Do:** extend the measured-versus-recalled marking above to a third
  category, the **predicted**, since a justification's risk claims are
  usually neither measured nor recalled.
- **Do:** delete an unverified failure mode rather than softening its wording,
  when the decision survives without it.
- **Don't:** add a mechanism to a justification after the decision is settled
  without running something that could falsify it.
- **Don't:** let a stronger verb ride on an unmeasured claim --- "would break"
  standing in for "is unnecessary" is the escalation to watch for.

(Measured 2026-08-24 on the `UCD-SERG/ucd-serg.github.io` gha migration.
`setup-r: false` was chosen on sound evidence, and an unverified `LazyData`
failure mode was then written into the justification, escalating the claim to
"would break every run".
A later round measured that mechanism false.
The incident was reported by the agent that made it, and the positional tell is
that agent's own.
Tracked as ai-config#2149.)

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

## A mechanism declining to act is a policy, not a prediction

The claim types in *Key on claim type, because confidence cannot be the
trigger* cover assertions you make about the world.
This one is about a sentence a **safeguard** hands you, and the reason it slips
past every check here is that it arrives already looking checked: a gate
declined to do something, the gate is well-designed, and its refusal reads as a
finding about whether the thing is possible.

It is not.
A guard that withholds a retry is answering a question about **its own**
cost and benefit --- is another attempt worth the money, would it likely repeat
--- and that question has a different subject from "can this succeed at all".
Converting one into the other is an Inference-type overreach, but it is worth
naming separately because the two sentences do not look adjacent.
The gate says *I will not retry this*.
You report *this cannot be reviewed*.

**The guard's own prose is usually what supplies the false generality.**
A well-written safeguard explains itself, and the explanation is phrased as a
claim about the world because that is what motivates the policy.
`check-review-execution.sh`'s comment says gha#198's pattern "has repeatedly
NOT recovered", which is true of the **automatic same-run retry** it governs
and reads as a statement about recovery generally.
So the sentence you quote back is the guard's, which makes the report feel
sourced rather than inferred.

**Measured 2026-08-21 on Morrison-Lab/gha#555.**
One commit, one workflow, one allowlist, three attempts: attempt 1
quota-skipped, attempt 2 produced no verdict at 8 denials and was classified
`high-denial` so the automatic retry was withheld, attempt 3 produced a
complete review with two well-founded findings.
On the strength of attempt 2 I reported the PR as structurally un-reviewable
and told the user that re-running "only spends money".
[`self-review-fallback`](self-review-fallback.md) already says the opposite in
as many words --- the denial count "is a label rather than a prognosis", and
"the one manual re-run stays worth spending" --- and records a run that posted
a real verdict at 72 denials.
The rule was loaded and did not fire, because nothing about reading a
classification feels like making a claim.

**The test is to name the decision the mechanism actually made.**
Write its subject, then write yours, the way *A sound measurement does not
license the claim standing next to it* does for measurements.
"The workflow declined a same-run retry" and "no review can be obtained" have
different subjects, and setting them side by side is enough.

- **Do:** read a gate's refusal as a fact about the gate, and say which
  decision it made.
- **Do:** spend the cheap manual retry before reporting something unobtainable,
  when the only evidence is a safeguard having declined.
- **Don't:** quote a guard's rationale as evidence for a wider claim --- its
  prose is written to justify a policy, not to bound what is possible.
- **Don't:** treat a well-designed refusal as more informative than a poorly
  designed one; the quality of the policy says nothing about the reach of the
  claim.

## A sound measurement does not license the claim standing next to it

The reachable-half and retraction-reach sections both concern a reading that
was narrower than it looked --- a scope left unexamined, or an instrument whose
input could not have held the evidence.
Naming them rather than counting back is deliberate: neither is adjacent to
this section, and a positional reference would point at the wrong pair.
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

**A recurrence on
[Morrison-Lab/gha#555](https://github.com/Morrison-Lab/gha/pull/555),
2026-08-21, over that repository's root `README.md` --- in the shape where no
near-synonym exists to slip on, because the noun was supplied rather than
mistaken.**
`branch` and `ref` are two named populations one word apart, so that case at
least offers a wrong word to catch.
Here the command named no population at all.
`grep -c '^|' README.md`, run in a checkout of that repository, returned 46,
and 46 was published as its capability table's row count --- but `grep` had
enumerated *lines beginning with a pipe*,
and "rows" was a noun I contributed from what I expected the file to contain.
There was nothing to misread, which is why re-reading the sentence would not
have helped.

**The specific trap is that a whole-file pattern match silently unions every
region that matches, and the claim is almost always about one region.**
At the commit where the count was taken, that `README.md` held **three**
disjoint runs of pipe-prefixed lines: the capability table, a blank line
splitting it in two, and an unrelated table 158 lines further down.
Enumerating **contiguous blocks** rather than counting lines gives
`5 + 35 + 6`, which is where the 46 comes from -- 42 data rows and four
header or separator lines, across a population the sentence described as one
table.

**The counts a reviewer later checked it against came from a different commit,
which is the same error one layer up.**
Two rounds of review were spent on this entry: the first because it never
named the repository, the second because the figures it did give were drawn
from more than one file state and presented as a single re-derivation.
Deriving the whole sequence settles it, and is what should have been written
the first time:

| Commit | Pipe lines | Blocks |
| --- | --- | --- |
| pre-PR `main` | 45 | `5 + 34 + 6` |
| where 46 was measured | 46 | `5 + 35 + 6` |
| after the blank line was removed | 46 | `40 + 6` |

The total is unchanged across the last two, which is precisely why an
unstructured count could not see the defect it was being used to describe.

The remedy is the same one this section already states, applied one step
earlier: before writing the noun, ask what the command's unit actually was.
A count is only about a table if something in the pipeline knew where the table
ended.

- **Do:** derive a count over the structure the claim names, not over a pattern
  that happens to occur inside it.
- **Do:** treat a whole-file scan as producing a union until you have shown the
  file holds one matching region.
- **Don't:** trust a number more because a command produced it --- the command
  chose the unit, and you chose the noun.

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

## A summary written above the account it summarizes escapes the re-read

The claim types above are monitored where they are asserted.
This is a claim whose **position** suppresses the check: a clause that
generalizes over an account, placed above it.

It is read as a heading rather than as an assertion.
So verification attaches to the purpose it was written for --- reconciling a
count, introducing a list, framing a section --- and never to the content it
quantifies over.
Both feel like the same act from the inside, which is why re-reading the
passage does not catch it.

Three things make it likelier than an ordinary scope claim.

**It is usually the newest text in the passage**, written last, to close a
finding or tidy a transition.
It therefore gets the least scrutiny at exactly the moment the surrounding
prose has just been checked most carefully, and that recent care reads as
having covered it.

**It is written to solve a different problem than the one it creates.**
A clause added to fix an arithmetic mismatch is checked against the
arithmetic, which is what it was for.
Whether it is *true of every member below* is a question nobody asked, because
that was never the clause's job.

**The reader's error is silent.**
A wrong summary above a correct account does not confuse anyone --- it tells
them something false and hands them consistent-looking detail to confirm it.

The trigger is lexical, so use it rather than judging: a **quantifier
introduced while fixing something else** --- "each", "every", "always", "in
both cases", "throughout" --- is a new claim, and its population is the text
below it.
Check it against every member, not against the problem that prompted it.

- **Do:** check a summarizing clause against each item it generalizes over,
  and separately from whatever it was added to fix.
- **Do:** treat a quantifier you introduced while addressing a finding as an
  unverified assertion, not as part of the fix.
- **Don't:** read position as licence --- a clause above an account is a claim
  about the account, not a label for it.
- **Don't:** let "I just checked this passage carefully" cover the sentence
  written after that check.

(Measured 2026-08-21 on
[ai-config#1833](https://github.com/Morrison-Lab/ai-config/pull/1833).
Round 1 found a citation claiming three events and narrating two.
The fix restored the missing event and added a lead-in: "across two rewrites of
the fixture set --- each rewrite relocating the confound rather than removing
it."
Three lines below, the same parenthetical reads "Rewritten once more as a bare
file write, both isolated" --- the second rewrite *removed* the confound.
Round 3 raised it as a self-contradiction introduced by round 2's fix.
The arithmetic the clause was added for was correct throughout.)

## A rule that names one direction is read as naming all of them

The **scope** claim type above is monitored against a population you choose.
This is the case where a *rule* chose it for you, and chose too narrowly.

A convention that says "audit the downstream steps", "check the callers",
"grep the sibling files" names a direction, and following it feels like having
audited rather than like having audited *one axis*.
Two properties make the gap invisible from the inside.

**Finding something confirms the direction, not the coverage.**
An audit that turns up a real defect is the strongest possible evidence that
you were right to run it, and no evidence at all about the axes you did not
run.
The reward lands on the wrong proposition, and a fruitful check is therefore
*more* likely to be treated as complete than a fruitless one.

**A named direction supplies its own stopping point.**
A rule with no direction leaves you asking when to stop; a rule that says
"downstream" answers that question, so the search terminates on having
satisfied the wording rather than on having covered the thing the wording was
protecting.

The remedy is to derive the population the rule is a proxy for, before
following it.
"Audit the downstream steps" is a proxy for *everything that decides something
about this path*.
So ask what decides, and let that produce the list --- callers above,
steps below, and any sibling branch of a conditional that mentions the event
and predates the new case.

**Widen the rule when a direction it omits produces a defect**, rather than
only fixing the defect.
A rule that has been shown to name a proper subset of its own purpose will
mislead its next reader in exactly the way it misled you, and the incident is
the only occasion anyone will have the evidence to correct it.

- **Do:** name the population the rule stands in for, then enumerate it.
- **Do:** treat a direction the rule omits as a defect in the rule, and widen
  it in the same pass.
- **Don't:** read a direction-naming rule as an inventory --- it is one axis
  chosen by whoever last hit a problem.
- **Don't:** let a productive audit settle whether the audit was complete;
  those are different claims, and the first is what makes the second feel
  answered.

(Measured 2026-08-21 on
[`Morrison-Lab/gha#552`](https://github.com/Morrison-Lab/gha/pull/552), which
added a new trigger path to a reusable workflow.
That repo's convention reads "widening a job's trusted-author `if:` gate to
admit a new event type needs a downstream-step audit, not just the gate
itself".
I ran it, and it found a real defect: a gate below the change would have stood
the new path down, so the trigger could never have fired.
Review then found two more of the same shape, in the two directions the rule
does not name --- a caller gate *above* the change that never admitted the
event, leaving the input silently inert, and *sideways*, a sibling branch of an
unrelated ternary that told every such run it had been triggered by a mention
that did not exist.
Three defects, one shape, one direction named.)
