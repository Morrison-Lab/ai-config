"Fully clean" is the terminal state the ARDI review loop drives toward.
A PR/MR is **fully clean** when **both** of these hold:

1. **All CI workflows and check runs are green AND completed.** Every workflow and check run passes --- not just the required checks and not just the review job.
   "Green" means finished with a passing outcome (success or skipped), not merely "currently reporting green while still running" --- never treat a workflow or check run that's still queued or in progress as clean, even if nothing has failed yet.
   **A reviewer's posted verdict does not mean the review check has finished, so don't let a clean verdict stand in for criterion 1 on its own job.**
   The bot posts its comment and then its run keeps going (bookkeeping steps, a cost tally, the gate job that consumes its result), so a full `Ready for merge` comment can sit on the PR for minutes while `claude-review` still reads `in_progress` and the `require-review` gate is still `queued`.
   Reading the verdict and moving straight to "clean" skips the very state this criterion exists to catch.
   The gap runs the other way from the stub-review case below: there the check is green and the verdict is missing, here the verdict is real and the check is unfinished.
   Re-read the check runs after the verdict lands, not just before.
   (ai-config#712, 2026-07-24: the round-2 verdict posted at `04:06`, about two minutes before its own `claude-review` job completed at `04:06:56` and `require-review` at `04:07:03`.) (The exact field names and casing for these states differ by API surface --- REST's check-runs endpoint returns lowercase `status`/`conclusion` strings like `completed`/`success`, while `gh pr checks`/GraphQL's rollup returns uppercase `state` values like `SUCCESS`; don't hard-code one casing when scripting a check.)
   **A raw Actions workflow run and a check run are not the same thing, and the usual lookups (`gh pr checks`, `get_check_runs`) only cover check runs (plus legacy commit statuses) --- not every workflow run necessarily produces one.** A workflow run that's blocked on `action_required` (e.g. pending manual approval) before any job starts can complete with zero jobs and consequently zero check runs, making it invisible to a check-runs-only poll. This normally doesn't affect mergeability (GitHub's branch-protection required-checks gate operates on checks, not raw workflow runs, so a check-run-less run can't be wired as required), but if something about a PR's CI state looks off despite `gh pr checks` reporting all-clear, cross-check the raw workflow runs before trusting the checks-only view. **`gh run list --commit <head-sha>` is not a reliable substitute for this cross-check on its own**: it returns every attempt for that SHA (including superseded/cancelled re-runs, so an old failed attempt can look like an outstanding blocker), and a run triggered by `issue_comment` or a `workflow_dispatch` invoked without an explicit `ref` can be recorded against the default branch's SHA rather than the PR's head SHA and be missed by a `--commit` filter entirely. Neither `--commit` nor `--branch` is fully reliable for this, because GitHub itself does not record a reliable PR linkage for these trigger types: an `issue_comment`-triggered run on this very PR (#635, run 29967418653) recorded `head_branch: main` and an empty `pull_requests` array via the raw REST API (`GET /repos/{owner}/{repo}/actions/runs/{id}`) --- verified directly, not assumed --- so no single filter (commit, branch, or the API's own PR-linkage field) reliably narrows these runs to the ones for this PR. Treat this cross-check as best-effort: `gh run list -R <repo> --workflow <name>` (unfiltered, or windowed by approximate timestamp) and eyeball for anomalies near when the PR activity happened, rather than trusting any one filtered command to be exhaustive.
   This includes non-gating checks like the Coverage / codecov job: don't merge around a red Coverage run just because it isn't a required check, unless there's a specific, stated reason for that merge (the project wants to maintain decent coverage, so a red Coverage job is a real signal to fix, not to ignore).
   **`codecov/patch` is a separate check from the repo's own Coverage workflow job, and both must be green.** The Coverage job runs the coverage-instrumented test suite; `codecov/patch` is the Codecov service's own status check, gating the PR's DIFF against a minimum patch-coverage percentage --- a repo can have a fully green Coverage job while `codecov/patch` still fails (uncovered new lines in the diff). When delegating implement-a-PR work to a subagent, name this check explicitly in the brief ("ensure `codecov/patch` passes, not just the test suite") --- a subagent that only runs the local test suite and checks it's green has no way to know it also needs to check a service-side status check unless told.
   **The set of checks is not fixed while the run proceeds, and a check run's
   name is not unique --- so "the ones I was waiting on went green" is not the
   same statement as "every check is green".**
   A job can spawn further jobs when it completes, so the total grows *after*
   you started watching.
   Nothing announces that, and the natural mental model is a fixed list
   draining toward zero, which makes the growth invisible precisely when you
   are closest to declaring ready.
   Re-fetch the whole list each time and re-count it, rather than checking off
   the names you remember.

   The name collision is the sharper half, because it turns a careless check
   into a confidently wrong one.
   Two check runs can carry the *same name* on the same head --- an earlier
   one that already succeeded, and a later one still running --- so matching
   on the name returns the stale green and reports the PR ready while the
   other is still going.
   They are usually not re-runs of each other: the common case is two
   separate workflow runs that each happen to define a job by that name, so
   neither replaces the other and both are legitimately present.
   Key on the check run's **id**, and read `status` before `conclusion`, since
   a run still `in_progress` has no `conclusion` to be misled by.

   (`ucdavis/bcs#458`, 2026-07-29: a check-in found the three jobs it was
   watching all green and would have called the PR clean, except the count had
   gone from 17 to 20 --- `update-snapshots` had finished and spawned a
   cross-platform R CMD check matrix.
   Two of those three were still running, and one was a *second* check run
   named `ubuntu-latest (release)`, alongside the original that had succeeded
   14 minutes earlier.)

   **`status` itself can be stale, so never infer a job's *duration* from it.**
   Reading `status` before `conclusion` is right, and it invites a second
   inference that is not: that a run still showing `in_progress` is still
   running, and therefore that the time since `started_at` is how long it has
   been going.
   The field lags.
   A job can read `in_progress` for minutes after it has actually finished,
   so "started at T, still in_progress now" measures the API's freshness
   rather than the job's runtime.

   That is harmless while you are only waiting for a job to end, which is the
   usual reason to read the field --- the lag costs a poll.
   It inverts the answer whenever **duration is itself the diagnostic**.
   A reviewer job that dies on a bad credential and one that genuinely
   reviews a diff differ mainly in how long they take, so a stale
   `in_progress` is indistinguishable from exactly the recovery you are
   watching for, and it arrives as good news.

   Take duration from the log's own timestamps --- first line to
   `Cleaning up orphan processes` --- or from `completed_at` minus
   `started_at` once the run really is complete.
   Both are facts about the job; `status` at any given moment is a fact about
   the API.

   - **Do:** read elapsed time from log timestamps whenever the length of a
     run is the thing being judged.
   - **Don't:** conclude a job is still running, or has passed some duration
     threshold, from `in_progress` plus the wall clock.

   (`d-morrison/altdoc#96`, 2026-07-30: `claude-review` had failed six times
   in ~26 seconds each, the signature of the model call failing at auth.
   A re-run was polled twice, three minutes apart, and read `in_progress`
   both times --- reported as "the reviewer has recovered", and acted on by
   firing a second re-run on the sibling PR.
   The log showed that job starting at `04:05:25` and cleaning up at
   `04:05:51`: 26 seconds, identical to the other six.)

