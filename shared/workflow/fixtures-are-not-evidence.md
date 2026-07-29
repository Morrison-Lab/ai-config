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
