# Rationale: the ARDI loop

The mechanism, evidence, and argument behind the rules in
[`ardi.md`](ardi.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

**Continuously monitor every PR/MR you are actively working until it reaches
that terminal state.**
At every periodic check-in, and again after any push or
base-branch advance, query the current head for all three surfaces: mergeability
(including conflicts), every CI workflow/check run, and both formal reviews and
top-level/inline review comments. A conflict, CI failure, or newly posted
finding is ARDI work immediately --- sync and resolve the conflict, investigate
and fix or track the CI failure, or disposition the finding --- not merely a
status item to hand back to the user.
Keep polling while a review or check is
in progress; do not call the PR clean from an earlier head or from green CI
without a current-head review verdict.
Pushing fixes for a finding-bearing review starts a new review cycle: the ARDI loop is NOT finished when you push fixes or post an ARD summary.
You must wait for the fresh review run evaluating your latest pushed commit to post, fetch and parse that review, and confirm it is clean before declaring the loop finished.

**That wait is conditional on a run having been scheduled, and on some repos a push schedules nothing.**
A review workflow whose `on:` block carries no push-based trigger --- `workflow_dispatch` and `issue_comment` only, which is how a repo disables automatic review on PR activity --- fires nothing when you push, so the run you are told to wait for will never exist and the poll cannot terminate.
The obligation is then discharged by **dispatching**, not by waiting, and it recurs on **every round** rather than once at PR-open time: `gh workflow run <review-workflow>.yml -R <owner>/<repo> --ref <PR-branch> -f pr_number=<N>`, taking the input's name from that workflow's own file.
Pass `--ref` rather than omitting it, for the reason the block below gives, and dispatch once per round rather than once per push.
Read the `on:` block once per repo, the first time you push to a PR there, and record which class it is.
This is the shape most likely to be missed while everything looks healthy, because CI still goes green on each push, and watching CI to green feels like watching the PR --- so the loop closes on "checks passed" while the last verdict on file dates from an earlier head.
`check-pr-fully-clean.py` returning non-zero for "no review at this HEAD SHA" on such a repo means *dispatch now*, not *poll longer*.
[`pr-on-claim`](pr-on-claim.md) covers the PR-open and draft-to-ready end of this.
The increment here is that each subsequent push owes its own dispatch.

**Dispatch once, after the round's LAST push --- a per-push rhythm cancels its own reviews.**
The paragraph above is right that a push on such a repo owes a dispatch, and the obvious reading of it produces a loop that reviews nothing:

```text
push -> dispatch -> push -> dispatch   # the second dispatch kills the first
```

[`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s "A `cancelled` review is the one case where retrying is the cause rather than the remedy" supplies the half that turns the advice against itself: the reusable review workflow carries a job-level `concurrency` group keyed on the PR number with `cancel-in-progress: true`, so a second dispatch for the same PR kills whatever is running.

The two rules are not redundant, and neither names the conflict.
That fragment governs the **retry** you make after noticing a cancellation, which is reactive and fires once you already have a symptom.
This governs the **rhythm** that manufactures the symptom, which fires on every ordinary round with nothing yet to notice.
Read literally and together, "dispatch after every push" and "a dispatch cancels the run in flight" are self-defeating, so the ordering has to be stated rather than derived.

So batch the round's commits, per [`efficient-pr-babysitting`](efficient-pr-babysitting.md), and treat the dispatch as a separate action that comes **last**.
A dispatch is not free to repeat.

**Dispatch with `--ref <PR-branch>`, or the resulting failure is invisible on the PR.**
A `workflow_dispatch` run invoked without `--ref` runs against the default branch, so its `head_sha` is that branch's tip and every check run it produces attaches there rather than to the PR head.
A cancelled review then fails its own review gate on a commit the PR does not display, and the PR reads `mergeable_state: clean` with nothing pending while its gate is red one surface over.
Both instruments [`fully-clean`](fully-clean.md) prescribes miss it: a check-runs query answers for the PR's head SHA, and a comment scan finds nothing because a cancelled run posts no comment --- so "no findings" and "no verdict" present identically, which that file already warns about in the abstract.

The remedy is not new, and its **incomplete application** is the part worth recording.
[`review-verdict-pitfalls`](review-verdict-pitfalls.md) already establishes that `--ref` decides this and reports the corpus's manual dispatch commands fixed.
That fix reached the **recovery** command, run after you notice a cancellation, and not the **routine** command above, run every round --- so the flag was present on the path taken rarely and absent on the path taken always.
This is [`fail-fast`](../principles/fail-fast.md)'s partial guard exactly: a reader who finds `--ref` on the recovery command reasonably concludes the hazard is handled.

**The same gate does not pause the loop *within* a single PR either, and that
is the harder half to see.**
The paragraph above says the merge gate does not stop you moving to the *next*
PR.
This says it does not stop you working *this* one.
An authorization gate attaches to a specific **action** --- the merge, a
force-push, a destructive one-off --- never to the PR as a whole.
Everything else the loop already mandates stays pre-authorized on that PR:
syncing with `main`, resolving a conflict, pushing a fix, re-dispatching a
review, resolving threads, reporting the result.
`CLAUDE.md`'s "Watch and ARDI every PR you touch --- don't ask first" states
the standing yes; this names the boundary it stops at.

Conflict resolution in particular is not merely permitted but **owed**, per the
continuous-monitoring paragraph at the top of this fragment: a conflict "is ARDI
work immediately --- sync and resolve the conflict ... not merely a status item
to hand back to the user".
Handing it back is the named anti-pattern rather than a cautious reading of the
merge gate.

What makes this hard to catch from the inside is that it is not laziness or
evasion.
The gate being over-applied is a **real** gate, correctly identified, and
usually one you have already invoked several times on that same PR for the
action it genuinely covers.
Having rightly refused to merge, refusing to touch it at all reads as
consistency rather than as a second and different refusal.
So the lesson is not "be more proactive" --- diligence was never the missing
input.
It is that a gate has a scope, and the scope is the action.

**The tell is lexical, and it sits in your own outgoing message: a
RECOMMENDATION or question whose proposed action is ordinary ARDI work.**
If the sentence you are about to write asks permission to do something the loop
already requires, that is the error.
Do it, and report in the past tense.

This bites hardest on a PR that **cannot** reach a clean verdict --- no external
reviewer will answer at any head, so nothing about it feels routine and the
whole PR starts to read as gated.
Drive it to whatever state it *can* reach: merged with current `main`, green on
every check that runs, threads resolved, self-review posted.
Then report it as blocked on the specific thing it is actually blocked on,
rather than leaving it dirty because the terminal step is unavailable.

**Self-review against the project's own stated conventions before every
push, not just the first --- and don't just re-read the criteria, actually
run the applicable review skills against your own diff and iterate on
what they find, the same ARD cycle you'd run against an external
reviewer's findings.** Don't treat the review bot as the mechanism that
discovers a project's documented conventions --- self-apply them first.
When a project's own `CLAUDE.md` (or equivalent agent doc) already states
specific criteria --- a DRY/no-duplication rule, a doc-sync checklist for a
new input, a changelog-category rule, a citation requirement, a "new logic
needs test coverage" norm, a prose-quality check like `fact-check-prose`,
`fix-forward-references`, or `detect-informal-definitions` --- a first-pass
implementation checked only against feature correctness forces the review
loop to spend a round re-deriving what the project's own docs already
said.
Before every push, brief the reviewer with the project's own stated
review criteria and have it actually invoke the review skills/checks
those name against the diff (not just recall them from memory), the same
way an external reviewer would apply them.
That pass is dispatched to a separate
[`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md)
subagent rather than performed inline, per
[`adversarial-self-review`](adversarial-self-review.md) --- the session
that wrote the diff reads it already knowing what it meant, so its own
pass confirms rather than reviews.
Address every finding that pass surfaces --- fix, rebut, or defer,
exactly like the ARD step above --- before the push goes out; a
self-review that finds issues and pushes anyway has only moved the round
to the external reviewer instead of skipping it.
Repeat until the dispatched pass comes back clean, then push.

## Pre-push checklist

**Pause point: after committing, before `git push`.**
Do-Confirm --- confirm all seven here, in whatever order suits the round, with
one exception: the items that **edit** the diff have to precede the items that
**measure** it.
Regenerating a generated tree and merging `main` change which lines are added,
so an added-lines scan or a deleted-lines read taken before either is an answer
about a diff you no longer have.
The same holds *inside* item 3, which bundles two checks: reflowing a long line
to clear its multi-sentence half retires the very lines its punctuation half
scanned, so satisfying one check expires the other's result
([`semantic-line-breaks`](../writing/semantic-line-breaks.md)).
Per [`skill-checklists`](skill-checklists.md); every item below exists because
the bullets in this fragment record it failing at this exact boundary.

**Review a round's fixes as one diff, not as N independent fixes: two of them,
each correctly addressing its own finding, can compose into a defect neither
introduces alone.**
Every check in this loop is scoped to a single finding.
You read finding A, fix it, satisfy yourself; you read finding B, fix it,
satisfy yourself; and nothing at any point looks at the two together.
So the composition is the one thing in the round that nobody examined, and the
next round's reviewer is no better placed, because it sees a diff rather than
the sequence that produced it.

The shape to watch for is a pair of fixes that touch **the same mechanism from
opposite ends** --- one relaxing a guarantee, the other adding a consumer that
depended on it.
Relaxing a step from fail-hard to best-effort is the classic first half, since
that is the standard remedy for "this shouldn't fail the job".
Making something downstream fire on that step's *precondition* rather than on
its *outcome* is the classic second.
Individually those are both right.
Together, the downstream action runs on a run where the upstream one silently
did nothing.

The tell is free, and it is the commit you are about to write: if its message
needs more than one numbered item, the round changed more than one thing, and
the items are worth reading against each other before pushing.
Ask specifically whether any fix **weakened a property** another fix now relies
on.

**A clean verdict does not certify that your diff contains only what you
meant, because a reviewer cannot tell an accident from a decision.**
Every check above tests whether the diff is *correct*.
None of them tests whether it is what you *intended*, and those come apart
whenever an edit does something extra --- a replacement string that drops
neighbouring lines, a global substitution that rewrites more than the
flagged occurrence, a stray hunk carried in from another branch.

A reviewer reads the diff as a set of deliberate choices, since that is the
only thing a diff can present.
So it does not report the extra change; it *explains* it, and often well ---
constructing a plausible rationale, grading the result appropriate, and
moving on.
That is worse than silence.
Silence leaves the change unexamined, while a reasoned endorsement converts
it into a decision the thread now records as settled, and any later reader
finds an accident with an argument attached.

The tell is reading a review that justifies something you have no memory of
choosing.
Treat that as a prompt to check the diff rather than as confirmation, and
note that the review's argument may be perfectly sound --- the question is
not whether the change is defensible but whether anyone decided it.

Deletions are where this concentrates, because an addition is something you
wrote and a deletion is usually something that got displaced.
`git diff origin/main...HEAD | grep '^-'` lists them in one command, and on
a prose diff the list is normally short enough to read in full.

**When the edit is a regex or string patch rather than the Edit tool, two
mechanisms turn that displacement into a silent over-deletion, and a self-check
can wave both through.**
A non-greedy `.*?` DOTALL span binds to the **first** occurrence of its start
anchor, so when that anchor is not unique the match runs from the wrong site
and swallows every intervening structure up to the target suffix.
And a self-check that counts only the **changed** element passes by
coincidental balance while its neighbours are gone: deleting one sibling append
and adding one target append leaves the target count unmoved, so the count
reports success over a diff that dropped whole intervening blocks.
The assertion that actually catches it verifies that neighbouring structures
**survive** --- the sibling loop still present, untouched element counts
unchanged --- rather than that the changed element's count is as expected.

**A clean verdict does not discharge the self-review against project
conventions either, and the reviewer's own "not a finding" is where that
shows up.**
The section above covers an **accident** a reviewer explains rather than
reports, and its check is reading the diff's deleted lines.
Here that check finds nothing.
The choice is deliberate, nothing was displaced, and the diff contains
exactly what you meant --- it simply violates a rule stated verbatim in the
repo's own `CLAUDE.md`.

A reviewer can notice such a choice, analyse it correctly, and still grade it
acceptable, because it is judging whether the code is defensible rather than
checking it against the project's written rules.
That verdict arrives under a heading like "Observations (non-blocking)" and
closes "Not a finding", which is stronger than the severity labels
[`address-every-comment`](address-every-comment.md) already warns about:
"nit" downgrades an item, while "not a finding" retires it.
So the part of a review most likely to be skimmed is the part a genuine
convention violation is most likely to sit in.

The pre-push self-review this fragment already requires is the only thing
that catches it, and a clean external verdict is exactly what makes that step
feel finished.

**A fix is not "pushed" until it is on the PR's head commit --- verify with a
SHA comparison before telling a reviewer you pushed it.** From inside a
session, an edited working tree and a pushed commit feel identical, so a
round that edits the files, writes the reply, and never runs `git push`
produces a reply asserting a fix that does not exist on the branch. Nothing
contradicts it: CI reports green, because it correctly validated the older
head; the next review round reviews code without the fix; and the session's
own recollection of having made the change agrees with the reply. That makes
it worse than an ordinary wrong claim --- it is a false statement about
*state*, which a reviewer has no reason to doubt and no cheap way to check.
Before posting any reply that asserts a push, compare `git rev-parse HEAD`
against the PR's own `head.sha` (`pull_request_read` `get`); if they differ,
push first, then reply naming the real SHA. Run the same comparison in every
periodic check-in on a PR you are babysitting, since the failure is silent
and survives each round until something explicitly looks for it. This is the
[`algorithmatize-checks`](algorithmatize-checks.md) rule applied to your own
claims: two SHAs decide it exactly, so never substitute recollection.

**A SHA you put in a PR body or a reply must be read, never recalled --- and
the PR body is where an invented one survives longest.**
The bullet above asks whether the right commit reached the branch.
This asks the prior question: whether the commit you named exists at all.
A short SHA is seven plausible hex characters, so writing one from memory feels
like recalling a fact rather than asserting one, and the result is
indistinguishable from a correct citation --- nothing renders differently, and
GitHub neither linkifies nor validates a SHA with no commit behind it.

The PR body is the worst host for it, for the reason
[`address-every-comment`](address-every-comment.md) gives about stale
paraphrases there: the body is in no diff, so no reviewer reads it as part of
the change and no `grep` over the diff finds it.
It is also what a maintainer reads while deciding whether to merge, so an
invented SHA misdirects the one reader most likely to act on it.

One command against the value you are about to paste settles it:

```sh
git rev-parse --verify <sha>^{commit}   # or: git cat-file -e <sha>
```

When a wrong SHA has already been published, correct it **visibly** rather than
overwriting it silently --- a reader who saw the original cannot otherwise tell
a revised body from one that always said this, which is the same reasoning the
withdraw-a-stale-blocker bullet below applies to a retracted caveat.

This is the commit-SHA case of the rule
[`report-mistakes-proactively`](report-mistakes-proactively.md) states for
issue numbers ("never name an issue number before the issue exists").
Same defect, different artifact: an identifier guessable enough to assert
casually, with nothing in the repository to contradict it.

**Knowing the prefix genuinely does not discharge this for the full SHA a
link wants.**
A markdown commit link is composed with the 40-character SHA,
and a 7-character prefix read off real `git log` output moments earlier
supplies only 7 of them ---
so the remaining 33 get invented at link-composition time, silently,
while the read-never-recall check reports itself satisfied
because the prefix genuinely was read.
The result is a link that 404s on a commit that exists.
Expand the prefix instead:
`git rev-parse <short-sha>` (without `--short`) prints the full SHA;
paste its output rather than extending the prefix by hand.

**The same rule governs a merge or squash commit message, which is worse than a
PR body on both counts the bullet above names.**
That bullet calls the PR body the worst host for an invented identifier because
it sits in no diff and is what a maintainer reads while deciding to merge.
A commit message beats it on each.

It is **permanent**.
A PR body stays editable indefinitely, while a message on the default branch
cannot be amended without rewriting shared history, so the correction has to
live somewhere else and a later reader may never meet it.

It is **composed after review ends**, in the same call that merges, so no round
remains in which anyone would catch it.
The PR body at least sits in front of whoever reviews the PR.

**The trigger is a PR with no closing issue, which is why "verify identifiers"
does not reach it.**
`Closes #N` is habitual enough in a repo's merge messages that its **absence**
reads as an omission to fill rather than as a fact to check, so a plausible
number gets typed to complete the shape.
That makes the remedy narrower and more actionable than the general rule: a PR
with no tracking issue should say so, rather than leaving a `Closes` slot that
invites filling, and any closing reference in a merge message should be read out
of the PR body it came from rather than recalled.

**An invented number here can close someone else's live work, because issues and
pull requests share one number space.**
This is the part to check rather than assume, and the intuitive answer is wrong.
GitHub's documentation is explicit that a closing keyword acts on a referenced
**pull request**, not only on an issue:

> If you use a keyword to reference a pull request comment in another pull
> request, the pull requests will be linked.
> Merging the referencing pull request also closes the referenced pull request.

So a merge message whose `Closes #N` names a plausible-but-wrong number is not
merely a false statement in permanent history.
Where that number belongs to an **open** PR, merging closes it, and the damage
lands on an artifact whose author never saw the message.
A wrong number that happens to name an already-merged PR changes no state, but
that is luck about the target rather than a property of the keyword, so it
cannot be the reason the practice is safe.

**A SHA's provenance is the question its source command answers, not merely
that a command produced it.**
The read-never-recalled bullet above governs *recollection* --- seven plausible
hex characters written from memory --- and its remedy, reading the value out of
`git rev-parse` or `git log`, is satisfied by the failure described here.
The SHA was read, out of real command output, seconds before it was pasted.
It answered a different question.
`git stash list` names the commit each stash was taken on, and
`git worktree list`, `git reflog`, `git log <other-branch>`, a CI run's
`head_sha`, and a review comment's caption each do the same for their own
subject.
So a value can be genuine, freshly read, and still not be the branch tip you
are about to call it.

This is harder to catch than recollection, because having just read a real
value feels like having verified one, so the check the bullet above exists to
prompt reports itself already satisfied.
That is the shape
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "Illusions of
knowing have an exact software form" describes for a claim whose supporting
command was narrower than it looked --- read that rather than re-deriving it
here.

Name what you are asserting before pasting: a branch tip, the checkout's own
commit, a merge base, the commit a run checked out.
Then confirm the command you read the value from answers that question, one
query per claim.
`git rev-parse --short origin/main` for a branch tip,
`git rev-parse --short HEAD` for the checkout.

**A verification table you write in the PR body is the same defect one artifact
over, and re-reading it cannot catch a wrong number.**
[`fully-clean`](fully-clean.md)'s "a reviewer's own verification block can be
wrong while its verdict is right" is written entirely about a block arriving
**as evidence** from a reviewer, and points at this fragment's skimmed-audit
bullet as the author-side counterpart.
That bullet governs care-per-item during a batched audit.
It does not govern the commoner author-side case, where each figure was
gathered carefully and the table simply stopped being true.

Two things make the author-side version distinct from the reviewer's, and both
argue for deriving rather than reading.

**It goes stale rather than being wrong on arrival.**
A verification table is written once, early, when the round's evidence is fresh,
and then later rounds change the diff underneath it.
So the failure has no moment of carelessness to catch: the number was right when
typed, and nothing about adding three more test cases feels like invalidating a
paragraph elsewhere.
That makes it a pause-point problem in
[`skill-checklists`](skill-checklists.md)'s sense rather than an arithmetic one,
which is why the remedy is a step at the boundary and not more care at the desk.

**It sits in the PR body, which nothing re-reads.**
[`address-every-comment`](address-every-comment.md) already establishes that the
body is in no diff, so no reviewer reads it as part of the change and no `grep`
over the diff finds it --- the same property that lets an invented SHA survive
in the bullet above.
It is also what a maintainer reads while deciding to merge, so on a PR whose
argument for safety *is* the verification table, a wrong headline number
misdirects exactly the reader the table was written for.

The remedy is not to re-read the table.
Re-reading catches a stale **description**, because a description can be checked
against the code it describes.
It cannot catch a stale **count**, because a wrong count reads exactly as
plausible as the right one.
Derive each figure with a command at push time, and paste the command beside the
figure, per
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md).
That fragment's "a count in the prose above a block" section is the same remedy
for a count whose subject sits one line away and which your own edit falsifies
first; here the distance is the problem rather than the adjacency, and the
subject is a diff between two commits rather than a block in one file.

