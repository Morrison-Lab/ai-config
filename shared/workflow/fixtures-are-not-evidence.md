A test fixture records what someone believed the real thing looks like.
Reasoning from a fixture back to the real thing is circular, so a fixture --
or a test outcome against one -- is never evidence about the system it
imitates.

Worked-example case records for the rules below live in
[`fixtures-are-not-evidence.cases.md`](fixtures-are-not-evidence.cases.md), moved out of the auto-loaded context.

A fixture is one adjacent artifact among several that get read in place of the
thing a claim is about; see
[`verify-the-right-artifact`](verify-the-right-artifact.md) for the general
case and its other shapes.

The circularity is invisible from the inside, which is what makes this worth
a rule rather than a reminder.
A test failing against a fixture feels exactly like a test failing against
reality: same red output, same specificity, same sense of having *checked*
something.
And the conclusion then arrives dressed as a test result, which is the most
trusted kind of evidence in a review thread and therefore the least likely
to be questioned.

## The shape

1. A fixture is written, commented as verbatim output from some real system.
2. A line is added to it that the real output does not contain -- for
   realism, or because it seemed like it belonged, or copied from a
   neighbouring case.
3. Later, a code change makes that fixture fail.
4. The failure is read as a fact about the real system, and acted on.

Step 2 and step 4 are usually separated by a few minutes and one context
switch, which is exactly enough for the fixture to stop feeling authored and
start feeling found.

## The rule

When a fixture's behaviour prompts a conclusion about the system it imitates,
go to the real artifact before acting on it or asserting it: the issue's own
quoted output, the tool's documentation, a live run.
This is nearly always cheap -- the original report usually quotes the thing
verbatim -- and it is the only check that can distinguish the two cases.

Keep the fixture honest in both directions.
A fixture claiming to be verbatim either is verbatim or drops the claim, and
its comment should say where it came from.
Where a fixture deliberately combines cases that co-occur rarely, name it for
what it is (`both_markers`, not `real_rejection`) so nobody later reads it as
a specimen.

## Distinguishing it from the neighbours

Three existing rules sit close to this one, and each misses it:

- [`ardi`](ardi.md)'s fixture bullets are about **coverage** -- a fixture
  lacking the input variety to reach a branch.
  This failure needs no coverage gap; the fixture exercised the branch fine.
  The defect was the inference drawn from it.
- [`ardi`](ardi.md)'s "test the class it distinguishes" bullet is about
  **unfalsifiable** evidence, where no true positive existed to get wrong.
  Here the claim was perfectly falsifiable, and false.
- [`fact-check-prose`](../writing/fact-check-prose.md) says to check claims
  against sources.
  The trap is that a fixture *presents* as a source: it lives in the repo, it
  is named after real output, and its own comment vouches for it.

So the addition is narrow: a repo artifact you or a colleague wrote is not a
source, however faithfully it is labelled.

## When the claim was already published

Correct it where it was published, not only in the thread that caught it, per
[`ardi`](ardi.md)'s self-correction rule -- and say plainly that the evidence
was your own fixture.
That last part matters more than it looks: "I was wrong about GitHub's
wording" invites the reader to wonder which source misled you, while "I
checked it against a fixture I had written" tells them the actual mechanism
and lets them discount any other claim from the same round.

Then remove the circularity rather than just the conclusion.
A design that no longer depends on the disputed fact cannot be re-broken by
someone re-deriving it later.

- **Do:** verify against the real artifact before drawing a conclusion about
  external behaviour from a fixture's behaviour.
- **Do:** name a synthetic combination fixture for what it combines, and
  record each fixture's provenance in its comment.
- **Don't:** cite a fixture, or a test result against one, as evidence about
  the system it stands in for.
- **Don't:** add a line to a fixture for realism while leaving a verbatim
  claim standing over it.

## Your own transcript is a fixture, and searching it contaminates it

The section above narrows the rule to a repo artifact you or a colleague wrote.
The session transcript is that artifact one step further out, and it is harder
to see, because it is not in the repo and does not look like an artifact at
all.
It reads as memory.

