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

## A drift claim is relational, so one read cannot settle it

Every shape above is one substitution: you read A and made a claim about B.
This is the case where the claim is about **both at once** ---
A has drifted from B, the install is stale, the two copies have diverged ---
and a two-place claim needs two reads.
Read one, supply the other from memory, and the check feels complete,
because the section's own Do line is singular:
"state which artifact a claim rests on, then read *that* one".
A drift claim rests on two, and reading either one satisfies that sentence.

Two proxies stand in for the missing read, and both are metadata
rather than content.

**An mtime.**
It records when a write happened, not whether contents lag a source.
A file copied once and never needing to change carries an old mtime
and current contents,
which is the same reading a genuinely stale file gives.
[`keep-checkouts-fresh`](keep-checkouts-fresh.md) already warns against mtime
in the opposite direction --- spotting *local edits*, where `git` resets mtimes
on checkout --- and the same metadata is uninformative in this direction
for a different reason.

**An absence.**
Finding that the installed copy lacks some function,
and asserting the source "has carried" it,
checks the consumer and infers a property of the source.
The absence is equally consistent with the source never having had it.

The falsifying question in "The test" above disposes of both:
ask what the artifact would read in the case you are worried about,
not only in the case you expect.
An mtime reads identically for a current copy and a stale one,
so it discriminates nothing.

Where the two artifacts are files, the deciding query is a direct comparison,
and it is cheap: `cmp` in a loop, or `diff -r`.
Where an instrument already owns the comparison, run the instrument instead ---
`scripts/check-install.py` compares `~/.claude` against the checkout
and reports `stale` by name,
so a hand-rolled diagnosis of install staleness is re-deriving
a verdict the repo already computes.

**A diagnosis that resolves an irritation deserves the deriving query
before it deserves an issue.**
The false one here was satisfying twice over:
it explained an incident that had already cost three blocked turns,
and it assigned the cause to infrastructure rather than to
an unmerged fix of my own.
Neither feeling is evidence, and both suppress the impulse to run the command.

- **Do:** name both artifacts a drift, staleness, or parity claim compares,
  and read both before asserting the difference.
- **Do:** run the direct content comparison --- `cmp`, `diff -r`,
  or the instrument that owns it --- rather than inferring drift from metadata.
- **Do:** slow down on a diagnosis that explains something annoying
  or points away from your own work, and derive it before filing it.
- **Don't:** read an mtime as evidence about contents;
  it is evidence about when a write occurred.
- **Don't:** infer what a source contains from what a copy of it lacks ---
  read the source.

See
[`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md),
"A stale install diagnosed from an mtime and an absence".
