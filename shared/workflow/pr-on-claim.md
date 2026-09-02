When an agent claims an issue it's about to work --- in `gi`, `gii`, `gip`, or
`st` --- open the PR **immediately**, before writing any code, and keep it a
**draft** until the implementation lands. Don't wait until the work is done to
open it.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`pr-on-claim.rationale.md`](pr-on-claim.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`pr-on-claim.cases.md`](pr-on-claim.cases.md), moved out of the auto-loaded context.

**Why up front.** The claim comment on the issue is easy to miss, and it isn't
what other sessions check. The authoritative in-flight signal is the issue's
cross-referenced **open PRs** --- the check `gi` runs before grabbing an issue.

**Mechanics.** Branch, then open the PR against an empty commit:

```bash
git fetch origin main -q
git checkout -b <type>/<slug> origin/main
git commit --allow-empty -m "start: <issue title> (closes #<N>)"
git push -u origin HEAD
gh pr create --draft --title "<title>" --body "Closes #<N>

WIP --- opened up front to claim the issue; implementing now."
```

On Claude Code prefix that push:

```bash
ALLOW_UNREVIEWED_PUSH=1 git push -u origin HEAD
```

The guard requires a reviewer-call result
before it reaches the commit comparison,
including for an empty commit
(see [`push`](../../skills/push/SKILL.md)).

**Do not `Closes` a parent issue on a partial ship.** `Closes #<N>` in the
draft body is the default because most issues are one slice. If the issue
(or a later comment) splits into independent cases and this PR only
implements one, file the leftover as its own issue before merge and
rewrite the PR body so it does not auto-close the parent.

- **Do:** keep `Closes #<N>` when the PR will finish every remaining case.
- **Do:** file the deferred case first, then change the PR to link both
  (`Fixes the Case B half of #N; remainder is #M`) with no `Closes` on
  the parent.
