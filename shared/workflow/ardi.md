Whenever you are working a PR/MR, run the full **ARDI** loop by default, without
being asked: **A**ddress every flagged item, **R**ebut findings that are wrong,
**D**efer out-of-scope items to tracked issues, then **I**terate with a fresh
review --- repeating until every reviewer's latest verdict is **fully clean**.
Don't stop at
"review-clean, just needs approval" and hand triage back; keep the cycle going
until it's genuinely clean.

Posting a review as comments, with no request to edit the branch, is not
working the PR.
Do not start ARDI, do not push fixes, and do not merge.
Leave the findings and stop unless asked to iterate.
A later request to iterate is a driving request.
"Watch and ARDI every PR you touch" applies when you are driving the
branch, not when you were asked only to read it.
(UCD-SERG/shigella#31, 2026-08-25.)

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`ardi.rationale.md`](ardi.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`ardi.cases.md`](ardi.cases.md), moved out of the auto-loaded context.

**Continuously monitor every PR/MR you are actively working until it reaches
that terminal state.**

**That wait is conditional on a run having been scheduled, and on some repos a push schedules nothing.**

- **Do:** read the review workflow's `on:` block before the first push to a PR in an unfamiliar repo, and dispatch explicitly after the round's last push when it carries no push-based trigger.
- **Do:** treat a non-zero `check-pr-fully-clean.py` on a dispatch-only repo as a prompt to dispatch.
- **Don't:** read green CI at the current head as evidence a review is in flight --- on a dispatch-only repo that is the steady state, not a transient one.
- **Don't:** let a verdict from an earlier head stand because the repo's trigger class was already known.
  Knowing it is not the same as acting on it each round.

**Dispatching needs no permission, so do not ask about the spend.**

The rule above is about the mechanism and says nothing about authorization,
which leaves a session free to know it and still stall --- by reasoning that a
review round costs money and the spend is the maintainer's call.
That sounds like restraint and is indistinguishable from it from the inside.

The asymmetry runs the other way.
A green, unreviewed PR is **parked, not clean**, so declining to dispatch does
not save a round; it holds the PR in a state that reads as finished and is not.
The stall also spends the user's attention every time, which is the thing the
review loop exists to conserve.

So dispatch when the round is ready, and put the run in the status report
rather than the question.

- **Do:** dispatch the review yourself once the round's last push has landed,
  on any repo whose reviewer is dispatch-only.
- **Do:** name the run you are waiting on, so the report carries a fact rather
  than a request.
- **Don't:** write "spending a round is the maintainer's call" into a status
  report, or hold a ready PR pending a spend question.
- **Don't:** read this as a general spending grant --- it covers scheduling a
  review, and merging is still [`mwc`](../../skills/mwc/SKILL.md)'s to govern.

