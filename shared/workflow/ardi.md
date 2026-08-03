Whenever you are working a PR/MR, run the full **ARDI** loop by default, without
being asked: **A**ddress every flagged item, **R**ebut findings that are wrong,
**D**efer out-of-scope items to tracked issues, then **I**terate with a fresh
review --- repeating until the latest review is **fully clean**. Don't stop at
"review-clean, just needs approval" and hand triage back; keep the cycle going
until it's genuinely clean.

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
This applies transitively to PR-driving
workflows such as `gi`, `gii`, and `ardia`; only monitor PRs the session owns or
has explicitly claimed, so the rule does not authorize changing someone else's
work.

The loop's terminal action is to **report the PR ready, not to merge it**.
Merging is human-gated --- it happens only on an explicit human "merge it" (the
`merge-it` skill), never as a step ARDI takes on its own. So when you carry a PR
across a `ScheduleWakeup` or `/loop` wait, **never** bake a self-merge directive
like "if clean and CI green, merge it" into the wakeup/loop prompt: a scheduled
prompt fires back as a user-role turn, so a self-authored "merge it" only *looks*
like human approval (and Claude Code's auto-mode classifier will rightly deny it
as a self-authored merge). Drive to fully clean, report ready, and leave the
merge --- and any other destructive one-off, e.g. a `gh workflow run` that
force-pushes --- for explicit human authorization.

Because the loop ends there, **the clean verdict is also where `ums` runs** ---
don't hold the pass for the merge, which is on the human's clock rather than
this session's and may land after a `/clear` or not at all.
See `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate";
the merge-time pass in `post-merge` then only has to cover what the merge
itself taught.

The one exception: if the human has explicitly granted the `mwc`
(merge-when-confident) session permission, that grant is a live human
instruction, not a self-authored one, so baking a self-merge step into a
wakeup/loop prompt is fine for the rest of that session. See
[`mwc`](../../skills/mwc/SKILL.md) for the grant's scope and limits.

In the **clear-all family** (`ardia`, `gia`, `gii`, `gip`), "report ready, don't
merge" gates only the merge --- it does **not** pause the sweep. A
clean-but-unmerged PR is not a stop; move to the next item, and stack it when it
isn't naturally independent of that PR. See
[`stack-dont-pause`](stack-dont-pause.md).

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
said. Before every push, re-read the project's own stated review criteria
and actually invoke the review skills/checks it names against the diff
(not just recall them from memory), the same way an external reviewer
would apply them. Address every finding your own self-review surfaces ---
fix, rebut, or defer, exactly like the ARD step above --- before the push
goes out; a self-review that finds issues and pushes anyway has only
moved the round to the external reviewer instead of skipping it. Repeat
until your own self-review pass is clean, then push.
([gha#219](https://github.com/d-morrison/gha/issues/219)/[#220](https://github.com/d-morrison/gha/pull/220): one review round surfaced five findings --- a DRY
duplication, an incomplete-coverage doc overclaim, a wrong changelog
category, an uncited claim, and missing test coverage for new logic --- all
catchable this way, since each was a direct match against gha's own
`CLAUDE.md` conventions, not new information the review surfaced.)

### Pre-push checklist

**Pause point: after committing, before `git push`.**
Do-Confirm --- the items are independent, so work in whatever order suits the
round and confirm all seven here.
Per [`skill-checklists`](skill-checklists.md); every item below exists because
the bullets in this fragment record it failing at this exact boundary.

- [ ] **The whole test suite ran**, not the files you predicted the change
      touches, and the tests/failed/**skipped** triple was read --- a
      non-trivial skip count means re-running with the gating flags set
      (`NOT_CRAN=true`, and whatever else un-gates a conditional skip).
- [ ] **Generated trees were regenerated** if the diff (or a `main` merge)
      touched a generator's inputs, and the PR body states how many changed
      files are generated.
- [ ] **Added lines were scanned** for banned punctuation and multi-sentence
      lines, run *after* committing and with the three-dot range
      (`origin/main...HEAD`) --- a pre-commit run reports on the wrong tree,
      and a two-dot range re-attributes whatever `main` deleted to you.
- [ ] **The changelog entry and the PR description were re-read** against the
      new behavior, not just the code --- neither is in the diff, so no
      reviewer and no grep will catch a stale one.
- [ ] **The diff's deleted lines were read**
      (`git diff origin/main...HEAD | grep '^-'`), and each one was a decision
      rather than collateral from an edit's blast radius --- a reviewer reads
      every deletion as deliberate and will rationalize an accidental one.
- [ ] **`main` was merged in** if it moved, with version parity re-checked
      afterward, so the round costs one review run rather than two --- and any
      whole-file count a merge can worsen (spliced changelog bullets) compared
      before against after, since a defect caused by a *deleted* line is
      invisible to every added-lines check
      ([`sync-with-main`](sync-with-main.md)).
- [ ] **Killer item: the push landed.** `git rev-parse HEAD origin/<branch>`
      agree before any reply asserting a fix.
      This one is marked because its failure is not an omission but a **false
      claim about state**, which a reviewer has no reason to doubt: CI reports
      green because it correctly validated the older head, and the session's
      own recollection agrees with the reply.

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

- **Do:** read your diff's deleted lines before pushing, and confirm each one
  was a decision rather than a casualty of an edit's blast radius.
- **Do:** say plainly, in the thread, when a review has blessed something
  unintended --- the reviewer cannot know, and its verdict will otherwise
  stand as the record.
- **Don't:** treat a clean verdict as evidence about intent; it is evidence
  about correctness only.
- **Don't:** keep an unintended change because the reasoning offered for it
  turned out to be good.

(Morrison-Lab/ai-config#922, 2026-07-30: a replacement string written to add
one block silently dropped the three `Do`/`Don't` bullets belonging to the
entry above it, leaving that entry with prose and a case record but no
labelled pair --- which `CLAUDE.md`'s "Record both the pattern and the
anti-pattern" specifically asks for.
`claude-review` returned Ready for merge, analysed all three deletions, and
concluded they were "appropriate", reasoning that two restated surviving
prose and the third was superseded.
The third point was right and the other two were not; the bullets were
restored, one reworded, and the deletion count fell from seven lines to two.)

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