2. **The latest review is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.
   A rebuttal the reviewer still disputes does **not** count as clean.
   That review must be a genuine posted verdict at the current head commit,
   from an external reviewer if one is reachable --- self-review is a
   fallback for when no working external reviewer is available, never a
   substitute once one is (see the `ardi` skill's step 2 for the
   availability-recheck procedure).
   Re-check availability right before declaring clean, not just at whichever
   round self-review first started; an inferred "probably clean" from green
   CI and resolved threads does not satisfy this.

**A clean CI run and a clean review verdict are a snapshot, not a standing
guarantee of mergeability.** `main` can advance after your last check ---
including gaining its own independent addition that collides with yours
(see `sync-with-main.md`'s "two PRs append the same numbered subsection" case)
--- so re-verify the branch still merges cleanly against current `main`
before reporting a PR ready, not just trust the last green run.

**Re-check version parity in that same sweep, not only conflict-freedom.**
[`sync-with-main`](sync-with-main.md) already covers comparing `DESCRIPTION`
versions *after merging `main` in*.
The case that rule misses is the one with no merge at all: `main` advances on
its own after your last review round and lands on the branch's exact version,
so an R package's `version-check` job (which requires the branch to *exceed*
`main`) goes from green to red with nothing to point at.
There is no conflict, no failing check yet, and no warning --- the last run
passed because `main` was still a version behind when it ran.
So the declare-ready sweep needs both `git merge-tree` for conflicts and a
direct version comparison; either one alone reports a PR ready that isn't.
(`UCD-SERG/serocalculator#392`, 2026-07-25: the final pre-declaration check
found `main` had reached `1.4.1.9016`, exactly the branch's version, minutes
after a clean `Ready for merge` verdict on an otherwise all-green head.)

