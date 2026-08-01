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

**Criterion 2's test is the absence of findings, not the presence of a verdict
line saying so.**
A reviewer routinely asserts both at once: a `### Verdict` reading
**Ready for merge**, and directly beneath it a findings section listing items
nobody has addressed.
Neither half is wrong, which is what separates this from the eight numbered
cases below --- those are all a reviewer producing an unreliable or absent
signal, whereas here the comment is accurate throughout and the defect is in
the reading.
The verdict line answers a narrower question than the one criterion 2 asks, and
it is the part that appears first and gets quoted into a status report.

So when the two disagree inside one comment, **the findings win**.
Read to the end of the comment before calling anything clean, and count the
items under every heading, whatever that heading is called ---
[`address-every-comment`](address-every-comment.md) already establishes that
"non-blocking", "nit", "minor", and "optional" are prioritization labels rather
than a pass, and a reviewer files findings under exactly those words in the
section that contradicts its own verdict line.

**The disagreement is measurable, and it is not a wording problem.**
Across 38 verdict-bearing `claude-review` comments sampled from 16 PRs,
8 (21%) carried a verdict line that disagreed with the findings in the
same comment.
Six read a pass over unaddressed nits, and two ran the other way,
blocking over findings the reviewer itself called non-blocking, so the
error is not a consistent bias that an offset could correct.
The vocabulary is nearly closed by contrast: five outcome lexemes across
five markup carriers, with 37 of the 38 naming "Verdict" somewhere.
So neither detection nor parsing is the weak link.

That is the argument against gating on a machine-readable verdict
field.
Adding one would encode the reviewer's own looser threshold, making
roughly one review in five confidently wrong in exactly the form that
invites automation.
Structured review output should carry **finding counts**, which are
checkable against the inline-comment and thread lists, rather than a
pass/fail mood, which is checkable against nothing.