- **Do:** re-run the project-conventions check against your own diff after a
  clean verdict, not only before the push.
- **Do:** read a reviewer's "observations" and "not a finding" items as
  candidate violations, and grep `CLAUDE.md` for whatever they discuss.
- **Don't:** let a reasoned "belt-and-suspenders is fine" settle a question
  the repo already answered in writing.
- **Don't:** treat a non-blocking label as deciding whether an item gets
  checked at all.

(Morrison-Lab/ai-config#965 at `b85941c`, 2026-07-31: a diagnostic block ran
both `git merge-base --is-ancestor HEAD origin/main` and
`git rev-list --count origin/main..HEAD`, where `CLAUDE.md`'s `wrap-up`-sweep
section says verbatim to "resist adding an ancestry check beside the first of
those", since the two confirm one thing twice rather than two things once.
`claude-review` returned Ready for merge, called the pair "logically
equivalent (both express `HEAD <= origin/main` in ancestry)", judged that
"presenting both is reasonable as belt-and-suspenders for a diagnostic
block", and closed the item "Not a finding"; a second reviewer comment
returned Ready for merge at the same head.
The same block's `--is-ancestor ... && echo "pure upstream history"` was
graded the same way, although `address-every-comment`'s own ai-config#868
case record already establishes that `--is-ancestor` exits 2 or higher on a
pruned ref and `&&` fails on any non-zero status --- measured here, a bogus
ref gives rc=128 and the two-arm form still reports "not ancestor".
Both verdicts were wrong; fixed in `0c19d3c`.)