**Threads:** at fully-clean, every **inline** review thread is resolved, and the only conversation left open is the final all-clear exchange --- the reviewer's all-clear comment and your reply to it. (The all-clear is usually a top-level PR comment, not an inline thread.)
Check this mechanically rather than from a memory of which threads you
replied to. Which field name to look for depends on the surface: the GitHub
MCP tool `pull_request_read` `get_review_comments` returns thread objects
under a `review_threads` key with snake_case `is_resolved`/`is_outdated`,
while a raw `gh api graphql` `reviewThreads` query --- what
[`resolve-pr-threads`](../../skills/resolve-pr-threads/SKILL.md),
`pr-status`, and `ard` use --- returns camelCase `isResolved`/`isOutdated`.
Both are correct on their own surface; this is the same REST-vs-GraphQL
casing split the check-state paragraph above already warns about, so read
the response you actually get rather than assuming one spelling. Either way,
sweeping for the unresolved ones is the entire check. An
**outdated** thread (`is_outdated: true` --- the code it anchored to has
since changed) still counts as unresolved: addressing a finding and resolving
its thread are separate actions, and only the second clears this criterion.
An addressed-but-unresolved thread reads as outstanding work to every later
reviewer, which is exactly what this criterion exists to prevent.

**One finding can own two threads, so sweep by thread id rather than by
finding.**
When a reviewer re-raises an item you already answered, the re-raise often
opens a **new** thread instead of continuing the original --- same file, same
line, same finding, different `threadId`.
Resolving the one you remember replying to therefore leaves a second thread
behind, and it is easy to miss twice over: it is usually marked
`is_outdated: true` (the line it anchored to has since changed), and your own
memory of the exchange says the item was settled.
Neither of those clears it.
Re-read the thread list before declaring clean and resolve every entry whose
`is_resolved` is false, whatever you recall about the finding it carries;
reply on the second thread too, pointing at the first, so a reader landing on
either one sees the resolution.
(`d-morrison/altdoc#61`, 2026-07-25: the round-4 re-raise of an unused fixture
parameter opened `PRRT_...TyfeQ` alongside the original `PRRT_...TyeRc`;
resolving the original left the re-raise outstanding, caught only by a
mechanical sweep of all seven threads.)

**Deadlock -> escalate to a human.** If you and the reviewer(s) can't reach consensus on an item (a rebuttal was exchanged and neither side is budging), don't loop forever and don't unilaterally override the reviewer --- request a **human reviewer**, `@`-mention them in a comment summarizing the impasse, and surface the open item.

**An automated reviewer's verdict on a disputed factual/technical claim is not stable across independent runs, even with identical evidence available each time.** Don't treat one round's "settled, no need to keep arguing" as durable: the very same review job, re-triggered later with no new code changes, can re-raise a claim it previously retracted --- and then retract it again on a subsequent run --- purely from re-deriving the question differently each time, not from anything changing in the PR. This means a rebuttal thread's outcome (however many rounds of citations and counter-citations) doesn't itself resolve a genuine deadlock the way a human's decision does; only escalating per the bullet above actually settles it. The one thing that DOES help going forward: fold the authoritative citation/evidence directly into the code or doc being reviewed (a comment, not just a PR conversation reply) --- a fresh reviewer run re-deriving the claim from scratch is more likely to find the citation sitting right next to what it's evaluating than to dig through prior thread history for it, though even that is not a guarantee against a bot that ignores context already in front of it. (Sparta#852, 2026-07-14: the same `@claude` review job's independent runs on this PR gave three different verdicts on the identical `gitglossary(7)`-backed pathspec claim across three re-triggers with no intervening code change to the claim itself --- "settled, accurate" -> "backwards, needs more work" -> "accurate after all, retracting my own prior finding" --- resolved only once the human merged it directly rather than by winning the argument with the bot.)

