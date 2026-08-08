"Fully clean" is the terminal state the ARDI review loop drives toward.
A PR/MR is **fully clean** when **both** of these hold (and verified via `python3 scripts/check-pr-fully-clean.py <pr-number>`):

Worked-example case records for the rules below live in
[`fully-clean.cases.md`](fully-clean.cases.md), moved out of the auto-loaded context.

1. **All CI workflows and check runs are green AND completed.** Every workflow and check run passes --- not just the required checks and not just the review job.
   "Green" means finished with a passing outcome (success or skipped), not merely "currently reporting green while still running" --- never treat a workflow or check run that's still queued or in progress as clean, even if nothing has failed yet.
   **A reviewer's posted verdict does not mean the review check has finished, so don't let a clean verdict stand in for criterion 1 on its own job.**
   The bot posts its comment and then its run keeps going (bookkeeping steps, a cost tally, the gate job that consumes its result), so a full `Ready for merge` comment can sit on the PR for minutes while `claude-review` still reads `in_progress` and the `require-review` gate is still `queued`.
   Reading the verdict and moving straight to "clean" skips the very state this criterion exists to catch.
   The gap runs the other way from the stub-review case below: there the check is green and the verdict is missing, here the verdict is real and the check is unfinished.
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

**Another surface,
and the one that defeats the gate itself:
the review check can pass on a blocking verdict.**
The cases above are ones where a *reader* looks at the wrong place.
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

(Morrison-Lab/ai-config#1251, 2026-08-07: a `claude-review.yml` run dispatched at 18:02:03Z reported `head_sha: 7d050a36...`, `main`'s tip at that moment, on an `event: workflow_dispatch` run for PR #1251.
Its verdict claimed a specific wording fix was "unchanged in the current diff," which `grep`ing the live file disproved --- the fix had landed in a push before the verdict posted, sometime inside the run's own 18:02-18:08 execution window.
A second dispatch, triggered directly via `actions_run_trigger` rather than by re-posting an `@claude` mention (which risks re-triggering the credit-gated `claude-bot.yml` ack step on its own `contains(body, '@claude')` gate), produced a genuine current-head verdict.)

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

**A review job's pass/fail conclusion can diverge from whether a genuine clean verdict was actually posted --- check both directions, not just the check's color.** The familiar direction: a green review job that posted only a stub with no verdict (a stalled/crashed review run) is NOT a clean verdict --- re-trigger and read the actual comment before trusting green.
The inverse, easy to miss: a review job reporting FAILURE can still have posted a complete, genuine "Ready for merge" verdict with real findings-review content --- some guard scripts that gate the job's own pass/fail on detecting a verdict string can misfire and report failure even though a full review ran and passed.
Read the posted comment body, not just the check conclusion, before concluding a PR is or isn't clean.
If the check is a **required** check and you've independently confirmed the posted content is genuinely clean, that is still not authorization to merge past it yourself --- a required check failing is exactly the "stop and ask" case even under a merge-when-confident grant (see `mwc`'s scope note); report the evidence and let the human decide whether to override, fix the guard script, or relax branch protection.

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
That carve-out's condition is necessary for a quota stop and not sufficient for
one, since an expired credential dies at the same point and produces the same
numbers --- so read it as "this run did no billable work", never as "quota".
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

**A third case, distinct from either misfire above: some checks are designed to NEVER fail regardless of their own posted content, so their green color carries zero signal at all.** A CI-runner-relative benchmark check that gates a soft threshold (e.g. "regressed beyond 20% vs. baseline") may deliberately report success/pass at the GitHub-check level even when it posts a `:warning:` regression comment, precisely because the project has decided that threshold is "a human call, not an auto-block" rather than a hard gate. `gh pr checks` (or the equivalent status API) showing this check as PASS is consequently not evidence there is nothing to look at --- it only means the check ran, not that its content was clean. Read the check's own posted comment body every time, the same discipline the review-job case above already demands, but don't expect the check's pass/fail conclusion to ever flip for this class of check even on a real, large regression.

