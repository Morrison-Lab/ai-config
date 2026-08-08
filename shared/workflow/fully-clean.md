"Fully clean" is the terminal state the ARDI review loop drives toward.
A PR/MR is **fully clean** when **both** of these hold (and verified via `python3 scripts/check-pr-fully-clean.py <pr-number>`):

Worked-example case records for the rules below live in
[`fully-clean.cases.md`](fully-clean.cases.md), moved out of the auto-loaded context.

1. **All CI workflows and check runs are green AND completed.** Every workflow and check run passes --- not just the required checks and not just the review job.
   "Green" means finished with a passing outcome (success or skipped), not merely "currently reporting green while still running" --- never treat a workflow or check run that's still queued or in progress as clean, even if nothing has failed yet.
   **A reviewer's posted verdict does not mean the review check has finished, so don't let a clean verdict stand in for criterion 1 on its own job.**
   The bot posts its comment and then its run keeps going (bookkeeping steps, a cost tally, the gate job that consumes its result), so a full `Ready for merge` comment can sit on the PR for minutes while `claude-review` still reads `in_progress` and the `require-review` gate is still `queued`.
   Reading the verdict and moving straight to "clean" skips the very state this criterion exists to catch.
   The gap runs the other way from the stub-review case in [`review-verdict-pitfalls.md`](review-verdict-pitfalls.md): there the check is green and the verdict is missing, here the verdict is real and the check is unfinished.
   Re-read the check runs after the verdict lands, not just before.
   (The exact field names and casing for these states differ by API surface --- REST's check-runs endpoint returns lowercase `status`/`conclusion` strings like `completed`/`success`, while `gh pr checks`/GraphQL's rollup returns uppercase `state` values like `SUCCESS`; don't hard-code one casing when scripting a check.)
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

   **A `BlobNotFound` / HTTP 404 on the job-log fetch means the job has not completed, not that it has hung.**
   The block above says to read a run's duration from its log timestamps.
   That remedy is unavailable while a job is still running, because there is no log to read yet: GitHub archives a job's log blob only when the job completes, so `gh api "repos/<owner>/<repo>/actions/jobs/<job-id>/logs"` (and the MCP `get_job_logs`) returns `BlobNotFound` / 404 until then.
   So a 404 there is evidence the job is still going, and reading it as a hang inverts the signal.

   A still-in-flight job also legitimately reads `status: in_progress` with `conclusion: null`, and neither the 404 nor that status distinguishes a normal long-running review from a genuinely stalled one.
   Only completion settles it, or the live streaming log in the Actions UI, which is served before the blob is archived.
   So do not conclude "hung" or "produced no verdict" from a 404 plus an `in_progress` status; wait for the job to finish and read the verdict it then posts.

   A bare 404 is ambiguous in one further way worth naming, because the two readings call for opposite responses.
   A job that *completed* with no logs at all --- the ~1s concurrency self-collision in [`debugging.md`](../../memories/debugging.md)'s "An Actions job that fails in ~1s with NO logs" section --- also 404s on the log fetch.
   The discriminator is the job's own `status`/`conclusion`, never the 404: `in_progress` / `null` is still running, while `completed` / `failure` with `completed_at` stamped before `started_at` is that instant-fail case.

   - **Do:** read a 404 / `BlobNotFound` on the job-log endpoint as "the job has not finished", and wait for completion (or read the live UI log) before judging its outcome.
   - **Do:** take a job's real state from its `status`/`conclusion`, since the same 404 covers a still-running job and a completed-with-no-logs one.
   - **Don't:** read a 404 on the log fetch as positive evidence of a hang or a stall --- it is the opposite, evidence the job is still running.
   - **Don't:** file an issue reporting a review job as hung or "no verdict produced" while its log fetch still 404s and its status is `in_progress`.

   **`gh pr checks` is not a complete enumeration of a head's check runs, so
   read the commit check-runs endpoint before deciding that everything has
   finished.**
   This is a different gap from the workflow-run one above, and that gap's
   remedy is not the direct answer to it.
   The earlier paragraph warns that a workflow run may produce **no check
   run**, so a check-runs query cannot see it, and sends you to the raw
   workflow runs.
   Here the check run **exists** and the check-runs endpoint returns it.
   It is `gh pr checks` that omits it.

   The raw-run route is not blind to this, but it is indirect, and every
   caveat that paragraph attaches to it applies unchanged.
   The omitted check does have a backing Actions run, so a
   `gh run list --commit <head-sha>` sweep can surface it under the run's own
   name rather than the check's --- which means the raw-run sweep is a
   best-effort corroboration here, not the instrument to reach for.
   The check-runs endpoint names the check directly and answers in one call.

   The failure direction is the expensive one, because the omitted check run
   can be `in_progress` while `gh pr checks` reports zero pending.
   Anything keyed on that count --- a watcher, a readiness gate, an ARDI
   round-close --- then calls a PR terminal while a reviewer is still running,
   which is precisely the state this criterion exists to catch.

   ```bash
   gh api --paginate "repos/<owner>/<repo>/commits/<head-sha>/check-runs?per_page=100" \
     --jq '.check_runs[] | select(.status != "completed") | "\(.name) \(.status)"'
   ```

   **`--paginate` is load-bearing, not tidiness.**
   That endpoint returns 30 check runs per page by default, so on a head with
   more than 30 an unfinished run can sit on page 2 while the unpaginated
   query returns nothing and reads as an all-clear --- reintroducing, one
   surface over, the exact incompleteness this block is about.

   **The endpoint covers check runs only, so a repo that still uses legacy
   commit statuses needs a second query.**
   `gh pr checks` folds both surfaces into one rollup; the check-runs endpoint
   does not, so swapping one for the other can hide a pending or failing
   status context.
   Read `commits/<head-sha>/status` alongside it wherever statuses are in
   play, and note that its combined `state` reads `pending` when the repo
   posts no statuses at all, which is not a pending status:

   ```bash
   gh api "repos/<owner>/<repo>/commits/<head-sha>/status" \
     --jq '{state, n: (.statuses | length)}'
   ```

   `Morrison-Lab/ai-config` returns `{"state": "pending", "n": 0}` on every
   head checked here, so the caveat is about other repos rather than this one.

   **Why the two surfaces disagree is unexplained, so do not assert a
   mechanism for it.**
   Three candidates were named and none of them was tested: whether
   `gh pr checks` filters by check-suite app, whether it reflects only the
   required or branch-protection set, and whether an `in_progress` app check
   is omitted until it completes.
   The counts in the #1056 case record happen to embarrass all three, which is
   a reason not to adopt any of them rather than a reason to keep looking:
   naming a mechanism that has survived one round of disconfirmation is still
   guessing, and it is the exact failure several later sections of this file
   are about.
   What is measured is the disagreement, and that alone decides which surface
   to read.

   - **Do:** take the check-run half of criterion 1 from the paginated
     check-runs endpoint, and add `commits/<sha>/status` where the repo uses
     commit statuses, rather than treating either query as sufficient alone.
   - **Do:** report both counts when the endpoint and the rollup disagree, so
     the gap stays visible to whoever reads the status next.
   - **Don't:** read `0 pending` from `gh pr checks` as evidence that nothing
     is still running.
   - **Don't:** drop `--paginate` --- an unfinished run on page 2 returns the
     same empty result as a finished head.
   - **Don't:** offer a reason for the omission --- none was established.

   **Every subsection above explains a check list that is short for a per-PR
   reason, and a platform outage produces the same shape for a reason none of
   them can reach.**
   When a repo's normal workflows never start at all, each affected PR reports
   a near-empty check list and `mergeStateStatus: BLOCKED`, with nothing red to
   point at --- so the per-PR readings above all fit, and all of them send you
   to the wrong place.
   The discriminator is scope: several unrelated PRs truncated at once, plus a
   repo-wide `gh run list` showing a workflow type that used to run and now
   does not.
   `memories/github-actions-outages.md`'s "Check the GitHub status page when
   workflows stall across several PRs at once" carries the queries and the case
   record; reach for it before applying any subsection above to a second PR
   showing the same emptiness.
   Its sibling section there covers the other half --- what the wreckage looks
   like once the incident clears, and why a job that is `cancelled` with zero
   recorded steps is an outage casualty rather than a failure to debug.

2. **The latest review is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.
   A rebuttal the reviewer still disputes does **not** count as clean.
   That review must be a genuine posted verdict at the current head commit,
   from an external reviewer if one is reachable --- self-review is a
   fallback for when no working external reviewer is available, never a
   substitute once one is (see the `ardi` skill's step 2 for the
   availability-recheck procedure).
   **Pushing fixes for a finding-bearing review starts a new review cycle.**
   The ARDI loop is **NEVER** finished when you push fixes for a review or post an ARD disposition summary.
   You must wait for the new review run evaluating your latest pushed commit to post, fetch and parse that review, and confirm it contains zero findings before declaring the PR clean or ending the loop.
   Re-check availability right before declaring clean, not just at whichever
   round self-review first started; an inferred "probably clean" from green
   CI and resolved threads does not satisfy this.

**Criterion 2's test is the absence of findings, not the presence of a verdict
line saying so.**
A reviewer routinely asserts both at once: a `### Verdict` reading
**Ready for merge**, and directly beneath it a findings section listing items
nobody has addressed.
Neither half is wrong, which is what separates this from the eight numbered
cases in [`review-verdict-pitfalls.md`](review-verdict-pitfalls.md) --- those
are all a reviewer producing an unreliable or absent signal, whereas here the
comment is accurate throughout and the defect is in the reading.
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

**A clean verdict can ratify an enumeration instead of testing it, and then it
reads as independent corroboration of a false scope claim.**
The entry above is the reviewer's own arithmetic going wrong.
This one contains no arithmetic error at all: every member the reviewer checked
was real, described accurately, and correctly called safe.
It took the *set* from the diff rather than deriving it, so it verified the
members that were named and never asked whether the naming was complete.

That leaves the claim worse off than if nobody had looked.
An unchecked enumeration is merely unsupported, while one a reviewer has
restated in its own words now carries a second signature, and the thread records
the scope as confirmed by someone independent.
The verdict is not evidence of independence on that point, because the
reviewer's population came from the author.

The tell sits in the review's own account of what it did.
A sentence naming the members it verified is reporting a check of the *cited*
set, which is a different claim from the one the diff makes.
So read any verdict that quotes your own count back to you as leaving exactly
that count unconfirmed.

The remedy belongs in the diff rather than in the review round, because no
reviewer can supply it: publish the command that derives the set instead of the
count it returned, so the next reader re-derives rather than inherits.
That is
[`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md)'s
prose-enumeration rule, and it is also what keeps the claim true when the next
member is added.

This is the mirror of
[`address-every-comment`](address-every-comment.md)'s "a reviewer who enumerates
the sites is the reason the scope goes unquestioned", and the direction is what
changes the cost.
There the author inherits the reviewer's list, and the failure surfaces one
round later in a site the enumeration missed.
Here the reviewer inherits the author's list, and nothing surfaces at all ---
the verdict is clean, so the loop ends.
[`derive-dont-enumerate`](derive-dont-enumerate.md) is the general principle
behind both.

- **Do:** derive any enumeration you publish with a command, and publish the
  command beside it.
- **Do:** treat a reviewer restating your count as that count still being
  unverified.
- **Don't:** read a clean verdict as evidence that a scope claim in the diff is
  complete --- a reviewer can only check the members you named.
- **Don't:** count a reviewer's agreement as independent when its population
  came from your own prose.

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

**Findings hide on several surfaces,
and no single check sees all of them --- so read the verdict body,
any suppressed-comments block,
the inline comments,
the thread list,
and the verdict's own conclusion every round.**
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
- **A clean overview can hide a collapsed findings block.**
  Copilot can say it "generated no new comments"
  and create zero inline comments
  while placing substantive findings inside a collapsed
  `<details>` suppression block in the review body.
  The heading moves,
  so match case-insensitively on `suppressed` **inside the `<summary>`
  heading**, not anywhere in the body:
  PR #660 emitted `Comments suppressed due to low confidence (3)`,
  while PRs #1029 and #1031 emitted `Suppressed comments (4)`.
  A literal grep for either exact phrase can return a false zero.
  A body-wide match over-corrects the other way and can permanently reject a
  genuinely clean review, since ordinary overview prose can also contain the
  word --- review 4837572117's summary table read "suppressed Copilot
  findings" outside any collapsed block.
  A body read that stops at the overview is therefore not a body read, and a
  match against the whole body is not the right instrument either.
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

- **Do:** read all review surfaces before calling a PR clean,
  every round,
  including collapsed suppressed-comments blocks.
- **Do:** distinguish "no findings" from "no verdict" explicitly, and treat
  the latter as unreviewed.
- **Don't:** report clean on a zero thread count, however many checks are
  green.
- **Don't:** treat an empty review body as an all-clear without checking the
  inline comments.
- **Don't:** treat a "generated no new comments" overview as an all-clear
  until every `<summary>` heading has been checked case-insensitively for
  `suppressed` --- not until the whole body has, which flags ordinary
  overview prose that merely mentions suppressed findings.
- **Don't:** read a reviewer's silence as a verdict --- a job that posted
  nothing leaves the same zero counts as a job that found nothing.

**A comment can be evidence-dense, correct throughout, and state no verdict at
all --- and its density is what gets read as the conclusion.**
The "no verdict is its own state" bullet above covers a job that posted
*nothing*, and the instrument it prescribes is to read the job's own step
outcomes.
Neither half reaches this case.
The job succeeded, the comment is long and rigorous, and there is no failed step
to inspect --- so that remedy points at a surface reporting success.

It is not the "reviewer's own verification block can be wrong" case either,
which is a *wrong* verification under a *right* verdict.
Here the verification is correct and there is no verdict at all, which inverts
which part deserves suspicion.
That section already notes a block labelled "verification" is the part least
likely to be re-checked, because it presents as the checking having been done.
When such a block is the last thing on the thread it does something further:
it reads as the sign-off, and the more rigorous it is the more it reads that way.
So thoroughness is not evidence of a conclusion --- it is what disguises the
absence of one.

**A later comment stating no verdict does not supersede an earlier one.**
This refines the latest-wins rules rather than contradicting them.
Those rules (`CLAUDE.md`'s "re-read the **most recent** review comment", and
criterion 2's "latest review") assume the most recent artifact *is* a verdict,
and say to prefer it over a cached one.
They do not say what happens when the most recent artifact concludes nothing.
Absence is not a clearing: the standing verdict is the last one anyone actually
stated, however much has been posted since.
Read "latest" as ranging over verdict-bearing statements, not over comments.

Note this is wider than the HEAD-SHA scope the rest of criterion 2 uses.
A "Needs more work" posted against an *earlier* commit is outside every
HEAD-matching check, and a later verdict-less comment raises no finding either,
so a PR reads clean on both while its last real verdict was not.
`scripts/check-pr-fully-clean.py` decides this as its criterion 4, scanning the
whole review history chronologically for the last verdict-bearing statement.

- **Do:** identify the last statement that actually states a verdict, and treat
  that as the standing one.
- **Do:** scan the whole review history for it, not only items matching HEAD.
- **Don't:** read a verification section, however rigorous, as an approval ---
  it is evidence, and a verdict is a conclusion about evidence.
- **Don't:** treat a later comment's silence on the verdict as superseding an
  earlier "Needs more work".

(Morrison-Lab/ai-config#1267, 2026-08-07, reverted by #1275.
Verified from the API rather than from the revert's own account: the PR carried
`reviews | length` of 0, and its four comments ran
`21:56:09Z` **Needs more work**, `22:12:47Z` no verdict, `22:49:12Z` **Needs more
work**, `23:05:32Z` no verdict --- a long `### Verification` section ending
"Not merging."
It was merged at `23:38:12Z`, 49 minutes after the last stated verdict, and
reverted at `23:47:50Z`.
All four comments were posted under the author's own login, so "the PR has been
reviewed" was true while "an independent reviewer approved it" was not.)

**Another surface,
and the one that defeats the gate itself:
the review check can pass on a blocking verdict.**
The cases above are ones where a *reader* looks at the wrong place.
This is the case where the repo's own gate looks at the right place and still
reports green, because `require-review` tests whether a review **ran**, not
what it **concluded**.
So a "Needs more work" verdict and a "Ready for merge" verdict produce an
identical check row.

It compounds with case 1 in [`review-verdict-pitfalls.md`](review-verdict-pitfalls.md) rather than sitting beside it.
A review invoked without a `--comment` argument reports its findings in the
run's own comment and posts nothing as a thread --- and the better reviewers
say so in their last line, which is the tell worth grepping for.
The result is a PR with every check green, zero inline comments, zero
unresolved threads, and a blocking correctness finding sitting in plain text
that no count reaches.

This is the third numbered case in
[`review-verdict-pitfalls.md`](review-verdict-pitfalls.md) -- a check that
cannot fail on its own content, so its green carries no signal -- arriving on
the one job whose whole purpose is to gate on review outcome.
The difference is what makes it worse than the benchmark check recorded
there.
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

**`check-pr-fully-clean.py` itself has the mirror false positive: it can report
NOT clean over a clean verdict.**
The cases above are fail-open --- the instrument reads clean when the PR is not;
this script fails the other way.
Its `finding_patterns` scan ran over the whole review body, so a clean
`Ready for merge` verdict that merely *quotes* finding vocabulary ---
`**Location:**`, `Needs more work`, and the like --- tripped a pattern and
printed `contains findings (matched pattern ...)`.
It bites hardest on PRs about the review tooling itself, whose reviews naturally
discuss finding-indicator words, and its direction is fail-closed, so it is the
safe one: it makes the script untrustworthy for auto-confirming clean, never for
waving a real finding through.
The scan now blanks cited finding vocabulary --- fenced code blocks, inline code
spans, and double-quoted spans --- before matching (Morrison-Lab/ai-config#1202),
so the two documented instances (a `**Location:**` code span, a double-quoted
`Needs more work`) no longer trip it, while the structural findings-heading and
formal `CHANGES_REQUESTED`/`REJECTED` checks remain as independent backstops.
A finding-mood phrase stated *unquoted* in prose, or in a blockquote line the
strip does not cover, can still trip it, so when the script does flag on quoted
vocabulary the remedy is unchanged --- read the verdict's own conclusion rather
than the script's raw pattern match.

- **Do:** read the verdict's own conclusion when the script reports findings
  against a review whose prose merely discusses finding vocabulary.
- **Don't:** treat a `contains findings (matched pattern ...)` line as a real
  finding without reading the verdict body it matched.

**A verdict comment quotes verdict phrases, so a phrase search identifies
nothing --- and it misreads in both directions at once.**
Every case above concerns *reading* a verdict correctly.
This one is about the instrument a multi-PR status sweep reaches for, where the
tempting shortcut is a one-line `jq` `capture` of the first verdict phrase
appearing anywhere in the body.

The premise under that shortcut is that a verdict comment states verdict
vocabulary only when stating its own verdict.
It does the opposite.
Quoting is part of the genre: a comment cites the previous round's verdict to
say what it is confirming, pastes a repro block showing what a classifier
returned, and discusses what a phrase *should* classify as --- all before
reaching its own `### Verdict` section.
So the first match is usually somebody else's verdict.

The bidirectionality is what makes this worth its own entry rather than a note
on the section above.
That one is fail-closed by construction, which is why it is called the safe
direction.
A first-match phrase search has no direction at all, so it cannot be corrected
by an offset or by assuming the reviewer errs one way.
Measured on one sweep, 2026-08-08, taking the latest verdict-bearing comment on
each PR:

| PR | first phrase match | real verdict, at the last `### Verdict` | direction |
|---|---|---|---|
| [#1278](https://github.com/Morrison-Lab/ai-config/pull/1278) | `Ready for merge`, inside a fenced block quoting a classifier call | **Needs more work** | false-clean |
| [#1257](https://github.com/Morrison-Lab/ai-config/pull/1257) | `Needs more work`, inside a parenthetical citing the prior round | **Ready for merge** | false-blocked |

The false-clean direction is the expensive one: it produced a **merge
recommendation** on a PR whose verdict was blocking.

So call the instrument.
`scripts/check-pr-fully-clean.py` is this corpus's verdict authority, and
[`ardi`](ardi.md) already requires it for the single-PR loop --- the gap is that
nothing said so for a **sweep**, which is where the hand-rolled parser goes in.
That is [`deterministic-tools`](../principles/deterministic-tools.md)'s
constraint violated in the presence of the instrument, which is the shape worth
recognizing: the tool existed, was documented, and was mandated one workflow
over.

Where a body genuinely must be parsed by hand, anchor on the **last**
`### Verdict` heading and take the first non-empty line after it, which returns
the right answer on both rows above.
Two hazards survive even then, and both were observed on #1278.
A `### Verdict:` heading can itself appear quoted inside prose, so the *last*
heading rather than the first is load-bearing.
And a **human** comment can carry a backticked `### Verdict` while stating no
verdict at all, so select candidates on the `**Claude finished` body marker
above rather than on the presence of a heading.

- **Do:** call `check-pr-fully-clean.py` for a sweep's verdict column, exactly
  as [`ardi`](ardi.md) requires for one PR.
- **Do:** anchor on the last `### Verdict` heading when parsing by hand, after
  selecting candidates on the `**Claude finished` marker.
- **Don't:** take the first verdict phrase in a body as that body's verdict ---
  quoting other verdicts is part of what a review comment does.
- **Don't:** assume such a misread has a safe direction; one sweep produced a
  false-clean and a false-blocked.

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

**That remedy assumes the run checked out the PR head, and a `workflow_dispatch`-triggered review run does not.**
`claude-review.yml` dispatched with a `pr_number` input runs against `ref: main` --- its own `head_sha` is whatever `main`'s tip was at dispatch time, not the PR branch or the commit its gather-context step actually diffed.
The job fetches the PR's diff separately, through the API, inside the run, so nothing in the run object records which PR commit that fetch saw.
Reading `head_sha` here answers a different question than the one being asked, and it answers confidently: a real SHA, on a real branch, that happens to be irrelevant.

So for a `workflow_dispatch` run, the SHA check has no target to read.
Fall back to **timing**: compare the run's `created_at` against your own push timestamps.
A run dispatched before your latest push cannot have reviewed it, whatever its verdict claims about "the current diff."
Where the verdict makes a specific claim ("this wording is unchanged"), the cheapest confirmation is direct: read the file yourself and check whether the claim is still true.
A verdict that is empirically wrong about present file content is conclusive proof it reviewed an earlier one, with no run metadata needed at all.

- **Do:** check a `workflow_dispatch` review's `event` field before reaching for `head_sha` --- on that trigger type the field names the dispatch ref, not the reviewed commit.
- **Do:** cross-check a stale-suspected verdict's specific claims against the file directly, rather than only against run metadata.
- **Don't:** trust `head_sha` as "the commit reviewed" on a workflow-dispatch-triggered run --- that guarantee only holds for push/pull_request-triggered runs, which check out the PR head by construction.

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

**Deadlock -> escalate to a human.** If you and the reviewer(s) can't reach consensus on an item (a rebuttal was exchanged and neither side is budging), don't loop forever and don't unilaterally override the reviewer --- request a **human reviewer**, `@`-mention them in a comment summarizing the impasse, and surface the open item.

**An automated reviewer's verdict on a disputed factual/technical claim is not stable across independent runs, even with identical evidence available each time.** Don't treat one round's "settled, no need to keep arguing" as durable: the very same review job, re-triggered later with no new code changes, can re-raise a claim it previously retracted --- and then retract it again on a subsequent run --- purely from re-deriving the question differently each time, not from anything changing in the PR. This means a rebuttal thread's outcome (however many rounds of citations and counter-citations) doesn't itself resolve a genuine deadlock the way a human's decision does; only escalating per the bullet above actually settles it. The one thing that DOES help going forward: fold the authoritative citation/evidence directly into the code or doc being reviewed (a comment, not just a PR conversation reply) --- a fresh reviewer run re-deriving the claim from scratch is more likely to find the citation sitting right next to what it's evaluating than to dig through prior thread history for it, though even that is not a guarantee against a bot that ignores context already in front of it.

The several distinct ways a review job's check color, or the presence and
content of a posted comment, can diverge from a genuine, complete, correct
verdict --- the "eight numbered cases" this file used to walk through
inline --- now live in
[`review-verdict-pitfalls.md`](review-verdict-pitfalls.md), split out per
ai-config#1236 once that material pushed this file past the size gate.
