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

## The five shapes

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
- **A future state for the present one.**
  A figure computed against what a tree *will* contain,
  written into a file whose own instrument reports what it contains *now*.
  The two sit inches apart on the page, so a reader compares them directly
  and the prose loses.
  Derive any number you commit against the state of the branch you are
  committing it to.

**A document that delegates carries claims about its delegate, and those are
the ones nobody checks.**
The shapes above are all about verifying a *claim you are making*.
This is about the claims a **delegating** document makes structurally, just by
saying "run X's steps 1 through 3" --- because that sentence quietly asserts
what those steps do.
Writing it feels like pointing rather than asserting, which is why no
claim-checking instinct fires on it.

The concrete failure: a skill built around "one confirmation, no mutation
before it" told the reader to run another skill's steps 1 through 3, and step 2
of that range ran a real `git worktree prune`.
The guarantee at the centre of the design was false, and every internal check
passed, because the skill was self-consistent --- the falsehood lived in the
*other* file.

So when you delegate to a numbered range, open that range and read it.
Any property you assert about it --- that it mutates nothing, that it is
read-only, that it asks before acting --- is a claim about a file you did not
write, and it decays when that file changes without touching yours.

- **Do:** read every step you delegate to before describing what it does.
- **Do:** state the invariant that survives the delegate's actual behaviour,
  rather than the one you wish it had.
- **Don't:** treat "run X steps N through M" as a pointer; it is an assertion
  about N through M.

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

Two proxies stand in for the missing read, and neither one reads the source.
That is the shared defect, and it is not "metadata rather than content" --- the
second proxy is a content read, of the wrong side.

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
The false half here --- the claim that the copy was already stale, as
distinct from the true claim that a copy cannot track later merges --- was
satisfying twice over:
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

**The interpreter's own defaults are a sixth adjacent artifact, and a failed
reproduction is where they stand in for the code.**
The five shapes above all substitute one *file* or *run* for another.
This one substitutes the **environment** for the program, and it arrives
disguised as diligence: you were told a defect exists, you tried to see it
yourself rather than taking the claim on faith, and nothing happened.

"Could not reproduce" is then a claim about the code, and the evidence
supports only a claim about the machine.
The direction is what makes it dangerous.
A failed reproduction closes the question --- the reported defect goes away,
the reporter is quietly downgraded, and no further check fires, because
there is no longer anything to check.

The tell is a defect whose trigger is a **default** rather than an input:
a decoder's error handler, a locale, a shell option, a umask, a timezone.
Those are configured outside the program, so the program is identical on
both machines and only one of them can show the bug.

The remedy is to force the condition rather than to hope for it.
Ask what setting has to hold for the report to be true, read that setting,
and set it explicitly before concluding anything.

- **Do:** read the setting the reported defect depends on, and say what it
  was on the machine where the reproduction failed.
- **Do:** force the condition and re-run before writing "cannot reproduce".
- **Don't:** treat a clean run as evidence about the code when the trigger
  is an ambient default.
- **Don't:** let a failed reproduction retire a report; it retires one
  environment.

**A sixth: the fact that a check ran, standing in for what the check found.**
The five above all substitute one artifact for another --- a file, a run, an
environment.
This one keeps the right artifact and reads the wrong property off it.
A guard asks "was a measurement taken?" when the rule it enforces asks "is the
value you stated the one that was measured?", and the two questions come apart
the moment a measurement is taken and then departed from.

It is the hardest of the six to see from the inside, because the guard is
**correct on every case anyone thought to test**.
A session with no measurement fires, a session quoting its measurement stays
silent, and both are the intended behavior --- so the test matrix is green and
the missing case is the one nobody wrote, since it requires imagining evidence
being present and ignored rather than absent.

The tell is an instrument whose state is a **position, a flag, or a count**
where the rule is about a **value**.
An index recording that a reading occurred cannot distinguish quoting it from
contradicting it.
Neither can a boolean "the linter ran", a count of checks executed, or a
timestamp proving a job started.

The remedy is to ask what the guard would have to compare in order to be
wrong.
If the answer names a value the guard never captures, the guard is measuring
its own execution rather than the property.

- **Do:** capture the value a check produces, not only the fact that it ran,
  wherever the rule is stated in terms of that value.
- **Do:** write the test where the evidence is present and the claim departs
  from it, which is the case a green matrix is least likely to contain.
- **Don't:** read a passing guard as covering a rule whose subject it never
  reads.
- **Don't:** treat "the check is registered and did not fire" as evidence the
  claim was sound.

