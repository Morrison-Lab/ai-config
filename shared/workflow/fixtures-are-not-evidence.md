A test fixture records what someone believed the real thing looks like.
Reasoning from a fixture back to the real thing is circular, so a fixture --
or a test outcome against one -- is never evidence about the system it
imitates.

Worked-example case records for the rules below live in
[`fixtures-are-not-evidence.cases.md`](fixtures-are-not-evidence.cases.md), moved out of the auto-loaded context.

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