So a verbatim quotation drawn from it --- an error string, a command's output,
a figure --- can rest entirely on your own earlier prose *about* that output,
with the output itself never recorded anywhere.
Each restatement is faithful to the one before it, so re-reading confirms the
quotation every time and no reading ever reaches a tool result.

**The obvious remedy is unsound, which is the part worth knowing.**
That remedy is to check whether the string appears in a `tool_result` block
rather than in your own text, on the reasoning that a tool result is
machine-produced.
Two sources defeat it:

- **A search writes its own needle into the transcript**, in the command and
  again in the output, so investigating the question manufactures evidence for
  whichever answer you were checking.
  The hit count grows as you look.
- **An API round-trip returns text you authored.**
  A `pull_request_read` result carries the PR body you wrote, so a
  machine-produced block can consist wholly of your own prose.

**The sound check pairs each result with the call that produced it**, and asks
whether that call could have *emitted* the string rather than merely *carried*
it:

```python
import json
T = "<path to this session's .jsonl transcript>"
needle = "fatal: Could not access"
uses = {}
for line in open(T, errors="ignore"):
    try: rec = json.loads(line)
    except Exception: continue
    for b in ((rec.get("message") or {}).get("content") or []):
        if not isinstance(b, dict): continue
        if b.get("type") == "tool_use":
            uses[b.get("id")] = (b.get("name"), needle in json.dumps(b.get("input") or {}))
        elif b.get("type") == "tool_result" and needle in json.dumps(b):
            print(uses.get(b.get("tool_use_id")))
```

A row whose second field is `True` is a search finding itself.
A row naming a read-back tool is an echo of something you wrote.
What is left, if anything, is the observation.

**Reproduce it, or drop the quotation marks.**
When no row survives, the honest repair is to run the command that would have
produced the string and quote what it actually prints --- or to replace the
quotation with a description, and say in the artifact that the literal was
never verified.

[`memories/github-actions.md`](../../memories/github-actions.md)'s "Grepping a
run log matches the echoed script, not its output" is the sibling case, and it
states the shared shape best: "a false positive shaped exactly like
verification: you searched the log for the thing, and the log contains the
thing."
A CI log is fixed once its run ends, so it carries only that one contamination
source; a transcript is still being written by the search, and carries the
API-echo source as well.

- **Do:** pair a transcript hit with the call that produced it, and treat a
  search's own output and an API read-back as carrying no evidence.
- **Do:** reproduce a literal before publishing it as verbatim output, and say
  plainly when it could not be reproduced.
- **Don't:** read a hit count as attestation --- N restatements of one claim
  are one claim, and some of the N are your own act of counting.
- **Don't:** treat a `tool_result` block as machine-produced evidence; that is
  the check this section exists to reject.

(`Morrison-Lab/ai-config#1573`, 2026-08-17: that PR's body quoted
`fatal: Could not access 'origin/main...HEAD'` as the observed failure of a
`git diff` run under a reset working directory, and said the wording had been
confirmed as git's own.
Six `tool_result` blocks in the session transcript carry that string.
Four are GitHub MCP responses echoing the PR body itself, and the two `Bash`
results both come from commands whose own text contained the needle --- so not
one is a command that could have emitted it.
The count was 5 on one pass and 6 minutes later, the extra block being the
output of the pass that went looking.
Neither candidate condition reproduces the literal on git 2.43.0: a deleted
working directory gives
`fatal: Unable to read current working directory: No such file or directory`,
and an existing non-repo directory gives
`warning: Not a git repository. Use --no-index ...`.
The body was corrected before merge, replacing the quotation with a
placeholder; what went unrecorded until now is the rule, and specifically that
the correction's own stated reason --- "no raw tool result" --- was imprecise
in the direction that invites the unsound check above.)

## The other direction: a fixture that agrees with the bug

Everything above concerns a fixture that behaves correctly, and a conclusion
drawn from that behaviour about the system it stands in for.
The mirror case is a fixture that agrees with a defect.
Its data lies outside the regime the correct code would enforce, so the
incorrect code and the fixture are mutually consistent, the suite is green,
and the green is not evidence the code is right.