(Directive from the user, 2026-08-16: "always dispatch".
Three PRs reached green CI on a `workflow_dispatch`-only repo in one session,
and each time the session asked before dispatching, citing rounds that had
billed \$12.14, \$10.37 and \$12.44 against a monthly limit already reached.
Both earlier dispatches came back `Needs more work`, one with a blocking
correctness bug, so the round was not a formality.
Tracked as ai-config#1571.)

**Dispatch once, after the round's LAST push --- a per-push rhythm cancels its own reviews.**

**Dispatch with `--ref <PR-branch>`, or the resulting failure is invisible on the PR.**

- **Do:** finish pushing, then dispatch once, and name in the status report which run you are waiting on.
- **Do:** pass `--ref <PR-branch>` on every dispatch, so the review's check runs attach to the PR head.
- **Do:** diagnose a missing verdict by reading the run, since a cancelled dispatched run leaves no trace on the PR's check-run list.
- **Don't:** dispatch per push --- each one cancels the last, and the round spends review time producing nothing.
- **Don't:** re-dispatch reflexively when a verdict is missing.
  If one is in flight, the retry cancels it.
- **Don't:** read a green, nothing-pending PR as reviewed on such a repo --- that is also what an invisible cancelled gate looks like.

**A cancelled run is invisible to a session READING the PR and loud to one
SUBSCRIBED to it, and the second is the dangerous direction.**

The bullet above is scoped to the check-run list deliberately.
GitHub lists check runs for the **head commit**, so a run cancelled after the
head moved leaves a `require-review` failure hanging off the superseded SHA,
where a session reading the PR will not find it.

The webhook stream is a different surface and it does not filter that way.
The cancel fires a `check_run.completed` with `conclusion: failure`, so a
session subscribed to PR activity is woken by a red **required** check on its
own PR.

That inverts the risk the bullet above describes.
An invisible failure costs you a verdict you thought you had, and you find out
by looking.
A visible failure on a superseded commit costs more, because the drive-to-green
posture says not to end a CI-failure wake without pushing a fix or replying
with a blocker --- so the reflex is to fix, against a commit that is no longer
in the PR's timeline.
At best that is wasted work.
At worst you change the current head on the authority of a red check that was
never about it.

One field decides it, and it is the field
[`fully-clean`](fully-clean.md) already names for the neighbouring problem:
compare the event's own `head_sha` against the PR's current head.
Equal means act.
Unequal means confirm a run is live at the real head, and leave the diff alone.

- **Do:** compare a CI-failure event's `head_sha` against the PR's current head
  before diagnosing anything.
- **Do:** reply naming the superseded SHA rather than staying silent, so the
  wake is visibly dispositioned rather than dropped.
- **Don't:** read "leaves no trace on the PR" as covering the webhook stream
  --- it describes the check-run list, which is filtered by head commit.
- **Don't:** push a fix in response to a red check whose `head_sha` is not the
  head; the check is not about the code you would be changing.

See [`ardi.cases.md`](ardi.cases.md), "A cancelled dispatch that fired a
failure webhook against the superseded SHA".

See [`ardi.cases.md`](ardi.cases.md), "A per-push dispatch cancels its own review, invisibly".

**A dispatch you make while idle can still be cancelled --- by a push you did not make.**
The per-push rule above governs your own pushing rhythm colliding with your own dispatch.
The concurrency group is keyed on the PR number alone, not on who triggered the run or how, so a **third party's** push into the same PR branch cancels your dispatch exactly as a push of your own would --- even when you have pushed nothing since dispatching.
On a repo with an active `@claude` agent, the bot itself is such a third party: reacting to review activity, it can push a `main`-sync merge into the PR branch (see [`claim-pr`](claim-pr.md)'s note on this), which is a `synchronize` event and, on a repo that reviews on push, schedules a fresh review run in the same group --- cancelling yours.

The tell: your dispatched run reads `cancelled`, its `headBranch` is whatever ref you dispatched against --- the default branch if you omitted `--ref`, the PR branch if you passed it, so this conjunct alone proves nothing --- and a newer `pull_request`-event run exists for the same PR, at a newer head.
The right response is to do nothing --- the cancellation is benign, since the newer run supersedes at a better head, and re-dispatching would cancel *that* one instead.

- **Do:** before treating a cancelled dispatch as a lost review, check for a newer `pull_request`-triggered run on the same PR.
  Its existence and its head are the whole explanation.
- **Do:** re-fetch the PR branch head before concluding a dispatch failed --- a head that moved without you pushing explains a cancellation the per-push rule above cannot.
- **Don't:** re-dispatch to "fix" a cancelled run that a newer, better-placed run already superseded --- that cancels the survivor instead.
- **Don't:** read `require-review: failure` on the cancelled run as a live problem.
  It is a side effect of the superseded run, and the newer run supplies the real verdict.

See [`ardi.cases.md`](ardi.cases.md), "A third-party push cancels an idle-dispatched review".

Always execute `python3 scripts/check-pr-fully-clean.py --quorum <number-of-reachable-providers> <pr>` synchronously in the foreground turn to evaluate clean verdicts.
Whenever ending a turn while waiting for an AI review or CI completion on an active PR after pushing code, launch a `schedule` timer (e.g. 120s) to check back.
When the timer fires:
- Check if a review for the HEAD SHA has arrived.
- If no review has posted yet, verify whether review workflow runs are still in progress (`gh run list` / `gh pr view --json statusCheckRollup`).
- If review workflows are still running: schedule another timer to check back.
- If the reviewer failed, was canceled, skipped with no replacement (e.g. quota limit), or produced a stub review with no stated verdict: invoke self-review fallback per [`self-review-fallback.md`](self-review-fallback.md) rather than stalling the loop.
- Otherwise, fix any underlying workflow or dispatch issues discovered along the way and schedule another timer to maintain continuous monitoring until a review lands, self-review fallback triggers, or CI completes.
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

Because the loop ends there, **the clean verdict remains a UMS checkpoint** ---
don't hold that pass for the merge, which is on the human's clock rather than
this session's and may land after a `/clear` or not at all.
**Reading the review is an earlier checkpoint than the verdict.**
Run UMS when the review arrives (Rebut and Defer included), not only once
every finding is Addressed or the round comes back clean.
See `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate";
the merge-time pass in `post-merge` then only has to cover what the merge
itself taught.

The one exception: if the human has explicitly granted the `mwc`
(merge-when-confident) session permission, that grant is a live human
instruction, not a self-authored one, so baking a self-merge step into a
wakeup/loop prompt is fine for the rest of that session. See
[`mwc`](../../skills/mwc/SKILL.md) for the grant's scope and limits.
The Scope Limit still binds: a disagreement among reviews --- one all-clear
and another with findings, nits included --- is not fully clean, so `mwc`
does not authorize merging it.
ARD every item from every review, then request fresh reviews
(ai-config#2274).

In the **clear-all family** (`ardia`, `gia`, `gii`, `gip`), "report ready, don't
merge" gates only the merge --- it does **not** pause the sweep. A
clean-but-unmerged PR is not a stop; move to the next item, and stack it when it
isn't naturally independent of that PR. See
[`stack-dont-pause`](stack-dont-pause.md).

**The same gate does not pause the loop *within* a single PR either, and that
is the harder half to see.**

**The tell is lexical, and it sits in your own outgoing message: a
RECOMMENDATION or question whose proposed action is ordinary ARDI work.**

- **Do:** resolve conflicts, sync, push fixes, and re-dispatch reviews on a PR
  whose merge you are correctly withholding, and report those in the past
  tense.
- **Do:** name the one action that is gated, so "blocked" stays a claim about a
  step rather than about the PR.
- **Don't:** generalize a withheld merge into withholding the rest of the loop
  as though one authorization covered both.
- **Don't:** write a recommendation proposing work ARDI already mandates --- a
  request to do the required thing is the error, not a courtesy.

See [`ardi.cases.md`](ardi.cases.md), "A merge gate is not a work gate".

**Self-review against the project's own stated conventions before every
push, not just the first --- and don't just re-read the criteria, actually
run the applicable review skills against your own diff and iterate on
what they find, the same ARD cycle you'd run against an external
reviewer's findings.** Don't treat the review bot as the mechanism that
discovers a project's documented conventions --- self-apply them first.

See [`ardi.cases.md`](ardi.cases.md), "A review round surfacing five findings
your own conventions already covered".

### Pre-push checklist

**Pause point: after committing, before `git push`.**

- [ ] **A separate `adversarial-reviewer` subagent reviewed this diff and returned a clean verdict** --- dispatched in the foreground against `git diff origin/<default-branch>...HEAD`, briefed with the standards rather than with your rationale for the change, with every finding Addressed, Rebutted, or Deferred to a tracked issue, and re-dispatched after the last commit so its `Reviewed-Commit:` fingerprint names the commits the push would ship ([`adversarial-self-review`](adversarial-self-review.md)).
  An inline pass under a reviewer framing does not satisfy this, and reads identically in the output --- the test is whether an `Agent` call was made.
- [ ] **The whole test suite ran**, not the files you predicted the change
      touches, and the tests/failed/**skipped** triple was read --- a
      non-trivial skip count means re-running with the gating flags set
      (`NOT_CRAN=true`, and whatever else un-gates a conditional skip).
- [ ] **Generated trees were regenerated** if the diff (or a `main` merge)
      touched a generator's inputs, and the PR body states how many changed
      files are generated.
- [ ] **Added lines were scanned** for banned punctuation and multi-sentence
      lines, run *after* committing, *after* every pass that edited the diff
      (your own reflow included), and with the three-dot range
      (`origin/main...HEAD`) --- a pre-commit run reports on the wrong tree, a
      later edit retires the lines an earlier run scanned, and a two-dot range
      re-attributes whatever `main` deleted to you.
      The mirror direction fires at merge-decision time rather than at
      line-scanning time, and reads as an emergency: a two-dot
      `git diff origin/main` shows whatever `main` **added** as *your*
      deletions, so a behind branch appears to be reverting a sibling PR that
      just landed.
      It is not.
      A merge is three-way, so a file this branch never touched keeps `main`'s
      version, and a deletion count in an untouched file means the branch is
      behind rather than dangerous.
      Settle it with `git merge-tree --write-tree origin/main <head>` and read
      the resulting tree, rather than acting on the two-dot diff.
- [ ] **The changelog entry and EVERY PR description this round touched were
      re-read** against the new behavior, not just the code --- none is in the
      diff, so no reviewer and no grep will catch a stale one.
      Read "every" literally: a round that corrects a claim appearing in two
      PRs' bodies discharges the *feeling* of having synced bodies as soon as
      one of them is done, and the one most likely to be skipped is your own,
      because fixing the other repo's copy is the part that felt like the
      work.
      This fires on a **prose** diff too: a body that explains the claim the
      round just walked back is stale in the way that matters most, and
      "reconciling prose" does not feel like changing what the PR does.
      Every **number** in the body was re-*derived* by command rather than
      re-read, run *at this push* rather than carried from the last one, with
      the command pasted beside it --- a wrong count reads exactly as plausible
      as a right one, so reading is no instrument for it, and a base figure
      owes its own derivation rather than riding on the delta's.
      "At this push" includes a push that only answers a self-review finding,
      and it includes the figures a "Corrections to this body" entry already
      refreshed --- that entry is a claim about the previous head, so the
      current push is what expires it.
      A figure whose deriving command carries a **precondition** owes one more
      step, because deriving it freshly discharges "don't recall it" and says
      nothing about whether the command was right for this diff: cross-check it
      against a quantity computed by something else
      (`git diff --shortstat` against a hand-run added-lines count), since
      re-reading a correct-looking pipeline confirms it
      ([`fail-fast`](../principles/fail-fast.md)).
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
      It answers whether the **branch** moved, and nothing about whether the
      **PR** is still open --- a closed PR keeps accepting pushes and stops
      tracking its branch, so both SHAs agree while the PR's own head stays
      frozen.
      Read the PR's `state` as a second check, per
      [`use-existing-pr-branch`](use-existing-pr-branch.md), rather than letting
      this item stand for both.

**Review a round's fixes as one diff, not as N independent fixes: two of them,
each correctly addressing its own finding, can compose into a defect neither
introduces alone.**

- **Do:** re-read the round's full diff as a unit once every finding is
  addressed, before running the pre-push checklist.
- **Do:** treat a multi-item commit message as the prompt to check the items
  against each other.
- **Don't:** conclude the round is sound because each finding's fix is sound;
  that is a claim about the parts.
- **Don't:** rely on the next review round to catch it --- it may, but it is
  then spending a round on something the previous round created.

See [`ardi.cases.md`](ardi.cases.md), "Two correct fixes composing into a defect
neither introduces alone".

**A clean verdict does not certify that your diff contains only what you
meant, because a reviewer cannot tell an accident from a decision.**

- **Do:** read your diff's deleted lines before pushing, and confirm each one
  was a decision rather than a casualty of an edit's blast radius.
- **Do:** say plainly, in the thread, when a review has blessed something
  unintended --- the reviewer cannot know, and its verdict will otherwise
  stand as the record.
- **Don't:** treat a clean verdict as evidence about intent; it is evidence
  about correctness only.
- **Don't:** keep an unintended change because the reasoning offered for it
  turned out to be good.

**When the edit is a regex or string patch rather than the Edit tool, two
mechanisms turn that displacement into a silent over-deletion, and a self-check
can wave both through.**

- **Do:** anchor a string or regex patch on text unique to the intended site,
  and prefer the Edit tool's exact-string matching over a broad `.*?` DOTALL
  span.
- **Do:** make a patch self-check assert that neighbouring structures survive
  --- the sibling function or loop still present, untouched element counts
  unchanged --- not merely that the changed element's count is as expected.
- **Don't:** trust a `re.sub(..., flags=DOTALL, count=1)` whose non-greedy
  `.*?` start anchor is non-unique; it binds to the first occurrence.
- **Don't:** read "the assertions passed" as "the patch is correct"; a
  count-based check can pass by coincidental balance, and the `git diff`
  deletion-review is the real gate.

**A clean verdict does not discharge the self-review against project
conventions either, and the reviewer's own "not a finding" is where that
shows up.**

- **Do:** re-run the project-conventions check against your own diff after a clean verdict, not only before the push --- dispatched to the [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent like any other self-review ([`adversarial-self-review`](adversarial-self-review.md)), rather than performed inline.
- **Do:** read a reviewer's "observations" and "not a finding" items as
  candidate violations, and grep `CLAUDE.md` for whatever they discuss.
- **Don't:** let a reasoned "belt-and-suspenders is fine" settle a question
  the repo already answered in writing.
- **Don't:** treat a non-blocking label as deciding whether an item gets
  checked at all.

**Proactively self-correct a technical claim you already told a reviewer,
the moment further testing shows it was wrong --- don't wait for the
reviewer to catch it.** If you stated a rationale (an approach is safe, a
risk doesn't apply, a backstop exists) and then discover through your own
follow-up verification that it's false, post the correction with the actual
evidence immediately, rather than leaving the stale claim standing until a
review round re-raises it. This keeps the review loop converging instead of
churning on a claim you already know is wrong.

See [`ardi.cases.md`](ardi.cases.md), "Self-correcting a rationale before the
reviewer re-raises it".

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

**A SHA you put in a PR body or a reply must be read, never recalled --- and
the PR body is where an invented one survives longest.**

**Knowing the prefix genuinely does not discharge this for the full SHA a
link wants.**

- **Do:** read every SHA you cite out of `git rev-parse` or `git log`, and
  confirm it resolves before pasting it.
- **Do:** correct a published wrong SHA with a visible note naming the real one.
- **Don't:** write a short SHA from recollection because it looks like the
  commit you just made.
- **Don't:** extend a genuinely-read short prefix into a full SHA by hand ---
  the prefix discharges nothing for the 33 characters it does not contain.
- **Don't:** expect review to catch it --- a reviewer has no reason to suspect
  a citation, and the body is not in the diff they are reading.

See [`ardi.cases.md`](ardi.cases.md), "A genuinely-read prefix, extended into
a fabricated link".

**The same rule governs a merge or squash commit message, which is worse than a
PR body on both counts the bullet above names.**

**The trigger is a PR with no closing issue, which is why "verify identifiers"
does not reach it.**

**An invented number here can close someone else's live work, because issues and
pull requests share one number space.**

- **Do:** read any `Closes`/`Fixes`/`Refs` number in a merge message out of the
  PR body it came from, and confirm the target is what you think it is.
- **Do:** say plainly that a PR closes nothing when it has no tracking issue,
  rather than leaving the slot empty for a number to fill later.
- **Do:** correct a published wrong reference visibly, in a comment, since the
  message itself cannot be amended once it is on the default branch.
- **Don't:** treat a closing keyword as inert against a pull request --- it
  closes one, and the number space is shared with issues.
- **Don't:** infer from "nothing changed state" that a wrong reference was
  harmless; check whether the target was open.

See [`ardi.cases.md`](ardi.cases.md), "An invented `Closes` in a merge commit
message" and "A negated closing-keyword sentence still closes the issue".

**A SHA's provenance is the question its source command answers, not merely
that a command produced it.**

- **Do:** name the claim, then run the one command that answers it, and paste
  that command's output.
- **Don't:** lift a SHA out of nearby command output because it is genuine and
  close at hand --- `git stash list` and `git reflog` answer about their own
  subjects, not about the tip.

See [`ardi.cases.md`](ardi.cases.md), "A read SHA can answer a different
question".

**A verification table you write in the PR body is the same defect one artifact
over, and re-reading it cannot catch a wrong number.**

**It goes stale rather than being wrong on arrival.**

**It sits in the PR body, which nothing re-reads.**

- **Do:** re-derive every count in the PR body with a command at push time, and
  publish the command next to the count.
- **Do:** treat any round that changes the diff as expiring every figure the
  body already states, not only the figure that round was about.
- **Don't:** substitute re-reading for re-deriving --- re-reading is the right
  instrument for a stale description and no instrument at all for a stale
  number.
- **Don't:** report a delta without deriving its base; a base carried from
  recollection is unfalsifiable by any later check of the delta.

See [`ardi.cases.md`](ardi.cases.md), "A verification table in the PR body going
stale as rounds change the diff".

**A reviewer's round-one confirmation of that table does not expire when the
diff moves, and the confirmation is what makes the stale figure dangerous.**

The rule above says the figures go stale.
This is about the one artifact in the review record that argues they have not.

Round 1 verifies the table, in detail, because a body full of derived counts is
exactly what a first review checks, and it says so, naming each figure it
matched.
Round 2 does not re-verify it, because round 2 is not about the table.
Round 2 is about whether round 1's findings were addressed, so the body sits
outside what that round set out to read.

The confirmation is therefore a claim about one head, and nothing retires it.
An unverified table at least invites suspicion.
A table a reviewer explicitly confirmed reads as settled by someone other than
its author, and that reading survives every push that falsifies it.

Sharper still, and this is the part worth pinning: round 2 can derive the
correct new figure and use it in its own prose while the body carries the old
one, and flag nothing.
The reviewer is not diffing its numbers against the body's.
The reviewer derives fresh ones for its own purposes, so the two figures sit
one round apart in a single comment thread, contradicting each other, with
nobody comparing them.

- **Do:** re-derive every figure in the body at each push, whatever an earlier
  round confirmed, and record the SHA the new figures were derived at.
- **Do:** compare any figure a later review states in its own prose against the
  figure the body states, and read a mismatch as the body being stale.
- **Don't:** carry a round-one confirmation forward to a later head --- it
  verified the diff that existed when it ran.
- **Don't:** read a later round's clean verdict as evidence the body is still
  accurate; that round checked the findings, not the table.

See [`ardi.cases.md`](ardi.cases.md), "A round-one confirmation laundering a
body the next round contradicts".

**A "Corrections to this body" entry is itself a figure in the body, so the
next push expires it too --- and it reads as more settled than the figure it
corrected.**

- **Do:** re-derive every figure a corrections entry vouches for at each push,
  and record the SHA the new figures were derived at alongside them.
- **Do:** append a further numbered entry when a later push moves the figures
  again, rather than editing the previous one, so the round that expired them
  stays visible.
- **Don't:** read a corrections entry as discharging the figures it names --- it
  is a claim about one commit, and the next push is what falsifies it.
- **Don't:** treat having written the correction as having done the check; the
  note is that check's output, never a substitute for re-running it.

See [`ardi.cases.md`](ardi.cases.md), "A corrections entry expires with the next
push".

**Verifying that a stale figure is gone needs a SECTION-scoped search, because
the corrections entry legitimately quotes it.**

The two rules above compose into a check that cannot discriminate.
The table must stop claiming the superseded figure, and the corrections entry
must quote that same figure in order to say what changed --- so the string is
still in the body after a fully correct fix, and a whole-body search for it
reports that fix as having failed.

That is a check whose pass path and failure path look alike, which
[`fail-fast`](../principles/fail-fast.md) says is not yet a check.
It also fails in the direction that invites damage: the natural response to a
"still present" hit is to delete the quotation, which is the one part of the
entry carrying the record.

Scope the search to the section that makes the claim, and assert the
corrections entry in the opposite direction:

```python
ver  = body[body.find("## Verification"):body.find("### Corrections")]
corr = body[body.find("### Corrections"):]
assert "484 added" not in ver    # the table no longer claims it
assert "484 added" in corr       # the entry still records what changed
```

- **Do:** scope a staleness check to the section that makes the claim, and
  assert separately that the corrections entry still quotes the old figure.
- **Do:** write the two assertions in opposite directions, so a deleted
  quotation fails as loudly as an uncorrected table.
- **Don't:** search the whole body for the superseded figure --- a correct fix
  leaves it present, so that search reports every correct outcome as a failure.
- **Don't:** answer a "still present" hit by removing the quotation from the
  corrections entry; that quotation is the record the entry exists to carry.

See [`ardi.cases.md`](ardi.cases.md), "A whole-body staleness check that
reported a correct fix as failed".

The one case where a figure does **not** expire is a push that leaves the tree
unchanged --- a revert-and-restore returns the tree to an object it already had, and a
measurement is a function of the tree rather than the commit.
[`dont-incur-technical-debt`](../principles/dont-incur-technical-debt.md)'s
"The one exception" section carries that mechanic, and the deferral it licenses.

**The read side of that comparison can lag a push by a few seconds, so test
the two *local* refs against each other before concluding anything failed.**

- **Do:** compare `HEAD` against `origin/<branch>` first when the PR API
  disagrees, and re-read rather than re-push when those two agree.
- **Don't:** amend, force-push, or re-commit on the strength of an API SHA
  alone.

**A brand-new branch can read back at the wrong commit, so the local two-ref
comparison above is not sufficient there.**

**The gap is in the trigger rather than in the remedy.**

**The likeliest explanation is a local one, and it reproduces offline.**

See [`ardi.cases.md`](ardi.cases.md), "A brand-new branch reading back at
`main`'s tip, reproduced offline".

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

**The same false claim arrives as *incoming* state when you pick a PR up
mid-flight, and there the SHA comparison usually has nothing to compare.**

- **Do:** run `gh pr diff <N> --name-only` against any inherited "already
  fixed" claim before deciding a finding is closed.
- **Do:** state plainly in your own summary that the prior claim did not hold,
  and name the head it was false at.
- **Don't:** treat green CI as evidence that a claimed fix landed.
- **Don't:** infer that a finding is stale because a comment says it was
  addressed.

**Your own fix-round commit makes the same claim one step earlier, and a
file-count coincidence is what lets it through.**
A commit message that enumerates a review round's findings asserts that the
commit's diff touches every file those findings name, and nothing checks that
assertion by default.
Measured 2026-08-27 on
[ai-config#2229](https://github.com/Morrison-Lab/ai-config/pull/2229): a
seven-finding fix commit changed seven files, and the match read as
confirmation --- but the findings named eight distinct files, because two
findings each spanned two files while one file was named by two findings.
The commit covered seven of the eight, so the one unfixed finding hid behind
the equal counts, and the next review round re-raised the finding against a
commit message that claimed to have fixed it.
A matching count is not a matching set.
Derive the union of files the round's findings name, compare it against the
fix commit's own changed-file list (`git show --name-only`, which prints
full one-per-line paths where `--stat` may ellipsize them) before pushing,
and account for every member missing from either side.

- **Do:** compare the fix commit's changed-file list against the files the
  findings name, member by member, before pushing a round.
- **Don't:** read "N findings, N files changed" as the round being covered
  --- the count coincidence is exactly what masked the miss.

**Run that same command before *any* readiness claim, not only against an
inherited one --- a PR whose branch carries no implementation is green on
every check.**

- **Do:** run `gh pr diff <N> --name-only` before reporting a PR ready, and
  read the returned paths against what the PR says it does.
- **Do:** treat an empty return, or a return holding only a `main` merge's
  incidental paths, as the PR carrying no implementation.
- **Don't:** count the claim commit or a `main` merge as work --- neither is
  implementation, and both give the branch a plausible history.
- **Don't:** read all-green CI plus a finding-free review as evidence a PR
  contains anything; on an empty diff that is the expected result.

**When the change affects downstream consumers, validate it against a real
consumer repo before reporting the PR ready --- a package's own test
fixtures are built to exercise its code, not to resemble the packages that
will actually use it.**

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

See [`ardi.cases.md`](ardi.cases.md), "Validating against a real consumer repo
covers what fixtures cannot".

**Verify a blocker you assert in a PR body or a reply, with the same rigor
you apply to a reviewer's claims --- a stated blocker becomes a premise
other people build on.**

**A hold SOMEONE ELSE stated is a premise you inherit, and nothing re-tests
it.**
The rule directly above governs a blocker *you* assert, and the one further
down governs a blocker you have restated until it hardened into the record.
Both are about your own claims.
The mirror is the case nobody owns: a hold written by another agent or another
session --- in a PR body, an issue comment, a handoff note --- with a reason
attached, whose reason later stops being true.

It is worse than a stale blocker of your own, for a reason that has nothing to
do with diligence.
The natural response to someone else's stated hold is deference, and deference
costs nothing at the moment it is chosen: honouring it is always defensible,
and re-testing it looks like second-guessing a peer.
So the hold is read as a fact about the artifact rather than as a claim with a
checkable condition inside it, and it survives exactly as long as nobody feels
entitled to check.

**The tell is a hold with a reason in it.**
"Do not merge" alone is a standing instruction and stays binding.
"Do not merge, because X may not have happened" is a *conditional*, and X is
checkable --- usually in one query.
The two look identical at a glance, because the reason reads as an explanation
of the instruction rather than as its condition.

**A reviewer honouring the hold is not evidence the hold is warranted.**
A reviewer honours instructions; it does not audit them.
It can dissolve the premise itself, in the same comment, and still defer ---
which is correct behaviour and is precisely why it cannot serve as
confirmation.

Testing the premise is yours.
Lifting the hold is not, when it is another party's, so the deliverable is a
verified report to a human rather than the action the hold was blocking.

- **Do:** treat a hold carrying a stated reason as a conditional, and test the
  condition before reporting the item blocked.
- **Do:** report what you found to whoever can lift it, naming the condition
  and the evidence, rather than lifting another party's hold yourself.
- **Don't:** repeat "held" across status reports without having tested the
  premise once --- the repetition is what converts a claim into a fact.
- **Don't:** read a reviewer's deference to the hold as an independent
  endorsement of it.

(`Morrison-Lab/gha#678`, 2026-08-26 to 2026-08-28.
Its body held the PR because the dogfood review might `self_mod`-skip and "a
skip is not a verdict".
Two skips did occur; then gha#674 reached `v2`, a genuine review ran at the
exact head on 2026-08-27 returning **Ready for merge**, and deferred to the
hold anyway.
The PR sat fully clean for two days, and one session reported it as "held by
its own do-not-merge" in three separate status sweeps before testing the
premise even once.)

**Attempting the base form of a command is not attempting its variants ---
a refusal describes the invocation you ran, never the flag you did not try.**

- **Do:** run the flag variant the docs or the error itself name, before
  generalizing a refusal into an impossibility.
- **Do:** scope the published claim to the invocation actually run, naming the
  exact command and what it exited with.
- **Don't:** read an unconditional-sounding error as covering flags you never
  passed.
- **Don't:** count an attempt at the base form as discharging the rule above
  for a variant of it.

**Name the specific gate when you report a blocker, not a category word that
happens to be one of several.**

- **Do:** quote the clause that distinguishes the failure, and name the gate
  it belongs to.
- **Do:** re-read a blocker you have restated several times, since a
  paraphrase repeated across status reports hardens into the record.
- **Don't:** use one mechanism's own name as a generic word for its category.
- **Don't:** treat having verified *that* something is blocked as having
  verified *why*.

**When the blocker is a hang, inspect the process rather than re-guessing
what it is waiting on.**

- **Do:** read `ps -o stat=`, `lsof -d 0`, and the process tree before
  describing what a hung command is waiting for.
- **Do:** say which read produced the answer, so the gate is checkable rather
  than asserted.
- **Don't:** substitute one guessed mechanism for another because a probe
  produced no output.
- **Don't:** report a timeout signal as evidence about *why* something
  blocked; it is evidence only that it had not finished.

**A blocker that was true when you published it can stop being true while
the PR is open, and withdrawing it is your job, not the reviewer's.**

- **Do:** after every `main` merge, scan the PR's touched files for merge-status
  hedges with whitespace-normalizing search, then re-read each hit against the
  new base.
- **Don't:** assume a hedge survived because the file that contained it merged
  without conflicts, or because literal grep missed a phrase split across
  semantic lines.

**Landing a fix falsifies whatever prose documented the defect, and that prose
is never in your diff --- so grep for it rather than expecting to be reminded.**

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

**An instruction's own suggested code is not exempt from the
project-conventions self-review above.**

See [`ardi.cases.md`](ardi.cases.md), "An instruction's own suggested code
breaking a project convention".

**When the code path under test has a staging or transform step between
input and output, a passing unit suite is not evidence it works ---
exercise the real path once.**

See [`ardi.cases.md`](ardi.cases.md),
"A staging step the unit fixtures could not reach".

**When new code branches on a third-party tool's behavior, read that tool's
own config or docs for the specific behavior --- don't infer it from what
the tool broadly does.**

**A regression test written alongside a fix can lock the bug in rather than
catch it --- assert the two paths that diverge, not the one you just
touched.**

**A systematic audit done by skimming is worse than the one-at-a-time
version it replaces.**

**Adding an explanation supersedes whatever the file already said about the
same thing, so re-read the older passage --- your own diff is the likeliest
source of a contradiction nobody flags.**

**The same rule applies within a single diff, and there nothing prompts the
check at all.**

**And when the explanation you add is a *mechanism* claim, test the class it
distinguishes, not just the sample in front of you.**

See [`ardi.cases.md`](ardi.cases.md),
"A mechanism claim whose population held no true positive".

**A symptom that stops reproducing is a fix having landed, until you have
checked otherwise --- reaching for nondeterminism is the attractive wrong
answer.**

- **Do:** look for a merged fix, and date it, before attributing a vanished
  symptom to anything.
- **Do:** report the before/after with its timestamps, so the negative
  control is visible rather than asserted.
- **Don't:** explain a symptom's disappearance as nondeterminism on the
  strength of one clean run.
- **Don't:** carry such a claim into an issue or a decision doc, where it
  argues against the very fix that produced the silence.

**The mirror runs the other way, and it is the one that discards a good fix: a
symptom that KEEPS reproducing after a fix landed is not evidence the fix
failed.**

The bullet above governs a symptom that vanished, where the attractive wrong
answer is nondeterminism.
Here the symptom is still there, and the attractive wrong answer is that the
diagnosis was wrong --- which sends you back to re-litigate a fix that is
working, and leaves the real remaining cause unread.

The mechanism is ordinary and worth naming, because it makes the persistence
expected rather than surprising.
A failure can have causes in series, and only the first one is observable while
it stands.
Removing it does not change the outcome; it changes which cause produces the
outcome.
So the job's colour is the same before and after, and the outcome is the one
thing everybody checks.

**The discriminator is the error, not the outcome.**
Both runs failed, so comparing conclusions establishes nothing.
Comparing the error text is decidable in one read, and a changed error means
the first cause is gone and a second was behind it.
Where the fix is upstream, pin the comparison to the dependency version each
run actually resolved, since a run predating the fix is not evidence about it
--- [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s "mirror
direction" section owns that lookup.

Note the asymmetry that makes this worth a rule.
Reading the new error costs one glance and usually names its own remedy.
Re-litigating the first fix costs a round, and it argues for reverting
something correct --- the same shape the bullet above warns about, where a
claim ends up arguing against the fix that produced the change.

- **Do:** diff the error text across the fix, not the pass/fail outcome, before
  concluding anything about whether the fix worked.
- **Do:** resolve which dependency version each run used, when the fix landed
  upstream, so a pre-fix run is not read as evidence against it.
- **Do:** report a changed error as a second cause found, and file it, rather
  than as the first fix having failed.
- **Don't:** re-open a landed fix because the symptom persists --- that is a
  claim about the outcome, and the outcome is what a serial second cause
  preserves.
- **Don't:** read the earlier bullet as covering this; it fires on a symptom
  that stopped, and this one fires on a symptom that did not.

See [`ardi.cases.md`](ardi.cases.md),
"A trust-gate fix that revealed a tool-name mismatch behind it".

**A third cell: a symptom that stops reproducing AFTER you applied a remedy is not evidence the remedy worked.**

The two bullets above cover the case where you changed nothing and the symptom vanished, and the case where you changed something and the symptom stayed.
This is the remaining one, and it is the only one of the three that ends in a green check --- which is why it is the one that gets reported.

A pass following your change is consistent with the change having fixed it.
It is equally consistent with an intermittent failure that did not fire this time, with something else having moved in the base, and with the failing condition never being reached on this run.
Applying a plausible remedy and observing success is not a controlled test, because no run of the unchanged head exists to compare against.
[`review-verdict-pitfalls`](review-verdict-pitfalls.md) states the complementary half, and its wording is the discriminator: a retry is a genuine negative control "because nothing changed between the two runs".
Change something and you have spent that control.

Three things make this harder to catch than either neighbour.

**The remedy is usually correct to apply.**
Porting a fix that already exists on `main` is what [`sync-with-main`](sync-with-main.md) asks for, so nothing about the action is a mistake.
The causal claim then inherits the action's correctness and is never examined on its own, which is the near-miss: right action, unchecked story, and no moment at which the two come apart.

**Green terminates inquiry.**
A red check invites investigation and a green one closes the question, so the wrong story survives in exactly the place least likely to be revisited.

**The refuting datum is usually free.**
A timeout failure carries its own duration, which is in the job metadata whether or not anyone reads it.

The test is one question, asked before the claim is written: **name the observation that would differ if your change were the cause, and go and look for it.**
For a raised timeout that is a duration falling between the old limit and the new one, so a passing run that finishes inside the OLD limit never reached the raise.
For a widened pattern it is an input matching the new alternative and not the old.
For an added dependency it is the code path that requires it.
Where the passing run does not show that observation, you have a green check and no evidence, and the honest report says the check passed rather than that your change fixed it.

- **Do:** name what the passing run would have to show if your change were the cause, and read that field before reporting causation.
- **Do:** report the pass as "the check passed" until that observation is in hand, and say separately that the remedy is worth keeping on its own merits.
- **Do:** compare a timeout's passing duration against the OLD limit --- a run finishing inside it proves the raise was never exercised.
- **Don't:** read a correctly-applied remedy as licensing the claim that it worked;
  the action being right is what carries the claim past review unexamined.
- **Don't:** treat a single pass as a controlled test --- changing something is precisely what removes the negative control a bare retry would have given.

See [`ardi.cases.md`](ardi.cases.md), "A green check credited to a timeout raise that never ran".

**Verify a command, path, or flag *you* write into a doc, with the same rigor
[`address-every-comment`](address-every-comment.md) demands for one a reviewer
suggests.**

- **Do:** confirm every literal you invent against the tool's own source or
  help output before it lands in a doc.
- **Do:** cite the file or command you checked, so the claim stays falsifiable.
- **Don't:** infer a subcommand from a family that has its siblings
  (`gh label list`/`create`/`edit` does not imply `gh label view`).
- **Don't:** treat a literal as exempt because the prose around it is
  well-sourced --- the literal is the part a reader executes.

**Run that check over your own fix, too --- the remedy for an unverified
literal is where the next unverified literal goes.**

- **Do:** re-run the rule you are applying against the text of your own fix,
  before committing it.
- **Do:** say in the thread when a fix's own draft tripped the same rule,
  since that is the only place the near-miss is visible.
- **Don't:** treat the effort of writing a correction as evidence the
  correction is verified.

**The same rule reaches past a literal, to the defect CLASS a code fix just
closed.**

**A consolidation commit is the highest-risk host for it, and the likeliest to
be trusted.**

- **Do:** ask whether the fix's own new code instantiates the class it closed,
  before committing it.
- **Do:** treat a commit that consolidates one duplicated concept as owing a
  check that it forked none, since its framing argues the other way.
- **Do:** compose an existing shared anchor or helper into a new site rather
  than hand-rolling an equivalent, so the site inherits later fixes too.
- **Don't:** read a diff that removes a duplicate as evidence that it added
  none.
- **Don't:** treat the next round's finding at a new address as a fresh gap
  without first checking whether your own previous fix created that address.

**When regenerating a generated tree makes it most of the diff, say so in the
PR body --- otherwise a reviewer reads it as pollution and blocks.**

- **Do:** grep a file for a generated-by header before editing it, and change
  the source instead.
- **Do:** state in the PR body how many of the changed files are generated,
  and name the hand-written ones.
- **Don't:** revert generated output because a reviewer calls it noise ---
  check first whether the sync check requires it.
- **Don't:** assume a reviewer sees the source files; on a large diff they
  frequently do not.

See [`ardi.cases.md`](ardi.cases.md), "Editing generated output, then being read
as pollution once regenerated".

**Run the whole test suite before pushing, not the files you predict the
change touches --- and check that the ones you ran were not silently
skipped.**

**Matching the tool's VERSION is not matching its ENVIRONMENT, and when the
tool GENERATES a file you are about to commit, the gap ships.**

**Read the generator's own diagnostics first**, because a good one says so
outright and names the cause.

**The file list is the backstop**, for a generator that degrades with no
diagnostic, or one whose diagnostics scroll past in a long run.

- **Do:** read the generator's own warnings before its output --- roxygen2
  names the missing package and the tag that needed it.
- **Do:** compare your generator's changed-file list against the CI log's, and
  treat any extra file as an environment mismatch until explained.
- **Do:** install the optional/dev dependency set as well as the tool, when a
  generator loads the package to do its work.
- **Don't:** read "I installed the same version CI installs" as having matched
  CI --- version is one input to the output, and rarely the one that differs.
- **Don't:** commit generated output whose diff is wider than the job you are
  trying to satisfy reported.

See [`ardi.cases.md`](ardi.cases.md), "A generator's environment, not its
version, changed the committed artifact".

- **Do:** run the full suite before pushing, and state the tests/failed/
  skipped triple rather than "tests pass".
- **Do:** set the flags that un-gate conditional skips, and re-run if the
  skip count is non-trivial.
- **Don't:** scope a local run to the files you edited --- the test asserting
  the old behaviour is usually somewhere else.
- **Don't:** read a green subset as a green suite, or a skip as a pass.

**Running a script is not running its tests, and an "advisory" check can have a
hard-gating twin.**

- **Do:** run every check the CI job runs, its test files included, before
  pushing.
- **Do:** grep the job definition for other steps touching the same property
  before saying anything about whether it gates.
- **Don't:** substitute a production script's exit code for its test file.
- **Don't:** infer a job's behaviour from one step's label --- "(advisory)"
  describes that step, not the job.

**A third failure mode of the whole-suite rule above: the suite holds no case
that could have failed.**

- **Do:** construct the input class the change is supposed to handle and diff
  its behaviour against the pre-change code, before calling a guard verified.
- **Do:** name which cases could have exercised the defect class, rather than
  quoting a suite total --- the total is a fact about the suite, not the diff.
- **Don't:** offer a pre-existing suite's green as verification of a change it
  holds no case for; those cases predate the defect and cannot speak to it.
- **Don't:** read the tests/failed/skipped triple above as covering this --- it
  makes the report more precise without making it any more relevant.

**A fourth failure mode: the case exists, and which branch it reaches is
decided by the host.**

- **Do:** name in the test which host-derived value selects which branch, and
  add a case that pins each branch regardless of that value.
- **Do:** run a host-dependent suite in both environments before believing its
  coverage, and say which branch each run took.
- **Don't:** read green in CI as covering a branch whose selection depends on
  an input CI happens to supply one way.
- **Don't:** reach for the skip count here --- nothing is skipped, so that
  component is identical on both machines even when the failed counts diverge.

See [`ardi.cases.md`](ardi.cases.md), "A suite whose branch coverage varies by
host".
