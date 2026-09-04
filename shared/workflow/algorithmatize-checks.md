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

#### Where the space is a product of a few small dimensions, generate it rather than labelling it

Both rungs above collect inputs somebody chose ---
the reported one, then a corpus of real ones.
A third rung opens when the inputs have structure.
Where the space is a product of a few small dimensions,
it can be enumerated exhaustively,
and every member checked against one invariant
rather than against its own expected answer.

The tell is that each round's new case differs from the last
in the value of a single dimension.
An interpreter, a flag subset, an argument form.
That is a product rather than a list,
and a product is generated rather than remembered.

Generating it takes the author's choice of members out of the loop,
which is the only part of the test that was ever wrong.
The section above already says authored cases
"inherit the understanding that produced the bug",
and prescribes a labelled corpus as the escape.
Where the space has structure you need no corpus to escape it.
You need the dimensions and one invariant.

Assert the invariant rather than a per-case expectation:
no combination of interpreter and flags discharges a wrapped read.
A case list grows by one member per round by construction,
so a green suite after each addition says only that the reported case is closed.
An invariant over a generated space cannot be satisfied
by the member nobody thought of.

**The mirror is the other half, and it is the half that gets skipped.**
A sweep asserting that nothing bad passes is one-sided,
and a matcher that rejects everything satisfies it.
So pair it with an assertion that every genuine input still passes.

**The two directions do not generate equally cheaply,
and saying so keeps the rule honest.**
A bypass is any member of the product, so the negative direction generates.
A genuine input has to be a command someone would really run,
so the positive direction stays an enumeration of realistic shapes.
Generate the direction that generates,
and enumerate the other rather than skipping it.