Neither half looks wrong alone, which is why re-reading either one never finds
it.
The code is plausible, the fixture is plausible, and only the pair is wrong.

The nearest neighbour is [`ardi`](ardi.md)'s "a regression test written
alongside a fix can lock the bug in", and it misses this by one step.
That case concerns a test authored **in the same pass** as the code it
validates, so you are at least present when the assertion is written.
Here the fixture predates the change.
It was written for some earlier purpose, possibly by you, and has been green
for as long as the file has existed -- which is exactly what makes it read as
a specification rather than as a claim.

### The tell is that the fix forces a fixture change

A fixture that has to move because the code became correct is a fixture that
was encoding the incorrect behaviour.
The forced change is the diagnostic, not the collateral damage.

That reading needs arguing for, because the instinct runs the other way.
A diff touching shared fixtures looks invasive, and a reviewer is right to ask
about it, so the cheap response is to narrow the fix until the pre-existing
tests pass again.
Doing that restores the bug, under cover of having reduced the blast radius.

The sharper version is a test that asserts the defect outright.
An assertion phrased as an invariant -- "perturbing this input leaves the
output unchanged" -- can be true only because the bug discards that input, so
correct code makes it fail and the honest repair is to assert the opposite.
A test that must be **inverted** rather than adjusted is strong evidence the
diagnosis is right, not a reason to doubt it.

Both readings stay open until you check what regime the fixture's data
actually covers, against the specification rather than against the code.
That is one comparison and it separates them exactly: data outside the valid
regime means the fixture was wrong, data inside it means the fix is.

### When the specification is a written RULE, quote it into the fixture

The paragraph above says to settle both readings against the specification rather than against the code, and leaves "the specification" to whatever the domain supplies.
Where the guard enforces a **written rule in this corpus** --- a disclosure format, a claim wording, a required marker --- that phrase has a concrete and easily-skipped referent: the rule's own text.

The failure is that a plausible variant reads as compliant.
`AGENTS.md` specifies the disclosure line as `_Posted by Claude Code (AI agent) --- not written by a human._`, with the agent's name substituted and the rest kept verbatim.
A fixture asserting that `_Posted by Codex (AI agent) -- not a human._` satisfies that rule looks exactly like a compliant example, and is not one: the substitution is correct and the *verbatim* half was rewritten, `---` shortened to `--` and `not written by a human` to `not a human`.
The fixture passed because the matcher anchored the prefix `posted by ... (ai agent)` and examined nothing after it, so neither deviation was in anything's field of view, and tightening the matcher to require the tail is what exposed it --- which is the forced-fixture-change tell above, arriving from a rule rather than from a bug.

Note which way this differs from the section it sits in.
There the fixture agrees with a defect in *code*, so reading the code cannot find it.
Here the fixture agrees with a laxness in the *matcher*, and the thing that would have found it is one paste from a document nobody thought to open, because the fixture's author was reconstructing the rule from a memory of what it means rather than from what it says.
That reconstruction preserves whatever the author reads as the rule's *point* and loses the rest, so the divergence lands wherever the literal text was doing work the paraphrase does not notice --- which is exactly where a matcher then has to be loose.

- **Do:** copy a required string into the fixture from the rule that defines it, and name that rule's file beside it, rather than composing a case that looks like it complies.
- **Do:** diff a fixture's expected value against the rule's text character for character when the rule specifies a literal, since a shortened dash or a dropped word reads as identical.
- **Don't:** read a fixture passing as evidence its expected value is conformant --- a loose matcher and a non-conformant fixture agree.
- **Don't:** restate a rule's literal text from memory inside a fixture; the divergence is the defect the matcher then has to tolerate, in whichever direction the paraphrase drifted.