**A "Corrections to this body" entry is itself a figure in the body, so the
next push expires it too --- and it reads as more settled than the figure it
corrected.**
[`address-every-comment`](address-every-comment.md) is what puts one there.
A body-staleness finding is answered by editing the body **and** recording the
correction inside it, so earlier rounds citing the old numbers stay resolvable,
and a "Corrections to this body" table is one form that does both at once.
Nothing there says what becomes of the entry on the next push, and the entry is
the artifact in the body most likely to be read as exempt.

Three properties make it read that way.
It is *about* staleness, so it presents as the remedy rather than as more of
the material the remedy applies to.
It names the SHA its figures were derived at, which reads as a timestamp
bounding the claim when it is really a claim about a commit the head has since
moved past.
And it asserts the derivation was performed --- "re-derived rather than
adjusted" --- so it vouches for the numbers above it in a way a bare figure
never does.

So this fires on the round *after* the rule was correctly applied, which is
what separates it from an unknown rule or a check run too early.
The item is discharged at one push, the correction is written down, and the
pause point then comes round again at the next push with a durable note
asserting the figures are current.
[`skill-checklists`](skill-checklists.md)'s "however recently you ran it,
whenever anything has been committed or edited since" is the governing bullet;
the increment here is that a correction note is the artifact that most makes
re-running feel unnecessary.