- **Don't:** leave `Closes #<N>` on a PR that explicitly deferred part of
  `#N` --- GitHub will close the parent and the deferred half disappears
  from the tracker
  ([gha#373](https://github.com/Morrison-Lab/gha/issues/373) /
  [#516](https://github.com/Morrison-Lab/gha/pull/516) /
  [#517](https://github.com/Morrison-Lab/gha/issues/517)).


**Draft, not ready-for-review --- deliberately.** A draft doesn't trigger the
`@claude` review bot, so no review round is spent on an empty or half-finished
diff. Implement on top, pushing commits to the same PR; when the change is
complete and the repo's checks pass, mark the PR **ready for review**
(`gh pr ready <N>`, or `mcp__github__update_pull_request` with `draft: false`).

**Marking a draft ready is a push-landed checkpoint, so verify the
implementation actually reached the branch head before `gh pr ready`.**

- **Do:** run the push-landed and non-empty-diff checks at the `gh pr ready`
  transition, exactly as before a reply asserting a push.
- **Don't:** mark a draft ready on the strength of a local commit, green checks,
  and an updated PR body --- none of those proves the branch head moved.

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"Marking a draft ready is a push-landed checkpoint".

**Request the external reviewer in the same stride.** Opening a PR or marking a draft ready can trigger the repo's own review workflow, but that does not summon every reviewer.

**Run that `requested_reviewers` POST as the sole (or last) command in its Bash call.**

- **Do:** issue the Copilot-request POST as its own Bash call, with nothing chained after it.
- **Don't:** fold the `--json reviews` / `gh pr checks` verification into the same call --- that makes the request non-last, and the hook cannot discharge it.

**"Nothing chained after it" includes a pipe added purely to trim the output.**

- **Do:** narrow the response with a flag on the POST itself rather than a downstream pipe.
- **Don't:** pipe the POST anywhere, including to `tail`, `head`, or `jq` --- the hook cannot tell a formatting pipe from a chained verification, because the shell does not either.

**A PreToolUse block for this was considered and rejected -- the Stop hook stays the only guard.**

- **Do:** treat the Stop hook's post-hoc catch as sufficient for this specific mistake, and re-run the POST alone when it fires.
- **Do:** re-open this question only once the mistake has recurred as a **dated, repeated** incident, per [`deterministic-tools`](../principles/deterministic-tools.md)'s "third occurrence" bar for building a tool -- not merely because it could recur.
- **Don't:** reuse the Stop hook's `last`-computation for a PreToolUse block without re-deriving which direction is safe for THAT consequence -- the bias that is safe for a nag is not safe for a refusal.
- **Don't:** read "the underlying question is decidable" as sufficient justification on its own; a genuinely safe block still needs the same order of adversarial hardening `no-unauthorized-merge.py` needed, and that cost has to be weighed against what is actually being prevented.

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"The reviewer-request POST must be the sole command in its call".

**Some repos schedule Copilot automatically, and this step is redundant there.**

**That blocked-request test has a false positive, and it fires on more repos than the section above describes.**

**The operative point is that three surfaces fail to discriminate here, and only a fourth one does.**

- **Do:** decide whether a reviewer is engaged by reading its posted review body, since the pending list, the ruleset, and the check run each fail to discriminate.
- **Do:** check for a `copilot_code_review` rule before concluding that a vanished pending request means a blocked one.
- **Don't:** read an empty pending list as evidence the request was blocked, nor as evidence a review is on its way.
- **Don't:** treat a negative ruleset result as establishing that the request failed --- ai-config returns exactly that while the request still reaches Copilot.
- **Don't:** re-POST on a repo whose ruleset auto-requests while a `copilot-pull-request-reviewer` check run is queued or in progress on the head --- the retry changes nothing and the empty read repeats.
  A completed run on an unchanged head is no veto: a Rebut/Defer-only round pushes nothing, and [`skills/ardi/SKILL.md`](../../skills/ardi/SKILL.md) requires a fresh request there.
  A ready head with no such run about a minute after the push is the other case, measured per push in [`memories/copilot-reviews.md`](../../memories/copilot-reviews.md): there a run followed the request within seconds, an observed sequence rather than a proven cause, and a merely delayed run makes the request a duplicate that spends one call, the accepted risk.

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"Three surfaces fail to discriminate a vanished pending request".

**Requesting Copilot discharges nothing when the repo's own reviewer runs on `workflow_dispatch` alone.**

- **Do:** read the review workflow's `on:` block, and dispatch explicitly when it carries no push-based trigger.
- **Do:** treat "I think this is ready" as the trigger to request the review, rather than as the moment to start waiting for one.
- **Don't:** count a successful Copilot `requested_reviewers` POST as the review obligation discharged on a repo whose primary reviewer is dispatch-only.
- **Don't:** read all-green checks with nothing pending as a review in flight.
  On such a repo that is the steady state rather than a transient one.

**The `Stop` hook cannot catch this, and its silence is why the rule has to be stated in prose.**

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"Requesting Copilot discharges nothing on a dispatch-only repo".

- **Do:** request the reviewer explicitly in the same step that opens the PR or marks it ready.
- **Do:** verify the request landed from the API response plus a fresh pending-request or current-head-review read.
- **Don't:** treat a PR's auto-triggered checks as evidence that every reviewer is engaged.
- **Don't:** write "review owed" or "still need to request review" into a status report; go request it instead.

**A REDACTION PR is the one case where requesting the reviewer is the harm, and it needs recording rather than silence.**

- **Do:** hold the automated review on a redaction PR, and record why with the label or the assertion.
- **Do:** ask a human to review it, which is the review it actually needs.
- **Don't:** request an AI reviewer on a diff whose removed lines are the thing being redacted --- the merged result being clean says nothing about what the reviewer read.
- **Don't:** mark such a PR draft to stop the guard asking.
  That misstates the reason and stalls its own review loop.

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"A redaction PR must not get an AI reviewer".

**Don't mark ready within seconds of the final push --- the two review runs race and the WRONG one can get cancelled.**
On repos whose review workflow runs on `pull_request` (`synchronize`, `ready_for_review`) with `concurrency: cancel-in-progress`, a push followed immediately by `gh pr ready` fires two runs a second apart, and the cancellation can land on the newer one, leaving the current head with a cancelled review job and a red require-review check while an older, nominally-stale run posts the real verdict.
See [`pr-on-claim.rationale.md`](pr-on-claim.rationale.md) for the full mechanism and the recovery command.

**The race has a second, sharper failure direction, and it is worse than a cancellation: no `ready_for_review` run at all.**
A cancelled run at least leaves a check to read and a run to re-run.
This direction leaves nothing --- no cancelled run, no red check, just an event GitHub never fired.
Measured on `Morrison-Lab/gha#702`, 2026-08-28: `git push` and `gh pr ready` issued in the same shell invocation, roughly 3 seconds apart, produced only the push's `pull_request`/`synchronize` run --- which correctly skipped, since the PR was still draft in its own event payload --- and no `ready_for_review` run whatsoever, confirmed by listing every run of the caller workflow in the window (`gh run list --workflow=<caller>.yml`), not by reading a single run's conclusion.
The PR sat CI-green and comment-free, which reads from the thread exactly like "review pending" rather than like anything broken.
The same push-then-ready sequence with roughly 30 seconds between the two commands, on `Morrison-Lab/gha#704` the same hour, produced both runs, with the `ready_for_review` one reviewing normally.
Recovery: dispatch the review workflow directly with the PR number (`gh workflow run <caller>.yml -f pr_number=<N>`), since re-mentioning the bot has nothing to react to when no run exists.

- **Do:** leave a deliberate gap of tens of seconds, not one or two, between the final push and `gh pr ready`.
- **Do:** confirm a `ready_for_review` run actually exists (`gh run list --workflow=<caller>.yml`) before waiting on its review, rather than trusting green CI and silence to mean review-in-flight.
- **Don't:** read a green-CI, comment-free PR as "review pending" without checking that a run exists for the ready event --- an absent run and a slow one look identical from the thread.
- **Don't:** assume a several-second gap is safe because an earlier incident used one too --- gha#702's roughly-3-second gap dropped the run entirely, while gha#704's roughly-30-second gap produced both runs cleanly.

**Check whether the race can even arise before paying for that wait --- on
many repos it cannot, and the check is one field.**

**Reading the caller's `on:` block is not reading the workflow's trigger
conditions, because a reusable workflow gates independently --- at job level,
in another repo.**

- **Do:** follow a `uses:` delegation to the called workflow at its pinned
  ref, and read the job-level `if:` there, before concluding anything about
  when a review fires.
- **Do:** treat a caller whose only content is `on:`, `permissions:`, `uses:`,
  and `with:` as having told you nothing about gating.
- **Don't:** read a caller's `on:` types list as the trigger condition --- it
  is the widest of the two constraints, and the narrowing is in the callee.
- **Don't:** conclude a repo lacks a draft gate from the absence of `draft` in
  the file you happened to open.

See [`pr-on-claim.cases.md`](pr-on-claim.cases.md),
"A caller's `on:` block is not the workflow's trigger conditions".

So the per-issue order becomes: claim → cut a worktree and branch → **open the draft PR now** →
implement → mark ready-for-review → ARDI.

**Working several issues in one session?
Verify you are actually in the second issue's worktree, on its branch, before writing its code.**
The worktree cut for issue 1 does not carry over to issue 2:
cut a new one for each issue, and `cd` into it,
since `git worktree add` leaves the shell where it was
([`memories/git-worktrees.md`](../../memories/git-worktrees.md)).
On the no-worktree fallback path the same slip is forgetting to run
`git checkout -b <type>/<slug> origin/main` again with a new branch name.
Either way the working tree stays on issue 1's branch, so issue 2's edits land
in the same commit/PR as issue 1's --- silently, since nothing errors (there is
no reused branch name here to trigger `git checkout -b`'s own "already exists"
error).

**The open-PR check fails silently in the one situation it exists for, and a hook now carries it.**

Every rule above assumes the check gets run.
The measured failure is that it does not, and that nothing about the moment suggests it was skipped.

Measured on `Morrison-Lab/wai`, 2026-08-19/20.
Five branches attacked the same `check-non-standard-chars` failure across roughly five hours: `fix/replace-em-dashes` (20:14), `fix/replace-em-dashes-v2` (23:29), `fix/replace-all-non-standard-chars` (23:38), `fix/all-non-standard-chars` (00:16, which became #77), and `fix/ascii-punctuation` (01:16, which became #78).
Three further branches --- `fix/fix-review-77`, `fix/fix-review-77-cleanup`, and `fix/fix-review-findings` --- addressed review findings on those five.
Two reached PRs and duplicated each other.

**The session that opened the fifth had filed the tracking issue minutes earlier.**
That is the whole difficulty.
Filing an issue and opening a PR against it is the issue-first workflow performed correctly, so it reads as compliance from the inside --- there is no moment that feels like skipping a step, because the skipped step is a *query about other people* rather than anything in your own sequence.

**The parallelism runs the wrong way, too.**
The more sessions working a repo, the likelier a collision and the less any single session can observe it.
So the check matters most exactly when the evidence for needing it is least visible, which is why judgment does not reach it and an instrument has to.

**One of those duplicates was actively dangerous, not merely wasteful.** #77 was cut from an unrelated PR's branch while targeting `main`, so it carried that PR's content two review rounds stale.
Merging it would have shipped a version of that PR's content which that PR's own reviewer had already rejected, under a title describing something else entirely.
A duplicate is not always the cheaper of two equivalent paths;
check what else the branch is carrying before picking one.

- **Do:** run `gh pr list --repo <owner>/<repo> --state all --search "<keywords>"` before creating a PR, not only before claiming an issue.
  `--state all` rather than `--state open`, per [`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md): a PR that merged minutes ago is invisible to an open-state search and is the likeliest duplicate there is.
- **Do:** check what a duplicate branch is *based on* before choosing between it and yours --- a branch cut from another PR ships that PR's content too.
- **Don't:** read "I filed the issue and am opening its PR" as evidence the in-flight check ran;
  those are different steps and only one of them looks at other sessions.
- **Don't:** treat a low collision probability as a reason to skip it --- the probability is unobservable from inside a single session.

`hooks/warn-pr-create-without-dupe-check.py` mechanizes this, per [`algorithmatize-checks`](algorithmatize-checks.md).
It warns rather than blocks: a duplicate PR is cheap to close, while a blocked `gh pr create` interrupts the one action that makes work visible to other sessions.

[`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md) carries the query rule in full, with the negative control showing that only `--state all` discriminates.
Read it before opening a PR, not only before scaffolding a new tool.
It also settles the two absence readings this check turns on: an absent remote branch means merged-and-deleted until a query that can see merged work says otherwise, and searching a *predicted* branch name is the same failure one axis over, since it enumerates a guess instead of deriving the population.

**One reading it does not cover: a `base..branch` commit range cannot answer "is this merged" in a squash-merging repo, at any freshness.**
`git log <base>..<branch>` lists the branch's commits whenever they are not ancestors of the base, and a squash merge puts the content on the base under a new commit the branch never saw --- so the range reports unmerged work for work that merged.
Re-fetching does not help, which is the trap: the reading looks like it expired rather than like it was never able to answer.

Measured 2026-08-22, with `origin/main` equal to the remote tip:

```
origin/main = 8811682d
range: 2 commits
content diff empty? exit=0
is-ancestor exit=1
```

Two commits listed, and `git diff <base> <branch>` empty.
So compare trees, or ask the forge, rather than counting commits.

`git merge-tree` answers neither question.
A branch whose content is already on the base normally merges cleanly, because both sides carry the same change --- so a clean result is compatible with the branch being wholly redundant.
The converse fails too: a redundant branch conflicts as soon as the base edits the duplicated content afterwards.
Merge-tree answers "will this apply", never "is this new".

- **Do:** settle whether work is merged from the PR's own state, or from whether the branch's own additions are present in the default branch's current content.
- **Don't:** read a non-empty `<base>..<branch>` range as unmerged work in a squash-merging repo --- it says nothing there, however fresh the base.
- **Don't:** read a non-empty two-dot `git diff <base> <branch>` as unmerged work either, for the same reason the range can't say it: the base advancing past the fork point makes the diff non-empty on its own, whether or not the branch's own content ever landed.
  Scoping the diff to the branch's own files does not fix this --- a sibling PR that touched the same file after the fork reproduces the same confusion.
  Use a one-directional `git diff <base>...<branch>` (three-dot, merge base on the left) to isolate the branch's own additions, then confirm those specific lines are present in the base with `git show <base>:<path> | grep -c '<distinctive phrase>'`.
- **Don't:** offer a clean or a conflicting `merge-tree` as evidence either way about novelty.

(Measured 2026-08-22 on `Morrison-Lab/ai-config`.
A worktree sweep found a local branch with two commits and no remote counterpart, and read it as unpushed work worth rescuing.
It had merged as [#1995](https://github.com/Morrison-Lab/ai-config/pull/1995) six minutes earlier.
The duplicate went out as [#1998](https://github.com/Morrison-Lab/ai-config/pull/1998), with [#1997](https://github.com/Morrison-Lab/ai-config/issues/1997) as its tracking issue, and its diff against the post-merge `main` was empty.
The rule above already existed in the fragment named at the top of this passage, which was linked from six files and not from this one --- so the session that needed it was reading the page that lacked it.
Tracked as [ai-config#1999](https://github.com/Morrison-Lab/ai-config/issues/1999).)

**The non-empty case is not exotic --- it is what a two-dot diff shows for most merged branches in an active repo, including the branch that produced this correction.**
`ums-quarto-format-scope` merged as [#3004](https://github.com/Morrison-Lab/ai-config/pull/3004).
Measured 2026-09-02, minutes after a later, unrelated PR ([#3016](https://github.com/Morrison-Lab/ai-config/pull/3016)) merged into `origin/main`: `git diff origin/main ums-quarto-format-scope` ran to 2839 lines across 30 files, not empty, purely because `origin/main` had moved on.
The one-directional `git diff origin/main...ums-quarto-format-scope` isolated the branch's own additions to 120 lines in two files, and `git show origin/main:memories/quarto-sites.md | grep -c "reaches every document that declares no"` returned 1, confirming the added section was already there verbatim.
A reader trusting the two-dot diff alone would have read this fully-merged branch as unestablished.
