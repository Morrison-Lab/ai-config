A test fixture records what someone believed the real thing looks like.
Reasoning from a fixture back to the real thing is circular, so a fixture --
or a test outcome against one -- is never evidence about the system it
imitates.

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

(gha#361, 2026-07-29: a `GH013` line was added to a fixture commented as the
verbatim rejection from gha#360.
When a reordered classifier chain made that fixture fail, the failure was
read as evidence that GitHub wraps workflow-permission rejections in the
generic rule-violation envelope, and that claim went into a review reply, a
code comment, and a commit message.
The real log quoted in gha#360's body has no `GH013` line.
The claim was the whole justification for a chain order that hid a security
bug, so the review round had to disprove the reasoning as well as the code.)

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
Here the fixture predates you, someone else wrote it, and it has been green
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
Run the new tests against the old implementation and confirm they fail:

```bash
git checkout origin/main -- R/<file>.R   # old code, new fixtures and tests
<run the test file>                      # must fail
git checkout HEAD -- R/<file>.R          # restore
```

Restoring only the implementation is what makes this work: the fixtures and
the assertions are then identical across both runs, so every failure is
attributable to the code rather than to the fixture edit.
Checking out `main`'s tests as well would compare two different suites and
prove nothing.

Report the count, per
[`algorithmatize-checks`](algorithmatize-checks.md), since "9 failures across
6 test blocks" is checkable and "the new tests exercise the fix" is not.
A test that fails against the old code only because the function did not exist
yet says nothing about the bug, so name those and exclude them from the count.

- **Do:** check what regime a fixture's data covers, against the
  specification, whenever a fix will not pass without changing that fixture.
- **Do:** restore only the implementation, run the new tests against it, and
  report the failure count before calling the fix regression-tested.
- **Don't:** read a forced fixture change as a sign the fix is too invasive
  -- it is frequently evidence the fixture was wrong.
- **Don't:** treat a long-green fixture as a specification; it records what
  the code did, not what it was supposed to do.

(ucdavis/bcs#479, 2026-07-30: `calc_ip_weights_ab507bs()` filtered adherence
intervals with an upper bound only, `window_dur <= window_months`, missing the
lower bound the SAS reference applies.
The shared fixtures built annual interval durations of 4, 7, 10, 13 and 8
months against an 11-18 month window, plus a 3-month multi-round interval, so
applying the correct bound emptied the model frame outright and the durations
had to move inside the real windows before the fix could pass.
One existing test asserted the bug: "only the terminal round enters the
adherence model, so perturbing the first exam's score leaves every weight
unchanged" held only because a `slice_max` had collapsed the accumulation to
one row per participant, and it now asserts the opposite.
Run against `main`'s implementation, the new tests produced 9 failures across
all six blocks that touch the behavior.)