(Measured 2026-08-21, on this repo's own
[`hooks/no-unmeasured-clock-claim.py`](../../hooks/no-unmeasured-clock-claim.py).
It exists to catch a stated Pacific time nobody measured, was registered and
running, and stayed silent while a recap claimed `15:22 PDT` against an
injected reading of `14:48:23 PDT` --- 34 minutes ahead, and in the future at
the moment it was written.
Its `scan()` recorded each reading as a line *index* and never captured the
timestamp, so `main()` compared positions.
Sixteen existing tests passed, none of them a departing claim.
Tracked as [ai-config#1848](https://github.com/Morrison-Lab/ai-config/issues/1848).)

(Measured 2026-08-21 on
[ai-config#1784](https://github.com/Morrison-Lab/ai-config/pull/1784).
A review reported that `run_cli`'s `sys.stdin.read()` could raise
`UnicodeDecodeError` on a non-UTF-8 diff, the third of three reads in that
function and the one a prior round's `errors="replace"` fix had missed.
Piping non-UTF-8 bytes to the unfixed hook exited 0 and reported no
findings.
`sys.stdin.errors` in that container is `surrogateescape`, not `strict`, and
stayed `surrogateescape` under `PYTHONUTF8=0` with an explicit
`en_US.UTF-8` locale, so the crash could not occur there at all.
`PYTHONIOENCODING=utf-8:strict` reproduced it on the first try ---
`'utf-8' codec can't decode byte 0xff in position 47` --- and the fixed hook
exited 0 on the same input.
Stopping at the first attempt would have reported the finding
unreproducible, a true statement about the container and a false one about
the code.)

**Documentation for a capability describes a SURFACE, and your code may reach
that capability through a different one.**

The shapes above substitute a cached copy for an origin, a checkout for a run,
half a mechanism for the whole, a neighbour for the target.
This is another: the documentation is correct, your reading of it is correct,
every quotation checks out --- and it describes the feature as reached through
a surface your code does not use.

The tell is a capability documented for a **settings file, an API, or a
library call** while your code exercises it through a **CLI flag, a wrapper, or
another entry point**.
That the second surface accepts the first's syntax is a separate proposition,
and documentation routinely leaves it unstated because it is obvious to whoever
implemented both.

It matters more than an ordinary unchecked assumption because of how it fails.
An unparsed rule is usually **dropped rather than rejected**, so the change is
a no-op that looks shipped: nothing errors, the diff reads correctly, review
passes, and the concern is retired.

Verifying it needs a **negative control**, and that is the part most likely to
be skipped, because running the thing and seeing no complaint feels like a
test.
It is not: a surface that silently ignores every unknown rule is quiet for the
same reason a working one is.
Pair the real input with one the documentation says must be refused.
If the refusal is announced and yours is not, the silence means something.

- **Do:** name the surface your code actually uses, and verify against it
  rather than against the one the docs describe.
- **Do:** run a known-bad input alongside, so silence is evidence rather than
  absence.
- **Don't:** read a correct quotation of a syntax as evidence that your caller
  parses it.
- **Don't:** ship a mechanism whose failure mode is a silent no-op on the
  strength of documentation alone.

(Measured 2026-08-21 on [gha#550](https://github.com/Morrison-Lab/gha/pull/550).
`code.claude.com/docs/en/permissions` documents `Tool(param:value)` deny rules;
every quotation in the diff was checked against the live page and all were
accurate.
The action passes its rules through `--disallowedTools`, which the page never
mentions.
On Claude Code 2.1.238 both rules were accepted with no warning --- and the
control is what made that informative, since `Bash(command:rm *)`, which the
same page says is ignored, answered
`targets command as a raw string and will not match` on that same CLI.)

**A PR body is prose no check reads, so it goes stale silently while the diff
moves underneath it.**

A near relative, and the one that bites after the work is finished rather than
during it.
Every claim a PR body makes about its own diff --- what is tested, what is
unchanged, what was verified --- was true when written and is unmaintained
thereafter.
No CI job compares the two, and a reviewer reads the body as context rather
than as a claim to check, so it is the one artifact in the review loop with no
detector at all.

Re-read the body at the moment you would report the PR ready, and treat each
of its factual claims as you would a line of the diff.

- **Do:** re-read and correct the body before reporting a PR ready, after the
  last push rather than before it.
- **Don't:** leave a body asserting a verification the diff has since outgrown.

(Same day, both PRs.
gha#550's body still read "the fixture suite unchanged and passing" after a
push that added two fixtures, and "there is no offline test" after a push that
added one.
ai-config#1833's body still carried, verbatim, all three prose defects that
three review rounds had just corrected in the file it was describing.)