Report how many combinations were examined and not only how many leaked,
per [`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s negative-control rule ---
a sweep reporting zero leaks and a sweep that never ran print the same line.

- **Do:** enumerate the product where the space is a few small dimensions,
  and assert one invariant across every member.
- **Do:** pair a negative sweep with a positive one,
  since a matcher that rejects everything passes the negative sweep alone.
- **Do:** say how many combinations the sweep examined.
- **Don't:** add the newly reported case to a case list
  and read the resulting green suite as evidence the class is closed.
- **Don't:** leave the positive direction unasserted because it cannot be generated ---
  an enumeration of realistic shapes is worth more there than nothing,
  and nothing is what a rewrite silently spends.

(Measured on [ai-config#1947](https://github.com/Morrison-Lab/ai-config/pull/1947),
merged 2026-08-22 after six review rounds.
Four of those rounds each closed one more way of wrapping a read of the same path ---
`cat <path>`, then `sh -c "cat <path>"`, then `bash -x -c` and `python3.11 -c`,
then `python3 -c <bare path>`.
`hooks/test-no-empty-promise.py` now sweeps interpreters against ordered flag subsets
and asserts that no combination discharges,
alongside a mirror asserting that every genuine arming shape still does.
Round 3's rewrite had dropped one such shape with nothing to report it.)

### An exclusion clause has a population too, and a character it spends may carry a second meaning

The three rungs above all grow the population of *inputs* a matcher is tested against.
The reported one, then a corpus of real ones, then a generated product.
Each takes the author's choice of members further out of the loop.

None of them reaches a dimension the author never conceived, and the **exclusion clause** is where that dimension hides.
A clause names characters rather than syntaxes.
It is written against the one syntax the guard must not fire on, and a character it spends there may serve a second syntax that needed the opposite verdict.

The worked example is a guard that must distinguish *reading* a skill's file from *invoking* the skill:

```python
_NOT_PATH     = r"(?<![\w/-])"      # rejects skills/ums and ./ums-helper
_NOT_PATH_END = r"(?![\w/-]|\.\w)"
```

That is correct about paths, and it is the whole reason the clause exists.
But the `/` inside the lookbehind is doing two jobs, and only one of them was intended.
In `skills/ums` it is a path separator, so the word must not match.
In `/ums` it is a slash-command invocation, so the word must match.
One character class collapses the two, so the guard silently stops recognizing `/ums`, `/memorize`, and `/record-learnings` as invocations at all.

The discriminator sits one position further out, and splitting the single lookbehind into a pair recovers it:

```python
_NOT_PATH = r"(?<![\w-])(?<![\w.]/)"
```

A path separator carries a word character or a `.` before it.
A slash-command carries nothing, or whitespace.

The same enumeration finds a third meaning for `/`, and it is worth running on the example itself: a leading separator opens an absolute path.
The pair does not split that one, and does not need to, because `/usr/ums` is already rejected on the `r` before its separator and only a bare top-level `/ums` stays ambiguous.
A residual case you have named and sized is a different thing from one you never looked for.

**Nothing in the guard's own tests could see this**, which is the part worth transferring.
The negative cases an author writes come from the syntax the exclusion clause was aimed at.
Paths were the frame, so paths were the cases, and every one of them passed in both directions.
Slash-commands never entered the frame, so no reported input, no corpus of real ones, and no generated product contained one --- a product is generated over the dimensions you named, which is exactly the limit of the rung above.

**Three fragments now name a population a check silently fails to cover, and they are worth telling apart, because each has a different remedy.**

- [`examples-are-scanned`](../writing/examples-are-scanned.md) --- the **checker's** population: the file it scans contains its own explanatory example.
- [`grep-is-not-coverage`](grep-is-not-coverage.md) --- the **query's** population: strings are matched, and concepts get claimed.
- This section --- the **pattern's** population: a character excluded for one syntax is excluded for every syntax that uses it.

The check is cheap and runs at composition time.
Before spending a character in a class or a lookbehind, ask what else that character means in the text the matcher reads.
Ask it of the character rather than of the input, since the input you would have thought to try is the one already covered.

- **Do:** enumerate every syntax an excluded character participates in, before spending it in a class or a lookbehind.
- **Do:** split one exclusion into a pair of narrower ones when a character serves two syntaxes that need opposite verdicts.
- **Do:** assert a positive case per syntax, so the second one is checked rather than assumed.
- **Don't:** read a passing negative suite as evidence the exclusion is right --- those cases came from the syntax you were already thinking about.
- **Don't:** widen the class to admit the missing syntax --- that readmits the one the clause was written to exclude.

(Measured on [ai-config#1968](https://github.com/Morrison-Lab/ai-config/pull/1968), merged 2026-08-22.
`(?<![\w/-])` entered `hooks/no-empty-promise.py` in [#1724](https://github.com/Morrison-Lab/ai-config/pull/1724) and stood unchanged on `main` until #1968 replaced it, so for that whole interval a dispatch prompt saying `/ums` did not discharge a promise.)

### An attribution claim in a guide-for-future-edits comment is settled by mutation, not by re-reading it

"Test the instrument against the incident that prompted it, verbatim"'s closing **Don't** governs a comment claiming *what* a matcher matches.

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

**Second occurrence, 2026-09-02 on `Morrison-Lab/gha#811`, where the disputed
part of the attribution was an EXIT CODE.**
The Do lines above already prescribe the remedy.
What is new is the tell, because an exit code reads as a detail of the
assertion rather than as an attribution claim, so the fact-checking exemption
this section denies to comments gets granted to it silently.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A mutation rationale that named the wrong exit code".

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

**A control's patch point drifts, and the drift is invisible in every configuration you are likely to run it in.**

The rule above is about where a control *enters*.
This is about the entry point silently ceasing to be one.
A control that neuters the instrument --- replacing a veto with a never-match, patching a function to a no-op --- names the function it patches, and a later refactor can move the real work to a sibling.
The patch then applies to code nothing calls.
Nothing errors, because the name still resolves and the patch still succeeds.

What makes this survivable long enough to ship is that the control keeps returning a healthy number.
A control comparing two revisions reports a large divergence whenever those revisions genuinely differ, whether or not the neutering did anything --- so every local run over a real change looks exactly like a working control.
It reads zero only when the two revisions are *identical*, which is the self-comparison case a dirty working tree never produces and a clean CI checkout produces on every run.
So the configuration that exposes the defect is the one a local session structurally cannot reach, and CI is the first thing to see it.

This is wiring rot rather than the blindness [`fail-fast`](../principles/fail-fast.md)'s fifth cause describes.
There the control is correctly attached and the subject's own fallback absorbs the failures;
here nothing absorbs anything, because the control is attached to code no longer on the path.
The distinction matters for the remedy: a fallback wants its bucket measured, while a detached control wants its target re-derived from the call the instrument actually makes.

The generalization is the part worth carrying: **a control validated only in a configuration where it cannot fail is indistinguishable from one that works.**
Run every control at least once in the configuration where its own expected answer is the boring one --- identical inputs, an empty diff, a no-op change --- and confirm it says so.

- **Do:** derive a control's patch target from the call the instrument actually makes, rather than from a function name you remember it making.
- **Do:** run the control once against identical revisions and confirm it reports zero, before trusting any non-zero it reports.
- **Do:** re-run every control after a refactor that renames or splits a function, treating the rename as a change to the control.
- **Don't:** read a healthy-looking divergence count as evidence the control fired --- a genuine difference in the inputs produces the same number either way.
- **Don't:** validate a control only in the configuration your working tree happens to be in.

(Measured 2026-08-28 on [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515).
The negative control patched `strip_cited_finding_vocab` after the scans it guards had moved to `strip_cited_finding_vocab_with_mask`.
Local runs kept reporting a plausible divergence;
CI, which compares a clean checkout against itself, was what caught it.
Re-pointed at the function the scans actually call, the control fires as it should: measured 2026-08-28, it produces 120 divergences within the first 8,000 generated bodies, the first at index 485.
That is what a control catching something looks like, and it is the reading the dead one had been imitating.)

## A baseline verdict is a detection only when the disputed construct alone produces it

The section above audits whether a control's wiring still reaches real code.
This audits something upstream of wiring: whether the control's own positive result, the one a comparison is trusting as ground truth, was actually produced by the thing under test.

A comparison against `origin/<default-branch>` is a negative control in the ordinary case: the baseline should classify a construct the same way the branch does, and a difference reads as a regression the branch introduced.
That reading assumes the baseline's classification is itself correct, which a bare pass/fail comparison never checks on its own.

Isolate the disputed construct and re-run the baseline alone before trusting a "the branch is worse than main" finding.
If the baseline's flag survives with every unrelated confound removed, it is earned, and the branch is regressing a real detection.
If the flag depends on something else entirely --- a citation, an adjacent construct, a different span of the same input --- the baseline was never detecting the disputed construct in the first place, and the branch is not losing anything the baseline earned.

- **Do:** before reading "worse than baseline" as a regression, isolate the disputed construct and confirm the baseline flags it alone, with whatever might be producing the flag by coincidence removed.
- **Do:** treat a baseline verdict that depends on an unrelated span (a citation, a comment, a different sentence) as unearned, whatever the raw pass/fail comparison reports.
- **Don't:** trust a baseline comparison's verdict as ground truth without checking what actually produced it --- a coincidental over-flag is not a detection, however cleanly it lines up with the disputed input.
- **Don't:** conflate this with the negative-control check above: that one asks whether the control still executes real code, and this one asks whether a control that IS executing and IS flagging is flagging for the right reason.

(Measured 2026-08-30 on [ai-config#2668](https://github.com/Morrison-Lab/ai-config/pull/2668), the same module as the case above;
reproduced directly against `origin/main`'s `scripts/check-pr-fully-clean.py` via `classify_verdict`, not taken on report.
A body ending in a correct `### Verdict` / `**Ready for merge**` heading, with no citation anywhere in it, classifies `clean`.
The same body with one addition --- a narration line citing a past round, `(posted 2026-08-30T05:22:14Z, verdict **Needs more work**)` --- classifies `not-clean` on `origin/main`.
Remove only that citation and keep the same clean heading: `clean` again.
So main's not-clean flag on the cited body was never a detection of anything the body's own current verdict says;
it was produced entirely by the literal bolded phrase inside the citation, matched exactly as if it were a live statement --- the exact false positive the PR exists to remove.
A comparison that read the branch's `clean` on this body as "worse than main" would have had it backwards: the branch was not losing a detection main had earned, it was correctly declining to make the one main was making by accident, and isolating the citation is what showed that rather than another vocabulary patch on the branch's own scan.)

## Widening an instrument invalidates every figure it produced, not only the one that exposed it

The section above ends where the control finally catches something.

**Two independent methods agreeing is not corroboration when both are narrow
in the same way.**

**A second, independent error hides in the same figure: summing two
quantities and labelling the total as one of them.**

**The remedy is already corpus doctrine and was simply not applied.**

**This is not mechanizable as a general hook, and saying so is the honest
answer.**
The artifact a check would read is the published figure, and the property it
cannot decide is whether that figure's population is the one the surrounding
claim is about --- which is semantic, per "Limits" below and
"Name the slice you examined" after it.

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

**A formatter you run yourself is a second way the shipped command can differ
from the tested one, and a command in provenance position is a stronger claim
than the bullets above cover.**
Those bullets name a manual restatement: you ran one command and typed a
tidier one.
Two measured instances in one session show a mechanism none of them names,
and a failure shape worse than an ordinary broken example.

The mechanism is a reflow or lint pass that runs *after* verification, as a
routine part of the same commit, and rewrites the shipped text without
rewriting its meaning by any measure the pass itself applies.
A shell line continuation --- backslash, then newline --- is one command to a
human and to the shell that ran it.
A prose reformatter has no shell semantics, so a pass built to join short
lines turns `\` + newline into `\` + space: a whitespace-only edit to the
reformatter, and a corrupted argument to the shell.
The command that was genuinely run and the command that shipped are then two
different artifacts, and having run the first certifies nothing about the
second.

The failure shape is a command sitting in provenance position ---
"read from `<command>`", "found via `<command>`" --- which is not only a
recipe but a claim that the command was run and produced the cited result.
A command that cannot run falsifies that claim outright, independent of
whether the underlying finding is otherwise true.
An ordinary broken example is merely useless; a broken provenance command is
a false statement about how a conclusion was reached.

- **Do:** run the command in the exact form that will ship --- after any
  formatter, linter, or `--write` pass the commit also runs has touched the
  file --- rather than the form you tested before it.
- **Do:** treat a command in provenance or citation position as a claim that
  it was run and produced the stated result, and confirm it can run before
  publishing it in that position.
- **Don't:** trust that a formatter preserves a command's meaning because it
  only touches whitespace; a whitespace-only edit to prose can still change
  what a shell parses out of the result.
- **Don't:** treat one passing run of a prescribed command as covering every
  later pass (a reflow, a lint `--write`, a squash) the file goes through
  before it ships.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"Publishing a command is not enough; it has to be the command you ran".

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

**Second occurrence, 2026-08-31, and this one consulted no exit code at all.**
The Do lines above already prescribe the remedy, so nothing here is new advice.
What is new is the **tell**, because the section states its cause as an exit
code, and a verification that read no exit code matches none of that wording.

The cause is a **name**.
A CI job and its best-known step routinely share one, so running that step
feels like running the job, and the enumeration the first Do line asks for
never presents itself as owed.
`Morrison-Lab/gha`'s `lint-markdown` is a composite action, and its
`action.yml` runs four checkers: `run_markdownlint.mjs`,
`check_code_block_length.mjs`, `check_list_item_splices.mjs`, and
`check_table_splits.mjs`.
Only the first is the tool the job is named after.

Everything else about the verification was right, which is why it is worth an
entry rather than a note about carelessness.
`markdownlint-cli2` was run at the version `lint-markdown/package.json` pins,
rather than at whatever `npx` resolves, which is that repo's own written
instruction and the step a local run usually skips.
It reported clean, and it was clean.
The job was not.
`check_list_item_splices.mjs` flagged three list items spliced onto a previous
item's continuation line with no blank line between them, which markdownlint
has no rule for and so cannot see however correctly it is invoked.

**Enumerating from the workflow is not enough, because the steps sit one layer
further down.**
A workflow's step list stops at `uses: ./lint-markdown`, so reading it returns
a single step and reads as a complete enumeration.
Open the composite instead:

```bash
grep -nE '^ +(run|uses):' <repo>/<capability>/action.yml
```

That form covers a composite whose steps run commands directly.
A composite step that is itself a `uses:` needs following one layer further,
per [`fact-check-prose`](../writing/fact-check-prose.md)'s rule that a
documented command should say which case it covers.

This is [`derive-dont-enumerate`](derive-dont-enumerate.md)'s "A helper's call
sites are a subset of the effect's sites" met from the caller's side.
There the helper's name under-counts where an effect happens.
Here the helper's name under-counts what a single call performs.
Both times the list that comes to hand is short, genuine, and plausible.

- **Do:** open the composite's `action.yml` and run every checker it names,
  whenever a job wraps a composite rather than invoking one tool.
- **Do:** read a shared name between a job and a tool as a reason to
  enumerate, rather than as evidence the two are the same thing.
- **Don't:** report a job clean from the one step whose name you already knew.
- **Don't:** treat a correctly pinned, correctly run, genuinely clean tool as
  covering the job that wraps it.

(Measured 2026-08-31 on
[gha#781](https://github.com/Morrison-Lab/gha/pull/781), squash-merged as
`a0e0342`.
The four checkers are derived from `lint-markdown/action.yml` at that commit
by the `grep` above.
The fix for the missed step is `298e184` on the PR branch, whose message names
the three spliced items.
`check_list_item_splices.mjs` exists because markdownlint carries no such rule,
per its own header comment citing gha#324.)

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
- **Do:** delete the clause a negative case is written for and confirm the
  input is then ACCEPTED, at the moment the case is authored --- if it is still
  rejected, an earlier stage is doing the work and the case measures nothing.
- **Don't:** accept "some case flipped" as "the case written for this clause
  flipped" --- those come apart wherever the clauses are stages.
  (Measured on `Morrison-Lab/gha#571` and `#574`, whose `CLAUDE.md` records it:
  "a guard that rejects for a second reason -- a missing file, an empty value, a
  type check -- fails the input whether or not the alternative under test
  exists."
  This is the INPUT-side twin of this file's "The same collision reaches the
  ASSERTION, not only the mutation, and there it makes the whole test vacuous":
  there the needle already occurs elsewhere in the unfixed artifact, so the
  assertion passes on that pre-existing occurrence; here an earlier rejection
  point keeps the input rejected instead.
  Both are a case passing for the wrong reason, by different mechanisms.)
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

**An eighth outcome belongs to the FIXTURE rather than to the mutant or the
matrix: the mutation applied faithfully, its own designated case ran, and a
SIBLING member of the same alternation produced the same observable anyway.**

Every outcome above asks whether a mutation applied, was faithful, or was
credited to the right row.
The pass-condition entry directly above asks a nearer question still --- whether
the case that flipped is the one written for this clause --- and answers it by
designating that case per mutation.
**This one starts where that remedy ends, and the two are easy to conflate
because both end in a row that scores clean.**
There, the designated case is never reached, so the clause is unmeasured and
the fix is to score the right case.
Here the designated case IS reached and the clause IS exercised; the row scores
clean because a sibling clause produces the same result for the same input.
Scoring a different case cannot help, because the case is already the right
one.
The fix is a different input.

The shape is a chain of alternatives that all guard one property --- a
redaction pipeline, a validator running several patterns, a dispatcher trying
matchers in order.
Any input written the natural way tends to satisfy more than one of them, so
deleting the clause you meant to test changes nothing observable and the row
scores clean.
It reads as redundancy, which is the dangerous misreading: the honest reading
is that the clause is untested.

**The natural fixture is the trap, and writing a better one is not obvious
in advance.**
A credential in an `Authorization:` header is caught by a header pattern
whatever vendor prefix it carries; the same credential in URL userinfo is
caught by a userinfo pattern.
Both are the *realistic* way to write the case, which is why the fixture gets
written that way and why the confound survives review.

**Its own detector is the mutation sweep, run across every clause rather than
the one you changed.**
A single mutation looks fine; the matrix is what shows one row silently
passing while its neighbours fail.
Read a row that stays green when its clause is deleted as a fixture problem
first, before concluding the clause is redundant.

- **Do:** construct each fixture so that exactly one clause can match it, and
  confirm by deleting that clause and watching only its own row go red.
- **Do:** sweep every clause, not only the ones a change touched --- the sweep
  is what exposes a pre-existing clause that no fixture reaches.
- **Don't:** read a clean row as evidence the clause is redundant; the same
  observation is produced by a fixture that never reached it.
- **Don't:** trust a fixture written the realistic way --- realism is what
  makes it reachable by several clauses at once.
- **Don't:** reach for the pass-condition entry's remedy here; designating the
  case per mutation is already satisfied, and the sibling still absorbs it.

(Measured on `Morrison-Lab/gha#548`, 2026-08-21, three times in one session on
one chain, across two rewrites of the fixture set --- the first relocating the
confound, the second finally removing it.
An Anthropic-key fixture written as `Authorization: Bearer sk-ant-...` passed
with the `sk-ant-` pattern deleted, because a generic header pattern caught it.
The GitHub-token fixture beside it, written the same way, passed with the
`gh[pousr]_` pattern deleted, for the same reason.
Rewritten into URL userinfo, that same fixture passed with `gh[pousr]_` deleted
again --- now because the userinfo pattern caught it.
Rewritten once more as a bare file write, both isolated.
The same sweep showed a pre-existing `github_pat_` pattern --- a second regex,
distinct from the `gh[pousr]_` one above --- that no fixture reached at all:
deleting it turned nothing red, and it had been shipped that way.)

**A ninth outcome, and the cheapest one to rule out first: the mutation
edited the WRONG occurrence of the matched text.**

A non-global substitution --- `perl -0pi -e 's/OLD/NEW/'` with no `g`,
or a `sed` call missing the `g` flag --- edits the first match in the
file.
When the same literal string also appears in a nearby comment or
docstring, the edit can land there instead of in the code, and the
file changes exactly as expected while the construct under test never
moves.
Outcome four already names the general shape --- "the artifact
changed" is not "the intended mutation applied" --- and this is the
specific, easy-to-miss way that gap opens in practice.

- **Do:** print the mutation's own diff and confirm the changed line
  is the construct you meant, not a comment or a sibling occurrence.
- **Do:** anchor a mutation on the code's own syntax --- a line
  number, a unique surrounding token --- rather than on a bare
  substring the file also carries in nearby prose.
- **Don't:** trust a `diff -q` or byte-count check that the file
  changed; that answers a different question than "did the right
  line change".
- **Don't:** assume a non-global substitution reaches the occurrence
  you meant just because the pattern is unique across the file's
  code --- it may not be unique across the file's text.

(Measured 2026-08-21 on `Morrison-Lab/gha#576`.
A mutation targeting a check's enforced value used a non-global
substitution.
The same literal string also appeared in a prose comment earlier in
the file, and the substitution rewrote the comment instead of the
code.
A `diff -q` guard confirmed the file had changed and did not catch
the miss.)

**The same collision reaches the ASSERTION, not only the mutation, and there it makes the whole test vacuous.**

The outcome above is about a mutation landing on the wrong occurrence of a string.
Its dual is a test whose needle is a string the artifact under test **already** carries somewhere else.
The assertion then passes on that pre-existing occurrence, so it passes against the *unfixed* artifact as readily as against the fixed one.
The control that should have turned it red does not, and the test discriminates nothing.

It bites hardest on a guard written throughout in the vocabulary of its own rule, since the phrase that best describes the new behaviour is the phrase the file already uses to explain the old one --- in a docstring, an inline comment, or a message an adjacent branch prints.
A grep sees all three, so it does not matter that only the last is ever printed.
`no-placeholder-reply.py`'s whole-message anchoring, in [`CLAUDE.md`](../../CLAUDE.md), is the shipped form of the same precaution applied to a matcher rather than to a test.

- **Do:** grep the artifact for the needle **before** writing the assertion, and pick one that returns zero hits on the unfixed file.
- **Do:** run the assertion against the pre-fix artifact and confirm it **fails** there;
  a needle that passes both ways is not a test.
- **Do:** scope the assertion to the region the fix touches when a bare needle cannot be made unique.
- **Don't:** choose a needle by quoting the fix's own explanation --- that wording is the likeliest to already appear in a neighbouring branch or docstring.

(Measured 2026-09-02 while adding a hook test for [ai-config#3017](https://github.com/Morrison-Lab/ai-config/issues/3017).
The needle was the phrase `chained AHEAD`, and `git show origin/main:hooks/no-unreviewed-pr.py | grep -n 'chained AHEAD'` returns 6 hits the fix never touches: three docstrings (lines 356, 418, 672), two inline comments (1522, 1550), and the label-exemption message (1917).
So the assertion passed against the unfixed script, and the pre-fix control that was supposed to fail did not.)

**A tenth outcome: the property under test is enforced at more than
one independent site, and mutating one leaves the others standing
guard.**

The AND-clause outcome earlier in this list covers one shape of this:
a single guard whose clauses are ANDed together, where flipping one
is masked by the rest.
This is the same failure at a coarser grain.
Two separate constructs --- two regexes, a check and its fallback, a
validator and its caller --- can each independently enforce the same
property.
Reverting one leaves the property enforced by the other, and the
suite correctly stays green, which reads as "my mutation did
nothing" when it means "this property has a second guardian I never
touched."

- **Do:** before mutating, grep the file or module for every site
  that could independently enforce the same property, not only the
  one nearest the line under test.
- **Do:** mutate every enforcing site together at least once, to
  confirm the suite depends on the property rather than on any single
  guardian.
- **Don't:** conclude a mutation was inert, or a test redundant, from
  a single-site mutation when the property could plausibly be
  enforced elsewhere.
- **Don't:** read "the two constructs look like they check different
  things" as proof they are independent; confirm it by mutating both.

(Measured 2026-08-21 on `Morrison-Lab/gha#576`.
A line-length property was enforced by two separately anchored
regexes, `PIPE_ROW` and `DELIMITER_ROW`.
Reverting only one left the other still enforcing the limit, and the
test suite stayed green.)

**Second occurrence, 2026-09-02 on `Morrison-Lab/gha#811`**, where a
non-mapping-job guard was declared in both `job_groups` and
`callee_calls`, because both walk the parsed workflow and both need
it.
The Do lines above already prescribe the sweep.
What they do not say is what happens *after* it resolves: the
second site is now known to exist, and the mutation matrix records
scores rather than structure, so the finding has nowhere to live
unless it is written down.

- **Do:** name every enforcing site in a comment at each of the
  others.
- **Don't:** let "the other site still holds" stand as the whole
  record --- it explains the survivor and loses the structural fact
  that produced it.

**When a mutation survives, the first hypothesis is that the mutation
was wrong --- mis-targeted, incomplete, or vacuous --- not that the
test coverage is weak.**

The ten outcomes above are what "wrong" actually looks like: a mutant
that never applied, one that applied to the wrong spot, one that
applied to only one of several guardians, a fixture a sibling clause
absorbs.
Every one of them reads as a coverage gap from the outside, and every
one of them is a defect in the mutation, not in the suite.
Doubting the suite first spends the same effort on the wrong side of
the check and, worse, can end in deleting a test that was fine.

- **Do:** work through the outcomes above before concluding a passed
  mutation means untested code.
- **Do:** re-check the mutation itself is what changed --- fully,
  faithfully, at every enforcing site --- before touching the test.
- **Don't:** weaken, delete, or "improve" a test on the strength of a
  mutation that survived and was never itself verified.

(Measured 2026-08-21 on `Morrison-Lab/gha#576`: this exact
misdiagnosis recurred three times in one review session, on one PR
--- outcomes nine and ten above, plus a third case recorded in
[`fact-check-code-logic.md`](../coding/fact-check-code-logic.md)'s
"A predicate a fix adds needs mutation in both directions" section.
Each time the mutation, not the test, turned out to be at fault.)

**Two `MISSED` rows on 2026-08-24, on [ai-config#2185](https://github.com/Morrison-Lab/ai-config/pull/2185), both read as coverage gaps on sight --- one correctly and one not.**
Recording the pair rather than a new outcome, per [`ums`](../../skills/ums/SKILL.md)'s recurrence step, because what separates them is the more useful half.

The first is this entry's thesis.
It fell under the outcome headed "The harness that performs those mutations needs the same scrutiny", whose `Do` is to verify each mutation changed the artifact.
The anchor matched nothing, so the mutation never applied, and doubting the coverage would have been the wrong move exactly as this entry says.

The second is the exception, and it is worth separating rather than folding in.
`ANY_BODY_FLAG_RE` is consulted only for `gh pr review`, so the `-b` and `-m` fixtures went through `POST_RE` and could not observe the mutation aimed at `ANY_BODY_FLAG_RE`.
The mutation was fine and the **suite** was the defect, so the remedy was a new discriminating fixture.
That is the pass-condition entry above, which is explicit that such a case reads as "an unmeasured clause rather than a robust one".

So read this entry's ordering as a **default** rather than a rule, and settle which of the two you have by asking the two questions in order: did the artifact change, and if it did, did the designated case reach the mutated code.
The first separates an inapplicable mutation from everything else;
the second is the pass-condition entry's own identity check, and it is what separates a faulty mutation from a suite that cannot see a good one.

The one thing worth adding is **when** to check the anchor.
It carried escape sequences and did not match the file's own escaping, which is the failure `CLAUDE.md`'s "Tool transport collapses doubled backslashes" section already covers --- read it for the mechanism, the remedy, and the platform caveat.
What that section does not say is that a mutation harness is where the check has to move earlier.
There the tell is a match that inexplicably fails, and you react to it;
here the same failure produces a green suite and a `MISSED` row that reads as a finding, so nothing prompts a reaction at all.

- **Do:** print `repr()` of a mutation anchor carrying escape sequences, and confirm it appears in the file, **before** running the mutation rather than after a match surprises you --- the fourth outcome's `Do` above already says to build the mutation from a raw literal or a written file, and this is the check for an anchor that reached you through a transport you did not choose.
- **Don't:** open a `MISSED` row by asking what the fixture failed to cover --- that is the second of the two questions above, and asking it first is what misread the row that belonged to the first.

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

## A required-subset assertion is not an inventory-pinning test

A test that loops a hand-written table and asserts each entry is present in a
production list looks like it pins that list.
It pins only the listed entries as a required subset of the production
collection, so deleting a production entry the table never named leaves the
suite green.

- **Do:** assert set equality in both directions where a test's purpose is to
  pin an inventory, rather than a `for x in required: assert x in actual`
  loop.
- **Do:** treat a failure in the reverse direction --- a production entry the
  table never named --- as a real finding, not as churn from a stale test.
- **Don't:** read a docstring's claim to "pin the list" as evidence the
  assertion does --- check what the assertion actually compares.
- **Don't:** trust a subset test's green run as coverage evidence without
  mutating an entry the table does not mention.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"A required-subset assertion is not an inventory-pinning test".

## Run new scheduled automation once, attended, before its first scheduled run

Every section above is about building the instrument and testing its logic.
This is about the first time it actually runs, which is a different event and
usually an unwatched one.

Automation that fires on a schedule has a first run you did not choose.
It happens whenever the cron says, into a workflow log nobody is reading, and
its failure mode is silence: the thing it was supposed to produce simply does
not appear, and nothing is visibly wrong anywhere.
A monthly job can therefore be broken for a month before anyone notices, and
the gap between shipping it and learning it never worked is the whole interval.

So trigger it yourself, once, while you are watching.
A `workflow_dispatch` trigger alongside the schedule costs one line and makes
this possible; add it if it is missing.

**What this catches is specifically the part unit tests cannot reach.**
The logic can be perfectly tested and the run still fail on everything the
tests stubbed: a token without the scope, a branch protection that refuses the
push, a missing permission, a path that exists only on the runner.
Those are properties of the environment rather than of the code, so they are
invisible to a local run and to review, and they are exactly what a first
attended run surfaces.

**Do it after the change has merged, not from the branch**, when the automation
mutates shared state.
A dispatch from a feature branch can open a real PR, write a real commit, or
consume real inputs, and doing that before the fix is in the default branch
creates work you then have to undo.

- **Do:** dispatch new scheduled automation manually, once, after it merges,
  and read its step conclusions rather than only its overall status.
- **Do:** add `workflow_dispatch` when the schedule is the only trigger, so a
  first attended run is possible at all.
- **Don't:** let the cron be the first execution --- that is the one nobody
  watches, and its failure is silent.
- **Don't:** dispatch from the branch when the job writes to shared state.

(Measured 2026-08-21 on `ucdavis/bcs`.
A monthly changelog-assembly workflow was dispatched by hand the day it landed.
Its collation step succeeded and its commit step failed: the job pushed to
`main`, which is protected by a ruleset requiring a pull request, so the push
was rejected with `GH013`.
The workflow had been adapted from a template whose commit step pushes
directly, and the assumption that the default branch is pushable transferred
silently.
Its only automatic trigger was `cron: '0 9 1 * *'`, so the alternative to
dispatching was discovering this on the first of the following month, unwatched.
Tracked as ucdavis/bcs#707.)

## Limits

The rule targets *decidable* checks. Judgments of legibility, intent,
aesthetics, and prose accuracy stay with a human or model reviewer --- but even
these often decompose into a decidable core plus a smaller judgment (declare
the intended outcome as data, assert it mechanically, and review only the
framing).
Prefer shrinking the judgment surface over automating a judgment badly:
an instrument with a mushy threshold that misfires trains everyone to
ignore it.

## In review

Flag a hand-run check where the property being checked has a numeric or
otherwise mechanical definition over data the diff already has access to ---
the same weight as any other standing review check.
This includes a new instruction added to a skill's or fragment's prose with
no runnable command behind it: the author's own words look like diligence,
which is exactly why nothing else in the review flags it.

Flag a threshold the diff asserts rather than derives from the system's own
constants, and ask for the derivation --- a number that was never computed
against a real input is a guess wearing a check's clothes, and it decays the
moment the constant it should have tracked changes.

Ask "has anyone actually run this?" of any check specified only as prose.
A command nobody has executed is unverified by construction, whatever else
about the diff is correct.

Per `Limits` above, this finding is never "automate the judgment" --- when
the property genuinely has no decidable core, say so and move on, rather
than pushing for an instrument with a threshold nobody can defend.

## Name the slice you examined before answering "not mechanizable"

The "Limits" section above licenses leaving a judgment to a reviewer, and
[`memories/preferences.md`](../../memories/preferences.md) together with
[`hooks/no-mistake-without-a-hook.py`](../../hooks/no-mistake-without-a-hook.py)
license "not mechanizable, **and why**" as a discharge when a mechanism is
owed.
This tightens the *why* into two named things, because the verdict as usually
written cannot be checked.

Claiming a decidable slice that turns out not to exist is caught by the first
person who looks for it.
Claiming none exists closes the question, so nobody looks again.
The second is therefore the one that needs evidence attached, even though it
is the one that sounds more cautious.

So name the artifact a check would read, and the property a predicate over it
cannot decide.
[`check-purpose-before-reusing`](check-purpose-before-reusing.md) and
[`metacognitive-monitoring.rationale`](metacognitive-monitoring.rationale.md)
both carry compliant examples worth copying.

**Three answers are legitimate, and only the first is "not mechanizable".**

- **No slice exists.**
  Name the artifact and the property, so the claim can be refuted.
- **A slice exists and the guard belongs elsewhere.**
  File it, carrying the slice and its coverage gaps,
  rather than reporting the case closed.
- **A slice exists and building it would misfire.**
  Say that, and say what would make it misfire.
  `metacognitive-monitoring.rationale.md`'s "The one decidable sub-case, and
  why it still is not a hook" is the worked example: decidable, deliberately
  not built, and no issue filed.
  A slice existing does not oblige a guard, which is the same trade "Limits"
  draws between a decidable check and one worth having.

**Ask where the content a check would read is composed, not which flag
carries it.**
This is the tell that decides most transcript-hook questions, and it is easy
to get backwards.
A body written by a heredoc *in the same tool call* is in the transcript
whatever flag posts it, including `--body-file`; a body composed by a separate
file-writing tool and then posted is not visible to a Bash-only check, whatever
flag posts it.
[`hooks/require-agent-disclosure.py`](../../hooks/require-agent-disclosure.py)
is the worked precedent, and it resolves this with a three-way verdict rather
than a binary, distinguishing a body it read from one it could not.

- **Do:** name the artifact and the undecidable property in the same sentence
  as the verdict.
- **Do:** file the guard with its slice and known gaps when one exists but the
  work does not fit the current change.
- **Don't:** infer visibility from the flag --- ask which step composed the
  content, and whether that step is in the transcript.

(Measured 2026-08-27 on a `ucdavis/bcs` sweep.
Six fallback reviews wrote their verdict as a `### Verdict` heading with the
word on the next line, which `classify_verdict()` in
`scripts/check-pr-fully-clean.py` returns `unreadable` for, so none of them
counted as a verdict.
Asked for a mechanism, the first answer was that no transcript predicate could
read the comment bodies, since they were posted with `--body-file` --- wrong
about its own case, because each body was built by a heredoc in the same tool
call.
Filed as
[ai-config#2435](https://github.com/Morrison-Lab/ai-config/issues/2435).
Note also what the measurement showed about the defect itself: the split
heading is not uniformly unreadable, since `Ready for merge` parses from it
while `Clean` does not.
A guard keyed on the shape would therefore be wrong; the artifact to check is
the phrase.)

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
A trigger is evaluated per event, so a wrong answer is normally wrong once --- but a trigger that matches *durable* transcript content re-matches on every later turn, which is why `no-unshipped-commit.py` fired permanently rather than once until that shape was fixed.
So the asymmetry is not that a trigger cannot fire forever.
It is that a discharge fires forever *by design*: it is the matcher whose whole job is to set state, so a wrong answer there is unrecoverable rather than merely repeated.
The discharge sets that *state*: once something in the transcript looks like the check was run, the guard is silent from then on, and its silence is indistinguishable from compliance.
That is the failure [`deterministic-tools`](../principles/deterministic-tools.md) warns about --- an instrument that has stopped measuring reports the same thing as an instrument reporting all-clear.

Measured 2026-08-20 on [ai-config#1749](https://github.com/Morrison-Lab/ai-config/pull/1749).
**The state described below is that PR's first draft, not its current head and not anything `main` carries.**
The draft anchored its trigger to a command position and carried a docstring paragraph explaining why --- this corpus quotes `gh pr create` constantly, so a substring matcher would fire on every reply citing the rule.
Its discharge, in the same file, was a bare substring search:

```
echo 'run gh pr list first'                     discharged=True
git commit -m 'mention gh pr view here'         discharged=True
heredoc body containing gh pr list --repo o/r   discharged=True
```

The reviewer's sharpest observation was that the hook's own reminder text names `gh pr list --repo <owner>/<repo>` --- so the guard told the user to run the command that would have disarmed it.

**That draft's bug is fixed, and the timing is the point rather than a caveat.**
`ca4a5651` added heredoc stripping at 09:57 PDT and `911f0ea8` anchored the discharge at 11:40 PDT, both on #1749's own branch.
Its head now reads `RX_DISCHARGE.search(strip_heredocs(text))`, so none of the three lines above still evaluates `True` there.
This section's first commit landed at 11:48 PDT --- **eight minutes after** the anchoring fix --- so the example was already historical when it was first written, and saying otherwise took three review rounds to catch.
Keep it as a worked example anyway: the discharge really was a bare substring search, the reviewer really did find it, and a bug fixed within the hour is still the bug this section is about.
What is not safe is the present tense.

**Command-position anchoring is not sufficient on its own, because a heredoc body is full of line starts.**
`^` matches inside quoted prose, so a fenced reproduction block in a PR comment satisfies the anchor.
`hooks/no-unshipped-commit.py` had exactly this shape, and fired permanently once a heredoc quoted a commit command ([#1775](https://github.com/Morrison-Lab/ai-config/issues/1775)).
That one is fixed: [#1807](https://github.com/Morrison-Lab/ai-config/pull/1807) merged 2026-08-21 and added `strip_quoted`, which **drops** a heredoc body written by `cat`/`tee` into a redirect before the trigger scans it --- distinct from `mask_heredocs` below, which blanks a body while preserving its length and line structure.
The example is kept in the past tense because the shape is the point, and because a present-tense claim about a hook's current behaviour is exactly what goes stale --- as this sentence did, four hours after that PR merged.

**The machinery already exists, which makes this a [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) finding too.**
`hooks/no-unauthorized-merge.py` solved the same problem across six review rounds, and carries `mask_heredocs` plus its `LEAD`/`PERMISSIVE_LEAD` pair for precisely this reason --- [`check-purpose-before-reusing`](check-purpose-before-reusing.md) records the rounds.
Two newer hooks each re-derived a weaker version instead of reusing it.

- **Do:** apply the same anchoring and the same heredoc masking to every matcher in a guard, including the discharge.
- **Do:** reuse `no-unauthorized-merge.py`'s masking rather than re-deriving it, and say so when you deliberately do not.
- **Do:** test the discharge against prose that quotes it, exactly as the trigger is tested.
- **Don't:** reason about the trigger's self-reference trap and leave its sibling unexamined --- writing the paragraph is what makes the omission feel handled.
- **Don't:** treat a command-position anchor as covering quoted text;
  strip heredoc bodies first.

**When every candidate discharge is satisfiable by typing the right characters, ship the guard with no discharge at all.**
The section above assumes the discharge can be anchored well enough to be sound, and asks for the same care the trigger gets.
Some obligations have no such matcher.
The design question there is whether to write a discharge at all.

The recognizable case is an obligation to have **derived** something, where every observable trace of the derivation is a string.
A guard warning that a required status-check context was set without deriving it from the default branch has no honest discharge: a run-jobs read names no branch, so it cannot show which branch was consulted;
`gh run list --branch <name>` accepts any branch, so its presence proves only that a branch was named;
and any transcript scan for the derived context string is satisfied by typing that string in a comment.
Each candidate is a check the obligation's own subject can write by hand, so it fails open in [`fail-fast`](../principles/fail-fast.md)'s sense --- "a precondition that can never fire is indistinguishable from one that fires correctly and finds nothing".

A guard with no discharge warns every time.
That is a real cost and it is the *right* one for a warning-only guard, because the alternative is not a quieter guard but a silent one --- and by the argument above, silence is indistinguishable from compliance.
The asymmetry decides it: a repeated warning is visible and annoying, while a typable discharge is invisible and permanent.
Note the boundary with the reminder-guard pattern, which does need a discharge because its obligation (run UMS, post a review) leaves a durable artifact a scan can anchor to.
The distinction is whether the obligation's satisfaction is *observable outside the transcript*, not whether the guard is a reminder.

- **Do:** enumerate the candidate discharges explicitly, and say in the guard which ones were rejected and why.
- **Do:** ship no discharge when every candidate is satisfiable by typing, and keep the guard warning-only so the cost stays a note rather than a block.
- **Don't:** add a weak discharge to reduce noise --- it converts a visible cost into an invisible one.
- **Don't:** read "this guard has no discharge" as an unfinished design;
  for an obligation with no artifact outside the transcript, it is the design.

(ai-config#3039 proposes such a guard, on ruleset and branch-protection writes.
Read as of 2026-09-03, its filed body carries a discharge this section would reject: the guard fires only when the transcript contains no default-branch job-name derivation, given as `gh run list ... --branch <default>` followed by `actions/runs/<id>/jobs`, "or an equivalent".
Both halves are strings a session can type, and neither names a workflow definition or the branch a run's job names came from, so the pair is the third candidate above wearing two commands.
The issue is open and no hook file exists on `main`, so this section is the argument that its discharge should be dropped rather than a description of a shipped file;
a comment recording that argument was posted on the issue on 2026-09-03.)

## Measure CPU time, not wall clock, when the assertion is about work done

A performance regression test asserts something about the *code*.
`perf_counter` answers a question about the *machine*: it counts the time a measured span spends descheduled, waiting for a core, alongside the time spent computing.
On an idle laptop those are nearly the same number, which is why a wall-clock bound looks calibrated right up until it runs somewhere busy.

`time.process_time()` counts CPU actually consumed and does not advance while the process waits for a core.
That is the property that makes a reading reproducible across machines and across load, and it is a property of the instrument rather than of the statistic computed from it.

Measured on `offending()` in `hooks/no-unauthorized-merge.py`, under six busy-loops on four cores, against byte-identical code:

| clock | growth ratio over eight runs |
| --- | --- |
| `perf_counter` | 2.18 - 4.58x |
| `process_time` | 3.96 - 4.31x |

The same scan's wall-clock figure had already been reported at 342ms, 1122ms and 2115ms on three machines, a 6x spread with nothing about the scanner changed, across four separate issue filings ([#1314](https://github.com/Morrison-Lab/ai-config/issues/1314), [#1396](https://github.com/Morrison-Lab/ai-config/issues/1396), [#1785](https://github.com/Morrison-Lab/ai-config/issues/1785), [#1796](https://github.com/Morrison-Lab/ai-config/issues/1796)).
Four reports of one defect is itself the tell that the instrument was wrong rather than the code under it.

Two limits are worth knowing before reaching for it.

The one thing CPU time cannot see is a span that blocks on I/O instead of burning cycles, so keep a wall-clock ceiling where the measured code can block.
For a pure-CPU scan it cannot, and a CPU-time ceiling is the honest one.

Its resolution is also platform-dependent, which matters when the measured span is short.
Do not assume it, and do not generalize from the machine in front of you: read `time.get_clock_info('process_time')`, which reports the implementation and resolution for the interpreter actually running.
On the Linux container these figures were measured on, that call returns `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` at `1e-09`.
CPython uses a different call on Windows, whose effective granularity is coarse enough to quantize a span of a few tens of milliseconds.
Size the baseline to clear that granularity by a wide margin, and fail loudly when it does not rather than dividing by a number the clock could not measure.

- **Do:** time a performance regression test with `process_time`, and label the reported figure as CPU so a reader knows which clock produced it.
- **Do:** keep a wall-clock ceiling only where the measured code can actually block.
- **Don't:** read a red `perf_counter` bound as a regression.
  On a shared runner it is at least as likely to be a busy neighbour.
- **Don't:** treat a wall-clock bound as calibrated because it passes locally, which is the machine least like CI.

### A ratio cancels noise only when both terms are equally exposed to it

The obvious repair for a machine-dependent bound is to divide it out: time the same code at two input sizes and assert the growth factor, so the machine's speed appears in both terms and cancels.
That reasoning is sound about *speed* and wrong about *noise*, and the error is easy to miss because the ratio genuinely does fix the cross-machine half of the problem.

Preemption is not a constant factor applied to a measurement.
It is a hazard per unit of elapsed time, so a span four times longer is likelier to be interrupted at least once.
Taking the minimum of several runs does not repair the asymmetry either, and inverts in the unhelpful direction: the minimum filters the short measurement well, because a short span often lands inside one uninterrupted timeslice, and filters the long one badly for exactly the same reason.

Measured: the wall-clock growth ratio of an unchanged, genuinely linear scanner reached **8.45x** under four busy-loops on four cores, against a bound of 8.0 that its unloaded readings of 4.2x sat nowhere near.
The ratio was doing its job on speed and amplifying the noise it was supposed to remove.

The general form is what carries past this instance.
Before dividing one measurement by another to cancel a nuisance term, ask what that term is proportional to.
Where it does not enter both measurements with the same magnitude, the ratio amplifies it rather than removing it, and the resulting statistic looks stable on an idle machine, which is the condition under which every timing method looks fine.

- **Do:** ask what the nuisance term scales with before assuming a ratio removes it.
- **Do:** fix the instrument when the noise is instrument-borne, rather than building a statistic that tolerates it.
- **Don't:** assume min-of-N filters two measurements equally when one is much longer than the other.
- **Don't:** read a ratio's stability on an idle machine as evidence that it is load-independent.

## A slow wall-clock reading is a claim about the machine before it is a finding about the code

The two sections above govern a timing **bound written into a test** --- which clock it uses, and whether a ratio cancels the noise it is meant to cancel.
Neither reaches the reading you take **once**, by hand, in the middle of diagnosing something, and then report as a defect.
No assertion is being authored there and no threshold is being chosen, so nothing about the moment resembles the situation those sections describe.

**The reading is self-authenticating in a way a wrong value is not**, and that is the whole of the trap.
A number you computed incorrectly still looks like a number you might have computed incorrectly.
A stopwatch reading feels like a measurement rather than a guess, so it goes into a report as an observation instead of as a hypothesis --- and the question of what else was running on the machine is never posed, because posing it requires first noticing that the reading has a second input.

**The session iterating fastest is the session most likely to have saturated its own machine**, which inverts the intuition that a busy machine is somebody else's problem.
Background test runs, a re-invoked suite that was never reaped, several agents dispatched at once: each is a normal artifact of working quickly, and together they are the load that makes the next reading meaningless.
So the readings likeliest to be wrong are the ones taken during exactly the kind of session that generates a lot of them.

The figures below are reported from
[ai-config#3059](https://github.com/Morrison-Lab/ai-config/issues/3059), which is
the filed record of the session that took them.
They name no hook, command, or machine, so treat them as an illustration of the
spread's *shape* rather than as a magnitude to cite --- which is itself the
lesson, since a reading with no provenance is the one most easily quoted back as
established.

An end-to-end hook run took **8.0s** against a declared 10s timeout, which read as
a serious performance defect worth filing.
Profiling the internals put them under **0.6s** in total, which is the discrepancy
that prompted looking further.
`uptime` then reported a load average of **376**, attributed in that record to the
session's own stacked background runs.
Re-running the identical command varied between **0.59s and 8.0s** with nothing
about the code changed.
That last figure is the load-bearing one: a range spanning more than an order of
magnitude on unchanged code needs no attribution to make its point.

The check is two steps, and the **second** is the one that decides:

```bash
uptime                                   # step 1: load average
for i in 1 2 3 4 5; do                   # step 2: the one that decides
  ( TIMEFORMAT=%R; time <the command> >/dev/null 2>/dev/null \
      || echo "  ^ FAILED (exit $?)"; ) 2>&1
done                                     # -> one elapsed-seconds figure per run
```

The loop uses the shell's **reserved word** `time` rather than `/usr/bin/time -f %e`, which is the form that first suggested itself and does not run: the binary is absent from this corpus's own remote containers (`exit 127`, measured), and `-f` is GNU-only where it is present, so the step the prose calls decisive would have printed nothing and left the reader holding only the load average.

Four details in that one construct, each measured rather than reasoned:

- **Reserved word, not a builtin**, which is worth getting right because the misnomer invites the natural prefix form and that form does not do what it looks like:
  `type -t time` reports `keyword` and `compgen -b` does not list it.
  An assignment prefix **demotes** `time` from reserved word to an ordinary command word, so `TIMEFORMAT=%R time <cmd>` stops invoking the shell construct and looks `time` up on `PATH` instead.
  What you then see depends on the machine, which is why the symptom alone is the wrong thing to record:
  where no `time` binary is installed --- this corpus's own remote containers, as above --- it dies with `time: command not found`;
  where a `time` binary is installed, that binary runs instead and ignores `TIMEFORMAT`, which it has never read --- measured not here but by the reviewer who raised this, on a runner carrying `/usr/bin/time`.
  The mechanism is the transferable half and the demotion is directly checkable:
  put an executable named `time` on `PATH`, and the prefix form runs it while the bare form still prints `%R`.
  Note what this rules out --- the reserved word does not "take precedence and merely fail to apply `TIMEFORMAT`";
  a different program is running, which is why the variable goes unused.
- **Parentheses rather than braces**, because a brace group is not a subshell and `TIMEFORMAT` would leak into the calling shell, silently reformatting every later `time` in that session.
  Measured: the brace form leaves `TIMEFORMAT=%R` set afterwards, the paren form leaves it unset.
- **`2>&1` is load-bearing**, since `time` writes to stderr.
  With it, `| tee` captured `0.202`;
  without it, `tee` captured an empty file.
- **Both streams discarded, and a failure still announced.**
  The construct writes to stderr, so a timed command that warns on stderr interleaves its warnings with the elapsed figures and the spread stops being readable --- measured, a `stderr warning` line landed above every timing line until `2>/dev/null` was added.
  But discarding both streams leaves nothing to distinguish a fast command from one that never ran: measured, a nonexistent command reported `0.007 / 0.003 / 0.003`, a tight and entirely plausible spread.
  That is this section's own thesis inverted --- a reading that cannot return false --- and it is the live case here, since `/usr/bin/time` is absent from this corpus's own containers, so the shell reports 127.
  Hence the `|| echo`: silent on success, and on failure it prints the exit status under the figure.

Read `uptime` first, but do not stop there.
Its figures are 1-, 5- and 15-minute *decaying* averages, so a burst that inflated
the run you care about can be gone from the 1-minute figure by the time you look,
and a high reading persists for minutes after the load has cleared.
A low number therefore does not clear the run, and a high one does not tell you
the run overlapped it.

So re-run the timed command several times and report the **spread**.
That is what settles it, because it measures the interval you actually care about
rather than a decaying average over a window you did not choose.
A reading you cannot reproduce is not a measurement of the code, and a spread that
spans an order of magnitude names its own cause.

**A timing assertion written as a regression guard is the same exposure, and the two sections above answer it** --- they are about exactly this, a busy machine inflating a wall-clock reading.
What those sections do not separate, and what a session that has just learned its own machine was loaded most needs, is **which question the assertion asks**.

A **regression bound** asks whether the code got slower.
It compares against a figure chosen earlier, so it is the case those sections govern, and widening it under load is the wrong repair --- [`hooks/test-no-unauthorized-merge.py`](../../hooks/test-no-unauthorized-merge.py) states why in its own comment: "Any bound tight enough to catch a regression sits inside that spread, so it goes red on PRs that never touched this hook, which is how a gating check stops being read."
`process_time` is the repair there, and the section above measures it at 3.96--4.31x under load against `perf_counter`'s 2.18--4.58x --- reproducible across machines and load rather than immune to either.

A **watchdog** asks whether the code finishes at all, and that is a question about elapsed time by construction, so it stays wall-clock.
This repo's own catastrophic-backtracking checker is exactly that shape: [`scripts/check_regex_patterns.py`](../../scripts/check_regex_patterns.py) arms `signal.setitimer(signal.ITIMER_REAL, timeout)` against a `DEFAULT_TIMEOUT` of 0.25 seconds, with a thread-join fallback, and `validate.yml` gates on it.
A backtracking probe is therefore not the exception that proves a `process_time` rule.
It is a **second** exception, and it needs its own reason rather than the blocking one's, which does not reach it: that carve-out is stated as "keep a wall-clock ceiling only where the measured code can actually block", and its rationale is that "the one thing CPU time cannot see is a span that blocks on I/O instead of burning cycles".
A runaway regex burns cycles, so CPU time sees it perfectly well and the blocking carve-out excludes it by construction.
What justifies wall-clock here is different and narrower, and it is not availability: a CPU-time interval timer interrupts a runaway regex perfectly well (`ITIMER_VIRTUAL` fires on the same catastrophic pattern in 0.253s against `ITIMER_REAL`'s 0.250s, measured), so the choice is not forced by what exists.
It is forced by what is being budgeted.
A watchdog spends a **termination budget**, which is a real-time quantity by definition --- the question it answers is "has this taken too long", and too long is measured on the clock the caller is waiting on.

So ask which question the assertion asks before reaching for either repair.
The `< 1.0s` probe that prompted this entry was a *regression guard shaped like a watchdog*, which is why it was ambiguous and why it could flake.

- **Do:** read the load average before reporting a timing observation as a finding.
- **Do:** re-run a timed command several times and report the spread, so a reading that cannot be reproduced is visible as one.
- **Do:** reap your own background runs before timing anything, since they are the likeliest cause of the load you are about to measure through.
- **Do:** ask whether a timing assertion is a regression bound or a watchdog before repairing it --- the first wants `process_time`, the second stays wall-clock.
- **Don't:** treat a stopwatch reading as evidence about the code merely because it was measured rather than guessed.
- **Don't:** assume a fast-moving session is running on an idle machine --- it is the session most likely to have loaded it.

(Recorded 2026-09-03 from
[ai-config#3059](https://github.com/Morrison-Lab/ai-config/issues/3059), during a
nine-round adversarial hook iteration.
That session's PR also carried a `< 1.0s` wall-clock assertion as a
backtracking regression guard, which under the same load could have flaked ---
the case the paragraph on regression guards above answers, and the reason it
answers it with `process_time` rather than with a wider bound.)

## Reading an instrument's PROSE instead of its exit status, generalized past the PR checker

[`fully-clean`](fully-clean.md)'s "Calling the checker is not consuming it"
section states this rule for `check-pr-fully-clean.py` and states it well: the
script answers twice, in prose for a human and in an exit status for a program,
and only the second is a stable interface.

The rule is written entirely in terms of that one script, so it reads as a fact
about that script.
It is a fact about **every** instrument this repo ships.
`check-links.py`, `validate-skills.py`, `check-hook-catalog.py`,
`semantic-line-breaks.py` and the rest all print findings and then exit
non-zero, and every one of them can be misread the same way.

**`tail` is the same defect as `grep`, and it is easier to commit** because it
does not feel like parsing.
Piping a checker to `tail -2` to keep a status recap short is a formatting
decision, not an interpretation --- and that is exactly what makes it
dangerous: a checker that prints its findings *before* its verdict shows you
the findings and hides the verdict, and a checker that prints many findings
shows you the last two.
Neither looks like a misread.

The failure direction is the same one `fully-clean` names: it fails **toward
clean**.
The tail of a passing run and the tail of a failing run look alike when the
failing run's last lines are finding bullets, so "no verdict line visible" gets
read as "nothing wrong".

**One reading settles it, and it is shorter than the pipe:**

```bash
python3 scripts/check-links.py >/tmp/out.txt 2>&1; rc=$?
case $rc in
  0) echo CLEAN ;;
  *) echo "NOT clean (rc=$rc)"; cat /tmp/out.txt ;;
esac
```

**The tell is a sentence about an instrument that names no exit status.**
"Links OK", "validators green", "checks pass" --- if you cannot say which code
the check returned, you did not read its answer.

- **Do:** branch on a checker's exit status, whichever checker it is.
- **Do:** treat `tail`, `head`, and a truncating pipe as interpretations of an
  instrument's answer, subject to the same rule as `grep`.
- **Don't:** report an instrument's verdict in a sentence that names no exit
  status.
- **Don't:** read this rule as scoped to `check-pr-fully-clean.py` because that
  is the script `fully-clean.md` happens to describe.

See [`algorithmatize-checks.cases.md`](algorithmatize-checks.cases.md),
"Tailing check-links.py reported clean over three broken links".

**A sentence naming the WRONG exit status defeats that tell.**
The tell just given is a sentence about an instrument that names no exit
status, so it cannot catch a sentence that names one.
A truncating pipe supplies exactly that: without `pipefail` the status belongs
to the pipeline's rightmost command, so a trailing `head` answers instead of
the instrument, and the number that prints is a real number produced by a real
read.

The mechanism, its two shapes, and its remedies belong to
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md)'s "A pipe
discards the status of everything left of it" and the ad-hoc-chain section
after it, which measure both.
[`fail-fast.rationale`](../principles/fail-fast.rationale.md)'s "`$?` belongs
to the last thing evaluated" separates this from the neighbouring case where a
command substitution misdirects the read and `pipefail` changes nothing.
Read those two fragments for the mechanism.
The bullets below restate their remedies rather than replacing them, because a
bare pointer is invisible to anyone who does not follow it, and the bullets add
one measurement of their own.
What is local to this fragment is the blind spot in its own tell, and which way
that blind spot points: the rule's success is what produces the shape, since a
reader who has internalized "always print the exit status" can satisfy that
instruction with the pipe still in place.

**The honest reason this became a guard is not that the corpus lacked a rule.**
`errexit-is-not-uniform` already names this exact shape, with `head` named ---
"pipe a verification check into `tail` or `head` for readability while its exit
status is still gating what runs next" --- and carries a 2026-08-03 case record
of the same defect.
That rule was not consulted.
A fourth prose site would not have been either, which is what makes the
composition-time condition worth an instrument instead:
[`hooks/warn-status-read-after-pipe.py`](../../hooks/warn-status-read-after-pipe.py)
warns when a `$?` read directly follows a pipeline carrying no `pipefail`.
It warns rather than blocks, since reading the last stage's status is correct
under `pipefail` and correct whenever that stage is the one you meant.

- **Do:** take the status before the pipe --- redirect to a file, read `$?`,
  then trim --- which is the remedy that holds whatever the producer does.
- **Do:** read `${PIPESTATUS[i]}` when you want stage `i` --- index `0` is the
  leftmost command, which is usually the instrument.
  `errexit-is-not-uniform` keeps splitting the pipeline as the alternative,
  and that one needs no array indexing to read correctly.
- **Don't:** read a printed exit status as evidence that the status was read
  correctly --- the wrong command's prints exactly like the right one's.
- **Don't:** reach for `set -o pipefail` first on a deliberately truncated
  output.
  A producer piped to `head` is SIGPIPEd once `head` has read enough, which
  `pipefail` turns into a false failure --- measured on bash 5.3.15 (Darwin,
  2026-08-24), `set -o pipefail; seq 1 200000 | head -20` gives `rc=141`,
  where the same line without `pipefail` gives `0`.
  It is producer-dependent: `seq 1 5 | head -20` exits `0` either way, since
  the producer finishes before `head` stops reading.
  `errexit-is-not-uniform` states this caveat where it prefers the
  split-command remedy for an ad-hoc chain.

(Measured 2026-08-24, driving `UCD-SERG/ucd-serg.github.io#111`.
The misread is measured.
The claim that this fragment's tell is what failed is inferred, and the
competing explanation --- a correct rule elsewhere that nobody opened --- is
the likelier one, stated above.

```bash
python3 scripts/check-pr-fully-clean.py 111 -R UCD-SERG/ucd-serg.github.io 2>&1 | head -20; echo "exit=$?"
```

reported `exit=0` while the checker itself exited 1, and the PR's cleanliness
was reasoned from the wrong number.
Tracked as ai-config#2149.)

## Put the discriminator at the producer, where it is exact

A consumer classifying an artifact by its content is running an inference;
the producer stating the fact at write time is running none.
When a classification keeps needing another special case,
stop refining the inference and move the fact upstream.

The measured case (Lacaedemon/sparta#1381, 2026-08-23):
a study harness had to tell a battle that *ended* from a dump that was *cut off*,
and both leave the same artifact -- a short snapshot series and a zero exit.
Three consumer-side discriminators failed in sequence,
each refuted by a reviewer with a case the heuristic could not see:
the exit code (the timeout path exits zero),
the snapshot count (identical in both cases),
and team presence in the last snapshot
(a victory between two sample ticks leaves both teams present,
and some victory conditions end a battle with both armies fielded).
The fix was one line at the producer:
the recorder, which can read the sim's own ended flag directly,
writes a terminal snapshot carrying an explicit `battle_over` marker.
Every consumer then classifies by the marker, exactly, with no heuristic left to refute.

The tell is a classifier that keeps being wrong in new ways.
Each refinement handles the last counterexample and invites the next,
because the information genuinely is not in the artifact --
while the producer had it all along, as one boolean, at the moment of writing.

The same session produced the same lesson in a second shape:
a study whose validity turned on a configuration value (which doctrine the sim ran under)
carried that value only in prose -- a README recommendation and a generator default --
and two full study runs silently executed on the invalid configuration
when a wrapper's own default shadowed the generator's.
The fix was again to make the producer state the fact:
the runner now reads the value back off a generated artifact
and prints it on the first and last line of every run log.
**A validity assumption that lives only in prose rots;
one echoed by the run that depends on it is checked on every execution.**

- **Do:** move a discriminator to the producer the moment its consumer-side
  version needs a second special case.
- **Do:** make every run echo the configuration values its validity depends on,
  read back from what was actually generated rather than from the intended inputs.
- **Don't:** refine a content heuristic past its second refuted counterexample --
  the refutations are evidence the information is not in the artifact.
- **Don't:** leave a validity assumption as prose in a README while the run
  that depends on it logs nothing.

## A log's file order is an assumption, so state it before keying an instrument on position

The sections above test an instrument's matcher.
This one tests its **ordering** assumption,
which is invisible precisely because it is never written down:
a last-wins reader over an append-only log assumes file order is time order,
and nothing in the code says so.

That assumption fails whenever the log is rewritten, replayed, or merged,
and it fails in the worst possible way ---
every record parses correctly and the reader holds a real one, just not the newest,
so there is no malformed input to notice.
A Claude Code transcript after a context compaction is the measured case, per
[`claude-code-transcripts`](../../memories/claude-code-transcripts.md).

**When a guard's refusal contradicts your own read of the session, run its own reader against the artifact rather than theorizing about why it fired.**
That is already
[`mistake-patterns`](../../memories/mistake-patterns.md) Pattern 17,
and it is what separates an ordering fault from a matcher fault:
both produce an identical refusal message,
and only executing the parser prints which record it actually held.

**A guard being wrong does not make its escape valve available.**
The two failures compose rather than cancelling.
On 2026-09-03 the sanctioned `ALLOW_UNREVIEWED_PUSH=1` override was classifier-denied
at the same moment the guard was holding a compaction-replayed stale verdict
([#2899](https://github.com/Morrison-Lab/ai-config/issues/2899)),
so the refusal was wrong and its documented remedy unreachable together.
The unblock was to satisfy the guard honestly ---
dispatch a second review so a fresher record lands last ---
rather than to keep rephrasing the override,
per [`mistake-patterns`](../../memories/mistake-patterns.md) Pattern 43.

- **Do:** key a "most recent" reader on each record's own timestamp, and say in the code why position is not enough.
- **Do:** run the instrument's own parsing function against the live artifact, printing what it held, before writing down a mechanism-level explanation.
- **Do:** produce a fresh record to satisfy a position-keyed guard honestly,
  once its own parser has been run and shown to hold a replayed record,
  and when both the guard and its override are unavailable at once.
- **Don't:** append a fresher record before that check --- a guard holding a current verdict is refusing on the merits, and appending over it is not an unblock.
- **Don't:** treat an append-only log as sorted --- that is an assumption about the writer, not a property of the file.
- **Don't:** diagnose a last-wins reader's wrong answer as a matcher bug without first checking the order of what it read.
