Never take shortcuts, and never copy-paste or pattern-match blindly.
Before reusing a structure --- a template, a working script, a
neighbouring file's shape, a pattern from another tool --- state what the
original was **for** and what the new one is **for**, and confirm those
are the same kind of thing.
When they differ, the template does not transfer, however well it fits
mechanically.

This is not an argument against reuse.
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) and the
3Rs "recycle" lens both push toward adapting what exists, and they are
right.
This is the check that makes adaptation safe: structural fit is
necessary and is not sufficient.

## The tell: your checks confirm the mechanism, never the purpose

The reason this survives ordinary diligence is that every check you
naturally run after adapting a template asks whether the **mechanism**
works, and none asks whether the **purpose** survived the substitution.

Same interface, same event, same test convention, passing tests: all
green, and the thing now does the opposite of what it should.
Nothing fails, so nothing prompts the question.

Two properties make it invisible from the inside.

**A template you wrote yourself, recently, gets the least scrutiny.**
Reusing something you just built and verified feels like *consistency*
rather than like assuming.
A pattern borrowed from a stranger's repo would have prompted more
suspicion than one you authored ten minutes earlier, which inverts the
scrutiny the situation actually warrants.

**Structural validity reads as evidence.**
The verification confirmed that the mechanism functions, not that the
mechanism should exist --- the same shape
[`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) describes for
a fixture that has been green so long it reads as a specification.

No instrument decides this, and that is not an oversight.
Structural sameness is mechanical; purpose sameness is not, so it lands
squarely in the judgment residue
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits" section
reserves.

## Not the opposite failure

`memories/preferences.md` uses "pattern-matching" pejoratively for
reading an example **too literally** --- applying a rule only to the
case it illustrates instead of to the principle behind it.
This rule warns about reading a template **too loosely**, carrying its
structure into a case whose purpose differs.

Same phrase, opposite directions, and they do not conflict: generalize
the *principle* a rule teaches, and do not generalize the *structure* an
implementation happens to have.

## The check

Two sentences, written out rather than felt:

1. The original exists to do X.
2. This new one exists to do Y.

Then ask whether X and Y are the same kind of thing.
When they are not, keep the interface if it genuinely helps and rebuild
the behaviour from the new purpose --- do not carry over the parts you
have not justified.

- **Do:** name the original's purpose and the new one's, out loud, before
  adapting a structure.
- **Do:** treat a template you authored recently as needing *more*
  scrutiny than a borrowed one, not less.
- **Don't:** read a passing test suite as evidence that the borrowed
  shape belongs --- it establishes that the mechanism works, never that
  it should exist.
- **Don't:** infer a convention from a sibling tool's shape without
  checking that tool's own reference for it.

## A bulk copy has the same failure at the level of a whole file

The check above assumes you are adapting one template you can look at.
A "port the set of X from repo Y" task usually copies a **directory tree**
instead, and the failure mode shifts from *purpose mismatch* to *state
mismatch*: some files in the incoming tree are genuinely new to the
target, and others already exist there under a different path, with their
own history.
A wholesale `cp -R` (or equivalent) cannot tell the two apart, so a file
that should have been a pure rename gets silently replaced by the source
repo's own, possibly-diverged copy.

Run the same two-sentence check per file rather than once for the whole
tree: does this path already exist in the target, and if so, is the
source repo's version authoritative for it, or is the target's own
history?
When the file already exists, treat the operation as a **relocation**
--- write the target's own current content (`git show <old-ref>:<old-path>`)
at the new path --- not an import.
Reserve the source repo's copy for files genuinely new to the target.

- **Do:** before bulk-copying a directory tree, check each incoming path
  against the target repo for an existing equivalent.
- **Do:** relocate an existing file with its own content intact; import
  only what's actually new.
- **Don't:** let a directory-level copy operation decide, by omission,
  that the source repo's version of a shared file wins.

## When two variants of one helper exist, the error asymmetry picks between them

The check above asks what the original was for and what the new one is for, and
for most structures that comparison is about behaviour.
For a **guard** helper it is about direction: what such a helper is *for* is
which way its mistakes fall, and two helpers can compute the same thing and
differ only there.

A codebase that has already learned this lesson once tends to carry two
variants of one anchor --- a narrow one enumerating what it accepts, and a
permissive one accepting everything it cannot rule out.
Both are live, both are right for their own consumer, and neither is a stale
copy of the other.
So a new consumer poses a real choice, and "which one is the real one" is not a
question with an answer.

**Reusing the narrow one is the default, and it is a decision nobody notices
making.**
It is usually older, usually named as though it were canonical, and composing
it reads as consistency rather than as picking a failure direction.
[`fail-fast`](../principles/fail-fast.md)'s safe-direction rule already says to
ask which way an unforeseen case falls --- but that rule fires while you are
*designing* a guard's shape, and reusing an existing helper does not feel like
shaping anything.

**A masking decision inverts the asymmetry relative to the matching passes it
feeds.**
A matching pass errs safely by over-matching: a false positive is a spurious
block that a documented override clears.
A pass deciding whether to **skip** text errs safely by over-detecting, which
is the opposite arithmetic --- judging some text worth scanning costs a scan,
while judging it inert deletes the evidence before any matcher runs.
So the narrow variant is the safe reuse in one and the dangerous reuse in the
other, and the two sit in the same file.

Derive the direction rather than recalling it.
Name what a false positive costs this consumer and what a false negative costs
it, one sentence each, and take the variant whose likelier error is the cheaper
one.
Where the helper runs upstream of the thing that would have caught the miss,
the false negative is usually unrecoverable, which settles it.

- **Do:** state what a false positive and a false negative each cost the NEW
  consumer, and choose the variant from that comparison.
- **Do:** treat a helper running upstream of a matcher, deciding what the
  matcher gets to see, as having inverted asymmetry relative to that matcher.
- **Don't:** pick between two live variants by which looks canonical, or by
  which the neighbouring code happens to use.
- **Don't:** read composing an existing helper as exempt from this check ---
  reuse is where the direction gets chosen without being decided.

## The mirror failure: a new check beside a sibling inherits none of its guards

Everything above prices reuse that should not have happened.
The mirror is reuse that should have and did not:
authoring a check, query, or command block **beside an existing sibling**
that does the same kind of job,
and writing the minimal version instead of mining the sibling's guards.

A sibling check encodes the domain's already-discovered failure modes.
Its extra clauses are not style --- each one is a fix somebody already paid
for, frequently with its own verified rationale sitting right next to it.
A minimal parallel check re-opens every one of those holes at once,
and nothing flags it,
because a new block that works on the happy path reads as complete.

The check is mechanical:
**diff the new block against its sibling clause by clause,
and for every guard the sibling carries,
either transfer it or state why it does not apply.**
A guard you cannot explain skipping is one you skipped by not looking.

- **Do:** enumerate the sibling's guards --- its filters, reductions,
  state carve-outs, `set -o pipefail`, self-containment --- and account for
  each in the new block before pushing.
- **Do:** state beside the new block why an inherited-looking guard is
  absent, when it genuinely does not transfer.
- **Don't:** write the minimal parallel check and let review restore parity
  one guard per round.
- **Don't:** read "my new block works" as evidence it is finished --- the
  sibling's guards exist for the inputs the happy path never shows.

(Morrison-Lab/ai-config#1490, 2026-08-15/16: a human-review query was added
beside two siblings --- the Copilot query and the `CHANGES_REQUESTED` check
--- in `pr-status`/`pr-status-all`.
Four of the PR's eight review findings were guards those siblings already
carried, restored one round at a time: the per-reviewer
`group_by(.user.login)` reduction (round 1), the `DISMISSED` carve-out
(round 2), the self-contained `head=` fence (round 3), and
`set -o pipefail` (round 4).
Each sibling guard had its own documented rationale one screen away when the
minimal query was written.)

## Reusing a CLAIM: its truth conditions travel with the question, not the sentence

Every section above reuses a **structure** --- a template, a directory tree, a
guard helper --- and each fails by carrying a shape into a purpose it does not
fit.
A sentence is reusable in the same way and fails differently, because a
structure at least *looks* like something that might not belong, whereas a
true sentence copied verbatim looks like the safest possible move.

The failure is that a claim is only ever an answer to a question, and the
question is the part that does not get copied.
Move the sentence into prose that asks something else and the words are
unchanged while the assertion is not, so the usual reuse check --- does the
mechanism still work --- has nothing to bite on.
Nothing here is a paraphrase error either, which is what makes re-reading the
source useless as a detector: the source is still right about its own subject.

**The threat model is the question that changes most often and is stated
least.**
A claim about identity, provenance, or authorship is answering some implicit
"as against what?", and the answer is usually a *cooperative* world when the
sentence is first written.
Restate it where an adversary is in scope and it silently acquires a stronger
reading, since text that merely distinguishes a friendly case from another
friendly case now reads as resisting a hostile one.

**Two questions decide it, and they are cheap:**

1. **What is this claim ruling out?**
   Name the alternative it distinguishes against.
   A claim that separates A from B says nothing about C, however confidently
   it is phrased.
2. **Does the destination rule out more?**
   Read what the *new* surroundings assert, not what the source did.
   A destination that establishes untrusted input, concurrency, or a second
   actor has widened the question, and the sentence has not kept up.

**Expect the answer to be a demotion rather than a deletion.**
The claim usually survives with its scope named, and frequently one direction
of it survives outright --- a signal too weak to confirm a thing can still be
strong enough to rule it out.
Keep the surviving direction and say which one it is, since "this is weaker
than it looked" is not the same finding as "this is wrong".

Note that the checks the rest of this fragment prescribes all pass here.
No test fails, no mechanism misbehaves, and the two-sentence purpose
comparison is about what an artifact is *for*, which a sentence does not
obviously have.
So this needs its own trigger: **the act of quoting yourself.**

- **Do:** name what a claim rules out, and re-read what the destination rules
  out, before restating the claim there.
- **Do:** demote to the direction that survives, and say which direction that
  is, rather than deleting a claim whose scope merely shrank.
- **Do:** treat a destination that introduces an adversary, a second actor, or
  concurrency as having changed the question, even when the sentence is
  copied verbatim.
- **Don't:** read "the source says exactly this" as clearing a claim --- the
  source is answering its own question, which is the one thing the copy leaves
  behind.
- **Don't:** rely on the structural purpose check above to catch it; a
  sentence has no interface, no tests, and no shape to compare.

(`Morrison-Lab/wai#54`, 2026-08-09, review finding 5.
[`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md) said a
webhook comment ending in the Claude Code attribution footer is
"mechanically, unambiguously your own post" --- sound for its own question,
separating a self-echo from a **human** reply.
Quoted into a chapter that states a threat model, it became false twice over:
the footer is body text anyone who can comment can paste, and it names a
class rather than an instance, so a concurrently-watching PR Steward carries
the identical footer.
The absence of a footer survived both objections and was kept.
The source file was not written with a threat model in view: grepping it at
`7d84365`, this change's own base, for
`untrusted|attacker|adversar|injection` returns zero hits.
That is the point rather than a mitigating detail --- the claim did not
change, and the question around it did.

Anchor that grep to the base ref rather than running it bare, because this
same change edits that file and introduces two of those very words.
A bare present-tense count would therefore have been true when written and
false on merge, which is this section's own subject arriving one artifact
early: the sentence stayed put while the file underneath it moved.)

## In review

Flag a diff that introduces a structure closely mirroring an existing one
where the two serve different purposes, and ask for the purpose
comparison rather than for the mechanism to be re-tested.

Flag a claim quoted or paraphrased out of another document into prose whose
surroundings assert more than the source's did --- an adversary, a second
actor, concurrency --- and ask what the claim rules out rather than whether it
is faithfully reproduced.
Verifying it against its source is the check most likely to be offered here,
and it is the one that cannot fail.
This is the arrival path for the "correct-looking implementation of the
wrong strategy" case in
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s strategic
correctness section: the wrong strategy usually got there by copying a
working neighbour.

Flag a "port/adapt from repo Y" diff that replaces an existing file's
content with Y's version and calls it a move --- check whether the diff
is a pure rename (no hunks) or carries an unexplained content change
riding along with it.

Flag a new consumer composing one of two live variants of the same guard
helper with no statement of why that variant, and ask for the two-sentence
cost comparison rather than for the composition to be re-tested --- the
mechanism works either way, which is exactly why it passes review.

(Corrected 2026-07-30: "cai: never take shortcuts, never copy-paste or
pattern match blindly; always think twice and critically about what you
are doing and how it might be wrong."
A `Stop` hook that blocks a message had just been written and verified.
Minutes later, asked to make a different rule mechanical, the session
reused that shape and swapped the regex --- producing a hook that would
have blocked *error admissions*.
The existing hooks block messages that are wrong to send; an error
admission is right to send, so the copy inverted the purpose while
remaining structurally valid at every step, with passing tests.
An earlier instance of the same failure is already recorded narrowly in
`memories/r-quarto.md`: a `.jarlignore` invented by analogy to other
tools' ignore-file conventions, structurally plausible and silently
inert, because nobody checked that tool's own config reference.)

(Caught by review, 2026-08-07: `UCD-SERG/serocalculator#639` ported a set
of Quarto extensions from `Morrison-Lab/rpt`.
One of them, `slidebreak`, already existed in the target repo at a
different path.
A wholesale `cp -R` of rpt's whole extension tree overwrote it with
rpt's own, trivially-diverged copy --- an `author:` field changed and
two blank lines picked up trailing whitespace, neither mentioned in the
PR description or commit message.
The `@claude` review caught both as "unexplained side effects of a
rename"; the fix was `git show <old-ref>:<old-path>` at the new path
instead of the source repo's copy.)

(`Morrison-Lab/ai-config#1287`, 2026-08-08, rounds 5 and 6:
`hooks/no-unauthorized-merge.py` carries two command-position anchors by
design.
`LEAD` enumerates what may precede a command word; `PERMISSIVE_LEAD` treats
every position as a command position and instead blanks text that provably
cannot execute, and the file's own comment states why --- "enumerating what may
precede a command word cannot be finished".
Round 4's fix composed `LEAD` into `HEREDOC_EXECUTOR`, which reads as the
correct move and is the one the previous round's finding asked for.
But `HEREDOC_EXECUTOR` decides whether `mask_heredocs` blanks a heredoc body as
inert prose, and it runs at step 2 of `offending()`, before either matching pass
sees the text.
Round 5's review states the asymmetry directly: "getting it wrong doesn't just
miss a match in one pass, it destroys the evidence before either pass runs",
and demonstrated `f() { bash <<EOF ... EOF; }; f` and a `case`-arm equivalent
allowing at the PR head while `main` blocked both.
Round 6 then found the same variant choice costing the guard again, over a
wider class and a second path: `KEYWORD_PREFIX`'s closed enumeration misses any
unenumerated wrapper (`timeout`, `nice`, `setsid`, `xargs`, `builtin`) and any
flag after an enumerated one (`sudo -u user`, `sudo -E`), for both the heredoc
path and the executor's quoted operand (`bash -c "..."`, `eval "..."`), with a
14-row table showing every one allowing at the head and blocking on `main`.
Both rounds trace to composing the narrow variant into a consumer whose false
negative is unrecoverable, and neither is a defect in `LEAD` itself.
Round 5's suggested direction is this rule's remedy stated as a design change:
"invert the default the way pass 2 already did --- treat a heredoc as executing
unless its introducing line is provably fed to a non-executing consumer".)

## Repointing a configured path at a different artifact is reuse, and the accessor's own docs say what it is for

Everything above concerns reusing a **structure** --- a template, a script, a
neighbouring file's shape.
The same failure arrives through **data**, and there it wears the clothes of
debugging rather than of authorship.

An artifact the code expects is missing.
A configured path --- an environment variable, a config key, a CLI flag ---
lets you point the code somewhere else, and another artifact on disk has a
compatible shape.
Setting the variable to that other artifact makes the code run.

Nothing about that sequence resembles reuse, which is why the check above does
not fire on it.
You wrote no code, adapted no template, and copied nothing.
You supplied a value that the software's own interface invited you to supply,
and it worked.

But the value is doing exactly what a reused template does: standing in for
something on the strength of fitting mechanically.
And the accessor almost always states its purpose in its own documentation,
which is the one thing a substitution made in a hurry does not read.
The tell is that the code is now running, so nothing prompts the question.

State the general form plainly, because it is the reusable half.
**A substitution that makes the code run is not evidence the substitution is
correct.**
Running is what the false positive and the true positive have in common; only
the docs of the thing you repointed separate them.

- **Do:** read the accessor's own documentation before pointing its path
  variable at a different artifact, and say what that accessor is for.
- **Do:** treat a missing artifact as a question about how to produce it, not
  as a question about what else has a compatible shape.
- **Don't:** read "the pipeline now runs" as evidence the substituted artifact
  is the right one.
- **Don't:** leave such an override in place undocumented; a value chosen to
  unblock one run reads to the next reader as the configuration.

This one is **not mechanizable**, and it is worth saying why rather than
leaving it as an omission.
The two checks in this PR's siblings are lexical --- a literal that left a
changed line and stayed in a comment, a list member with no matching probe ---
so a script can decide each from the diff with no understanding of what the
values mean.
Here the condition is whether artifact B satisfies the contract accessor A
documents, which is a semantic comparison between prose and a dataset.
Nothing in the diff distinguishes a correct override from a wrong one; both are
one line setting one variable to a real path that exists.
Per [`learn-from-review-findings`](learn-from-review-findings.md), saying
plainly that a finding has no mechanism behind it discharges the lesson as
completely as building one does, and inventing a guard here would produce the
misfiring check [`algorithmatize-checks`](algorithmatize-checks.md) warns
against.

(`ucdavis/bcs#679`, 2026-08-20: `AB507BS_PARQUET_PATH` was set to the
all8sites cohort dataset to get past a missing file.
The accessor's own roxygen says the path is "a derived cache of the AB507BS raw
RDS, not a second copy of the all8sites cohort" --- a sentence written to
forbid exactly the substitution that was made.
It was never read.)