Distinct from
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A correction
inherits its instrument", where the replacement figure is wrong because the
gauge itself was never checked.
Here the gauge was right and the subject moved underneath it.

**The read side of that comparison can lag a push by a few seconds, so test
the two *local* refs against each other before concluding anything failed.**
The rule above is an
[`algorithmatize-checks`](algorithmatize-checks.md) case because two SHAs
decide it exactly.
That holds only as far as both numbers are current, and one of them is fetched
over the network: `gh pr view <N> --json headRefOid` can still report the
**previous** commit immediately after a successful push.

The failure direction is a false alarm rather than a false all-clear, so it is
the safe one --- but the reflexive response to it is wrong twice over.
The rule's own remedy is "if they differ, push first", which is a no-op here,
and treating a healthy branch as broken invites an amend or a force-push that
manufactures the problem the check was watching for.
A check that cries wolf on a clean branch also stops being run, which is the
objection `algorithmatize-checks` raises against any instrument whose
threshold cannot be trusted.

Local refs cannot lag this way, so they settle it:

```sh
git rev-parse HEAD origin/<branch>   # both local reads
```

- Equal --- the push landed, and any disagreement with the PR API is a
  read-side artifact.
  Re-read it, preferably on a different surface, rather than re-pushing.
- Different --- a genuinely unpushed commit, which is the case the rule exists
  for.

