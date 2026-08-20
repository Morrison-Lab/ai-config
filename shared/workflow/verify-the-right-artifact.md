Before reporting a finding, name the artifact the claim is about,
and confirm that is the one you read.

The failure this prevents is not lazy verification.
It is thorough verification of the wrong object.
Evidence gets gathered, it is genuine, the reasoning from it is sound,
and the conclusion is false --- so nothing along the way feels like a guess.
That is what separates this from an unchecked assertion,
and it is why care alone does not catch it:
the sensation of having checked is present and correct,
and it is attached to the wrong thing.

Worked-example case records for the rules below live in
[`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md),
moved out of the auto-loaded context.

## What this adds to the rules already covering one substitution each

Three fragments already name a *particular* adjacent artifact,
and each is worth reading on its own terms:

- [`metacognitive-monitoring`](metacognitive-monitoring.md)'s
  "Read the artifact that failed, not the one beside it"
  governs the **cause of a failure** read off a neighbouring step,
  a sibling job, or the log line above the error.
- [`fixtures-are-not-evidence`](fixtures-are-not-evidence.md)
  governs a **test fixture** standing in for the system it imitates.
- [`fact-check-prose`](../writing/fact-check-prose.md)'s
  "Confirm a rendered page carries your commit before reading anything off it"
  governs a **published build** standing in for the branch that produced it.

What none of them reaches is the substitution's generality.
Each is written as a fact about one situation --- diagnosing a failure,
reading a fixture, fetching a preview ---
so a claim outside those three situations matches none of them,
and the rule that would have caught it never loads.
The substitution is not a property of failure diagnosis.
It happens to a claim about **state**
(what a plugin currently contains),
about **location**
(where a file lives),
and about **mechanism**
(whether a cache is ever read),
in exactly the same shape.

## The four shapes

Recognizable in advance, which is the point of enumerating them:

- **A cached copy for the origin.**
  A CDN-served page, a stale local checkout, a plugin cache.
  Go to the authoritative store instead:
  the branch's raw bytes, the install directory, the API.
- **A checkout for the run.**
  What a branch contains is not what a workflow checked out.
  An `issue_comment` trigger checks out the default branch,
  not the pull request's head.
- **One half of a mechanism for the whole.**
  A cache `save` with no `restore` caches nothing.
  A marketplace entry with no install installs nothing.
  Find the counterpart before asserting that the mechanism works.
- **A neighbour for the target.**
  A directory that happens to contain the files you expected
  is not thereby the path they are read from.
  It can coincide today and diverge tomorrow.

## The test

Confirming the claim against what you read cannot detect this,
because that is exactly what already happened.
Ask the falsifying question instead:
**what would have to be true for this claim to be false,
and could the artifact I read show me that?**

An artifact that cannot exhibit the claim's failure mode
has not tested the claim, however much it agrees with it.
A CDN copy cannot show that the branch differs from it.
A `save` step cannot show that no `restore` exists.
This is
[`fail-fast`](../principles/fail-fast.md)'s denominator move applied to
evidence:
a check whose passing and failing readings are indistinguishable
is not yet a check.

Where the answer is one command, run the command.
The cleanest measured case was settled by `grep -n "actions/cache"`
over a workflow directory:
a single line came back, `actions/cache/save@v6`,
which killed a claim that had already propagated
into an issue body, a second issue, a commit message,
and a pull request opened on its premise.

- **Do:** state which artifact a claim rests on, then read *that* one ---
  the branch's raw bytes over the rendered site,
  the install manifest over a guessed path,
  a search for the counterpart step over an inference from the one you found.
- **Do:** ask what would falsify the claim,
  and whether the artifact in hand could show it.
- **Don't:** treat "I checked something real and it supported the claim"
  as verification.
  The support is real and it is about a different object.
- **Don't:** read a specific, checkable-looking particular as a sign of rigour.
  Specificity is inherited from the artifact that was read,
  not from the one the claim is about.