**A review job's pass/fail conclusion can diverge from whether a genuine clean verdict was actually posted --- check both directions, not just the check's color.** The familiar direction: a green review job that posted only a stub with no verdict (a stalled/crashed review run) is NOT a clean verdict --- re-trigger and read the actual comment before trusting green.
The inverse, easy to miss: a review job reporting FAILURE can still have posted a complete, genuine "Ready for merge" verdict with real findings-review content --- some guard scripts that gate the job's own pass/fail on detecting a verdict string can misfire and report failure even though a full review ran and passed.
Read the posted comment body, not just the check conclusion, before concluding a PR is or isn't clean.
If the check is a **required** check and you've independently confirmed the posted content is genuinely clean, that is still not authorization to merge past it yourself --- a required check failing is exactly the "stop and ask" case even under a merge-when-confident grant (see `mwc`'s scope note); report the evidence and let the human decide whether to override, fix the guard script, or relax branch protection. (Learned on sparta#590/#594/#598, 2026-07-02: two independent PRs hit the inverse misfire in the same session, and an attempt to merge past the required check on verified-clean content was correctly blocked by the harness's own permission system.)

**A third case, distinct from either misfire above: some checks are designed to NEVER fail regardless of their own posted content, so their green color carries zero signal at all.** A CI-runner-relative benchmark check that gates a soft threshold (e.g. "regressed beyond 20% vs. baseline") may deliberately report success/pass at the GitHub-check level even when it posts a `:warning:` regression comment, precisely because the project has decided that threshold is "a human call, not an auto-block" rather than a hard gate. `gh pr checks` (or the equivalent status API) showing this check as PASS is consequently not evidence there is nothing to look at --- it only means the check ran, not that its content was clean. Read the check's own posted comment body every time, the same discipline the review-job case above already demands, but don't expect the check's pass/fail conclusion to ever flip for this class of check even on a real, large regression. (Sparta#995/#998/#999, 2026-07-19: `gh pr checks` reported `benchmark` as PASS across three separate PRs while the actual posted comment showed regressions of 45%, 38.8%, and 36.9% respectively against the CI-runner baseline --- two were real, fixable redundant-computation bugs; the third traced to a stale baseline that predated an earlier PR's own accepted cost increase and hadn't been refreshed yet, since the refresh workflow only runs on a weekly schedule, not on every main push.)

**A fourth case: a review job can post a syntactically valid, confidently stated verdict that is nonetheless invalid because it rests on a hallucinated premise about the PR's own state --- not a stub (no verdict) and not a misfire (guard-script/check-conclusion mismatch), but a fabricated fact baked into an otherwise well-formed review.** A reviewer that infers PR state from a commit message rather than querying the PR's actual `state`/`merged` API fields can mistake a routine `Merge remote-tracking branch 'origin/main' into <PR-branch>` commit --- pushed to resolve a sync conflict on the still-open PR branch itself --- for evidence the *PR* was merged into `main`, and confidently report "PR is closed, no action taken" while never actually reviewing the diff. This reads exactly like a legitimate all-clear (a `### Verdict` section is present, the job reports success), so the stub-detection guards described in CLAUDE.md's "Do the review yourself when the @claude workflow doesn't produce a verdict" section don't catch it. Sanity-check any surprising verdict --- especially "nothing to review" or "already merged/closed" --- against the PR's real API state before trusting it, and re-trigger for a genuine review rather than accepting a verdict-shaped comment built on a false premise. (gha#293/gha#295, 2026-07-24: after a merge-conflict-resolution push, the re-triggered `claude-code-review` run reported "The PR is closed --- it was merged as commit `db11634`" even though the PR was still open and `db11634` was only the PR branch's own merge-with-main commit; re-triggering once more produced a genuine review of the actual diff.)

**A fifth case, and the one that decides what "reachable" means in criterion 2 above: an external reviewer can decline to review at all, posting a refusal in the shape of a review.**
Unlike the four cases above --- all of which are a review that ran and produced something misleading --- this is a reviewer that never ran, and says so in a `COMMENTED` review whose whole body is the refusal (e.g. Copilot's *"unable to review this pull request because the user who requested the review has reached their quota limit"*).
Three consequences for driving a PR to fully clean:

- **A refusing reviewer is not "reachable,"** so criterion 2's external-verdict requirement falls to whichever external reviewer *is* working.
  Don't stall a PR waiting for a reviewer that is refusing --- but don't quietly downgrade to self-review either while another external reviewer is answering normally.
- **Reviewers fail independently.** One can be quota-dead while another reviews the same head normally, so check each one rather than generalizing from the first refusal.
- **Keep re-requesting each round anyway.** A quota resets on its own schedule, so a reviewer that refused a few pushes ago can come back mid-session --- which is exactly what criterion 2's "re-check availability right before declaring clean" is for.
  Say so explicitly when reporting a PR ready: name which reviewer's verdict the clean call rests on, and which one never weighed in at this head.

The mechanics of detecting a refusal (it arrives as a posted review, not an API error, so the request call's success proves nothing) are in [`memories/github.md`](../../memories/github.md)'s GitHub MCP tools section.
(`ucdavis/rampp#111`, 2026-07-24/25: Copilot refused three times across two heads for quota while `claude-review` posted genuine verdicts at both; the PR was reported clean --- and merged --- on `claude-review`'s verdict, with Copilot's absence stated in the ready-for-merge comment rather than papered over.)

**A sixth case runs the other way from all five above: the review is genuine and complete, but the workflow posts the reviewer's own tool invocation instead of the review body.**
The comment opens with a literal `gh pr comment <N> --repo <owner>/<repo> --body "$(cat <<'EOF'` and closes with `EOF\n)"`, wrapping a real, correct verdict as unrendered text --- the model emitted a shell command as its final response and the workflow posted that string verbatim.
Nothing is lost, and the same body usually also lands as a properly-rendered sibling comment, so the PR carries the review twice.
Two reasons not to shrug at it: a comment opening with a raw `gh` invocation reads as a broken run, so a human is likely to discount a review that actually passed; and a verdict-detecting guard script (`check-review-execution.sh`) is now matching against a shell command rather than prose, which can misfire into a needless stub-retry and a second full review's cost.
Read the body and extract the verdict from inside the heredoc rather than re-triggering.
(`UCD-SERG/serocalculator#392`, 2026-07-25; filed as [`d-morrison/gha#312`](https://github.com/d-morrison/gha/issues/312), which proposes unwrapping the pattern before posting.)

**A seventh case: a reviewer can post a `BLOCKING` verdict on a false
positive that will reproduce on every future round.**
The six cases above all turn on what a reviewer said about the *code* ---
or, in the fifth, on its declining to say anything.
This one is a policy detector firing on the repo's own conventions, and it
behaves differently from every case above in the way that matters for the
loop: **re-triggering cannot clear it**, because it keys on text that is
still there and that you are declining to change.
A timeout or a quota refusal resolves itself on a re-run; this does not.

The shape is an injection detector reading imperative prose as instructions
aimed at the reviewer.
That misfires badly on an agent-instruction corpus, where imperative mood is
the medium rather than a signal of compromise --- the distinction that
matters for injection is **provenance**, not grammar.
Repo-authored guidance in a PR against that repo is not untrusted input, and
a detector that cannot tell the difference will flag most of the corpus.

That reading is not an inference from one misfire.
The detector went on to block **this very entry**, citing its
"Do not count the re-raise" line, and in the same verdict flagged the PR
*description* --- text that is not in the repository at all and cannot be a
convention, a file, or anything a later reader would see.
So the trigger is mood alone, on whatever text is in front of it.
Treat a third data point arriving on the write-up of the first two as
confirmation rather than as coincidence: it is the cheapest possible
demonstration that re-running and rewording both miss the point, since the
only rewrite that would satisfy it is one that stops giving instructions ---
which is the entire function of a `shared/` fragment.

Three consequences:

- **Answer with corpus evidence, not argument.**
  One command usually settles whether the flagged form is a convention:
  `grep -l "^## In review" shared/coding/*.md | wc -l` against the directory
  total.
  Eight of eighteen is a convention; one of eighteen would be a real finding.
- **Do not count the re-raise against the rebuttal test in criterion 2.**
  That test assumes a reviewer that can be convinced.
  Reply once naming the evidence, then hold, per
  [`address-every-comment`](address-every-comment.md)'s per-item noise rule
  --- and keep processing that reviewer's *other* findings normally.
- **Escalate rather than comply, and say why in the thread.**
  Complying means either a one-file exception to a convention already merged
  many times, or a corpus-wide change; both are the human's call.
  State plainly that the check is red **by decision, not oversight**, so a
  later reader does not treat it as an unaddressed finding and silently
  "fix" it.

(Morrison-Lab/ai-config#818, 2026-07-29: Jules returned `VERDICT: block` for
"prompt injection attempt in diff" on a new `shared/coding/` fragment's
`## In review` section, then repeated it verbatim at the next head without
engaging the rebuttal.
Eight of the eighteen existing fragments carry an identically-worded section.
`claude-review` returned Ready for merge at the same head.
The maintainer's call was to hold; the PR merged with `jules/review` red.)

**An eighth case: the reviewer's workflow can fail outright on an upstream
failure, so there is no verdict of any kind --- and its error message may
blame the wrong thing.**
All seven cases above concern a reviewer that produced *something*: a stub, a
misfiled conclusion, a pass that cannot fail, a fabricated premise, a
refusal, a wrapped verdict, a false positive.
This one produces nothing.
The job goes red, no review comment appears, and the check is simply absent
as evidence either way.

It matters for the loop because the right response is neither of the two
obvious ones.
It is not a finding to address, so do not self-review as though the reviewer
had spoken.
And it is not the fifth case's unreachable reviewer either, so do not write
the reviewer off yet: an infra failure is frequently transient, where a quota
refusal is not.
Retry the failed job once, per this repo's standing flaky-infra rule, and
only treat the reviewer as unreachable if it fails again.

**Read the log rather than the error message, because the message can name a
cause the log rules out.** A failure of this shape often surfaces as a
credential hint ("check `<SERVICE>_API_KEY` is valid"), which is the most
expensive possible wrong diagnosis --- it sends you to repo secrets for
something that will clear on its own.
The log usually settles it: a request that *authenticated*, did work, and
then failed on a follow-up call was never an auth failure, whatever the
summary says.

Two pieces of evidence beat arguing about it, and both are cheap:

- **Prior successes on the same credential in the same session.** A reviewer
  that posted verdicts minutes earlier is not using an invalid key.
- **A retry with no code change.** If it passes, the failure was transient by
  construction.
  This is the mirror of [`ardi`](ardi.md)'s "a symptom that stops reproducing
  is a fix having landed" --- there, silence after a merge needs the merge
  ruled out before you may call it flaky; here the retry is a genuine
  negative control, because nothing changed between the two runs.

Say which of the two you have when reporting it, so a later reader can tell a
diagnosed transient from a hopeful one.
And state plainly that the posted error text was wrong, since the next person
to hit it will read that text first.

- **Do:** retry the failed job once, then read the log for where the request
  actually broke.
- **Do:** cite prior successes or a no-op retry as the evidence for calling it
  transient.
- **Don't:** treat a crashed reviewer as either a finding or a refusal.
- **Don't:** act on a credential hint that the same log contradicts.

(Morrison-Lab/ai-config#835, 2026-07-30: `jules/review` failed with a 404 on
`GET /v1alpha/sessions/<id>/activities`, reported as
"Check `JULES_API_KEY` is valid".
The log showed the key creating that session and confirming it *ready* 0.2s
earlier, so the 404 was a propagation race on the sub-resource, not auth ---
an invalid key fails at creation with 401/403.
Jules had already approved twice on the same key that session, and
`rerun_failed_jobs` with no code change returned `approve`.)

**A second shape of that failure is cheaper to diagnose, because the
reviewer names its own session in the failure comment.**
`jules/review` can fail with
`Jules did not return a review within 15 minutes. Session: <id>`,
which is not an API error at all --- the request authenticated, created that
session, and then never delivered a verdict.
The session id is itself the auth-succeeded proof, so this shape needs no log
fetch: a credential that cannot authenticate never gets a session to name.
Prefer that field to the log whenever it is present, per
[`algorithmatize-checks`](algorithmatize-checks.md) --- one value in the
comment decides the question the log was going to answer.

And when a fix is already queued for the same round, **the push is the
retry**, so a separate `rerun_failed_jobs` call is wasted: the push
re-triggers every reviewer on the new head anyway.
Say which of the two you did, because they are not equally good evidence ---
a push changes the code, so it demonstrates only that the reviewer works now,
rather than being the no-op negative control the bullets above prize.

- **Do:** read the failure comment for a session id or similar
  work-happened marker before fetching a log.
- **Do:** let a pending push serve as the retry, and label that evidence as
  weaker than a no-op re-run.
- **Don't:** spend a `rerun_failed_jobs` call on a head you are about to
  replace.
- **Don't:** report a push-triggered pass as proof the failure was transient
  by construction.

(Morrison-Lab/gha#374, 2026-07-30: `jules/review` reported "Jules did not
return a review", with the 15-minute timeout and session
`4236561570323034536` in its own comment.
A review fix was already staged, so the push carried the re-trigger, and
Jules returned `VERDICT: approve` on the new head about four minutes later.)

**A third shape is the one the retry rule hands off to and then stops
short of: the failure that reproduces identically on every attempt.**
The eighth case tells you to retry once and call the reviewer unreachable if
it fails again, which is right, and it is where that case ends.
But "unreachable" covers two situations with different owners and opposite
next actions.
A service-wide outage clears on its own, so waiting is correct.
A credential scoped to this repository or organization never clears by
itself, so every further retry is wasted and the real deliverable is an
issue naming a human with admin access.
Retrying cannot separate them, because both keep failing.

The discriminator is a repository you are not asking about: run the same
reviewer on a **different** repo in the same session.
A success there proves the service is up, which leaves the failing repo's own
credential as the only remaining explanation.
This is an [`algorithmatize-checks`](algorithmatize-checks.md) case rather
than a judgment call -- two check runs decide it -- and a multi-repo session
usually has the second one for free.

**The inversion is what makes this worth writing down, because it reuses the
eighth case's own evidence and points the opposite way.**
That case offers "prior successes on the same credential in the same session"
as grounds for calling a failure transient.
Read it carefully: it holds only when the successes are on the **same repo**.
A cross-repo success is a different credential, so treating it as evidence of
transience argues for waiting out precisely the failure that will never
clear.
Same evidence type, opposite conclusion, and only the scope tells them apart.

The duration signature is the corroborating half.
A reviewer that authenticates and then works takes minutes; one whose
credential is rejected dies in seconds, with `is_error: true`, zero cost, and
zero permission denials, because no work ever started.
Take those seconds from the completed run's own `started_at`/`completed_at`
rather than from `status`, per criterion 1 above.

- **Do:** run the same reviewer against another repo in the session before
  concluding a service is down.
- **Do:** stop retrying and file an issue naming the credential once a
  cross-repo success has localized the failure.
- **Don't:** read a success on a different repo as evidence that this repo's
  failure is transient.
- **Don't:** keep spending retries on a failure whose every attempt dies at
  the same short duration.

(d-morrison/altdoc#95 / altdoc#96, 2026-07-30: `claude-review` failed seven
times across those two PRs -- six on #96, one on #95 -- each run finishing in
the 26-to-35-second band, with `is_error: true`, `total_cost_usd: 0`, and no
permission denials.
The nearest pair is 38 seconds apart: the run on altdoc#95 failed
`04:07:37Z -> 04:08:12Z`, and the same reviewer returned a full
`Ready for merge` verdict on Morrison-Lab/ai-config#858 over
`04:08:50Z -> 04:11:41Z`.
So the service was fine and the `d-morrison` credential was not, which no
number of re-runs would have shown.
Tracked in d-morrison/altdoc#99.)