(Sampled 2026-07-31 across 12 `Morrison-Lab/ai-config` PRs and 4 in
`Morrison-Lab/gha`.
All eight are named, so the rate is reconstructable.
The six pass-over-nits cases were ai-config #955, #941, #939, #935, #934,
and #925 --- #934's verdict line *is* the hedge, reading
`**One finding (nit), otherwise ready for merge.**`.
Both opposite-direction cases were on
[gha#371](https://github.com/Morrison-Lab/gha/pull/371), which returned
`**Needs minor changes**` over "two non-blocking, fact/scope findings".
Four other comments within the same 38 are counted out as unclear for a
different reason: three of them passes --- two with the verdict restated
or hyperlinked from an earlier review, one whose findings never reached
the PR --- plus one where `Needs work` did double duty as both the
verdict and an inline finding's heading.
Those are legibility problems rather than disagreements, and they sit
inside the pass and non-pass groups rather than beside them.
Of the 24 passes, 23 used `Ready for merge` and one used the hedged
variant above; the four non-pass lexemes were `Needs more work`,
`Needs minor changes`, `Needs work`, and `Needs one fix`.)

**A reviewer's own verification block can be wrong while its verdict is
right.**
The verdict-versus-findings test above needs a disagreement to spot.
This one offers none: the verdict is right, the findings section is empty and
correctly so, and the defect sits in the arithmetic the reviewer posts to show
its work.

A block labelled "verification" is the part of a review *least* likely to be
re-checked, because it presents as the checking already having been done.
That is what makes a wrong one worse than no block at all.
It will usually sum, too, since a balancing partition is what the reviewer was
aiming for, so only the composition is wrong.

Re-derive the groups rather than the total.
Arriving at the right number says nothing about which groups the parts came
from, and that is exactly the error a table that balances conceals.

Read it as the mirror of [`ardi`](ardi.md)'s "A systematic audit done by
skimming is worse than the one-at-a-time version it replaces".
That entry governs an audit *you* produce; this one governs an audit arriving
*as evidence*.

The secondary signal is worth acting on rather than merely noting.
A reviewer's reconstruction error usually traces to something genuinely
ambiguous in the diff, so treat it as evidence about your own prose and not
only about the reviewer.

- **Do:** re-derive a posted verification's groups, not just its total.
- **Do:** fix the wording that invited a wrong reconstruction, even when
  nothing in the diff was false.
- **Don't:** let the word "verification" stand in for having verified.
- **Don't:** read a table that sums as one that partitions correctly.

(Morrison-Lab/ai-config#957 round 2, 2026-07-31: `claude-review` returned
**Ready for merge** with no findings, above a table partitioning the same 38
comments as 24 passes + 10 blocking + 4 unclear.
That sums, and the composition is wrong: the sample is 24 passes and 14
non-passes, with the four counted-out comments sitting inside those groups
(three passes, one non-pass) rather than beside them.
It balanced only because the four were subtracted from the wrong group.
Nothing in the diff was false, but "Four further comments" read as a disjoint
third bucket, which is how a careful reader reached the wrong partition.)

**What "an approving review" means here is not a review state.**
Across the 25 most recent merged PRs, all 106 posted reviews are `COMMENTED` and
none is `APPROVED` --- `d-morrison`'s own included, so this is not a bot
limitation:

```sh
gh api graphql -f query='{search(query:"repo:Morrison-Lab/ai-config is:pr is:merged", type:ISSUE, last:25){nodes{... on PullRequest{reviews(first:20){nodes{state}}}}}}' \
  --jq '[.data.search.nodes[].reviews.nodes[].state] | group_by(.) | map({state: .[0], n: length})'
#=> [{"n":106,"state":"COMMENTED"}]
```

The key order there is not a typo: `gh api --jq` marshals through Go and sorts
keys alphabetically, so `n` precedes `state` even though the expression builds
`state` first.
Plain `jq` would preserve the insertion order and print `{"state":...,"n":...}`.

A constant carries no information, so `.state` cannot confirm clean here, and
waiting for a formal `APPROVED` would stall every PR indefinitely.
Approval is established instead by the two reads criterion 2 and the
**Threads** paragraph already name: zero findings in the latest review body,
and zero unresolved inline threads.
The one state that does still carry information is `CHANGES_REQUESTED`, which
stays blocking however a later verdict line reads.

- **Do:** read the whole review comment and count findings under every heading
  before calling a PR clean.
- **Do:** establish approval from the findings and thread lists, since `.state`
  is `COMMENTED` on every review this repo receives.
- **Don't:** quote a **Ready for merge** line as the clean signal while the same
  comment lists findings.
- **Don't:** wait for a formal `APPROVED` review, or read `COMMENTED` as a
  defect in the reviewer.

(Morrison-Lab/ai-config#900, 2026-07-30: the verdict read "**Ready for merge.**
No hallucinations, fabricated references, or factual errors found", immediately
above a "Findings (all nits, non-blocking)" section naming three inline
comments and closing "None of these affect correctness or usability of the
guidance".
All three threads were unresolved at that point, so the PR failed both halves of
criterion 2 while carrying a verdict line that read like a pass.)

**Findings hide on four different surfaces, and no single check sees all
four --- so read the verdict body, the inline comments, the thread list, and
the verdict's own conclusion every round.**
The entry above is about a reviewer contradicting itself inside one comment.
This is about the *detection method* returning an answer that is technically
true and substantively wrong, which is harder to notice because nothing looks
inconsistent.

- **An out-of-diff finding never becomes a thread.**
  A finding about a line the diff did not touch cannot be attached as an
  inline comment, so it appears only in the body --- reviewers say so
  explicitly ("inline comments were unavailable for out-of-diff lines").
  A thread count therefore cannot see it.
  Zero unresolved threads is not evidence of zero findings.
- **An empty body hides the mirror case.**
  A review can post a completely empty top-level body and carry its entire
  finding in one inline comment, so a body-only read finds nothing to act on
  and concludes there is nothing.
- **"No verdict" is its own state, distinct from "a verdict with no
  findings".**
  A review job can fail having posted *nothing* --- not a stub, not an empty
  comment.
  Zero findings and zero review are indistinguishable by any count, and they
  call for opposite responses: one is done, the other needs a self-review and
  a re-run.
  Read the job's step outcomes when a review is missing rather than inferring
  from the absence of comments.

The reason this defeats otherwise-good instruments is that each check answers
a narrower question than the one being asked.
"Are all threads resolved" is not "are there no findings", and neither is
"does the verdict say ready".
Per [`algorithmatize-checks`](algorithmatize-checks.md), prefer the instrument
that decides the question exactly --- and where none does, as here, say so
rather than substituting the nearest available count.

- **Do:** read all four surfaces before calling a PR clean, every round.
- **Do:** distinguish "no findings" from "no verdict" explicitly, and treat
  the latter as unreviewed.
- **Don't:** report clean on a zero thread count, however many checks are
  green.
- **Don't:** treat an empty review body as an all-clear without checking the
  inline comments.
- **Don't:** read a reviewer's silence as a verdict --- a job that posted
  nothing leaves the same zero counts as a job that found nothing.

**A fourth surface, and the one that defeats the gate itself: the review
check can pass on a blocking verdict.**
The three above are cases where a *reader* looks at the wrong place.
This is the case where the repo's own gate looks at the right place and still
reports green, because `require-review` tests whether a review **ran**, not
what it **concluded**.
So a "Needs more work" verdict and a "Ready for merge" verdict produce an
identical check row.

It compounds with case 1 rather than sitting beside it.
A review invoked without a `--comment` argument reports its findings in the
run's own comment and posts nothing as a thread --- and the better reviewers
say so in their last line, which is the tell worth grepping for.
The result is a PR with every check green, zero inline comments, zero
unresolved threads, and a blocking correctness finding sitting in plain text
that no count reaches.

This is the third numbered case below -- a check that cannot fail on its own
content, so its green carries no signal -- arriving on the one job whose whole
purpose is to gate on review outcome.
The difference is what makes it worse than the benchmark check recorded there.
That one is *designed* never to block, and a reader who knows the design knows
to read its comment.
`require-review` is designed to block, is frequently a required check, and
still reports green on a verdict that says the opposite.
Read the verdict line itself, every round; a green `require-review` is
evidence a reviewer spoke, and nothing more.

- **Do:** grep the verdict body for its own conclusion, and treat a
  `require-review` pass as orthogonal to whether the PR is clean.
- **Don't:** let a green review-gate check stand in for reading what the
  review said.

(Morrison-Lab/ai-config#921, ucdavis/bcs#477, ucdavis/bcs#473, all 2026-07-30,
within hours of each other.
On #921 every mechanical check passed --- all CI green, zero unresolved
threads, verdict line reading "Ready for merge" --- and the PR was reported
clean twice while carrying an open out-of-diff finding.
On #477 the review body was empty and the finding was inline-only.
On #473 `claude-review` failed after its built-in retry, posting nothing at
all, so there was no body to read past and zero threads because zero
comments.)

(The fourth surface, ucdavis/bcs#468, same night.
`require-review` passed, `claude-review` passed, all 18 checks were green,
and there were zero inline comments and zero threads --- while the verdict
read "Needs more work" over a blocking finding that the new section's own
safety rule was false on one code path.
The review's own closing line said as much, noting that because no
`--comment` argument was passed, it had not posted the findings to the PR.
Every count-based check called that PR ready.)

**A review comment's header SHA can be stale, so take the reviewed commit from
the run's own `head_sha`.**
Criterion 2 requires the verdict to sit at the current head, and the obvious
instrument for checking that is the unreliable one: the commit named in the
comment's own caption.
A verdict captioned with a superseded commit can be a current-head review
whose caption simply names a different commit than the run checked out.

The failure direction is the expensive one.
It reads as a stale review, which invites a needless re-trigger, and under
`concurrency: cancel-in-progress` that re-trigger cancels the run already
in flight at the real head.
So the caption costs you the verdict it was making you doubt.

The run's `head_sha` settles it, and the comment links the run it came from,
so the check is one call.
This is [`algorithmatize-checks`](algorithmatize-checks.md) applied to a
verdict: prefer the API field over the prose caption.

- **Do:** follow the job link in the comment and read that run's `head_sha`.
- **Don't:** treat the SHA in a comment's heading as the commit reviewed.

(Morrison-Lab/ai-config#957, 2026-07-31: the `Ready for merge` comment is
captioned "Review of `de72464`" while the run it links, `30614782680`, records
`head_sha: c8d5d8a` --- the PR's head at the time, since a `main` merge had
superseded `de72464` 64 seconds earlier.
Both facts came from `get_workflow_run`; the caption was never rewritten, and
the cancelled prior run `30614715159` is the one that actually ran at
`de72464`.)

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

**That inverse has a second mechanism, and under this one the guard is not
misfiring at all.**
The sparta case above is a guard that reads the transcript for a verdict and
gets the answer wrong, so the red is a defect, and finding the defect explains
everything.
A guard can also fail a run **before** it ever asks about a verdict, and then
nothing is malfunctioning.

`Morrison-Lab/gha`'s review guard is built that way, in both shipped versions.
It reads the run's result object and, on `is_error == "true"`, prints
`Claude review ended in an error state` and exits 1, with a single carve-out
for the quota case (`total_cost` 0 at `num_turns` 1).
At `@v1` the step is inline in `claude-code-review.yml` and contains no verdict
test whatsoever.
At `@v2` the logic moved into `check-review-execution.sh`, which does scan for
a verdict, but every line of that scan sits below the `is_error` branch, on the
`is_error: false` path.
So an errored run is failed without either version asking whether a review was
posted, and the version that ran is not the variable.

The claim the guard makes is therefore true, and narrower than it looks: the
run ended in an error state.
The false step is the reader's.
A review reaches the PR through tool calls **as it works**, so its comment can
be complete minutes before the run's own result object reports a failure.
Read `is_error` as a fact about how a run **ended**, never about what it
**accomplished**.

That is what lets this survive a long investigation rather than a careless one.
Every reading of the run data is correct, and the natural check against the
case above, whether the guard misfired, comes back **no**, which reads as
confirmation that the red can be trusted.
Nothing in the run's conclusion, result object, or step list differs between
"the reviewer produced nothing" and "the reviewer produced a full verdict and
then errored", because the verdict is an artifact on the PR rather than a field
of the run.
Be precise about how far that goes: at `@v2` the execution output does carry
the posted text, so the fact is present in the run and merely unreachable ---
the guard exits above the scan that would read it --- while at `@v1` there is
no such scan to reach.
Gated by control flow rather than absent, and on neither version does any path
the guard takes evaluate it.

So read the guard's own failure branch once, and let it tell you what its red
is worth.
A branch that exits before evaluating the artifact yields a red carrying no
information about that artifact, which is the mirror of the benchmark-check
case this file records, whose green carries none about its content.
Two timestamps then localize it exactly, per
[`algorithmatize-checks`](algorithmatize-checks.md): bracket the verdict
comment's `updated_at` inside the **review** step's own `started_at` and
`completed_at`.
A comment written while that step was running is a comment that run produced.
Comparing it against the guard step's `started_at` instead does not
discriminate, since the guard always runs after the review step in the same
job, so a stale comment from any earlier round clears that bar just as easily.

- **Do:** read the PR's own comments before accepting that a failed review run
  produced no verdict.
- **Do:** read a guard's failure branch to learn whether its red is evidence
  about the artifact at all, rather than keeping "go look" as a habit to
  remember.
- **Don't:** infer that a run produced nothing from a true report that it ended
  in an error.
- **Don't:** treat "the guard did not misfire" as establishing that its red is
  informative.

(`Morrison-Lab/ai-config#984`, 2026-07-31, job `91208954246`:
`Run Claude Code Review` concluded **success** over `16:17:16Z` to `16:28:13Z`;
the review's comment carries a `### Verdict` heading reading
**Ready for merge** above a substantive findings review, last updated
`16:28:12Z`; `Fail the check if the review did not complete` then failed at
`16:28:13Z`, and the job went red.
A session spent several hours on that failure and its siblings, asserting
throughout that the runs had produced no verdict, without reading either PR.
The unsuffixed step name is the `@v1` tell, and `@v1` is the version with no
verdict test at all, which is why the mechanism had to be read at both tags
rather than at the one the extracted script lives in.)

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

The mechanics of detecting a refusal (it arrives as a posted review, not an API error, so the request call's success proves nothing) are in [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md).
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

**A check-run reading `failure` is a fact about one *attempt*, not about the
whole `run_id` -- a later attempt of that same run can still resolve on its
own, with nobody having triggered it.**
The section above is right that repeated *identical* failures at the same
short duration point to a durable cause, and that retrying blindly is
wasted motion once that pattern is established.
It does not say the reverse: that a run which has failed once, or even
twice, is done.
GitHub records each `rerun_failed_jobs`/`rerun_workflow_run` as a new
**attempt** of the same `run_id`, and `actions_get`'s `get_workflow_run`
exposes that directly via `run_attempt`, `run_started_at`, and
`previous_attempt_url`.
A check-run's `failure` conclusion describes the attempt it belongs to; it
says nothing about whether attempt 3 of the same `run_id` might still post a
genuine verdict, from anyone -- a scheduled retry, a maintainer's manual
re-run, or a mechanism this session never identified.

So don't infer "this run_id is exhausted" from a failed attempt, however
many rounds have already failed.
Read `run_attempt` before writing that off, and treat a later successful
attempt as the real, final verdict -- not as an anomaly to explain away.

- **Do:** check `run_attempt`/`run_started_at`/`previous_attempt_url` on the
  actual `run_id` before declaring a review permanently stuck, even after
  more than one failed attempt.
- **Do:** accept a later attempt's genuine verdict as authoritative, without
  needing to know who or what triggered it.
- **Don't:** assume a `run_id` is done because its most recent check-run you
  read was `failure` -- fetch the run fresh rather than trusting a cached
  conclusion.
- **Don't:** claim a specific cause (a scheduled retry, an org-level rerun)
  for an attempt you did not trigger yourself, without evidence naming it.
- **Don't:** trust a contemporaneous explanation for why a prior attempt
  failed -- your own included -- without checking it against that attempt's
  actual job logs.

(Morrison-Lab/gha#390, 2026-07-31: run `30646364412` failed twice --
attempts 1 and 2 both stubs (no verdict, low denial count, on both the
initial call and its own built-in gha#185 in-job retry), confirmed against
attempt 2's own job logs rather than recalled -- and was treated as
reproducibly stuck, with self-review relied on instead of a further retry.
Attempt 3, `run_started_at: 2026-07-31T23:34:41Z`, `previous_attempt_url`
pointing at attempt 2, resolved with `conclusion: success` and posted a
genuine, itemized "Needs more work" verdict -- without this session
triggering it, and with nothing on the PR explaining who or what did.
A same-thread comment offered a different, already-documented explanation
for the earlier failures (a downstream guard misreporting failure after a
real verdict had posted) -- checked against attempt 2's actual job logs and
found not to match: both prior attempts genuinely produced no verdict at
all, so that explanation was itself an unverified guess, not a checked one.)

**That duration signature does not run backwards, and reading it in reverse
is how several unrelated bugs get filed as one.**
The paragraph above offers a short run as **corroboration**, once a credential
is already the hypothesis on other grounds.
It is not a test that *produces* the hypothesis, and the difference is easy to
lose because the sentence reads the same in both directions.

The reason it cannot run backwards is that every failure occurring before the
model call takes about the same time.
A job that dies at checkout, at the App token exchange, or at authentication
has spent its whole life on setup, so 13 seconds and 28 seconds are the same
observation.
The duration tells you the run stopped early.
It says nothing about **which** early step stopped it, and a credential
problem is only one of several candidates.

The failure this produces is worse than an ordinary wrong guess, because it
**merges** distinct bugs.
Reading a cluster of short failures as one credential fault yields a single
tidy story covering all of them, and every separate root cause underneath it
goes unfiled.
Grouping by symptom feels like pattern recognition, which is why nothing about
it prompts a second look.

So read each job's own terminal error before naming any cause, and expect
short failures sharing a repo and an afternoon to have nothing to do with each
other.

- **Do:** open the log and quote the line the job actually died on.
- **Do:** treat a cluster of short failures as several candidate bugs until
  each one's error says otherwise.
- **Don't:** infer a credential or quota problem from a short duration alone.
- **Don't:** let one explanation absorb every failure that resembles it.

(2026-07-30, auditing which repos held a `CLAUDE_CODE_OAUTH_TOKEN`: three
failures in the 13-to-28-second band were reported as one App-permissions
problem.
They had three unrelated causes.
`UCD-SERG/ucd-serg.github.io` run 30529959398 (25s) failed
`App token exchange failed: 401 Unauthorized - User does not have write access
on this repository`, because the triggering actor was the `Copilot` coding
agent, which is not a collaborator -- filed as ucd-serg.github.io#84.
Run 30509709695 (13s) on the same repo logged `Actor has write access: write`
and then failed
`Command failed: git fetch origin --depth=20 pull/77/head:main`.
`d-morrison/qwt` run 30391041128 (28s) reached the model and returned
`is_error:true` after a workflow-modification denial.
Only the first was about permissions at all.)

**A group established on real discriminating evidence can still admit a case
that was never held to it, and widening scope is when that happens.**
The section above concerns a weak signal, duration, being read as though it
produced a hypothesis rather than corroborating one.
This one fires later and is narrower.
The signature is strong, it was established correctly, and the defect is in
what gets added to the group afterward.

The shape is a first pass done properly, followed by an admission done on
less.
You read two or three failures' own output, find a genuine shared signature,
and group them.
Then a further case turns up sharing only the **symptom** that made you look
at it, which is usually no more than "this check failed today", plus a
plausible shared cause story.
It goes into the group without anyone rereading a log.

So the check is one question, asked of every case after the first.
Does this match on the **discriminating evidence** that defined the group, or
only on the symptom that made me look?

Note that the remedy above does not catch this on its own.
It says to open the log and quote the line the job died on, and that is
exactly what was done for the cases that formed the group.
Applying a standard to the first N cases is what makes the N+1th feel already
covered by it.

**A cross-repo or cross-project case is the likeliest to be admitted this
way, and the one that most needs the bar raised.**
It arrives feeling like independent corroboration rather than like another
instance, so it reads as strengthening the finding rather than extending it.
A scope claim is also the most quotable thing you will write about a bug.
"This affects two repositories" is what other people act on, and it usually
gets published in a tracking issue, where it outlives the session that
produced it.
Widening scope is therefore the moment to demand the same evidence again,
rather than the moment to accept a weaker kind.

Three disconfirming signals are cheap and general enough to look for by name.

- **How far the pipeline got.**
  A run that produced two attempt artifacts reached a retry path, and a run
  whose guard rejected it before any retry cannot have produced a second
  attempt.
  A structural difference in progress is evidence about which failure this
  is, independent of any log line.
- **The error text itself.**
  Two failures printing different messages came from different code paths,
  and both strings are usually already in front of you.
- **Whether the run produced the artifact the check exists to gate.**
  For a review job that means asking whether a verdict is on the PR, which
  is a different question from whether the job went red.

That third one is the last resort and the sharpest, because it is the only
one that survives the two above agreeing.
Two runs can print the identical error, from the identical code path, at the
identical stage, and still be opposite phenomena -- one where the reviewer
failed, and one where the reviewer succeeded and the guard failed it anyway.
Nothing in the run data distinguishes those, because the distinguishing fact
is not in the run: it is on the PR.

So when a check's own output is the only evidence, remember that a check is a
claim about an artifact, and go read the artifact.

The cost is not only a mislabelled case.
Dropping the second repository also removed the support for a real inference
that had been drawn from it, that two repositories sharing one action implies
the bug lives in the action.
That support was never real, so the false claim cost an inference on top of a
case record.
The retraction only revealed the loss rather than causing it.

- **Do:** re-read the new case's own terminal error before adding it to an
  existing group, however well established that group is.
- **Do:** compare the attempt or artifact count for a structural difference
  in how far each run got, before treating two failures as the same one.
- **Don't:** admit a case on a shared symptom plus a shared cause story when
  every earlier member was admitted on quoted evidence.
- **Don't:** publish a widened scope claim without holding the added case to
  the standard the original ones met.

(2026-07-31, `claude-review` failures on Morrison-Lab/ai-config #984, #985,
and #986: two run results were read directly and shared a genuine signature,
`is_error: true` alongside `subtype: "success"` after real work
($4.10 over 13 turns, $0.97 over 2 turns).
Both of those reads were #986's own two runs, though.
PRs #984 and #985 were admitted on nothing but a `claude-review` failure the
same day, with no result object read for either -- so that grouping was
already the pattern this section condemns, one step before the one it was
written about.
Reading them later made it worse rather than merely unverified: both had
posted complete **Ready for merge** verdicts, minutes before their guards
failed the check.
They were the *opposite* phenomenon -- the reviewer succeeded and the check
was wrong -- filed as instances of the reviewer failing.
Neither signal above would have caught it, since their error text and their
stage are identical to #986's; only the third one is, and it was added to
this list because of them.
The duration rule above was invoked explicitly to confirm that #986's
9-minute and 53-second runs were the same bug.
Morrison-Lab/gha#390 was then added to the group because its own
`claude-review` had failed the same day, and a scope correction widening the
finding to two repositories was posted to the tracking issue,
Morrison-Lab/gha#391.
It was a different bug.
That PR's log reads `Attempt 1 produced a stub review (gha#185) and the retry
ALSO ended without a verdict with a low denial count`, a path reachable only
when `is_error` is false, so the grouped signature is rejected by the guard
before any retry can happen.
The two attempt artifacts and the differing guard wording were both visible
at the time.
The claim was retracted on the same issue.)

**A stale branch can make workflow validation fail red before the reviewer starts,
even when the PR edits no workflow file.**
The workflow-validation case above is a green skip on a PR that edits the review
workflow itself.
This one is different.
The action refuses to run because the branch's workflow file no longer matches
`main`, but the message still names only two familiar causes: adding a Claude
Code workflow to a new repository, or changing workflow files in the PR.
A PR that changed neither looks unrelated, so the natural check clears the PR
and leaves the actual cause hidden.

Nothing else necessarily points at staleness.
`mergeable` can read `UNKNOWN` rather than `CONFLICTING`, and the check can die in
the same short-duration band this file already warns not to read as a credential
signal.
The standing retry-once remedy does not clear it either: the action itself says
`Error is not retryable, giving up immediately`, so attempt 2 only proves the
branch is still stale.

So compare workflow files against current `origin/main` before classifying the
failure.
If any `.github/workflows/` file differs and the PR branch is behind, merge
`origin/main` first and let that push carry the retry.
That ordering matters when another real failure is present on the same PR queue:
a stale branch can turn a genuine stub into a workflow-validation failure on the
next rerun, making two different bugs look like one symptom.

- **Do:** when `claude-review` fails with workflow-validation text on a PR that
  does not edit workflows, check the branch's behind count and compare
  `.github/workflows/` against `origin/main`.
- **Do:** merge `origin/main` before rerunning or grouping the failure, and let
  the push trigger the next review.
- **Don't:** treat the message's two named causes as exhaustive, or stop at
  "this PR did not change workflows".
- **Don't:** spend another `rerun_failed_jobs` call before merging `main`, or
  group the red check with stubs or credential failures on duration alone.

(Morrison-Lab/ai-config#981, 2026-07-31/2026-08-01: run `30647227071` reached
`run_attempt: 2` and failed in 16 seconds at
`Fail the check if the review did not complete`, with
`Workflow validation failed`, `Action skipped due to workflow validation error`,
and `Error is not retryable, giving up immediately`.
The PR touched only `CLAUDE.md`, two hook files, one hook test, and one
`shared/workflow/` fragment.
It was 30 commits behind `main`; #998 had merged at `2026-07-31T22:43:13Z` and
changed `.github/workflows/claude-review.yml`; comparing every workflow file
showed `claude-review.yml` and `validate.yml` differed before the merge and
matched after.
`git merge origin/main` was the whole fix, after about 27 hours stalled.
#994 was 24 commits behind and would have hit the same block if rerun then, but
its existing 5m26s `is_error: true`, `subtype: "success"`,
`permission_denials_count: null` stub ran an hour before #998 merged, so it was
a different bug; merge first, then retry.)