**Proactively self-correct a technical claim you already told a reviewer,
the moment further testing shows it was wrong --- don't wait for the
reviewer to catch it.** If you stated a rationale (an approach is safe, a
risk doesn't apply, a backstop exists) and then discover through your own
follow-up verification that it's false, post the correction with the actual
evidence immediately, rather than leaving the stale claim standing until a
review round re-raises it. This keeps the review loop converging instead of
churning on a claim you already know is wrong. ([d-morrison/rme#989](https://github.com/d-morrison/rme/pull/989) /
[ucdavis/epi204#363](https://github.com/ucdavis/epi204/pull/363): after telling both reviewers `references.bib` didn't
share `CLAUDE.md`'s union-merge corruption risk, a follow-up merge
simulation showed it does --- posted the correction with repro steps on
both PRs before either reviewer re-raised it.)

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
(d-morrison/altdoc#54, 2026-07-25: two review fixes were edited locally and a
PR comment said they were "addressed in the latest push"; the head sat at the
pre-fix commit for over an hour, with 14 green checks validating a branch
carrying neither fix, until a scheduled check-in compared the SHAs.)

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

- **Do:** read every SHA you cite out of `git rev-parse` or `git log`, and
  confirm it resolves before pasting it.
- **Do:** correct a published wrong SHA with a visible note naming the real one.
- **Don't:** write a short SHA from recollection because it looks like the
  commit you just made.
- **Don't:** expect review to catch it --- a reviewer has no reason to suspect
  a citation, and the body is not in the diff they are reading.

(ai-config#871, 2026-07-30: the PR body credited a sentence-boundary fix to
`1f79a4a`, which existed nowhere in the branch or the repository ---
`git cat-file -e` returned `Not a valid object name`.
The real commit was `fcb605f`.
Two review rounds read that body without flagging it; it surfaced only when the
body was re-read against the diff before declaring the PR ready, which is the
`address-every-comment` check above doing work its own rule did not anticipate.)

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

- **Do:** compare `HEAD` against `origin/<branch>` first when the PR API
  disagrees, and re-read rather than re-push when those two agree.
- **Don't:** amend, force-push, or re-commit on the strength of an API SHA
  alone.

(Morrison-Lab/ai-config#845, 2026-07-29: `git rev-parse HEAD` and
`git rev-parse origin/<branch>` both read `9a3e722` and `git push` said
`Everything up-to-date`, while `gh pr view --json headRefOid` still returned
the prior commit `4bf5063`.
`pull_request_read` `get` returned `9a3e722` moments later, so the two
surfaces disagreed and the git-native one was right.)

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
Reproduced in a local bare repo, where no replica and no race exists: the
push printed `* [new branch]` and exited 0, `git ls-remote` and the tracking
ref both read `main`'s tip, `main..<branch>` held zero commits, and
`git push origin HEAD:refs/heads/<branch>` then reported a real range.
That last command is a test as much as a fix, since it answers
`Everything up-to-date` when the branch ref and `HEAD` already agree.

Two things weigh against the read-side story, which an earlier draft of this
entry weighted equally against the write-side one.
A lagging replica cannot invent a value for a ref that never existed before,
so its failure mode is the ref reading **absent** rather than reading one
specific wrong commit.
And a tracking ref is set from what the push sent, which makes its value a
client-side fact rather than a later network read.

What stays genuinely unsettled is narrower than either reading claimed: the
branch ref's own value at push time was never recorded, so the local
explanation is the best supported one rather than a proven one.
Note the shape of that, since it is the failure this entry is about.
The entry has now over-claimed twice, first asserting a write-side fault, then
asserting a parity between two hypotheses that the record does not support
either.
The practical advice survives all three readings, because the checks below
are cheap whichever is right.

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

- **Do:** run `git ls-remote origin <branch>` after the first push to a new
  branch, and compare its SHA against `git rev-parse HEAD`.
- **Do:** run `git rev-parse HEAD <branch>` first when those two disagree,
  since a branch ref left behind accounts for the whole signature (and note
  that `--short` rejects a second revision, so pass neither).
- **Do:** re-run plain `git ls-remote` as well, so a ref that self-corrects
  stays distinguishable from one a re-push repaired.
- **Do:** re-push with `git push origin HEAD:refs/heads/<branch>` when the
  mismatch persists, and read the SHA range it prints as the confirmation.
- **Don't:** treat a `git push` that exited 0 and printed `* [new branch]` as
  evidence the commit reached the remote.
- **Don't:** assume `git push -u origin <branch>` sent the commit you just
  made -- it sends the branch ref, which `HEAD` may have moved past.
- **Don't:** credit a corrective re-push with having repaired a remote-side
  fault when neither of those two controls was run.
- **Don't:** answer a `No commits between main and <branch>` error by
  re-checking the base branch argument before checking where the head ref
  actually points.

(Morrison-Lab/ai-config#985, 2026-07-31:
`git push -u origin ums/prose-count-adjacent-to-block`, carrying commit
`1611ccc`, printed `* [new branch]`, set the upstream, and exited 0.
`git ls-remote` showed that ref at `98102a2`, which was `main`'s tip.
The local `origin/ums/prose-count-adjacent-to-block` agreed with the wrong
value, so the two-ref comparison reported the push as landed.
`create_pull_request` then returned a 422 reading
`No commits between main and ums/prose-count-adjacent-to-block`.
`git push origin HEAD:refs/heads/ums/prose-count-adjacent-to-block` reported
`98102a2..1611ccc`.
Neither `git rev-parse ums/prose-count-adjacent-to-block` nor a second plain
`git ls-remote` was run, so the branch ref's own value at push time is the
fact the record is missing.
Describing that push as "carrying commit `1611ccc`" was an inference from the
commit just made, not a reading of the ref that was pushed.)

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

- **Do:** run `gh pr diff <N> --name-only` against any inherited "already
  fixed" claim before deciding a finding is closed.
- **Do:** state plainly in your own summary that the prior claim did not hold,
  and name the head it was false at.
- **Don't:** treat green CI as evidence that a claimed fix landed.
- **Don't:** infer that a finding is stale because a comment says it was
  addressed.

(Morrison-Lab/ai-config#804, 2026-07-29: the PR's own review workflow posted
"Three fixes landed in two commits", naming `bootstrap.sh`, `validate.yml`,
and `validate-skills.py`.
The head was still the original commit plus a `main` merge, and
`gh pr diff --name-only` returned four paths, none of them those three.
All ten checks were green, because `validate` did not yet check out the
submodule the fixes were about.
This is the ownerless cousin of the parallel-session case in
[`claim-pr`](claim-pr.md), which assumes a real commit exists to cross-check;
here there was none.)

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

- **Do:** run `gh pr diff <N> --name-only` before reporting a PR ready, and
  read the returned paths against what the PR says it does.
- **Do:** treat an empty return, or a return holding only a `main` merge's
  incidental paths, as the PR carrying no implementation.
- **Don't:** count the claim commit or a `main` merge as work --- neither is
  implementation, and both give the branch a plausible history.
- **Don't:** read all-green CI plus a finding-free review as evidence a PR
  contains anything; on an empty diff that is the expected result.

(2026-07-30/31, a `ucdavis/bcs` session: a PR was reported `CLEAN` with every
check passing, on a branch holding the empty claim commit plus a `main` merge
and nothing else.
Nothing had gone wrong with any instrument.
The implementation had never been pushed, and no check, no reviewer, and no
rule in this file was asking whether there was one.)

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

- **Input shapes no fixture happens to contain.** A real package carries
  metadata the fixtures never needed --- an entry of a different kind, an
  extra tag, an unusual name --- so a branch written for it has never
  actually run on real input.
- **Message formatting under real counts.** Fixtures usually trip the plural
  path; a real repo hitting the same code with exactly one item exercises
  the singular wording, which no test asserted.
- **The migration/upgrade path, as opposed to the fresh-install path.**
  This is the one fixtures can never reach: a fixture is created new by the
  test, so it always gets the current templates. An existing consumer has
  the *old* config, and whether the feature reaches it at all is a different
  question from whether it works. Verify the claim in the changelog by
  running the documented migration step, rather than describing it.

Do it against a throwaway copy and push nothing to the consumer; the
deliverable is evidence in the PR, not a change there. Record what the run
covered in a PR comment, so a reviewer can see which paths real input
reached. (d-morrison/altdoc#34: running the new reference-index generator
against `d-morrison/rpt` covered a `\docType{package}` topic, the singular
form of a missing-topic warning, and the documented "existing settings files
do not pick this up automatically" caveat --- confirmed by the page
generating while `grep -c reference.html docs/index.html` returned `0`. None
of the three were reachable from the repo's own fixture packages.)

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
(d-morrison/altdoc#76, 2026-07-27: the PR body said roxygen2 8.0.0 --- the
version `DESCRIPTION` pins --- was unavailable, inferred from one failed
`packageVersion()` call with no install attempted. The review built a
"this may need a follow-up" recommendation on top of it. A single
`install.packages()` disproved it, and the regeneration landed in the same
round the finding did.)

**Name the specific gate when you report a blocker, not a category word that
happens to be one of several.**
The rule above governs *whether* something is blocked, and its remedy is to
attempt the thing once.
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

- **Do:** quote the clause that distinguishes the failure, and name the gate
  it belongs to.
- **Do:** re-read a blocker you have restated several times, since a
  paraphrase repeated across status reports hardens into the record.
- **Don't:** use one mechanism's own name as a generic word for its category.
- **Don't:** treat having verified *that* something is blocked as having
  verified *why*.

(2026-08-01, `Morrison-Lab/ai-config` worked from a `d-morrison`-scoped
session: an unresolvable review thread was reported as blocked "for scope
reasons" across roughly six status updates, while the failure actually
observed under that spelling was the node-versus-declared-string comparison.
`memories/github-mcp-tools.md` records both gates and their verbatim errors.)

**A blocker that was true when you published it can stop being true while
the PR is open, and withdrawing it is your job, not the reviewer's.**
The verify-a-blocker bullet above covers a blocker that was never true, and
the gate-naming bullet between it and this one covers a real blocker whose
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

(ai-config#774, 2026-07-28: the PR body said four `adv-r.hadley.nz` anchors
could not be verified because the host was egress-blocked, which was
accurate when written.
The host was unblocked mid-session, and all 16 URLs then verified 200 with
every anchor resolving.
The review had already absorbed the caveat --- it listed those anchors as
"unverified per the PR body's own caveat ... not a new finding" --- so
leaving it would have shipped a limitation that no longer existed, blessed
by a reviewer who could not have known.)


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

- **Do:** after every `main` merge, scan the PR's touched files for merge-status
  hedges with whitespace-normalizing search, then re-read each hit against the
  new base.
- **Don't:** assume a hedge survived because the file that contained it merged
  without conflicts, or because literal grep missed a phrase split across
  semantic lines.

(Morrison-Lab/ai-config#981: its fragment said ai-config#959 was still open as
of 2026-07-31 and that, once merged, the fragment would live at
`shared/workflow/flag-practice-slippage.md`.
PR #959 merged at 2026-07-31T16:24:34Z, and commit `df243ee9` merged `main` into
PR #981 on 2026-08-01, pulling in that very file.
The merge conflict was in `CLAUDE.md`, so the cleanly merged fragment was not
re-read, and a reviewer caught the stale hedge afterward.)

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

- **Prose staled by the fix.**
  It was accurate when written, so nothing about it reads as a defect, and a
  workaround it prescribes becomes active misdirection the moment the thing it
  worked around is gone.
  Keep the entry where the old behaviour explains something --- most of a
  corpus is written against it --- but mark plainly that it is history and name
  the change that ended it.
- **Prose asserting conformance to a reference.**
  A docstring saying the code "follows" some reference implementation is a
  claim about two artifacts, and your own divergence falsifies it.
  This one is not staleness at all: it was false before you arrived, and it is
  load-bearing, because a reader checking the code against the reference stops
  at the sentence saying someone already did.

- **Do:** grep the repository for the defect, the workaround, and the behaviour
  you changed, before calling a fix complete.
- **Do:** mark a superseded entry as history and name the change that ended it,
  rather than deleting it, when the old behaviour still explains other text.
- **Don't:** treat a clean grep over the diff as coverage --- the stale prose is
  outside it by construction.
- **Don't:** leave a doc asserting conformance to a reference standing when the
  code diverges; correct the claim in the same change that establishes the
  divergence.

(`ucdavis/bcs#534`, 2026-07-30/31: standardizing a G-computation CIF over the
observed age distribution falsified two documents at once.
`compute_gcomp_cif_ab507bs()`'s roxygen had read "this function follows the SAS
pipeline's plug-in-at-the-mean approach", which the SAS program does not do ---
false before the fix, and quoted by the fix's own changelog entry as such.
A row in `inst/docs/program_steps.qmd` described the retired behaviour and was
refreshed in a separate commit.
Concurrently, ai-config#951 diff-scoped `scripts/semantic-line-breaks.py`, which
falsified `memories/tools.md`'s entry prescribing "format new prose by hand" as
the workaround; that entry was kept and marked `**Fixed in ai-config#951.**`,
which is the first shape handled correctly.)

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
(d-morrison/altdoc#73: the issue proposed ending a function with a bare
trailing `hashes`, which reads as a fix for the fragility it names but is
still an implicit return, so a statement added after it silently becomes
the return value. The lab manual asks for an explicit `return()`
regardless. Review caught it; the project's own stated convention would
have, one step earlier.)

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
(d-morrison/altdoc#76: a guard checked for the copied logo under `docs/`,
but the `quarto_website` path stages into `_quarto/` first, so the logo
line was dropped on every render of the one generator the feature wired
up. Seventeen unit assertions passed throughout; one throwaway render
found it immediately.)

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
(d-morrison/altdoc#78, 2026-07-27: a generator-to-extension map gave mkdocs
`.html`, reasoning that mkdocs compiles Markdown to HTML. Its
`use_directory_urls` default is `TRUE`, so it serves `/man/foo/` and never
`/man/foo.html` --- every reference link the feature emitted for that
generator would have 404'd. Caught in review, not by the 39 tests.)

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
(d-morrison/altdoc#78, 2026-07-27: twice.
A `.pdf` vignette test asserted
the entry's extension but never its label, so an extension leaking into the
label passed; and a nested-article test built no source tree, so top-level
and nested resolved identically and a nested-only title bug was pinned as
expected output.
Both were found by review reading the test, not the code.)

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
(d-morrison/altdoc#78, 2026-07-27: a commit written to get ahead of a
one-finding-per-round loop claimed mkdocs' sidebar matched only `\.md`.
It matches `\.md$|\.pdf$`; the grep had returned a different function 120
lines above the sidebar builder in the same file.
Caught by the very next review round.)

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
(ai-config#770, 2026-07-28: an added explanation established that seven
reported orphans were misclassifications, while the note two lines below went
on calling them "already deleted from the repo."
Caught by review, in the same hunk as the text that contradicted it.)

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
(ai-config#801, 2026-07-28: a new UMS entry argued against the `/clear`
section's "disclose the owed pass in the flag" line while the same PR rewrote
that line to say the opposite.
Review caught it before merge; the fix was to drop the cross-reference and
state the point inline.)

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
(ai-config#770, same day: a `git log -- skills/<name>` probe was said to
separate "deleted from the repo" from "never ours" *exactly*, on the evidence
that it reported zero false orphans.
The repo contained no deleted-but-still-installed skill at all, so there was
nothing for it to get wrong; and `git rev-parse --is-shallow-repository`
returned `true`, meaning anything deleted before the shallow boundary would
have been silently misread as harness-provided.
The claim went into a PR reply before either check was run, and ai-config#765
had independently reached the correct conclusion.)

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

- **Do:** look for a merged fix, and date it, before attributing a vanished
  symptom to anything.
- **Do:** report the before/after with its timestamps, so the negative
  control is visible rather than asserted.
- **Don't:** explain a symptom's disappearance as nondeterminism on the
  strength of one clean run.
- **Don't:** carry such a claim into an issue or a decision doc, where it
  argues against the very fix that produced the silence.

(ai-config#827, 2026-07-29: the Jules AI reviewer approved a diff carrying
both of its known false-positive triggers, and the first explanation
drafted was that the false positives are nondeterministic.
ai-config#817 had in fact merged an `extra_instructions` fix at
`21:30:51Z`, between #820's block at `19:43` and #827's approve at `22:51`.
The nondeterminism claim was about to be posted to gha#366 as evidence,
where it would have argued against porting the fix that actually worked.)

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

- **Do:** confirm every literal you invent against the tool's own source or
  help output before it lands in a doc.
- **Do:** cite the file or command you checked, so the claim stays falsifiable.
- **Don't:** infer a subcommand from a family that has its siblings
  (`gh label list`/`create`/`edit` does not imply `gh label view`).
- **Don't:** treat a literal as exempt because the prose around it is
  well-sourced --- the literal is the part a reader executes.

(Morrison-Lab/ai-config#834, 2026-07-29: a `GET_LABEL` registry row shipped
`gh label view <name>`, which does not exist --- cli/cli's
`pkg/cmd/label/label.go` registers `list`, `create`, `clone`, `edit`,
`delete`.
Caught by review, in the same file where the previous round had declined to
extend an untested claim from `gh issue create --label` to `gh issue edit`.
The reviewer's own enumeration of the real subcommands also missed `clone`,
which is why the fix cited the registration list rather than the finding.)

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

- **Do:** re-run the rule you are applying against the text of your own fix,
  before committing it.
- **Do:** say in the thread when a fix's own draft tripped the same rule,
  since that is the only place the near-miss is visible.
- **Don't:** treat the effort of writing a correction as evidence the
  correction is verified.

(Morrison-Lab/ai-config#929, 2026-07-30: a review found `--failed`
documented from recollection.
The fix quoted `gh run rerun --help` correctly and anchored it to "`gh`
2.83.0" --- a version invented in the same breath, where `gh --version`
reported `2.96.0`.
Caught before committing only by running this rule against the fix, which is
the entire mechanism; the round-2 review confirmed the corrected text and
would have confirmed the wrong version just as readily.)

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
The PR body is the only place that can pre-empt this, since it is what a
reviewer reads before the diff.
Lead with the ratio and a per-path table marking each path generated or
hand-written.

- **Do:** grep a file for a generated-by header before editing it, and change
  the source instead.
- **Do:** state in the PR body how many of the changed files are generated,
  and name the hand-written ones.
- **Don't:** revert generated output because a reviewer calls it noise ---
  check first whether the sync check requires it.
- **Don't:** assume a reviewer sees the source files; on a large diff they
  frequently do not.

(Morrison-Lab/ai-config#834, same day: a fix was applied to the generated
`tool-mappings.md`, which `sync-codex-skill-wrappers.py` then overwrote,
failing `validate` with `stale tool-mappings.md`.
Redoing it in `tool-mappings.yml` regenerated 175 `codex-skills/` wrappers,
and Jules returned `VERDICT: block` twice for "bulk pollution", its second
verdict noting it had read only a truncated diff.
`claude-review` called the same finding a false positive at the same head.)

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

- **Do:** run the full suite before pushing, and state the tests/failed/
  skipped triple rather than "tests pass".
- **Do:** set the flags that un-gate conditional skips, and re-run if the
  skip count is non-trivial.
- **Don't:** scope a local run to the files you edited --- the test asserting
  the old behaviour is usually somewhere else.
- **Don't:** read a green subset as a green suite, or a skip as a pass.

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

- **Do:** run every check the CI job runs, its test files included, before
  pushing.
- **Do:** grep the job definition for other steps touching the same property
  before saying anything about whether it gates.
- **Don't:** substitute a production script's exit code for its test file.
- **Don't:** infer a job's behaviour from one step's label --- "(advisory)"
  describes that step, not the job.

(Morrison-Lab/ai-config#1067, 2026-08-02: a UMS pass took `memories/git.md`
from 1172 to 1315 lines.
`scripts/check-memory-file-size.py` exits 0 and its `validate.yml` step is
labelled advisory, both genuinely so, and the threshold was therefore reported
as non-blocking on #1007.
`scripts/test_check_memory_file_size.py` asserts this repo's own `memories/`
are under the default and hard-fails, turning `validate` red on the next push.
The claim had to be retracted on #1007 as well as fixed in the PR.)

(d-morrison/altdoc#95 and #96, 2026-07-29: twice in one session.
On #95 a test asserting "aborts when no venv is configured" read that
precondition from the ambient environment; the local run missed it because
`NOT_CRAN` was unset and `skip_on_cran()` skipped that very test, and
Windows R-CMD-check caught it.
On #96 `test-llms_txt.R` asserted non-recursive discovery for `docsify` ---
the exact behaviour the PR changed, with a comment stating the now-false
rationale --- and was not among the files run locally, even though
`.llms_txt_vignettes()` was one of the functions edited.
Windows caught that one too.
The subsequent full-suite run was itself misleading in the opposite
direction: run *with* an env var CI does not set, it reported two failures
belonging to the sibling PR.)