Note also that `git push` answering `Everything up-to-date` is itself evidence
the remote branch already carries the commit.

**A brand-new branch can read back at the wrong commit, so the local two-ref
comparison above is not sufficient there.**
That bullet offers `git rev-parse HEAD origin/<branch>` as the pair that
settles the question, on the grounds that local refs cannot lag.
They cannot.
What they can do is agree with a remote ref that reads back at the wrong
commit, and then the pair reports the push as landed.

The failure direction inverts, which is what makes this worth separating.
A read-side lag is a false alarm, correctly called the safe one there.
This is a false all-clear, arriving on the one instrument that rule offers
for deciding the question.

**The gap is in the trigger rather than in the remedy.**
The original SHA comparison does catch this whenever it is run.
Nobody runs it after a `git push -u` that printed `* [new branch]`, set the
upstream, and exited 0, because that is the least suspicious moment in the
round.

`git ls-remote origin <branch>` reads the remote directly rather than through
a tracking ref, so it is the instrument that catches it.
The corrective push is an explicit refspec:
`git push origin HEAD:refs/heads/<branch>`.

**The likeliest explanation is a local one, and it reproduces offline.**
`git push -u origin <branch>` pushes the **branch ref**, not `HEAD`.
So a local branch left behind at `main`'s tip, while `HEAD` carries the new
commit, produces this whole signature with nothing on the server going wrong.

Two things about diagnosing one of these.
The downstream error misdirects, because opening the PR fails with
`No commits between main and <branch>`, which names a base-versus-head
relationship and sends you to check the wrong argument.
And `* [new branch]` here is the ordinary output for a branch that did not
exist before, **not** the deleted-underneath-you signal `CLAUDE.md`'s
"Use the existing PR branch" section describes.
There the line is diagnostic precisely because the branch had already been
pushed to; here it is expected, so the two cases must not be conflated.

The wrong value is the informative part, and it reads at first like noise.
A race or a server fault has no reason to land on `main`'s tip in particular,
whereas a branch ref cut from `main` and never advanced sits there by
construction.
So read a wrong value that happens to equal `main`'s tip as pointing at the
local ref rather than at the network.

**The same false claim arrives as *incoming* state when you pick a PR up
mid-flight, and there the SHA comparison usually has nothing to compare.**
The bullet above governs a claim you are about to make.
Its mirror is the claim already sitting on the PR when you arrive: the latest
comment says which findings are fixed, so starting from it means starting from
a summary rather than from the branch.
The rule is the same either way, and only the *instrument* differs, because a
claim written for a human rarely carries a SHA to check.
"Three fixes landed in two commits" names files, not commits.

So compare the claim against the file list, which decides it in one call:

```bash
gh pr diff <N> --name-only   # DIFF_PR
```

A named file absent from that list was not touched, whatever the comment says.
Nothing else in the PR contradicts a claim like this, and the trap is that
green CI reads as corroboration when it is nothing of the sort.
The checks that would have exercised the claimed fixes are frequently the very
checks those fixes were supposed to add, so their absence is the reason CI is
green.

The right response is to do the work rather than to dwell on the discrepancy.
Say once, in the round's summary, that the earlier claim was not true of the
branch, since a reader who saw it will otherwise assume the round was
redundant.

**Run that same command before *any* readiness claim, not only against an
inherited one --- a PR whose branch carries no implementation is green on
every check.**
The bullet above uses `gh pr diff <N> --name-only` **differentially**: it has
a claim naming files, and it asks whether those files are in the list.
That test needs a claim as input, so when nobody claimed anything it never
runs, and the readiness path is exactly the case where nobody has.
The **existential** question --- does the list have anything in it at all ---
is the one no rule was asking.

[`pr-on-claim`](pr-on-claim.md) manufactures the hazard by design, and is
right to: it opens the PR from `git commit --allow-empty` so the branch has a
diff before any code exists.
Merge `main` in later and the branch carries two commits, a real history, and
no implementation.
Every instrument then works perfectly and certifies nothing, because a check
that finds no fault in an empty diff and a reviewer that raises no finding
against one are both answering a narrower question than the one being asked.

Note which nearby checks *pass* on such a branch, since their passing is what
makes the state feel verified.
`git rev-parse HEAD origin/<branch>` agree, so the pre-push checklist's killer
item is satisfied.
The branch is not behind `main`.
`get_commits` returns two, so a sweep keyed on zero commits does not flag it.
[`fully-clean`](fully-clean.md)'s two criteria are each satisfied **maximally**
by an empty diff, since neither has a term about content.

