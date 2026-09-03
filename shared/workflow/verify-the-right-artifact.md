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

(Measured 2026-08-21 on
[ai-config#1849](https://github.com/Morrison-Lab/ai-config/pull/1849),
[review comment](https://github.com/Morrison-Lab/ai-config/pull/1849#discussion_r3834408153).
The delegating skill is `skills/clean-git/SKILL.md`, added by that PR, and the
delegate is [`clean-worktrees`](../../skills/clean-worktrees/SKILL.md) step 2,
which runs `git worktree prune -v` rather than `--dry-run`.
Note that a grep of `main` cannot corroborate this while #1849 is unmerged,
since the delegating skill does not exist there yet --- which is the case for
citing the PR rather than the file.
Fixed in `c59ae986` by narrowing the gate's invariant to "nothing that can lose
work happens before confirmation".)

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

## A working-directory checkout is another shape, and it stays silent

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

## A comparison's base is an artifact too, and it moves the scope in both directions

Every shape above concerns an artifact you **read**.
A diff is an artifact you **derive**, from two refs, and attention goes to the one you are interested in --- the branch under review.
The other ref is the base, and nothing about naming it feels like making a claim.

`git diff main...pr-98` reads as "the PR's changes".
It is not.
It is the changes since whatever commit your **local** `main` shares with `pr-98`, and a local branch is a cached copy of a remote branch, which is shape 1 exactly.
The three-dot form is what conceals it: a merge-base is a real computation over real history, so the range feels self-correcting, and the sensation of having used the careful form stands in for having checked the ref the careful form is computed from.
A merge-base is only ever as fresh as the ref you fed it.

**The error runs in both directions, and the quieter one is the worse.**
A base **behind** its remote moves the merge-base earlier, so the diff gets bigger.
The extra content is commits that already merged --- other people's work, already reviewed, already landed --- and a review run on it produces findings against code the author of this PR never wrote, spending the author's time and the reviewer's credibility at once.
A base carrying local commits the remote lacks --- **ahead** of it, or diverged from it --- where the head branch also carries those commits, moves the merge-base *later*, so the diff gets smaller.
That is the dangerous one.
An over-wide diff produces findings the author will dispute, so it announces itself within a round;
an under-wide one silently omits part of the change and comes back clean, and a clean verdict is the one nobody questions.

**Nothing in the output announces either direction.**
A 53-file diff and a 14-file diff are equally plausible artifacts.
Every finding derived from the wrong scope is individually well-formed, correctly quoted, and about a real line of real code.
So the usual detector --- a finding that looks wrong --- never fires, because none of them do.

A dispatched reviewer cannot catch it either, and [`challenge-the-assignment`](challenge-the-assignment.md) says why in the mirror: a brief must not assert what the author cannot query about the *recipient's* environment.
This is the inversion of that.
The brief asserts something about the author's **own** environment, which the author could have queried in one command and did not, and which the recipient cannot query at all.

**The falsifying question in "The test" above disposes of it, and its answer is that the diff cannot testify about itself.**
Ask what would have to be true for the base to be wrong, and whether the diff in hand could show it.
It could not.
The forge could, and it is one call:

```bash
git -C <repo> fetch -q <remote>
BASE=$(git -C <repo> merge-base <remote>/<default-branch> <pr-ref>)
git -C <repo> diff --shortstat "$BASE" <pr-ref>
gh pr view <N> --json changedFiles,additions,deletions
```

The two readings must agree.
A mismatch means one of the two refs is wrong, and the base is only the first place to look: the local copy of the *head* goes stale the same way, so a PR that has received commits since you fetched it disagrees with a perfectly correct base.
Re-fetch the head before concluding anything about the base. (Rename detection is a smaller third cause, since `diff.renames` is on by default and the forge counts renames its own way.)
This section is about attributing a discrepancy to the wrong artifact, so a single diagnosis for a symptom with several causes is the failure it describes rather than a shortcut past it.
Resolve the default branch from the repo rather than assuming `main`, and note the remote is not always `origin` --- a dual-forge repo has the PR's forge under a second remote name, and the fetch has to name that one.

The `fetch` is the load-bearing half, for the reason the working-directory section already gives: a remote-tracking ref is itself a cached copy, current only to the last fetch.
A fetch at session start does not cover a review dispatched an hour later, which is [`check-before-pushing`](check-before-pushing.md)'s point about a reading of a moment that has passed, moved from the push to the dispatch.

Report the base you resolved.
A review brief, or a review comment, that states the merge-base SHA and the file and insertion counts alongside its findings is one a reader can check;
one that says "the PR's diff" is not.

- **Do:** resolve a review diff's base from a remote-tracking ref, after fetching that remote, and state the merge-base SHA and the file and insertion counts beside it.
- **Do:** cross-check the derived counts against the forge's own (`gh pr view --json changedFiles,additions,deletions`) before dispatching, and treat any mismatch as a wrong base rather than as noise.
- **Don't:** pass a bare local branch name as a diff's base, in your own command or in a brief you hand a subagent.
- **Don't:** read the three-dot form as self-correcting --- it computes a merge-base from refs you supplied, and cannot know one of them is behind.
- **Don't:** wait for an implausible finding to reveal it;
  over-wide scope produces findings that are all individually sound.

`hooks/warn-stale-review-diff-base.py` is the instrument, per [`algorithmatize-checks`](algorithmatize-checks.md).
The rule it enforces is not "was the local ref fresh", which no hook can know, but "name a remote-tracking ref", which is lexical.
It warns and never blocks, because a bare local base is entirely correct for an ordinary local comparison and the hook cannot tell those apart.
It has no fetch-based discharge on purpose: [`keep-checkouts-fresh`](keep-checkouts-fresh.md) mandates a fetch at session start, so keying on one would silence the hook in exactly the sessions that follow the corpus.

See [`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md), "A stale local base that nearly quadrupled a review diff's file count".

## A summary is another shape, and the auto-loaded copy is the one you read

[`fact-check-prose`](../writing/fact-check-prose.md)'s "any condensation
of a verified source is a fresh claim" already names the psychology, and
[`citations`](../writing/citations.md) already names why an unquoted
attribution launders --- a paraphrase reports the source's conclusion in
your voice, with the source's authority attached.
What neither covers is the *retrieval* asymmetry that decides which copy
you consult at all.

Run `scripts/check-context-closure.py` for the current set: `CLAUDE.md`
and the fragments it `@`-imports are always in context, while `memories/`
and the rest of `shared/` are not.
So a rule restated in an auto-loaded file is the copy you will read, and
often the only one, while its source is a file you must decide to open.
The summary is not merely available --- it is already there, and it names
the source, which answers "where does this come from?" convincingly
enough that nothing prompts the read.

Two consequences follow that the neighbouring fragments do not draw.
Compression fails in a direction: hedges, caveats, and disambiguating
steps go first, because those read as qualifying detail rather than as
the claim itself.
And quotation is not the boundary.
A *characterization* --- "`X.md` records that ..." --- is the looser form
and the one no phrase-grep can check, so the attributions most likely to
be unfaithful are exactly the ones an instrument cannot see.
`hooks/remind-brief-premises.py` detects that sentence shape already, but
only on `Agent`/`Task`/`SendMessage` payloads, so the reader-side case is
currently uninstrumented.

- **Do:** open the cited file before asserting what it says, including
  when the passage in front of you names it.
- **Do:** suspect a dropped hedge first when a summary and its source
  disagree.
- **Don't:** treat "the auto-loaded file says so" as having consulted the
  fragment it cites.
- **Don't:** read an unquoted attribution as checkable --- it is
  precisely the form that is not.

See [`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md),
"A summary read as its source, in the session that fixed the summary".

**The same substitution runs over your own transcript,
and there it corrupts a measurement rather than a citation.**
The section above concerns a summary of a corpus *file*.
A context-window summary of the *conversation* is the other copy that is already in front of you,
and the reply it condenses is not.

That matters most when the text is being used as a **specimen** rather than as a source.
Designing a matcher --- a hook's regex, a grep, a classifier's word list ---
against the summary's rendering of a reply is validating it against paraphrase.
The summary's wording is written to be representative, so it matches readily,
and the measurement comes back clean;
the real reply's wording is what the matcher will actually meet in production,
and it need not match at all.
Nothing distinguishes the two outcomes,
because both are "the pattern fired on the text I tested it against".

Measured 2026-09-02/03 while drafting the `no-unverified-approval-claim` Stop hook on `Morrison-Lab/ai-config` (branch `hook/no-unverified-approval-claim`,
unpushed at the time of writing, so there is no PR to cite):
the matcher was designed and validated against a context-window summary of the session's own reply.
The summary's phrasing matched and the reply's phrasing did not,
so the design read as validated by its own measurement while not firing on the one case that motivated it.

- **Do:** pull the verbatim text out of the raw transcript when a matcher is being fitted to it,
  per [`get-under-the-hood`](../principles/get-under-the-hood.md)'s raw-log practice.
- **Do:** treat "the pattern matched my test string" as a claim about the test string until you can say where that string came from.
- **Don't:** fit a matcher to a summary of the thing it must match ---
  a paraphrase is the one specimen guaranteed to be cooperative.

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
a hand-rolled diagnosis of a property an instrument already computes
is re-deriving a verdict the repo already owns.
(The worked example here was `scripts/check-install.py`,
which compared `~/.claude` against the checkout and reported `stale` by name;
it was removed along with the symlink install it verified,
so read it as a historical illustration ---
see [ai-config#2229](https://github.com/Morrison-Lab/ai-config/pull/2229).)

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

**The interpreter's own defaults are another adjacent artifact, and a failed reproduction is where they stand in for the code.**
The four shapes above all substitute one *file* or *run* for another.
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

**The mirror of that, for the person who made the report: a reviewer's failed
reproduction is not a refutation, and the remedy is to SCOPE the claim rather
than retract it.**
The section above tells whoever failed to reproduce what they owe.
It does not say what the original claimant owes when someone competent runs
the case, carefully, and sees nothing --- and the pull there is strongly
toward retracting, because the reviewer has evidence and you have a memory.

Both can be right, and usually are.
An observation made on one machine is true on that machine; stating it without
a scope is what makes it false everywhere else.
So the disagreement is rarely about whether the thing happened.
It is about a qualifier nobody wrote down.

Two moves settle it, in order.
**Re-run your own original case**, since a remembered failure is not evidence
and may simply have been a mistake.
Then, if it reproduces, **reduce it to a form that removes the suspected
explanation** --- the reviewer's runs are a hypothesis about the cause, so
build a case their hypothesis cannot account for.

What lands in the corpus afterwards is the scoped claim plus the environment
both parties measured, and the reviewer's null result belongs in the entry
rather than being discarded by it.
A rule stated unconditionally, true where it was written and false where it is
read, is [`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md)'s
failure with an environment in place of a date.

- **Do:** re-run your original case before conceding anything.
- **Do:** reduce to a form that rules out the reviewer's proposed cause, then
  publish the scope both of you measured.
- **Do:** record the null result in the entry; it is what tells the next reader
  to test rather than trust.
- **Don't:** retract a reproducible finding because someone else could not see
  it --- that discards a true observation to resolve a missing qualifier.
- **Don't:** defend it unscoped either; unconditional is the actual defect.

(Measured 2026-08-22 on
[ai-config#1926](https://github.com/Morrison-Lab/ai-config/pull/1926).
A `CLAUDE.md` entry claimed a doubled backslash collapses inside a quoted
heredoc.
The reviewer ran three cases in a Linux CI runner, could not reproduce any of
it, and said so with its evidence.
Re-running the original case reproduced it immediately; reducing it to a `cat`
heredoc writing two lines to a file --- no interpreter anywhere --- showed a
typed `\\` and a typed `\` both landing as one backslash, which the
reviewer's Python-parsing explanation could not account for.
Platform: Windows 11 / MINGW64 through the Claude Code Bash tool.
The entry now leads with that scope and carries the reviewer's null result.)


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

**A seventh: a future state for the present one.**
The six above all substitute one artifact, environment, or property for
another that exists *now*.
This one substitutes a state of the **same** artifact at a *different time* ---
what the tree will contain once some other branch lands.

The figure is not wrong when written, which is what makes it durable.
It is wrong when read, because it is committed to a file whose own instrument
reports the present number a few lines below, so a reader compares the two
directly and the prose loses.

- **Do:** derive any number you commit against the state of the branch you are
  committing it to, not the state you expect after some other PR merges.
- **Do:** re-run the file's own checker and quote what it prints, when the file
  ships one.
- **Don't:** compute against a listing, count, or size that only exists on
  another branch.

(Measured 2026-08-21 on
[ai-config#1853](https://github.com/Morrison-Lab/ai-config/pull/1853).
A source comment claimed "about 21 skills of runway", derived from a listing of
8,070 --- the value once
[#1849](https://github.com/Morrison-Lab/ai-config/pull/1849)'s entry lands ---
in a file whose own validator printed `7998/9000` on that branch.
The reviewer re-derived it as `1002 // 43 = 23` and the figure was corrected in
`653dc9df`.)

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

**Re-reading each round does not fix it, and which half decays tells you what to write instead.**
The remedy above is a discipline, and a discipline applied every round on a PR with many rounds still loses, because the body has two kinds of content and they rot at different rates.

A body describing the **mechanism** is stale the moment the mechanism changes, which on a PR under revision is every round.
A body organized around the change's **invariants** --- what must remain true however it is built --- plus an **append-only history** survives, because neither is invalidated by a rewrite.

The residual after that restructuring is **counts**: a test total, a round number, a file tally.
They read as settled facts rather than as claims, so they escape the re-read that catches everything else, and they are wrong within one push.
The fix is not to check them harder but to give the deriving command beside each one, so a stale figure is repairable by running a line rather than by remembering what it was.

Two things follow.
Keep the mechanism in the module docstring or the code comment, which is version-controlled with the thing it describes and therefore cannot drift from it.
And prefer a figure a reader can re-derive to one you assert: `wc -l` beside a count costs nothing and converts an assertion into an instrument.

- **Do:** organize a body around invariants and an append-only history, not around how the change currently works.
- **Do:** print the deriving command beside every count.
- **Do:** put mechanism detail where the code lives, so it is versioned with what it describes.
- **Don't:** rely on re-reading each round --- it is necessary and it does not scale past a few rounds.
- **Don't:** treat a number as the safe part of a body.
  It is the part that reads as checked and is not.

(Same day, both PRs.
gha#550's body still read "the fixture suite unchanged and passing" after a
push that added two fixtures, and "there is no offline test" after a push that
added one.
ai-config#1833's body still carried, verbatim, all three prose defects that
three review rounds had just corrected in the file it was describing.)

**A suite's own summary line is the verdict; a count you derive from its log is
an adjacent artifact.**

The narrowest form of this substitution, and the one that survives review
because the derived number is *nearly* right.

A test suite typically reports two things: one line per failing case, and a
final line saying how many failed.
Counting the first with `grep -c` looks like reading the result and is not ---
the summary line is usually formatted like a finding (`::error::N of 14 cases
...` is itself an `::error::` line), so it counts as a case and every figure
comes out inflated by exactly one.

That constant offset is what makes it durable.
A wildly wrong number invites a second look; `5` where the truth is `4` reads
as plausible, stays plausible when re-derived the same way, and is not
checkable against anything else in the report.
Nothing in the suite's output contradicts it, because the suite never made the
claim --- you did.

It bites hardest on **mutation counts**, where the number is the entire
evidence for "this assertion is load-bearing".
A corpus that asks for counts to be confirmed by mutation rather than assumed
gets a count that was measured, from the wrong line.

- **Do:** read the suite's own summary line, or its exit status, as the
  verdict.
- **Do:** state which line you read it from when a count reaches prose someone
  will rely on.
- **Don't:** `grep -c` a suite's findings and call the result its failure
  count.
- **Don't:** treat a number as verified because you ran something to get it ---
  ask which artifact answered, and whether it was the one making the claim.

(Measured 2026-08-27 on [gha#687](https://github.com/Morrison-Lab/gha/pull/687).
Three mutation counts were documented as 5/8/4 in `gha`'s `CLAUDE.md`, read via
`grep -c '^::error::'`.
The reviewer independently reproduced 4/7/3 and flagged the mismatch at reduced
confidence, guessing the mutation implementations might differ.
They did not --- the suite's summary line was being counted as a fourteenth
case, which is why all three were off by the same amount.
Note the detector here was a second party re-running the measurement, not a
check: nothing in CI could have caught it.)

**An eighth: what a change TRANSFORMS, standing in for what it CONCLUDES.**

The shapes above substitute one artifact, environment, or property for another, and this one substitutes a property too --- so what distinguishes it is not *what* gets swapped but *where* the swap happens.
It happens inside a verification built specifically to catch the error it then misses, so the substitution arrives wearing the clothes of a parity proof, and the instrument's own clean number is what conceals it.

A change to a fail-closed instrument widens what it blanks before scanning, and the proof asks: does every character the new revision blanks and the old one did not lie inside a code span the change is meant to blank?
That question cannot come back non-zero for any implementation of that shape.
The extra-blanked set *is* the span set, so the metric restates the change's own definition and reports the restatement as evidence.
Its zero was truthful and worthless: two real fail-opens were live at the time, and both arose in the passes that run *after* the blanking, about which a metric over the blanking says nothing whatever.

The tell is that the metric's inputs are the two revisions' outputs at an **intermediate stage**, rather than the two revisions' **verdicts**.
An instrument exists to conclude something, and a change to it is safe when the conclusions match --- not when an intermediate buffer differs in the shape the change predicted.
So diff the **acceptance sets**: which bodies each revision calls clean, which it calls not clean, and which moved.
Let the transformation be whatever it needs to be.

Distinguish it from [`fail-fast`](../principles/fail-fast.md)'s fifth cause of a vacuous zero, which it superficially resembles.
There the check examines the right quantity and the *subject* absorbs its own failures through a designed fallback, so the remedy is to measure the fallback bucket.
Here the subject is fine and the check asks a question with only one possible answer, so no bucket exists to measure --- the metric has to be replaced rather than instrumented.

This is the general form of the trap [`mistake-patterns.md`](../../memories/mistake-patterns.md) Pattern 15 warns about.
Pattern 15 says to prove parity before widening a fail-closed exemption;
what it does not say, and what this section adds, is that a parity proof can be constructed over the wrong quantity and then cannot fail.
A proof that cannot fail is not a weak proof, it is an absent one wearing a number.

- **Do:** define a parity metric over what the two revisions *decide*, and name the decision function in the metric's own docstring.
- **Do:** ask of any verification metric what result would make you abandon the change --- and treat "none" as the finding.
- **Do:** report the acceptance-set delta in both directions, since a change that only narrows is still a change.
- **Don't:** measure the transformation a change performs and call the agreement a parity proof;
  that measures the diff against itself.
- **Don't:** read a zero as reassurance without checking that a non-zero was reachable for some implementation of the same shape.

(Measured 2026-08-28 on [ai-config#2515](https://github.com/Morrison-Lab/ai-config/pull/2515), fixing [#2449](https://github.com/Morrison-Lab/ai-config/issues/2449).
The first parity instrument compared what `strip_cited_finding_vocab` blanked across two revisions and reported 0 extra characters outside a code span.
The replacement, `scripts/check-verdict-scan-parity.py`, diffs what the two revisions conclude instead, triages each widening by offset, and runs a negative control first.
Only half of its discrimination claim is reproducible **from `main`**, and the entry says which half and how to reach the other.
Running it against the shipped design reports 0, which any reader can re-run.
The 3,924 / 108 / 270 / non-zero off-axis figures for the four rejected designs were recorded on that branch before #2515 was **squash-merged** as `07847b9`, so they are not reproducible from `main` --- which is the artifact a reader has.
They are not lost, though, and the difference matters: GitHub retains `refs/pull/<N>/head`, so `git fetch origin 'refs/pull/2515/head:refs/remotes/pr/2515'` restores the branch and all four designs (`c7ff646`, `4f9d3fc`, `68a14b9`, `a3251bf`) with it.
Name that route whenever you mark a figure unreproducible, since "unreachable" and "not on the default branch" are different claims and only the second is true here --- the first was asserted in this very section and refuted by one `git ls-remote`.)

**A ninth: a LOSSY CONVERSION of a document, standing in for the document.**

The shapes above substitute an artifact that is stale, partial, or adjacent.
This one substitutes an artifact that is current and complete for its own purpose, and **lossy by design**.
A conversion drops what its target format cannot carry,
so its omissions are the reason the tool is useful rather than a defect in it.

The tell is that the derived view answers the question you asked and cannot answer the question you meant.
`pandoc -t markdown` on a `.docx` reports the text a reader sees.
Asked whether a link is present, it can report nothing about a URL stored as a Word HYPERLINK field code,
and **more than one thing decides whether it does**.
All three arms below were measured on pandoc 3.1.3 under `--track-changes=accept`.
A `fldChar` HYPERLINK field in ordinary body text whose `instrText` sits in a single run
converts to a markdown link with its URL intact.
Splitting that same `instrText` across two runs, at the space before the quoted URL,
still emits a link and empties its target: `[anchor]()`.
The identical single-run field nested inside a `<w:ins>` tracked insertion drops the link entirely,
leaving bare text.
So `<w:ins>` is **sufficient** to lose the URL without being the determinant,
since the split-run arm loses it with no `<w:ins>` anywhere in the document.
The split-run arm is not a corner case either:
Word and Zotero routinely split `instrText` across runs,
which is the premise of [`memories/office-open-xml.md`](../../memories/office-open-xml.md)'s sibling entry
and the reason its `merge_runs.py` exists at all.
Say "single-run" rather than "contiguous", which this entry reached for first and which decides nothing:
a field split across *paragraphs*, its `instrText` still in one run, converts with the URL intact.
The negative control is what identifies each mechanism.
Without it the omission reads as "pandoc does not carry field-code links at all",
which is false and was written down that way once before the control was run.
A listing of `word/_rels/document.xml.rels` is no better:
it enumerates one of the two ways Word stores a hyperlink and is silent about the other.
Two independent readings then agree, and the agreement is a property of what both drop.

So before concluding a document does not contain something,
search the **stored form**: grep the source XML, the raw bytes, the file the application actually writes.
The converted view is evidence about what a reader sees, which is a different claim.

- **Do:** name which representation a negative is about --- rendered text, or stored source --- before reporting it.
- **Do:** grep the stored form (`word/document.xml`, the raw file) when the claim is that something is absent.
- **Do:** run a negative control on the conversion before naming a mechanism for what it dropped;
  an omission with no control behind it is a guess wearing a measurement.
- **Don't:** promote one mechanism to *the* determinant once a control has shown it sufficient;
  sufficient and necessary are different findings, and only a further arm separates them.
- **Don't:** read two derived views agreeing as corroboration when both drop the same class of content;
  that is [`grep-is-not-coverage`](grep-is-not-coverage.md)'s guaranteed-either-way null in a new surface.
- **Don't:** treat "lossy" as "stale" --- refetching a conversion returns the same omissions.

(Measured 2026-09-01 while adding tracked changes and comments to three `.docx` files for a journal resubmission.
A manuscript's Shiny-app link was absent from the rels listing and absent from pandoc's markdown output,
and the conclusion that it had been deleted was written into a draft review finding.
It was present as a `fldChar` HYPERLINK field code, found by grepping `word/document.xml` for the URL.
In that manuscript the field carries exactly one `instrText` element and *is* wrapped in `<w:ins>`,
so the tracked insertion really is the operative cause there;
the split-run mechanism generalizes the entry rather than retracting its case.
The manuscript is private, but the pandoc behaviour needs no manuscript:
build a minimal `.docx` carrying the same HYPERLINK field three times ---
once in plain body text with its `instrText` in a single run,
once in plain body text with that `instrText` split across two runs at the space before the quoted URL,
and once single-run but wrapped in `<w:ins>` --- then convert with `--track-changes=accept`.
The three arms emit the URL, an empty target, and bare text respectively.
Read a `w:ins` grep over `word/document.xml` carefully when building the split arm:
`w:instrText` contains the substring `w:ins`, so a plain `grep -c` reports a match in a document that has none.
[`memories/office-open-xml.md`](../../memories/office-open-xml.md) carries the docx-specific mechanics,
including the two-pandoc-diff verification for a redlined document.)

**A tenth: a diff's changed lines, standing in for the file they changed.**

The shapes above substitute one file, run, or environment for another.
This one keeps the right file and reads only the fraction of it a diff highlighted.
A diff marks what changed;
it says nothing about what the surrounding text, including context the same diff adds, now means.
Grepping the diff for a keyword returns exactly the lines matching that keyword and nothing about the lines around them --- and those surrounding lines are the file's meaning as often as not, because a change is scoped by its neighbours.

The tell is a conclusion drawn from **removed or added lines alone**, when the same diff's own added context sits one hunk away and narrows what the removal actually licenses.

Case: `Morrison-Lab/gha#811` deleted three lines from `examples/quarto-publish.yml` --- `concurrency:` / `group: gh-pages` / `cancel-in-progress: false` --- with no replacement.
Reading that removal through `gh pr diff | grep` for `concurrency`/`group` lines supports one conclusion: the PR tells consumers to delete the block outright.
The same diff, earlier in the same file, adds a six-line NOTE the grep pattern never matched: "Do NOT declare a top-level `concurrency:` block naming `gh-pages`" in the caller workflow.
That sentence is scoped to the group's *name*, not to the presence of a block.
A caller-level group with a different name --- `website-publish-${{ github.ref }}`, the literal name `gha#667` gave a different workflow's group in the same repo, or `quarto-publish-${{ github.ref }}`, the name the consumer PR that motivated this fix later merged --- names something else and is not what the note forbids.
The removal and the addition are two edits inside one diff, and only reading the file whole, rather than the diff's hunks in isolation, shows that the second scopes the first.

**This survives the quote-the-passage check, which is what makes it worth recording rather than dismissing as ordinary carelessness.**
[`quotable-findings`](quotable-findings.md) requires a finding to quote the exact passage it is about, on the theory that a quotable finding is a checked one.
Quoting the three removed lines satisfies that rule to the letter: the passage exists, the quote is exact, the mechanical filter passes clean.
What the filter cannot check is whether the *file*, read whole, means what the quoted fragment suggests once its own neighbouring lines are included.
The check that would have caught this reads "open the file the passage lives in," not "quote the passage" --- a stricter requirement than [`quotable-findings`](quotable-findings.md) states, and this is the shape that shows the gap between them.

**Before writing a retraction, check whether the head moved.**
A wrong claim about a file can be wrong for two different reasons, and they produce different retractions.
The commit could have changed since the claim was written, in which case the honest statement is "this changed" and no misreading occurred.
Or the commit could be exactly the one that was read, in which case the honest statement is "I misread it" --- and conflating the two either lets a real misreading hide behind an invented edit, or accuses a PR of moving when it did not.
Settle it before writing either sentence: fetch the specific commit SHA the claim was written against (`gh api repos/<owner>/<repo>/contents/<path>?ref=<sha>`) and confirm it is unchanged, rather than assuming from the PR's current state.
In the case above, the branch head had in fact already moved by the time of both flagged comments --- a separate commit (`e34e03d5`) landed less than a minute before the first of them, fixing an unrelated review round --- but a direct compare (`gh api repos/<owner>/<repo>/compare/<cited-sha>...<later-sha>`) shows that commit never touched `examples/quarto-publish.yml`.
So the file the claim was about was genuinely unchanged, and the retraction's "I misread it" holds;
but the retraction described the cited commit as the one its comments were written against without checking the branch's own commit history, which shows a different commit was already the head by then.
A retraction is a claim like any other, and this one needed the same check.

- **Do:** read the file a diff's hunk lives in, not only the hunk, before concluding what a removal licenses or forbids.
- **Do:** treat added context in the *same* diff as evidence about scope, even when it sits in a different hunk than the lines a grep matched.
- **Do:** fetch the exact commit a wrong claim was written against before deciding whether to retract it as "I misread" or "this changed."
- **Don't:** treat a clean pass of [`quotable-findings`](quotable-findings.md)'s quote-the-passage check as evidence the file was read;
  it only proves the passage exists.
- **Don't:** infer a rule's scope from the lines a diff removed when the same diff also adds prose stating the scope.

(Measured 2026-09-02 on [`Morrison-Lab/gha#811`](https://github.com/Morrison-Lab/gha/pull/811).
Two comments on the PR, both derived from `gh pr diff | grep`-ing the changed `concurrency`/`group`/`cancel-in-progress` lines, argued that the deletion was the wrong fix and that a rename (as `gha#667` had already used elsewhere in the same repo) should have been kept instead;
a later comment restated the same position once a consumer PR merged its own renamed group, phrasing it as the stub telling consumers to delete the block while the consumer had shipped a rename.
The stub's own added NOTE at the cited commit (`856b8702`) read "Do NOT declare a top-level `concurrency:` block naming `gh-pages`," which scopes the prohibition to the group's name and forbids nothing about a renamed group.
Verified with `gh api "repos/Morrison-Lab/gha/contents/examples/quarto-publish.yml?ref=856b8702" --jq '.content' | base64 -d`.
The claim was retracted in the PR thread;
the retraction described `856b8702` as the commit its comments were written against, which a separate check against `gh api repos/Morrison-Lab/gha/pulls/811/commits` and `.../compare/856b8702...e34e03d5` did not confirm, though the file itself was confirmed unchanged.)

**An eleventh: an issue's OPEN state,
standing in for the behaviour it describes.**

The seventh shape above substitutes a *future* state for the present one.
This one substitutes a **stale past** one,
and it arrives with a citation attached,
which is what makes it the more persuasive of the two.
An open issue is a durable, linkable,
timestamped artifact that describes a defect precisely.
Everything about it reads as evidence.
What it actually records is that nobody has closed it,
and closing is a bookkeeping act performed by a person,
so the gap between "the defect exists" and "the issue is open" is exactly the set of fixes that landed without their issue being closed ---
which in a fast-moving repo is a large set.

The asymmetry runs against you.
A closed issue over-claims in the safe direction: you go and check.
An open issue under-claims in the dangerous one:
it confirms the belief you already had, from a source you can cite,
so nothing prompts the read.

The falsifying question from "The test" above disposes of it in one step:
*could this issue be open while the behaviour it describes is fixed?*
It always could.
So the issue can never settle the question, and only the code can.

- **Do:** read the code (or run the test) before asserting current behaviour,
  and cite the file and line rather than the issue.
- **Do:** cite the issue for the *history* --- that this was once broken,
  and is tracked --- which is the claim it can actually support.
- **Do:** check whether the fix landed and the issue simply was not closed,
  and close it (or say so) when it did.
- **Don't:** treat an open issue as a live measurement;
  its state is bookkeeping, not behaviour.

(Measured 2026-09-02, and re-checked 2026-09-03.
`hooks/flag-background-review-dispatch.py` ---
authored at commit `9009e787a` on the local `ai-config` branch `hook/flag-background-review`,
which `git ls-remote --heads origin hook/flag-background-review` confirms is unpushed,
so neither the commit nor the file is reachable from any clone but the author's ---
carried a docstring asserting that [`no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py) does not register verdicts arriving via background task notifications,
citing [ai-config#2483](https://github.com/Morrison-Lab/ai-config/issues/2483), which was ---
and as of 2026-09-03 still is --- open.
The fix had landed on 2026-09-01 in [#2820](https://github.com/Morrison-Lab/ai-config/pull/2820) (`0d78e04c`),
whose `is_task_notification` branch sits at `hooks/no-push-without-self-review.py:1400-1417` and is covered by a passing test.
`git log -L 1400,1417:hooks/no-push-without-self-review.py` names that commit in one command;
no such command was run, because an open issue looked like the answer.
The docstring was still uncorrected on that branch as this was written.)

**A twelfth: a pull request's check-run names, standing in for the branch's own workflow definitions.**

The seventh and eleventh shapes above are both substitutions across time, and the eleventh is unaware too, so what is new here is that **the artifact offers nothing to date**.
The seventh reads a future state for the present one knowingly, because the future state is the one being worked toward.
The eleventh reads a stale past one from a citable artifact: an issue carries a number and a timestamp, so its staleness is checkable by anyone who thinks to check, and what defeats it is that nothing prompts the read.
A check-run **name** carries neither.
`Spellcheck` is the same ten characters whenever it was produced, so there is no field to inspect and no version to compare --- the thing you would have to date is not in what you read.
A pull request's check runs are current, complete, and correct.
What they describe is the workflow definitions **in force when each run executed** --- resolved from the pushed commit for a `push` run, and from the head-into-base merge for a `pull_request` one.
Neither of those is the default branch as of now, and the name carries no trace of which moment or which resolution produced it.

The tell is a claim of the form "this repository emits X", derived from observing X somewhere.
A check run is produced by a workflow file, and a workflow file is versioned like any other, so a rename, a job restructuring, or a migration from inline jobs to a called reusable workflow changes every context string the repository publishes from that moment on.
A check run therefore records the definitions **in force when that run executed**, and its name carries no trace of when that was.

Two facts about a run decide which definitions it used, and a check-run name shows neither.
**When** it executed, and **which ref** it resolved the workflow file from.
For a `push` run that ref is the pushed commit;
for a `pull_request` run it is the merge of the head into the base, so a head that edits the workflow file overrides the base's copy while a head that does not simply gets whatever the base carries at that moment.
That second case is worth stating plainly, because the intuitive rule --- an old head publishes old names --- is false: an untouched workflow file follows the base, so a pull request opened long before a migration publishes the *new* names on its next run.

The staleness that does bite is therefore temporal rather than positional.
A name observed at time T is a fact about time T, and any later merge to the default branch retires it without touching the pull request you read.
Merged-ness is what conceals that.
A merged pull request feels like it *became* the branch, and in the ordinary case it did;
what it did not become is the branch as of any later moment, and nothing about a merged status says which moment you are reading.

The consequence for a required status check is unusually expensive, because it fails in the direction nothing reports.
A required context naming a check that no workflow emits does not error, does not turn red, and does not appear in any run.
It sits as `Expected`, and the only diagnosis is noticing that a check listed as required never appears at all.
How far that spreads is a question about runs rather than about settings.
An open pull request keeps whatever check runs it already has, so one that last ran before the workflow change still shows the old names and still looks satisfied.
Its next **push** re-resolves the workflow file through the current base and publishes the new names, after which the required context is unreportable on that pull request.
A *re-run* does not do this: GitHub re-runs reuse the original event's `GITHUB_SHA` and `GITHUB_REF`, so re-running a pre-change run republishes the old names and looks like evidence that nothing changed.
So the requirement is retired one pull request at a time, as each one is next pushed to, and nothing about that transition is announced.
Date the check runs you are reading before describing the blast radius;
a rollup showing a required context green may be showing a week-old run.

The authoritative artifact is the default branch's own workflow definitions, confirmed against a run **of that branch**:

```bash
gh api "repos/<o>/<r>/contents/.github/workflows?ref=<default-branch>" --jq '.[].name'
gh api "repos/<o>/<r>/contents/.github/workflows/<file>?ref=<default-branch>" --jq .content | base64 -d
gh api "repos/<o>/<r>/actions/runs/<run-id-on-that-branch>/jobs" --jq '.jobs[].name'
```

Read the definition rather than only the run, because a run answers only for the workflows that happened to trigger on that push.
A caller job `check:` invoking `uses: <org>/gha/.github/workflows/spellcheck.yml@v2`, in a workflow whose own `name:` is `Spellcheck`, publishes `check / spellcheck`.
The workflow-level `name:` does not appear at all.
What appears on each side of the slash is a **job** display name --- the caller job's, then the called workflow's inner job's --- and a job's display name is its `name:` where one is set and its key otherwise.
So the string is derivable from the file, and reading it off any observed check run is derivable from the wrong file.

This is also [`run-ums-proactively`](run-ums-proactively.md)'s false-*state*-claim case in its purest form.
No belief about reusable workflows was ever held and then corrected;
the wrong thing was simply looked up, so the reusable lesson is the query rather than the value.

One clause on the corroborating run, because the obvious reading of it is unsatisfiable.
The workflow definition on the default branch is the authority;
the run is corroboration that the definition composes the string you think it does.
A workflow triggered only by `pull_request` produces no run at all on an ordinary push to the default branch, so for that class the corroborating run is usually a pull-request run.
The exception is worth taking when it exists: a pull request opened *from* the default branch into some other base carries that branch's copy of the file on its head side, so its run reads what you want unless the base has diverged on that same file.
Failing that, a pull-request run resolved the workflow file from the merge of its head into its base, so it corroborates the **default branch's** copy only when two things hold together.
Its base is the default branch --- `gh pr view <N> --json baseRefName` --- since a stacked pull request or one targeting a release branch resolves the file from that other base instead, and would corroborate a different branch's copy while looking identical.
And its head does not touch that one file --- `gh pr diff <N> --name-only`, matching the single path rather than the `.github/workflows/` directory, since a head editing some other workflow is irrelevant.
The first condition is the one that goes unstated, and omitting it reinstates this shape's own substitution by way of its remedy.
Prefer a recent run, since an older one may predate the definition you just read.

- **Do:** derive a required-context string from the default branch's workflow definitions, and use a run only to corroborate how those definitions compose.
- **Do:** date every check-run observation by the commit its run executed, and say what has landed on the default branch since.
- **Don't:** accept a pull-request run as corroboration without reading its `baseRefName` --- a head that leaves the workflow file alone is necessary and not sufficient.
- **Don't:** read check names off a pull request, however recent, and generalize them to the repository.
- **Don't:** treat a pull request having merged as evidence its check names still describe the branch --- they described it at one instant, and a later merge can retire them without touching that pull request at all.

See [`verify-the-right-artifact.cases.md`](verify-the-right-artifact.cases.md), "A merged pull request's check names written into a live ruleset".
