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

## A working-directory checkout is a fifth shape, and it stays silent

Shape 1 already names "a stale local checkout" among its examples, so this is a sharpening of that shape rather than a wholly new one.
What it adds is the *tell*, which shape 1 leaves implicit: its remedy, go to the authoritative store, presumes you already suspect the copy, and that presumption is exactly what fails here.
A working-directory read offers nothing to raise the suspicion: the path resolves, the file exists, and its contents are real bytes from a real commit.
Nothing distinguishes reading the default branch from reading a feature branch that happens to be checked out, so `cat <path>` in a repo you have open reads as consulting the repository rather than as consulting one revision of it.

Two properties make it worse than an ordinary stale read.

**The staleness is invisible in the direction that matters.**
A file missing from the branch errors, and an empty file is obviously wrong.
A file that is merely *older* returns a complete, coherent, plausible document --- frequently the document you remember, since a feature branch usually forked from a `main` you had already read.
So the failure mode is not confusion but false confidence.

**A shared checkout moves under you.**
Another session, or a `@claude` bot reacting to PR activity, can switch branches or pull between your read and your next command, so the branch you verified once is not the branch you are still on.
`git reflog` is what shows this after the fact; nothing shows it at the time.

The cheap check is one command, and it belongs *beside the read*, not once at session start:

```bash
git -C <repo> rev-parse --abbrev-ref HEAD     # which revision am I reading?
```

The better move is to skip the checkout altogether whenever the claim is about what the repository currently documents, and read the revision by name:

```bash
git -C <repo> fetch -q origin
DEF=$(git -C <repo> remote show origin | sed -n 's/.*HEAD branch: //p')
git -C <repo> show "origin/$DEF:<path>"
```

This names the revision in the command, so the bytes you read and the revision you cite cannot come apart, and it answers correctly whatever the checkout is doing.
Resolve the default branch from the repo rather than assuming `main`.

The `fetch` is load-bearing rather than tidiness.
`origin/<default-branch>` is a remote-tracking ref, so it is only as current as the last fetch --- without one, this substitutes a different stale artifact for the right one, which is this whole fragment's failure mode wearing the remedy's clothes.

The consequence generalizes past reading.
An assignment derived from a stale read is wrong in a way [`challenge-the-assignment`](challenge-the-assignment.md) cannot catch, because every premise check the recipient runs confirms a document that genuinely exists.
When a brief, an issue body, or a review finding asserts what a repository says, cite the revision alongside the path.

- **Do:** name the revision in the command when the claim is about what a repo currently says.
- **Do:** re-check the branch beside each read in a shared checkout, rather than trusting a verification from earlier in the session.
- **Don't:** treat a successful `cat` in a repo directory as evidence about that repo's default branch.
- **Don't:** read plausibility as freshness --- a feature branch forked from a `main` you already read returns exactly what you expect.

See [`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md), "A stale branch read that produced two issues and a config edit".

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