**When the change affects downstream consumers, validate it against a real
consumer repo before reporting the PR ready --- a package's own test
fixtures are built to exercise its code, not to resemble the packages that
will actually use it.**
Fixtures are minimal by construction and tend to share one shape, so whole
branches of new code can be structurally unreachable from them. A real
consumer brings the input variety fixtures lack, and it is usually one clone
plus one command to check.

This bullet, and the two further down that also turn on fixtures, are all
about **coverage** --- a fixture too thin to reach the code.
[`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) covers the
opposite direction: a fixture that works perfectly, and an inference drawn
from its behaviour back to the real system it stands in for.

Three classes of gap this catches, none of them findable in a fixture:

Do it against a throwaway copy and push nothing to the consumer; the
deliverable is evidence in the PR, not a change there. Record what the run
covered in a PR comment, so a reviewer can see which paths real input
reached.

**Verify a blocker you assert in a PR body or a reply, with the same rigor
you apply to a reviewer's claims --- a stated blocker becomes a premise
other people build on.**
The reviewer-facing checks above all point outward: verify the suggestion,
verify the literal, verify the push landed.
The inward case is easier to miss, because a limit you hit yourself feels
like an observation rather than a claim.
It is still a claim, and writing it into a PR body publishes it as
settled fact: a reviewer reading "the pinned tool is unavailable in this
sandbox" will reason from it, recommend a follow-up around it, and never
re-test it, so one unverified sentence quietly redirects the review.
Before asserting that something is unavailable, blocked, or impossible
here, actually attempt it once --- an install, a fetch, a single command
--- and say what you tried.
A negative result from one incidental symptom (a failed version query, a
single 403) is evidence the thing is not *already set up*, not evidence
it cannot be.
When a blocker you published turns out to be false, correct it where it
was published, not only in the thread that surfaced it.

**Attempting the base form of a command is not attempting its variants ---
a refusal describes the invocation you ran, never the flag you did not try.**
The rule above is discharged by one attempt, which is what makes this the
harder miss: the attempt genuinely happened, so the instinct that rule exists
to trigger has already fired and reported itself satisfied.
What ships anyway is a claim about a *different* command --- the same one plus
a flag --- for which no attempt exists at all.

The error message is what makes that generalization feel safe, because it is
usually phrased about the operation rather than about the invocation.
A refusal reading `cannot be moved or removed` sounds like a statement about
the whole family, and it can even be half-true: that wording really is
unconditional for one of the two operations it names.
A half-true message is worse than a plainly wrong one, since re-reading it
confirms the reading you already had.

So before writing that something is impossible, check whether the tool's own
`--help` or documentation offers a flag for exactly this case, and run that
form too.
One `--force` is cheaper than the correction round, and it is the only thing
that turns "the command refused" into "the operation cannot be done".

**Name the specific gate when you report a blocker, not a category word that
happens to be one of several.**
The verify-a-blocker rule two sections above governs *whether* something is
blocked, and its remedy is to attempt the thing once.
This governs *why*, and it fires after that remedy has already succeeded: the
call was attempted, it genuinely failed, and the blocker is real.
Only the attribution is wrong, which is why nothing about it feels like an
unverified claim -- the part that usually goes unchecked has, this time, been
checked.

The hazard is a platform with two gates whose refusals read alike.
`resolve_review_thread` on a transferred repo fails under either spelling of
the owner, saying `Access denied` both times, for unrelated reasons: the old
owner trips a comparison between the thread's node and the declared
`owner`/`repo` string, and the new owner trips the session's own repository
allowlist.
Only the second of those is scope.
So "blocked for scope reasons" is not a loose summary of the first.
It names a mechanism that was not involved, and it names one that genuinely
exists on that platform, which is what lets it survive re-reading.

That last point is the whole cost.
A category word that is also the proper name of one mechanism cannot double as
the generic term for its family, because a reader cannot tell which you meant,
and the wrong reading is actionable: someone told a call failed on scope will
reach for the other owner, which fails too.
Quote the error's distinguishing clause instead of classifying it.
The quote is usually shorter than the paraphrase, it is checkable, and it
stays correct even when your model of the platform is not.

**When the blocker is a hang, inspect the process rather than re-guessing
what it is waiting on.**
The bullet above governs a real failure whose gate was misnamed from an error
message, so there is at least a message to re-read.
A hang gives you nothing to quote and nothing to classify, and that vacuum
gets filled by a guess about mechanism.
The guess then arrives feeling like a measurement, because something really
was run and something really did block.

"It needs a TTY" and "it hangs when run non-interactively" are both category
words in the sense the bullet above means.
Each names a plausible mechanism, neither was observed, and a reader cannot
tell which one you checked.
Replacing the first with the second after a probe returns nothing feels like
progress, and moves you no closer to a gate you can name.

A blocked process answers the question directly, and the reads are cheap:

```bash
ps -o pid=,stat= -p <pid>        # S: alive and blocked, rather than spinning or gone
lsof -p <pid> -a -d 0            # what fd 0 actually is: tty, pipe, or socket
ps -o ppid=,command= -p <pid>    # what launched it, and with what arguments
```

Those turn "it hangs" into a specific, checkable fact about *what* it is
waiting on, which is the gate the bullet above asks you to name.
They also separate two states that no amount of re-running distinguishes: a
capability check refusing at startup, and a read reached only late in the
flow after the interactive step succeeded.
Those call for opposite responses, so guessing between them is not a
harmless imprecision.

Do not reach for the probe first, either.
The probe that produces the hang is itself a live command with its own first
instant, and running an interactive one to see what it does is the failure
[`growth-mindset`](growth-mindset.md)'s "A timeout bounds how long you wait"
section covers.

**A blocker that was true when you published it can stop being true while
the PR is open, and withdrawing it is your job, not the reviewer's.**
The verify-a-blocker bullet above covers a blocker that was never true, and
the "Name the specific gate" bullet covers a real blocker whose
mechanism was misnamed.
This is the harder case, because the caveat was correct and diligent when
written, so nothing about it reads as a defect later --- and a sentence
saying "this could not be checked" is one nobody re-checks, least of all
the reviewer, who has no way to know the environment moved.
It keeps steering the review regardless: a verdict can repeat the caveat
back as an accepted limitation, which makes the stale claim look
corroborated.
So when the cause of a blocker changes --- a host unblocked, a tool
installed, a quota reset, a dependency published --- re-run the check and
withdraw the caveat where it was published, saying explicitly that it is
withdrawn rather than quietly deleting the sentence.
A reader who saw the original needs to know it was retested, not be left
wondering whether it was ever true.

A `main` merge is one moment that must fire this check, because it can falsify
one of your own hedges without producing a conflict in the file that carries it.
After merging `main`, run a whitespace-normalizing search over the PR's touched
files for hedge forms such as `still open`, `not yet merged`,
`once that merges`, `as of`, `will live at`, and `proposed in`.
Do not use line-oriented literal grep in this semantic-line-break corpus: a
phrase split across lines is exactly the case this check must still find.
Re-check each hit against the new base before pushing the merge.
The conflict marker is not the scope of the review: a cleanly merged file can be
where the stale caveat lives.

**Landing a fix falsifies whatever prose documented the defect, and that prose
is never in your diff --- so grep for it rather than expecting to be reminded.**
The blocker-withdrawal rule above, illustrated by ai-config#774, covers a
caveat **you** published on **this** PR, which the environment then moved out
from under.
This is the case where you moved it yourself, and where the stale text lives in
the standing corpus rather than on the PR: a memory bullet describing the
hazard, a README warning about it, a docstring asserting the behaviour you just
changed.

The sync rules in
[`address-every-comment`](address-every-comment.md) all end at the PR's own
artifacts --- the changelog, the PR body, a skill's inline restatement --- and
each prescribes grepping the diff.
Documentation of a defect cannot be found that way, because not being in the
diff is the entire property that makes it survive.
So the trigger has to be the fix itself, and the search has to leave the files
you edited.

Two shapes, and the second is worse because it was never true.

**An instruction's own suggested code is not exempt from the
project-conventions self-review above.**
The self-review rule assumes you wrote the diff; a snippet handed to you
in an issue, a task description, or a design doc slips past it, because
adopting someone else's suggestion does not feel like authoring.
It is authoring --- once pushed, it is your diff, and the project's
conventions bind it exactly as they bind anything you wrote yourself.
Run the same convention check over borrowed code before pushing it,
especially when the suggestion is a plausible-looking one-liner and the
convention it breaks is documented rather than linted.

**When the code path under test has a staging or transform step between
input and output, a passing unit suite is not evidence it works ---
exercise the real path once.**
Fixtures instantiate the shape the test author had in mind, so a wrong
assumption about *where* the code runs is invisible to every one of them:
the tests and the bug share the assumption.
This is the same gap the downstream-consumer rule above covers, one level
in --- there the missing variety is the consumer's input, here it is the
pipeline's own directory layout, timing, or intermediate representation.
One real invocation is usually cheap, and it tests the assumption the
fixtures encode rather than re-confirming it.

**When new code branches on a third-party tool's behavior, read that tool's
own config or docs for the specific behavior --- don't infer it from what
the tool broadly does.**
The bullet above covers your own pipeline's layout; this one covers the
tools that pipeline drives.
An inference of the form "it builds HTML, so link to `.html`" is exactly
the shape that feels too obvious to check, and a tool's defaults routinely
contradict it.
Two properties make this worse than an ordinary wrong guess.
The inference usually lands in a branch your own fixtures cannot reach ---
you have no fixture for someone else's renderer --- so the test suite
agrees with you.
And it produces output that is well-formed and plausible (a link, a path, a
flag), so a reviewer skimming the diff has nothing to catch, and the
failure surfaces only in a consumer's published site.
Name the setting you are relying on, and check its actual default before
writing the branch.

**A regression test written alongside a fix can lock the bug in rather than
catch it --- assert the two paths that diverge, not the one you just
touched.**
A test authored in the same pass as the code tends to record what the code
*does*, because you run it, see it pass, and move on.
That is usually harmless.
It becomes a lock when the fixture is thin enough that the buggy and the
correct path produce the *same* output: the assertion then encodes the
degraded result as intent, and every later reviewer reads a green suite as
evidence the behavior was chosen.
The next round's finding lands on your test, not just your code.

The tell is the same each time: **a fixture missing the input variety that
makes the two paths differ.**
So when a bug is an asymmetry --- nested versus top-level, second render
versus first, one generator versus another --- build the fixture so both
sides are present and assert them together.
Either side alone is unfalsifiable, since the case that reveals the bug is
the *comparison*.
Then prove it: revert the fix and confirm the new test actually fails.
A regression test never seen to fail is a guess about what it covers.

**A systematic audit done by skimming is worse than the one-at-a-time
version it replaces.**
Batching a check --- "rather than wait for the next round to find divergence
number four, compare all four at once" --- is the right instinct, and it
inverts if each lookup gets less care than it would have alone.
Two things make the batched form more dangerous, not less.
Its output is usually a claim recorded somewhere durable (a comment, a
doc, a table), so an error is published rather than merely held; and it
arrives labelled *audited*, which is precisely the word that stops the next
reader from checking.
A wrong comment in a block written to prevent a specific future change
invites that change while appearing to forbid it.
Concretely: when the thing being audited is a function, grep for the
function, not for a pattern in its file --- a file with several functions
will hand you the first match, which is often not the one you mean.
Name the function in whatever you write down, so the claim stays checkable.

**Adding an explanation supersedes whatever the file already said about the
same thing, so re-read the older passage --- your own diff is the likeliest
source of a contradiction nobody flags.**
The sync rules in
[`address-every-comment`](address-every-comment.md) all fire on an external
trigger: a reviewer quotes a phrase, or behavior changes and a changelog goes
stale.
This one has no trigger at all.
You add a paragraph explaining that something was misunderstood, and the note
recording the original misunderstanding sits a few lines below, still stating
it as fact.
Nothing conflicts, no check fires, and both passages read plausibly on their
own --- but a reader who reaches the older one first comes away with exactly
the belief the new text was written to remove.

The tell is a diff that adds an explanation, a correction, or a "what this
actually means" paragraph near existing prose.
Re-read the surrounding passage as a whole rather than diffing your addition
in isolation, and treat a historical record ("we observed N of X") as a claim
your explanation may have just falsified.
When the older passage recorded a *different* session's observation, correct
it with reasoning that stands on its own rather than restating it as though
you had seen it --- an inference presented as an observation is the same
defect one level up.

**The same rule applies within a single diff, and there nothing prompts the
check at all.**
The version above compares your addition against the *existing* file, so
re-reading the surrounding passage catches it.
The harder case is a diff that both adds an explanation arguing against some
older wording **and** rewrites that wording, in the same changeset.
Then the argument survives while its target does not, and every file still
reads plausibly on its own: the new prose is coherent, the rewritten passage
is coherent, and only the cross-reference between them is stale.
There is no older text to go back and re-read, which is the cue the other
version relies on.

So when a diff rewrites a passage, grep the rest of the diff for references to
what that passage used to say, not just for references to the file.
A rebuttal of the form "the section below already says X" is the shape to
watch, since it pins the argument to wording the same commit may be deleting.
Prefer stating the anti-pattern directly over citing another section as the
thing being argued against; a self-contained sentence cannot go stale when its
neighbour changes.

**And when the explanation you add is a *mechanism* claim, test the class it
distinguishes, not just the sample in front of you.**
The bullet above is about contradicting old text; this is about the new text
being unfalsifiable on the evidence you gathered.
A classifier validated on a population containing no positive instance of the
class it is supposed to catch will report a clean result either way, so
"it returned zero" is not evidence it works --- it is the same
missing-input-variety tell the regression-test bullet above describes, moved
from a fixture to a diagnostic.
Ask what a true positive would look like, confirm one exists in what you
tested, and if none does, say so instead of claiming the mechanism separates
the cases.

**A symptom that stops reproducing is a fix having landed, until you have
checked otherwise --- reaching for nondeterminism is the attractive wrong
answer.**
The bullet above governs a mechanism claim you write into a file.
The same defect arrives in a status report, and there it is easier to
publish, because "the check is just flaky" sounds like a complete
explanation while resting on nothing.
It is also unfalsifiable from a single observation and predicts nothing,
which is exactly why it feels safe to say.

The shape to watch for: a known-failing check, a tracked false positive, or
a reproducible bug goes quiet, and you explain the silence with a property
of the *tool* rather than a change in the *world*.

Check for the merge first, because the instrument is a timestamp comparison
and it costs one API call.
Compare when a candidate fix merged against when each observation was made.
That turns "it seems flaky" into a before/after table with a negative
control --- a far stronger claim than the one you were about to make, and
one a reader can act on.

**Verify a command, path, or flag *you* write into a doc, with the same rigor
[`address-every-comment`](address-every-comment.md) demands for one a reviewer
suggests.**
That rule and the verify-a-blocker rule above both point outward, at a claim
someone else made or at a limit you hit.
This is the one you author from scratch, and it is easier to miss than either,
because inventing a plausible command does not feel like making a claim at
all --- it feels like remembering one.

The shape is a CLI invocation, a file path, or a flag written into
documentation, a comment, or a registry, where the surrounding prose is
carefully sourced and the literal is not.
A reader reaching for it gets `unknown command`, and they get it while
following a document whose every other sentence checked out, so they are
likelier to doubt their own setup than the doc.

Settle it against the tool's own source or `--help` rather than recollection.
For a CLI, the subcommand registration list is definitive and usually one
fetch away, and it beats a docs page because it cannot lag the release you
are describing.
Quote what you checked in the commit message, so the next reader inherits the
evidence instead of the assertion.

**Run that check over your own fix, too --- the remedy for an unverified
literal is where the next unverified literal goes.**
The rule above fires when you notice you are writing a literal.
Answering a finding does not feel like that: it feels like careful work, and
the care is real, so the fix inherits an assumption of rigor from the
diligence of writing it.
The specific rule you are in the middle of applying is therefore the one
least likely to be applied to its own application.

A correction also tends to *add* literals rather than merely repair one.
Citing a source properly means naming the tool, the flag, the version, the
file --- each an assertion, each as guessable as the one under review, and
none of them the thing the finding was about.
So the fix can carry more unverified surface than the original did.

Nothing external catches this.
The reviewer sees a fix that addresses the finding and confirms it, per the
clean-verdict entry above, and the thread then records the item as settled
twice over.

**The same rule reaches past a literal, to the defect CLASS a code fix just
closed.**
The block above governs a correction to prose, where the artifact is a citation
and the risk is one more guessable literal.
A fix to code carries the same exposure at a larger unit: the change that
closes an instance of a defect class is itself new code, so it can instantiate
that class again, one layer down, in the very edit that removes it.

Nothing about writing the fix surfaces this.
The finding names a site, the fix closes that site, and the diff reads as a
strict improvement, so the question "does what I just wrote have the property I
just removed" is never posed.
The next round then reports the original class at a new address, and it reads
as a fresh gap rather than as the previous fix's own residue.

**A consolidation commit is the highest-risk host for it, and the likeliest to
be trusted.**
Merging several drifted copies of a concept into one shared definition is a
textbook DRY repair, and it makes the commit *feel* like the opposite of
forking.
That feeling is what carries a newly hand-rolled helper past your own review: a
second concept can be duplicated in the same edit, and the de-duplication of
the first supplies the whole commit's framing.
Consolidating one duplicated concept is no protection against forking a
different one beside it.

So after fixing an instance of a class, ask what the fix **added**, not only
what it removed, and check the addition against the class.
For a new helper the mechanical form is cheap: whatever shared definition the
neighbouring code already composes for the same job, compose that instead of
writing a fresh equivalent, so the new site inherits every property the old
sites have and whatever they gain next.

**When regenerating a generated tree makes it most of the diff, say so in the
PR body --- otherwise a reviewer reads it as pollution and blocks.**
Two failures share one root here, and both cost a round.

The first is editing the generated file rather than its source.
A generated file usually declares itself in a header, and that header is the
last thing you read when you have already found the line you wanted to
change; the generator then reverts the edit and the sync check fails.
Grep for `generated by` before editing any file you did not create.

The second is what happens once you regenerate correctly.
A one-line source change can rewrite hundreds of files, and a reviewer
working from a truncated diff sees only the generated bulk --- so the finding
comes back as "revert the unintended changes", where complying would break
the very check that demanded them.
Say so in the PR body, which is what a reviewer reads before the diff: lead
with the ratio and a per-path table marking each path generated or
hand-written.

**Do not read that as a fix the cited case establishes, and note that the
obvious wrong reading is the opposite of the true one.**
The reasoning is sound for a human, who does read the body.
For an automated reviewer working from a truncated diff it is a guess, and
the case cannot settle it, because the body rewrite did not land alone.

The timestamps are what decide this, and they were misread once already ---
[#837](https://github.com/Morrison-Lab/ai-config/issues/837) filed this entry
as an overclaim on the grounds that the mitigation was in place for a block
that followed it, which the record does not show.
On #834 both blocks precede the rewrite: `01:33:07Z`, then `01:35:23Z`
carrying the truncated-diff note, with the rewrite announced at `01:37:01Z`.
The next verdict after it was `approve`, at `01:50:49Z`.

So the evidence runs mildly *for* the mitigation and still cannot isolate it.
The approving review began at `01:46:19Z`, twelve seconds after `9f0d7a1`
changed content, so a body rewrite and a content change both sit between the
last block and the approve.
One case with two candidate causes decides nothing either way.

- **Do:** write the note, for the human reviewer, where the reasoning holds.
- **Do:** expect to still need the rebuttal-and-hold path from
  [`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s seventh case,
  since nothing here shows an automated reviewer reading the body at all.
- **Don't:** claim the body is the *only* thing that can pre-empt this, or
  that the note is what cleared the block --- neither survives the timeline.
- **Don't:** reach for the intervening commits as the explanation either;
  that is the nondeterminism error this file's "A symptom that stops
  reproducing is a fix having landed" section describes, with the sign
  flipped.

**Run the whole test suite before pushing, not the files you predict the
change touches --- and check that the ones you ran were not silently
skipped.**
The pre-push self-review above assumes your local green means something.
Two things quietly hollow it out, and they compound: you choose a subset,
and the subset then reports success without having run.

The subset is chosen by predicting blast radius, which is exactly the
judgement the change calls into question.
The tests that break are frequently *not* in the files you edited: a test
elsewhere asserts the behaviour you are changing, often with a comment
stating the rationale your diff invalidates.
Nothing about editing `R/foo.R` suggests opening `test-bar.R`, so the
prediction feels complete while omitting the one file that matters.

The second is worse, because it looks like evidence.
A conditional skip --- `skip_on_cran()` without `NOT_CRAN=true`,
`skip_if(!.venv_exists())`, `skip_if_offline()` --- turns the test that
would have caught the bug into a pass.
`devtools::test()` sets `NOT_CRAN` for you --- it applies
`withr::local_envvar(r_env_vars())`, and devtools documents that set as
"the standard environment variables set by devtools", singling out
`NOT_CRAN` as "of particular note for package tests"
([`R/test.R`](https://github.com/r-lib/devtools/blob/main/R/test.R),
[`R/check.R`](https://github.com/r-lib/devtools/blob/main/R/check.R)).
`testthat::test_file()` and `testthat::test_dir()` do not, so the harness
you reach for by hand for a quick targeted run is exactly the one that
skips.
Setting it explicitly anyway (`NOT_CRAN=true Rscript -e '...'`) costs
nothing and is what the rest of this corpus does.
So read the **skip count**, not just the failure count: a run reporting
`0 failed, 20 skipped` has told you almost nothing, and is indistinguishable
at a glance from one that verified everything.

Match the environment the change will be judged in, too.
Running with an env var set that CI does not set (or vice versa) reproduces
a *different* configuration, and its failures and passes both mislead.

**Matching the tool's VERSION is not matching its ENVIRONMENT, and when the
tool GENERATES a file you are about to commit, the gap ships.**
The paragraph above is about running a suite: a mismatched configuration
misleads you about a verdict, and the cost is a wrong belief.
A code generator run under a mismatched configuration writes a **different
artifact**, and you commit it -- so the cost is a wrong file in the tree,
carrying the authority of having been machine-generated.

What makes it slip past is that the obvious precaution succeeds.
Installing the exact version CI installs feels like reproducing CI, and it
reproduces the half everyone thinks of.
A generator's output also depends on what it can **resolve** while it runs:
optional dependencies, plugins, a locale, a package it loads to read
docstrings out of.
Miss one of those and the tool usually does not **fail** --- it emits a
degraded version of whatever it could not resolve, which is exactly the output
that looks plausible.

**Read the generator's own diagnostics first**, because a good one says so
outright and names the cause.
roxygen2 is the worked case and it warns loudly:
`@inheritDotParams failed because testthat is not installed`, plus a line per
tag that referenced the missing package.
That is the earliest and most specific signal available, and it is free.

**The file list is the backstop**, for a generator that degrades with no
diagnostic, or one whose diagnostics scroll past in a long run.
A generator run in a thinner environment usually touches a superset of what CI
touches, since the extra file is the one it degraded.
So compare the file *list* against the failing job's own log, and treat a file
CI did not name as evidence about your environment rather than about the repo.

Both are worth having, because they fail in different ways: a warning can be
lost in noise or absent entirely, and a file-list comparison needs CI to have
reported a list in the first place.

**Running a script is not running its tests, and an "advisory" check can have a
hard-gating twin.**
The bullets above assume you reached for the test suite and took too little of
it.
The nearer miss is reaching for the **production script** instead: you touch
something a checker measures, run that checker, read its exit code, and treat
that as having verified the property.
It feels like stronger evidence than a test, since it is the real instrument on
the real data.

It answers a different question.
A script **reports**; a job **gates**, and the gate is frequently a separate
step asserting the same property about the repo itself.
The two can disagree by design --- one deliberately advisory, its twin
deliberately blocking --- so a script's exit 0 says nothing about whether the
job is green.

What makes this worth its own entry is that the conclusion is easy to
**publish**, and a claim about what CI enforces is the kind other people act
on.
Per [`metacognitive-monitoring`](metacognitive-monitoring.md) that is a scope
claim, and its remedy applies: check the population --- every step of the job
--- rather than the sample that came to mind.

**A third failure mode of the whole-suite rule above: the suite holds no case
that could have failed.**
The two hazards that rule names both assume a test aimed at the behaviour you
changed exists --- one you skipped by scoping the run, or one a conditional
turned into a pass.
Widening the run and un-gating every skip fixes those two and does nothing for
this one, where the case simply is not there, because the defect class had not
been conceived when the suite was written.

Provenance is the whole argument.
A suite's case population was fixed before your change existed, so its green is
**logically independent** of whether that change is correct.
Red still carries information, since a suite that fails has found something.
Green is not its mirror, and reading the two symmetrically is what turns a
routine run into a verification claim.

That asymmetry is what makes such a report persuasive rather than obviously
thin.
Running the whole suite is real work and the diligent thing to do, and a line
like `15/15 suites passed` is specific, checkable, and true.
It is just an answer about the cases somebody wrote earlier.

So when the change is a **guard** --- a matcher, a validator, a filter, anything
whose job is to refuse a class of input --- the verifying step is to construct
that class yourself and run it against the pre-change and the post-change code,
reporting the two behaviours side by side.
Two columns over inputs you chose is a comparison; a suite total is not.
This is [`metacognitive-monitoring`](metacognitive-monitoring.md)'s "an
instrument's answer is only as wide as its input" with a test suite as the
instrument, and the construction step is
[`algorithmatize-checks`](algorithmatize-checks.md)'s "never predict which case
will fail; enumerate the class" applied to inputs rather than to a report.

Distinguish it from the neighbours it resembles, since all of them concern a
test that was aimed at the question and fell short.
[`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) governs a fixture
that cannot discriminate; the regression-test rule earlier in this file governs
a case you wrote in this pass and never saw fail;
[`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md)
governs a test that reimplements its own subject.
Here nothing is defective.
The suite is sound, and it was pointed somewhere else.

**A fourth failure mode: the case exists, and which branch it reaches is
decided by the host.**
The third mode above is a case that is **absent**, and its remedy is to
construct the missing input class yourself.
The two before it are a case you skipped by scoping the run, and a case a
conditional turned into a pass.
All three assume that which branch a case exercises is a property of the case.

It is a property of the case **and its inputs**, and a test can derive its
inputs from the machine it runs on: a PID, a process ancestry, a hostname, a
locale, a filesystem.
Then the same file, the same assertions, and the same code under test reach a
different branch in CI than on a developer machine, and neither run reports
that anything varied.

The skip-count remedy is the one that most looks like it covers this, and it
does not.
Nothing is skipped.
The test runs, takes a path, and passes, so the tests/failed/skipped triple
reads identically on a machine that covered the branch and on one that did not.

Green in CI is also worse than uninformative here, because a host-dependent
suite is not merely silent about the branch it missed.
It can be **unstable**, passing in one environment and failing in another, so
the developer who meets the red is meeting a real defect in the test's premise
rather than a flake.
Treat a failure that CI cannot reproduce, in a suite whose setup reads the
host, as evidence about the inputs rather than about the machine.

So when a test's setup reads anything from the host, name the value it read and
the branch that value selects, and pin the remaining branches with cases that
do not depend on it.
A branch the environment selects is a branch no CI configuration promises to
cover.