(Measured 2026-08-24 Pacific on [ai-config#2185](https://github.com/Morrison-Lab/ai-config/pull/2185).)

### Prove the new fixtures catch the old bug

A fixture edited until the fix passes is otherwise only a fixture edited until
the fix passes.
[`ardi`](ardi.md) already asks for the general form of this check -- revert
the fix, confirm the new test actually fails -- so what this shape changes is
*what* to revert.
The fixtures moved too, so reverting the whole change reverts them as well and
compares two different suites, which proves nothing.
Restore only the implementation:

```bash
git checkout origin/main -- <implementation-file>   # old code, new tests
<run the affected tests>                            # must fail
git checkout HEAD -- <implementation-file>          # restore
```

The fixtures and the assertions are then identical across both runs, so every
failure is attributable to the code rather than to the fixture edit.

Report the count, per
[`algorithmatize-checks`](algorithmatize-checks.md), since "9 failures across
6 test blocks" is checkable and "the new tests exercise the fix" is not.
A test that fails against the old code only because the function did not exist
yet says nothing about the bug, so name those and exclude them from the count.

#### Which ref to restore from, not only which file

The block above answers "what to revert" as a question about which **file**.
There is a second axis, and `origin/main` is the wrong answer to it whenever
the regression was introduced **within the PR**, across rounds.

A multi-round PR has at least two candidate baselines: the base branch, and
the previous round's head.
Only the second is the control for a bug the PR itself introduced, because the
base branch may not contain the structure the test targets at all -- so
restoring from it does not reproduce the failure, and cannot.

The failure direction is what makes this worth stating.
A base-branch control does not error.
It returns a **plausible** result, which reads as the new test being weak
rather than as the baseline being wrong, and nothing in the output says which
one you are looking at.
Published, it also misattributes the regression's provenance: a two-column
old-versus-new table implies the bug pre-dated the PR when the PR's own first
round created it.

Note this is the exact mirror of the preceding paragraph, which is why the two
belong together.
There, a test fails against the old code for a reason unrelated to the bug,
because the function did not exist yet -- a false positive that inflates the
count.
Here, a test passes against the old code for the same underlying reason, that
the base branch lacks the structure under test -- a false negative that empties
it.
One root cause, opposite symptoms, and only the second is silent.

So restore from the previous round's head, and prefer a three-way baseline
over a two-way one: base branch, previous round, current head.
The three-way form makes the provenance visible rather than implied, and it
costs one extra column.
Report the checks **completed** alongside the pass and fail counts, since a run
that died partway reports few failures rather than many, and the completed
count is what distinguishes a crash from a clean run.

- **Do:** check what regime a fixture's data covers, against the
  specification, whenever a fix will not pass without changing that fixture.
- **Do:** restore only the implementation, run the new tests against it, and
  report the failure count before calling the fix regression-tested.
- **Do:** restore from the previous round's head, not the base branch, when
  the regression was introduced within the PR.
- **Do:** report a three-way baseline for a multi-round PR, and include the
  checks-completed count so a crash is distinguishable from a clean run.
- **Don't:** read a forced fixture change as a sign the fix is too invasive
  -- it is frequently evidence the fixture was wrong.
- **Don't:** treat a long-green fixture as a specification; it records what
  the code did, not what it was supposed to do.
- **Don't:** read a plausible result from a base-branch control as evidence
  the new test is weak -- for an intra-PR regression that is what a wrong
  baseline looks like, and it is indistinguishable from a real pass.

## A third direction: a fixture that cannot tell the two apart

The two sections above concern a fixture that **disagrees** with reality, and
one that **agrees** with the bug.
Both are claims about the world that happen to be wrong.
The third case makes no claim at all: the fixture is faithful, the assertion is
correct, and the data simply carries no information about the question, so the
test passes identically whichever implementation it runs against.

[`ardi`](ardi.md) already covers the version of this you can see --- "a fixture
missing the input variety that makes the two paths differ" --- and its remedy,
building the fixture so both sides are present and asserting them together, is
the right one.
What it does not cover is the case where the variety is **present but
degenerate**.
The column exists, the model fits it, the fixture looks exactly like one built
to discriminate.
Only its magnitude is wrong, and no reading of the fixture shows that, because
the number is produced by the fit rather than written in the file.

That defeats the usual review question.
"Does the fixture vary the thing under test?" answers yes.
The question that decides it is quantitative: **would the two implementations
actually produce different output on this data?**

### Assert the discriminating property, in the test

The remedy is to make the fixture's fitness for purpose a **checked
precondition** rather than an assumption --- the same move
[`fail-fast`](../principles/fail-fast.md) asks for anywhere a pass and a
non-answer are indistinguishable.
Two assertions, and they are not redundant:

1. **The discriminating parameter is non-negligible.**
   A bound on the coefficient, the spread, the count --- whatever the two paths
   diverge on.
   This is what fails loudly when a fixture degenerates, including later, when
   someone changes the generator for an unrelated reason.
2. **The two implementations differ on this fixture.**
   Keep the retired computation as a helper and assert a floor on the gap.
   Without it, assertion 1 shows the input varies while leaving open whether
   the output does.

Both are cheap, and together they turn "this fixture discriminates" from a
belief into a check.
This is [`algorithmatize-checks`](algorithmatize-checks.md) applied to the test
suite's own inputs: a threshold decides it exactly, so it should not be
eyeballed once at authoring time and then trusted forever.

- **Do:** assert a floor on the parameter the two paths diverge on, so a
  degenerate fixture fails rather than passes.
- **Do:** keep the superseded computation as a test helper and assert the two
  differ, rather than asserting the new one against a constant.
- **Don't:** accept "the fixture has that variable" as evidence it
  discriminates --- presence and magnitude are different questions.
- **Don't:** write a regression test whose passing is compatible with both
  implementations; per `ardi`, one that was never observed to fail is a guess
  about what it covers.

## A fourth direction: the two implementations differ, and the target is still unreachable

The section above ends where the two implementations agree, so the fixture
carries no information.
This is the case where they disagree perfectly well and the **proposed expected
value** is still unattainable, because the metric has a floor neither of them
sets.

The shape is a reviewer's finding that is correct about the bug and supplies a
number for the test.
The number comes from a mental model of what the fixed code should do, and it
omits whatever the metric already reads when the code path under test does not
run at all.
Both remedies above pass on it: the input varies, and the two implementations
genuinely differ.
The test still fails, against the fix, at a value nobody predicted.

**The missing measurement is a third one, and neither of the usual two supplies
it.**
Buggy and fixed are the pair everyone takes.
The **do-nothing** reading --- the same fixture with the changed path removed
entirely, not reverted to its old behaviour but not exercised at all --- is what
says whether the proposed target sits inside the metric's reachable range.
Where a floor comes from some third mechanism the change never touches, that
floor is the best the fix can possibly score, and a target below it is
unreachable by construction.

So take three readings before adopting a threshold anyone proposed, your own
included:

| reading | what it establishes |
| --- | --- |
| buggy | the metric moves when the defect is present |
| fixed | the metric moves back |
| **do-nothing** | **the floor the fix cannot beat** |

Then bound the metric against a quantity derived from the fixture's own
geometry rather than against a hand-picked constant, so the floor cannot creep
under the threshold later.

Note what this does *not* license.
The finding is usually right, and its number usually wrong only in scale --- so
the response is to re-derive the bound and say which reading killed the proposed
one, never to discard the finding because its expected value did not hold up.
That is [`address-every-comment`](address-every-comment.md)'s rule that a
finding can be right while its suggested fix is wrong, arriving on the assertion
rather than on the code.

- **Do:** measure the do-nothing reading before adopting any proposed expected
  value, and publish it beside the buggy and fixed ones.
- **Do:** derive the bound from the fixture's own geometry, so a later shift in
  the floor cannot silently satisfy it.
- **Don't:** read "buggy and fixed differ" as evidence a proposed target between
  them is reachable --- the floor can sit above it.
- **Don't:** drop a finding because its number was unattainable; re-derive the
  bound and keep the fix.

## A regression fixture must contain something the bug would destroy

The sections above concern what a fixture's *behaviour* licenses you to
conclude.
This one concerns a fixture that never exercised the bug at all, and so
concluded nothing while appearing to.

When the bug under test is **loss** --- content dropped, a record skipped, a
branch never reached --- the fixture has to contain content the bug would
actually destroy.
A fixture built from only the *structure* that triggers the bug, with nothing
of value positioned where the loss would occur, passes under both the buggy
and the fixed code.
It is green, it is named after the bug, and it discriminates nothing.

That is worse than having no fixture, and the reason is the fixture's **name**.
An untested path is at least visibly untested.
A vacuous fixture converts it into an apparently-tested one, and every later
reader --- including the author --- reads the green line as coverage and stops
looking.
The count goes up while the evidence does not.

The check is mechanical, so run it rather than judging: **revert the fix, and
confirm the fixture fails.**
A regression fixture that passes against the unfixed code is not a regression
fixture.
Where reverting is awkward, ask the narrower question the revert would answer:
*what, in this fixture, would be missing from the output if the bug were still
present?*
If the answer is "nothing", the fixture is asserting the bug's own behaviour.

- **Do:** position real, identifiable content exactly where the loss would
  happen, so the assertion can distinguish the two code paths.
- **Do:** run the fixture against the unfixed code and confirm it fails.
- **Do:** re-read the assertion against the fixture's own name --- when they
  disagree, the name is usually the intent and the assertion is usually the
  bug.
- **Don't:** build a loss fixture out of the triggering structure alone; the
  structure is the precondition, and the content is the test.
- **Don't:** treat a rising fixture count as rising coverage without reading
  what each one asserts.

(Measured 2026-08-19 on [rme#1082](https://github.com/d-morrison/rme/pull/1082).
A fixture named `"two consecutive declarations: reaches back past both"`
asserted the buggy output rather than the fixed one: it supplied two trailing
markers with **no message behind them**, so nothing existed for the lookback to
reach back *to*, and it passed against code that could not reach back at all.
The reviewer identified it precisely --- "the fixture likely only exercised two
declarations with nothing substantive before them" --- and the replacement
fixtures each place a real answer behind the run.)

**A fixture can also reach the expected outcome by a second route, and the
revert check above is what exposes that one.**
The section above concerns a fixture too thin to exercise the bug.
This one concerns a fixture rich enough to exercise it, paired with an
assertion too coarse to say which route produced the result.
A row asserting only that an input was refused is satisfied by any refusal, so
a setup carrying an unrelated reason to refuse scores green against the fix and
against a mutant with the fix removed.

The confounding setup is the natural one to write, which is why foresight alone
does not reach it.
A row testing that a guard resolves `--repo=origin` against that remote's
configuration invites naming the remote `origin`, which is also the literal the
unfixed code falls back to.
Both readings then find the same configuration key and refuse.

**The durable remedy is to assert the reason rather than the outcome bit.**
Isolating the fixture also works and has to be re-derived by hand for every new
row, which is
[`algorithmatize-checks`](algorithmatize-checks.md)'s eighth mutation outcome.
A row that names the reason it must fail for reports
`denied, but not for` that reason once a masking setup is restored under a
mutant, where the bit alone reported a pass.

- **Do:** assert the discriminating detail --- the reason, the message, the
  resolved value --- on any row whose expected outcome has more than one
  producer.
- **Do:** run each new row against a mutant with the fix removed before
  trusting it, since a realistic setup is the kind most likely to mask.
- **Don't:** read a green row as coverage when its own setup could have
  produced that outcome without the code under test.
- **Don't:** treat isolating the fixture as the whole fix --- it holds only
  until the next author writes the natural setup again.

(Measured 2026-08-22 on
[ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911),
repeatedly within one session on `hooks/test-no-push-without-self-review.py`.
Regression rows written as `--repo=origin` against `remote.origin.push` passed
against a mutant with the fix removed, because ignoring `--repo` falls through
to a literal `origin` and finds the same key.
Rows for the option abbreviations `--al` and `--re` masked the same way until
their config was switched to a benign `branch.main.pushRemote`.
That table now states the reason each row must deny for, and its own docstring
records that the bit alone cannot tell a working row from a masked one.)

## A row you found vacuous is not fixed by the rewrite that answers it

The section above already requires the mutation run: assert the discriminating detail, and run each new row against a mutant with the fix removed before trusting it.
Two things it does not say, and they are the two that decide whether that run actually happens.

**The rewrite is the row least likely to get the control, and it is the row that most needs it.**
Having caught one row scoring green against a mutant, the diagnosis feels like the hard part and the replacement feels like bookkeeping.
It is the other way round.
The masking property --- some second route to the same observable --- is a fact about the fixture, not about the spelling that tripped over it, so it survives a rewrite by default.
And the rewrite is authored by the same understanding that missed it the first time, which is the understanding that just failed on this exact question.
So a replacement row is unverified until it has failed against the same mutant, and the second spelling failing the control is an ordinary outcome rather than a surprise.

**The forward-looking half is one question: what does the fixture supply for free?**
The mutation run discovers the masking route afterwards.
This predicts it, and it costs a sentence.
A row can only discriminate on a difference the fixture does not already provide by some other path, so name that path before writing the assertion --- a working directory the harness sets, a default the code falls back to, a fallback remote, an environment value the test inherits.
Where the fixture already supplies the thing the row is trying to vary, the row is asserting a tautology however carefully it is phrased.

Note the interaction with the preceding section's own remedy, since the two are easy to run together and easy to confuse.
Asserting the **reason** rather than the outcome bit is what makes a row survive a masking setup.
Asking what the fixture supplies for free is what tells you a masking setup exists, and it can rule out a whole family of spellings before any of them is written.
Neither replaces the mutation run, which is the only thing that reports on the row you actually wrote.

- **Do:** re-run the mutation control after every rewrite, and treat a replacement row as unverified until it has failed against the mutant.
- **Do:** name what the fixture supplies for free --- cwd, a default, a fallback, an inherited environment value --- before writing an assertion meant to discriminate on it.
- **Don't:** read having diagnosed a vacuous row as having fixed it.
  The diagnosis and the replacement are separate claims, and only the second one ships.
- **Don't:** vary a quantity the fixture already provides by another path and expect the row to discriminate, however precisely the assertion is worded.

(Measured 2026-08-22 on [ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911), **unmerged** at the time of writing, on `hooks/test-no-push-without-self-review.py`.
A row was written to establish that the guard's directory-hint scan resolves a push the same way its primary parser does, both going through the sibling detector rather than through a literal `git push` prefix match.
A mutant with that call site reverted made the row pass.
It was rewritten, and the rewrite was vacuous against the same mutant.
Only the third spelling discriminated.

What the fixture supplied for free is `cwd`: the harness runs the hook with its working directory set to the fixture repo (`cwd=REPO` in `run_hook`), so a directory hint naming that same repo is indistinguishable from no hint, and a row carrying no verdict denies either way.
Only a row that changes directory to the harness's *second* repo and carries a clean verdict separates the two builds, because only then does losing the hint change the answer.

At that PR's branch head `51be639e` the suite is still vacuous on this point, measured here rather than recalled:

```
$ sed '433s/_SIBLING and _SIBLING._argv_push(rest)/_SIBLING and rest[:2] == ["git", "push"]/' \
    hooks/no-push-without-self-review.py > hooks/mut-hint-naive.py
$ python3 hooks/test-no-push-without-self-review.py hooks/mut-hint-naive.py
All 169 cases passed
```

The mutant is faithful and behaviourally different --- `_hints_by_position("cd /other && git -C /elsewhere push")` returns `['/other']` under the original and `[]` under it --- so the zero is a measurement rather than an inapplicable mutation.
A discriminating spelling may exist unpushed.
What is measured here is the pushed head.)

## A fixture that models the wrong record SHAPE makes a carve-out look covered while it is inert

Every case above is about a fixture whose *content* was wrong --- too thin to
reach a branch, or asserting the buggy output.
This one is about a fixture whose **shape** was wrong, and it is harder to see
because the shape is the very thing the fixture exists to stand in for.

A guard reading a transcript needs to know what a record looks like.
Its fixtures encode that belief.
So when the belief is wrong, the fixtures are wrong in exactly the way that
makes them agree with the code: both were written from the same guess, the
suite is green, and the mechanism the fixtures describe **does not exist**.

Nothing internal can catch it.
The tests pass, the code is self-consistent, and a reviewer reading both sees a
covered feature.
Only the real artifact settles it --- which is
[`verify-the-right-artifact`](verify-the-right-artifact.md)'s point arriving one
level down, at the fixture rather than at the claim.

So when a guard consumes a machine-produced artifact, read one **real** artifact
before trusting any fixture of it, and say in the fixture where the shape came
from.
A fixture whose docstring cites a live sample is checkable; one that cites
nothing is a guess with tests around it.

- **Do:** dump a real record and copy its shape into the fixture, citing the
  date and source.
- **Do:** treat "the carve-out has a passing test" as evidence about the
  fixture until you have seen the real shape.
- **Don't:** infer a record's shape from how the surrounding code reads it ---
  that is the same guess twice, and their agreement measures the guess.
- **Don't:** count a green suite as evidence a carve-out fires; an inert branch
  and a correct one are both green.

(Measured 2026-08-22 on
[ai-config#1917](https://github.com/Morrison-Lab/ai-config/issues/1917) /
[#1925](https://github.com/Morrison-Lab/ai-config/pull/1925).
`no-unmeasured-clock-claim.py` carried a deliberate carve-out so that quoting
the harness's just-injected clock reading would not trip it, and a fixture named
"quoting the harness's just-injected reading is exactly what the rule says to do"
asserted it.
Both modelled the reading as a bare-string `user` turn.
A live transcript shows it is not a user record at all: it is its own record,
`type: "attachment"`, carrying the text under `attachment.content` /
`attachment.stdout`, with neither a `message` nor a top-level `content` --- so
the scan skipped it and the carve-out never fired, while its test passed.
The reviewer on [#1919](https://github.com/Morrison-Lab/ai-config/pull/1919)
raised the possibility and explicitly could not settle it from the fixtures,
which is the shape of the problem in one sentence.)


## An alternative no fixture can isolate may be DEAD, not merely untested

Every section above treats a masking fixture as a defect in the **test**: the
setup supplies a second route to the observable, so the remedy is to assert
the reason, isolate the fixture, or rewrite the row and re-run the control.
Each of those presumes the property under test is real and the row is what
failed to pin it.

There is an outcome the presumption hides.
When you sit down to isolate an alternative and find that you *cannot* ---
that every input which reaches it necessarily carries the masking substring
too --- the finding is about the production code, not the fixture.
An alternative that no admissible input can reach alone is dead, and a test
proving it fires would have to be built from an input the system never sees.

The reason this is worth separating is that both states present identically at
the point you notice them.
A row that fails to discriminate and a branch that cannot be discriminated
both look like "this fixture needs more work", and the natural next move ---
try a sharper fixture --- is the correct response to one and an unbounded
search in the other.
So the question to ask on the second or third failed attempt is not "what
fixture would isolate this" but "does an input exist that reaches this
alternative and nothing else".

The generative case is an alternation over substrings of a structured value,
where the domain guarantees co-occurrence.
A URL path matched against `/comments` and `/replies` cannot distinguish them
when every reply URL the API issues contains `/comments` as a prefix segment,
so the `/replies` arm is unreachable by construction rather than by omission.
Note the direction of the check: the co-occurrence is a fact about the
**upstream format**, so it is settled by reading that format's documentation or
a real response, never by trying more fixtures.

The same reading applies to a fixture whose value satisfies two arms at once
for an unrelated reason --- a `/discussions` path that also contains
`/comments`.
That one is the ordinary masking case and a sharper fixture does fix it, which
is why the two have to be told apart rather than treated as one symptom.

- **Do:** ask whether an isolating input can exist, once a second attempt at
  isolating an alternative has failed.
- **Do:** settle co-occurrence from the upstream format's own documentation or
  a real response, rather than from further fixture attempts.
- **Do:** report an unreachable alternative as a finding about the
  implementation --- dead code to remove, or a predicate to restate ---
  instead of as a coverage gap to fill.
- **Don't:** read "no test pins this" as "this needs a test";
  it is equally consistent with "this can never fire", and the two call for
  opposite changes.
- **Don't:** keep generating fixtures for an arm whose domain rules out an
  isolating input --- the search does not terminate, and its failure is the
  answer rather than an obstacle.