**A fourth case: a review job can post a syntactically valid, confidently stated verdict that is nonetheless invalid because it rests on a hallucinated premise about the PR's own state --- not a stub (no verdict) and not a misfire (guard-script/check-conclusion mismatch), but a fabricated fact baked into an otherwise well-formed review.** A reviewer that infers PR state from a commit message rather than querying the PR's actual `state`/`merged` API fields can mistake a routine `Merge remote-tracking branch 'origin/main' into <PR-branch>` commit --- pushed to resolve a sync conflict on the still-open PR branch itself --- for evidence the *PR* was merged into `main`, and confidently report "PR is closed, no action taken" while never actually reviewing the diff. This reads exactly like a legitimate all-clear (a `### Verdict` section is present, the job reports success), so the stub-detection guards described in CLAUDE.md's "Do the review yourself when the @claude workflow doesn't produce a verdict" section don't catch it. Sanity-check any surprising verdict --- especially "nothing to review" or "already merged/closed" --- against the PR's real API state before trusting it, and re-trigger for a genuine review rather than accepting a verdict-shaped comment built on a false premise.

**A fifth case, and the one that decides what "reachable" means in criterion 2 above: an external reviewer can decline to review at all, posting a refusal in the shape of a review.**
Unlike the four cases above --- all of which are a review that ran and produced something misleading --- this is a reviewer that never ran, and says so in a `COMMENTED` review whose whole body is the refusal (e.g. Copilot's *"unable to review this pull request because the user who requested the review has reached their quota limit"*).
Three consequences for driving a PR to fully clean:

- **A refusing reviewer is not "reachable,"** so criterion 2's external-verdict requirement falls to whichever external reviewer *is* working.
  Don't stall a PR waiting for a reviewer that is refusing --- but don't quietly downgrade to self-review either while another external reviewer is answering normally.
- **Reviewers fail independently.** One can be quota-dead while another reviews the same head normally, so check each one rather than generalizing from the first refusal.
- **Keep re-requesting each round anyway.** A quota resets on its own schedule, so a reviewer that refused a few pushes ago can come back mid-session --- which is exactly what criterion 2's "re-check availability right before declaring clean" is for.
  Say so explicitly when reporting a PR ready: name which reviewer's verdict the clean call rests on, and which one never weighed in at this head.

The mechanics of detecting a refusal (it arrives as a posted review, not an API error, so the request call's success proves nothing) are in [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md).

**The same reviewer has a third state, and it is worse for a reader than the refusal: the check goes green and no review is posted at all.**
A refusal at least leaves a record.
It costs a review and says so, in a comment anyone scanning the thread will see.
The silent state costs the same review and says nothing.
The check surface reports it in neither direction, and it fails two different
ways rather than one.
An earlier revision of this section said something stronger: that on the PRs
below the reviewer contributed **no check run at all**, and that the check
surface is therefore silent about it *by construction*.
That is too strong, and both observations are worth keeping with their dates
rather than replacing one with the other.

- **2026-07-31/08-01, on #1005 and #1008.**
  The check rollup carried no Copilot-attributable context.
  Re-measured 2026-08-03, `gh pr checks` still returns 0 such contexts for
  either PR, while `commits/<sha>/check-runs` returns exactly one for each ---
  a `copilot-pull-request-reviewer` run with `conclusion: success`.
  So the original measurement reproduces on the surface it was taken from, and
  is false on the other one.
- **2026-08-02, on #1056.**
  The reviewer contributed a check run that `gh pr checks` again did not list,
  caught this time while it was still `in_progress`.

Do not read that pair as the behaviour having changed.
Two dates cannot establish a change, and no change is needed to explain the
original record: the two surfaces disagreed with each other on the *same* PRs
on the *same* day, so reading the rollup accounts for it entirely.
Treat the check surface as unreliable about this reviewer in both directions.
The `gh pr checks` rollup can omit a check run that exists, per criterion 1
above, and the run itself can be green with no review behind it.

That second mode is the sharper one, and it is the newly evidenced one.
On #1008 `copilot-pull-request-reviewer` completed `success` while Copilot
posted no review on that PR at all.
On #1056 it completed `success` at head `cbf39b64`, while both of its actual
reviews sit at earlier commits, `252d8fb5` and `1e17d166`.
A green Copilot check therefore attests that the app ran, never that it
reviewed the current head --- which is exactly the inference a reader scanning
checks will draw from it.

Note which remedy already in this file the silent state defeats.
The "no verdict is its own state" bullet in criterion 2's four-surfaces list covers a job that posts nothing, and the instrument it prescribes is to read the job's own outcome rather than infer from the absence of comments.
That works there because the job **failed**.
Here it succeeded, so the outcome reads `success` and points away from the gap the bullet exists to expose.

What decides it is the review list filtered by the reviewer's own login, never the check run.
**Mind which surface you filter on, because the field name and the value both differ**, and getting either wrong returns zero hits and reads as "this reviewer did not review":

| surface | field | value |
|---|---|---|
| REST `pulls/<N>/reviews`, and `pull_request_read` `get_reviews` | `user.login` | `copilot-pull-request-reviewer[bot]` |
| `gh pr view <N> --json reviews` | `author.login` | `copilot-pull-request-reviewer` (no `[bot]`) |

Measured on `Morrison-Lab/ai-config#1005`, which carries a real Copilot review.
So a reader who takes the field name from one surface and the value from the other reproduces the exact false negative this section warns about.
A green check answers whether the app ran.
Only the review list answers whether it reviewed.
Read past the first page before concluding an entry is absent, since a busy PR can carry more reviews than one page returns.

The two failure modes above strengthen that instruction rather than
complicating it, because they land on the same remedy from opposite sides.
A check run the **rollup** omits leaves a reader of that rollup nothing to
read, and the run it does surface answers a narrower question than the one
being asked.
Note that the first of those is a gap in the rollup, never in the check run:
the run exists, and criterion 1's endpoint returns it.
Either way no amount of care reading checks recovers whether the reviewer
reviewed.
Read the reviews.

- **Do:** confirm each external reviewer by an entry in `get_reviews`, not by the conclusion of its check run.
- **Do:** read the `commit_id` on the review you find, since a green check at the current head is compatible with every review sitting at an earlier commit.
- **Do:** name a silent reviewer in the ready-for-merge report, exactly as the bullets above ask for a refusing one.
- **Don't:** read a green reviewer check as a verdict --- it survives a refusal, it survives silence, and it survives having last reviewed three commits ago.
- **Don't:** read an absent Copilot context in `gh pr checks` as evidence that no such check run exists.
  That rollup omits it, per criterion 1 above.
- **Don't:** reach for the job-outcome remedy above here.
  It is scoped to a job that failed, and this one succeeded.

**A clean verdict from the counting reviewer does not mean every reviewer's backlog is addressed --- sweep the other reviewer's earlier findings before declaring clean.**
The cases above are about a reviewer that refuses, goes silent, or last reviewed an earlier commit.
This is the inverse blind spot: a *second* reviewer that reviewed real, current code several rounds ago, raised findings, and has been silent since --- so its findings sit at a stale head, and the counting reviewer (the one whose verdict gates the merge) never inherited them.
When that counting reviewer returns a clean verdict, the natural reading is "the PR is clean", and the other reviewer's earlier, still-open findings evaporate unexamined.

They are easy to under-weight for two compounding reasons.
They are attached to a superseded commit, so they read as history.
And they often arrive as *suppressed* / low-confidence inline comments (Copilot's `<details>` block, per criterion 2's four-surfaces list), which reads as "the reviewer itself wasn't sure".
Neither makes a finding false.
A finding about a line the later commits never touched is still live at the current head, whatever commit it was filed against.

So before declaring clean on one reviewer's verdict, re-read the *other* reviewer's most substantive prior review and check each of its findings against the current code, exactly as you would a fresh one --- verify, then Address, Rebut, or Defer.
A clean verdict answers "did the reviewer who spoke find anything"; it does not answer "did the reviewer who went quiet leave anything real behind".

- **Do:** sweep a silent-since-earlier reviewer's prior findings against the current head before reporting clean, treating a stale-head or suppressed finding as live until checked.
- **Don't:** read one reviewer's clean verdict as evidence that a different reviewer's earlier backlog is empty.

**A sixth case runs the other way from all five above: the review is genuine and complete, but the workflow posts the reviewer's own tool invocation instead of the review body.**
The comment opens with a literal `gh pr comment <N> --repo <owner>/<repo> --body "$(cat <<'EOF'` and closes with `EOF\n)"`, wrapping a real, correct verdict as unrendered text --- the model emitted a shell command as its final response and the workflow posted that string verbatim.
Nothing is lost, and the same body usually also lands as a properly-rendered sibling comment, so the PR carries the review twice.
Two reasons not to shrug at it: a comment opening with a raw `gh` invocation reads as a broken run, so a human is likely to discount a review that actually passed; and a verdict-detecting guard script (`check-review-execution.sh`) is now matching against a shell command rather than prose, which can misfire into a needless stub-retry and a second full review's cost.
Read the body and extract the verdict from inside the heredoc rather than re-triggering.

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

**The zero-cost signature that names the quota case is necessary and not
sufficient, so reading it as "quota" is an inference rather than an
observation.**
The section above offers the duration signature as the *corroborating* half of
a diagnosis the cross-repo test has already made, and it is right to.
This is what happens when that signature is read on its own: `is_error: true`
with `total_cost_usd: 0` at `num_turns: 1` is genuinely what a quota stop looks
like, and it is equally what an expired or invalid credential looks like,
because in both cases the run dies at the model call having done no billable
work.
The result object cannot distinguish them, since the work that would have
distinguished them never happened.

Two things make the wrong reading feel confirmed rather than assumed.

The signature is **documented as the quota case**, in the review guard's own
carve-out and in
[`memories/claude-bot-workflows.md`](../../memories/claude-bot-workflows.md).
Matching a documented signature reads as recognition, so nothing about it
presents as a step you took.

And a **second reviewer can genuinely be quota-limited at the same time**, in
words, on the same PR.
That is a coincidence rather than corroboration, since the two reviewers hold
different credentials, and it is the trap worth naming: it arrives as an
independent source agreeing with you.

The cross-repo test above narrows this, and it is worth being exact about how
far, because the obvious reading claims one step too much.
A success elsewhere at the same time rules out **the service**.
It does not rule out the account's quota, and reading it as though it did is
the same over-reading one level up.

The reason is in this repo's own tooling.
`scripts/rotate-claude-token.py`'s docstring records that
`CLAUDE_CODE_OAUTH_TOKEN` is "provisioned one repo at a time, by whichever
Claude account the local CLI happened to be logged into", that "nothing
records which account minted a given token, and nothing can", and that "an
estate provisioned across several sittings ends up a mix of accounts that
cannot be untangled after the fact".
[`refresh-claude-token`](../../skills/refresh-claude-token/SKILL.md) says the
same.
So two repos' secrets are the same account only when someone has deliberately
made them so, and after the fact that is unanswerable rather than merely
unchecked.
A cross-repo success therefore leaves *two* live explanations --- a different
account with quota remaining, or the same account and a bad credential here ---
and only the second is a credential problem.

Note this is the Don't-bullet below about another reviewer's quota refusal,
arriving in the direction that flatters you.
There a different vendor's exhaustion is obviously not evidence about yours.
Here a possibly-different account's health is not evidence about yours either,
and it is harder to see precisely because both runs are the same reviewer
reading the same variable name.
The distinguishing fact is not "same tool" but "same account", which no API
call can supply.

**The decisive instrument is a before/after on the failing repo alone.**
Rewrite that repo's secret from a known account, change nothing else, and
re-run.
A run that then reaches the model settles it outright, because the credential
is the only variable that moved --- and it needs no assumption about any other
repo's account, which is exactly what makes it stronger than the cross-repo
comparison.
[`refresh-claude-token`](../../skills/refresh-claude-token/SKILL.md) owns the
rotation, and is right that no property of the secrets API proves a token will
authenticate: the proof is the run afterwards, never the write.

The secret's timestamps are a **triage** signal ahead of that, not a verdict,
and are still the cheap first call for this class:

```bash
gh api repos/<owner>/<repo>/actions/secrets \
  --jq '.secrets[] | "\(.name) \(.updated_at)"'
```

A failing repo whose token was written long before a working repo's is a
rotation that plausibly missed it, which tells you where to point the
before/after test.
It is not itself evidence, since it says nothing about either value or either
account.

- **Do:** rewrite the failing repo's secret from a known account and re-run,
  and treat that before/after as the thing that settles a credential
  diagnosis.
- **Do:** run the cross-repo test to establish that the service is up, and
  stop there.
- **Do:** use the `updated_at` comparison to choose which repo to test, rather
  than to conclude anything.
- **Don't:** read `total_cost_usd: 0` at `num_turns: 1` as evidence of quota
  --- an expired credential produces an object indistinguishable from it on
  every field the guard reads.
- **Don't:** read a cross-repo success as ruling out the account's quota; that
  holds only if both secrets were minted from one account, which after the
  fact is unanswerable.
- **Don't:** count another reviewer's quota refusal as corroboration; it is a
  different credential, so its exhaustion says nothing about yours.

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

**The expensive stub --- a `claude-review` run that bills minutes of model time
and posts no verdict --- has no stopping rule yet, and the fingerprints this
file already trusts cannot supply one.**
Everything above about when to stop retrying is built on runs that die before
the model call: the short-duration band, `total_cost_usd: 0`, `num_turns: 1`,
`Error is not retryable`.
The long stub the entry above mentions in passing --- 5m26s, `is_error: true`,
`subtype: "success"`, `permission_denials_count: null` --- fits none of them.
It reached the model, worked for minutes, spent real money, and returned no
verdict, so every discriminator this file offers either does not apply or
points the wrong way.
A credential before/after is pointless against a run that just billed five
dollars, and the empty denial count means nothing was refused.
What is left is the default, which is to retry --- and each retry costs a full
review.

**`num_turns` is the stopping rule, and it is sharp exactly where cost and
duration are noise.**
Those two vary between runs, because the model's own output length varies.
The turn count does not: it is the shape of the work rather than its size.
So compare it across **independent heads** --- different commits, different
diffs, a fresh run each time.
Identical `num_turns` there means the job walked the same path to the same
wall, and nothing that leaves the diff's shape intact will move it.
Say it that way rather than "no further commit will move it", which is the
looser claim and a false one: a commit that *shrinks* what the reviewer has to
read is exactly the thing that can clear the wall, and the paragraph after
next is about finding it.
What the turn count rules out is another attempt at the same work, which is
the only decision this rule is being asked to make.
That is a deterministic failure wearing an infrastructure failure's clothes,
and it is the one case where a second identical result is enough to stop on.

**Check for a configured turn cap before reading agreement as determinism.**
If the workflow sets `max_turns`, then every run that reaches it stops at the
same number by construction, and matching counts across two heads say nothing
at all --- they are the cap, not the path.
That reverses the diagnosis rather than weakening it: a capped run has been
cut off, so raising the cap is the fix and the entry below does not apply.
One grep of the workflow and whatever reusable workflow it calls settles it,
and this rule is only safe once that grep comes back empty.

Note this inverts the file's usual use of the field.
Above, `num_turns: 1` is read as a *value* naming the quota case, and read on
its own that is an over-reading.
Here the value carries nothing --- 11 says no more than 9 would --- and the
whole signal is that two independent runs **agree**.

Then look at what the diff makes the reviewer read, because a deterministic
failure is a property of the task.
A PR touching a directory whose sibling files run to thousands of lines can
exhaust the reviewer's context during its reading phase, every time, before a
verdict exists to post.
That recurs on every future PR of the same shape, so it belongs in an issue
against the reviewer's own configuration --- a file-size cap, a narrower tool
allowlist --- rather than in a wait for something to recover.

- **Do:** grep the workflow chain for `max_turns` first --- an agreement at
  the cap is an artifact, and inverts the diagnosis.
- **Do:** compare `num_turns` across the failed runs before paying for another
  attempt.
- **Do:** file it against the reviewer's setup once two independent heads fail
  identically, naming the diff shape that reproduces it.
- **Don't:** run the credential before/after against a failure that spent real
  money --- the spend already proved the credential authenticates.
- **Don't:** read varying cost and duration as evidence of transience while
  the turn count is fixed.

**A `cancelled` review is the one case where retrying is the cause rather than
the remedy.**
Every retry rule above is written for a run that **failed** --- errored,
stubbed, refused, crashed --- where a second attempt costs one review and buys
a genuine negative control.
A `cancelled` run is not a failure.
It is a run that something else killed, and under
`concurrency: cancel-in-progress` the thing that kills it is the **next
dispatch for the same key**.
So the standing retry-once remedy, applied here, is the mechanism that produced
the symptom: dispatching again cancels whatever is currently running.

Two places in this corpus currently say the opposite, and both need reading
with this caveat.
[`ardi`](../../skills/ardi/SKILL.md)'s step 6 and
[`preferences.md`](../../memories/preferences.md) each say that a review
cancelled with no comment should be dispatched cleanly.
That is right when nothing else is running and wrong when something is, and
neither says which case you are in.

**The casualty may not be yours.**
Every existing entry frames the victim as your own push-triggered run.
It can equally be a review a **human** asked for: `claude-bot.yml` carries
`review-workflow-file: claude-review.yml`, so a human posting the
review-trigger mention does not summon a separate reviewer --- it re-dispatches
the *same* workflow into the *same* per-PR group.
Neither party can see the other's intent, so the collision reads as a broken
workflow rather than as two people asking at once, and the retry that appears
to fix it destroys minutes of someone else's in-flight review.

So check before dispatching, and key the check on the **PR number** rather than
the branch.
[`push`](../../skills/push/SKILL.md)'s in-flight check filters
`gh run list --branch`, which is sound for a push-triggered run and unsound
here: a dispatched review records `headBranch: main`, so a branch filter finds
none of them.
[`memories/github-actions.md`](../../memories/github-actions.md)'s "A caller
with no `concurrency:` block can still have its runs cancelled" carries the
mechanism and the attributing query --- read each in-flight run's `PR_NUMBER`
from its own `gather-context` log.

- **Do:** read a review run's `conclusion` before retrying, and treat
  `cancelled` as "something newer is running" rather than as a failure to
  retry.
- **Do:** list the review workflow's in-flight runs and attribute each to a PR
  before dispatching, then wait for the survivor and name in the status report
  which run you are waiting on.
- **Don't:** apply the retry-once remedy to a run whose conclusion is
  `cancelled` in a `cancel-in-progress` group --- the retry is what cancels.
- **Don't:** assume the run you are about to cancel is your own.
- **Don't:** filter in-flight review runs by branch; a dispatched run reports
  the default branch whatever `--ref` it was given.

(`Morrison-Lab/ai-config#1281`, 2026-08-08: five `claude-review.yml` dispatches
ran within twenty minutes and only three were for #1281, each run's PR
confirmed from its own `gather-context` log.

| run | PR | dispatched by | created | ended | outcome |
| --- | --- | --- | --- | --- | --- |
| `31232187007` | 1281 | agent | 01:14:45 | 01:30:38 | cancelled |
| `31232684036` | 1276 | --- | 01:27:27 | 01:37:18 | success |
| `31232771312` | 1281 | human mention, via `claude-bot.yml` | 01:29:48 | 01:32:29 | cancelled |
| `31232853975` | 1281 | agent, retrying the cancelled first run | 01:31:40 | 01:50:52 | success |
| `31232973624` | 1283 | --- | 01:34:36 | --- | --- |

Each cancellation follows the next **same-PR** dispatch by 50 and 49 seconds,
matching the 45-to-46-second signature measured on #1224.
The human's mention killed a run 15m53s into its work, and the agent's retry
then killed the human's.
The survivor is simply the one nothing followed; it posted a genuine verdict at
01:50:37, so the window discarded two runs' work and produced one verdict.
The session's own reading of `gh run list` counted four colliding dispatches,
because that list reports `headBranch: main` for every one of them --- two of
the four were other PRs' reviews and were never in #1281's group at all.)
