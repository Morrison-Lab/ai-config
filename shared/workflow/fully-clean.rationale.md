# Rationale: fully clean

The mechanism, evidence, and argument behind the rules in
[`fully-clean.md`](fully-clean.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

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

   **When you are waiting for a job rather than timing one, poll its step list
   instead of its status --- the steps are not subject to the same lag.**
   The rule above says not to infer *duration* from `status`, which leaves the
   ordinary case looking harmless: a poll loop waiting for `completed` merely
   costs an extra poll when the field lags.
   That is true of any single poll and false of the loop, because the loop
   reads the one field the lag applies to, over and over, and stops only when
   it clears.
   So the lag is not amortized away --- it is the whole of the loop's tail.
   Worse, the loop's output is a column of identical `in_progress` lines, which
   is indistinguishable from a genuinely stuck job.

   `gh api repos/<owner>/<repo>/actions/jobs/<job-id>` returns the job's own
   `steps[]`, each carrying its own `status`/`conclusion`.
   A terminal step (`Complete job`, or the last one the workflow defines)
   reading `completed` settles it, and the step list doubles as a progress
   indicator while the job really is running --- which the status field cannot
   offer at all, having one value for the entire run.

   Reach for it whenever the answer changes what you do next: a review whose
   verdict is already posted is one you should be reading, not waiting on.

   **A `BlobNotFound` / HTTP 404 on the job-log fetch means the job has not completed, not that it has hung.**
   The block above says to read a run's duration from its log timestamps.
   That remedy is usually unavailable while a job is still running, because there is usually no log to read yet: GitHub typically archives a job's log blob at completion, so `gh api "repos/<owner>/<repo>/actions/jobs/<job-id>/logs"` (and the MCP `get_job_logs`) returns `BlobNotFound` / 404 until then.
   So a 404 there is evidence the job is still going, and reading it as a hang inverts the signal.
   The archive timing is a tendency rather than a contract, and it only supports the 404 direction: the blob can also be served mid-run (measured 2026-08-15 on run 31903219396, where `get_job_logs` returned a signed `logs_url` while the job's `status` read `in_progress`), so a served log URL is not evidence of completion either.

   A still-in-flight job also legitimately reads `status: in_progress` with `conclusion: null`, and neither the 404 nor that status distinguishes a normal long-running review from a genuinely stalled one.
   Only completion settles it, or the live streaming log in the Actions UI, which streams while the job runs regardless of when the blob gets archived.
   So do not conclude "hung" or "produced no verdict" from a 404 plus an `in_progress` status; wait for the job to finish and read the verdict it then posts.

   A bare 404 is ambiguous in one further way worth naming, because the two readings call for opposite responses.
   A job that *completed* with no logs at all --- the ~1s concurrency self-collision in [`debugging.md`](../../memories/debugging.md)'s "An Actions job that fails in ~1s with NO logs" section --- also 404s on the log fetch.
   The discriminator is the job's own `status`/`conclusion`, never the 404: `in_progress` / `null` is still running, while `completed` / `failure` with `completed_at` stamped before `started_at` is that instant-fail case.

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

2. **Every reviewer's latest verdict is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.
   A later all-clear from a different reviewer does not supersede a standing
   not-clean (ai-config#2274).
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

**Both criteria are per-PR, and a stack is where that stops being automatic.**
Everything above reads as being about "the PR" because a session normally has one.
Two stacked PRs are one unit of *work* and two units of *evidence*, so every check here is owed twice --- and the phrase "I read the review" silently becomes ambiguous the moment a second PR exists.

The failure needs no carelessness, only adjacency.
Stacked PRs are reviewed within seconds of each other by the same reviewer, their comments look alike, and they are usually open in the same status sweep.
So an impression formed from one PR's verdict transfers to the other without anything asserting it, and the transferred impression is *correct about a real review* --- just not that PR's.

Two things make it survive the round.
A reviewer that refuses on one PR looks like an answer for the pair, whereas [`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s fifth case already establishes that reviewers fail independently --- and the same independence holds across PRs, so one reviewer's refusal on the stacked PR says nothing about whether a different reviewer posted there.
And the stacked PR is the one whose evidence gets skipped, because the base is what the session is attending to.

Settle it per PR, from the `**Claude finished` body marker rather than from recollection, and say which PR each verdict came from when reporting the pair:

```bash
for n in <A> <B>; do
  printf '%s: ' "$n"
  gh api "repos/<owner>/<repo>/issues/$n/comments" --paginate \
    | jq -s '[.[][] | select(.body | startswith("**Claude finished"))] | length'
done
```

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
Both assume a lapse of care at some desk.
For the author-side case where every figure was gathered carefully and the table
simply went stale as later rounds changed the diff, see [`ardi`](ardi.md)'s
"A verification table you write in the PR body is the same defect one artifact
over" --- and note that its remedy is to re-derive by command at push time
rather than to re-read, since reading is no instrument for a wrong count.

The secondary signal is worth acting on rather than merely noting.
A reviewer's reconstruction error usually traces to something genuinely
ambiguous in the diff, so treat it as evidence about your own prose and not
only about the reviewer.

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

**What "an approving review" means here is not a review state.**
Across the 25 most recent merged PRs, all 106 posted reviews are `COMMENTED` and
none is `APPROVED` --- `the repository owner`'s own included, so this is not a bot
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

The reason this defeats otherwise-good instruments is that each check answers
a narrower question than the one being asked.
"Are all threads resolved" is not "are there no findings", and neither is
"does the verdict say ready".
Per [`algorithmatize-checks`](algorithmatize-checks.md), prefer the instrument
that decides the question exactly --- and where none does, as here, say so
rather than substituting the nearest available count.

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
Absence is not a clearing: each reviewer's standing verdict is the last one
that reviewer actually stated, however much has been posted since.
Read "latest" as ranging over verdict-bearing statements, not over comments,
and as per reviewer, not as the globally last comment
(ai-config#2274).
A later all-clear from a different reviewer does not supersede a standing
not-clean.

Note this is wider than the HEAD-SHA scope the rest of criterion 2 uses.
A "Needs more work" posted against an *earlier* commit is outside every
HEAD-matching check, and a later verdict-less comment raises no finding either,
so a PR reads clean on both while a reviewer's last real verdict was not.
`scripts/check-pr-fully-clean.py` decides this as its criterion 4, scanning the
whole review history chronologically and failing when any reviewer's latest
verdict-bearing statement is not-clean.

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

[`hooks/no-handrolled-verdict-parse.py`](../../hooks/no-handrolled-verdict-parse.py)
mechanizes this, per
[`algorithmatize-checks`](algorithmatize-checks.md): it refuses a Bash command
that matches a verdict phrase against a PR's review comments while
`check-pr-fully-clean.py` has not answered for that PR.
The discharge is deliberately per-PR --- one call early in a sweep must not
license hand-rolling the rest of it --- and a genuinely needed hand parse
clears the guard with an `ALLOW_HANDROLLED_VERDICT_PARSE=1` prefix.

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

**That remedy assumes the run checked out the PR head, and a `workflow_dispatch`-triggered review run does not.**
`claude-review.yml` dispatched with a `pr_number` input runs against `ref: main` --- its own `head_sha` is whatever `main`'s tip was at dispatch time, not the PR branch or the commit its gather-context step actually diffed.
The job fetches the PR's diff separately, through the API, inside the run, so nothing in the run object records which PR commit that fetch saw.
Reading `head_sha` here answers a different question than the one being asked, and it answers confidently: a real SHA, on a real branch, that happens to be irrelevant.

So for a `workflow_dispatch` run, the SHA check has no target to read.
Fall back to **timing**: compare the run's `created_at` against your own push timestamps.
A run dispatched before your latest push cannot have reviewed it, whatever its verdict claims about "the current diff."
Where the verdict makes a specific claim ("this wording is unchanged"), the cheapest confirmation is direct: read the file yourself and check whether the claim is still true.
A verdict that is empirically wrong about present file content is conclusive proof it reviewed an earlier one, with no run metadata needed at all.

**A third surface names a commit the run never read, and unlike the two above
it points the confident direction: the run object's own
`pull_requests[].head.sha`.**
Both rules above leave you without a usable SHA --- a caption that may be
stale, and a `head_sha` that names the dispatch ref.
A workflow run object also carries a `pull_requests[]` array, and its
`head.sha` looks like the missing answer.
It is not an answer about the run at all.
That field is a live pointer to the pull request, resolved when you read it, so
it reports the PR's **current** head whatever commit the run checked out or
diffed.

The failure direction inverts relative to the caption case.
A stale caption reads as a stale review, which invites a needless re-trigger.
This field reads as a **current** review, so it argues that the verdict already
covers your latest push --- and it argues that with a real SHA matching your
branch tip exactly.

The field also empties once the PR closes, so on a merged PR it answers nothing
rather than answering wrongly.
Read an empty array as carrying no information, not as a finding.

So the field cannot distinguish the case this criterion is about, and the
remedy is the one the block above already reaches for in its last line:
**read the review body.**
Find a figure, a quotation, or a claim in the verdict whose value differs
between the candidate commits, and check which one it states.
A verdict empirically wrong about present file content read an earlier commit,
whatever any SHA field says.

**`check-pr-fully-clean.py` uses the same unreliable body-text surface, and
whichever SHA that text happens to contain --- present, absent, or wrong ---
is incidental to which head the run actually reviewed.**
The three blocks above are about a reader trusting a comment's own caption.
The script has the identical instrument and a sharper version of the same
blind spot, moved into code: for an issue-comment verdict with no
formal-review `oid`, its match requires the head SHA, full or short, to
appear as a literal substring of the comment body, and its fail-closed
branch treats an absent SHA and a present-but-wrong SHA identically --- no
match, either way.

That is the right call against a stale review, which is what the design is
defending against.
It is the wrong call whenever the body's SHA content has nothing to do with
the question being asked, and that is the ordinary case rather than an edge
one, because a hex token lands in a review body for its own reason, not to
answer "does this evaluate HEAD."
A findings-free verdict usually has nothing to cite at all: no
`blob/<sha>/...` permalink, no prose reference to the head commit, since
there is no finding to anchor a citation to.
A verdict can also discuss a commit's own message rather than its diff, or
quote a SHA the diff itself cites while verifying some other claim in the
PR, and either way name a real commit while never mentioning the head ---
and the SHA it lands on can be an *earlier* commit on the same branch, or a
commit from an entirely different PR that the diff happens to reference.
So the failure concentrates on exactly the verdicts criterion 2 exists to
certify: the cleaner the review, the less its body has to do with the head
SHA at all, and the more likely the script reports `No review comment has
been posted evaluating HEAD SHA <sha> yet` over a PR that is in fact clean.

The direction is overwhelmingly the withholding one, but it is not a
guarantee against the other, and the reason is the same substring test that
produces the withholding: the match certifies only that a SHA string
appears somewhere in the body, never why it is there or what the run
actually evaluated.
A slow review of an earlier commit that posts after a newer push can, in
principle, still name the new head --- this repo's review jobs routinely run
live `gh` queries as part of their own verification (a "Verification
performed" section quoting a freshly fetched field is the common shape), so
a review's commentary can echo the PR's *current* head even while its diff
analysis is against an older one.
That is the exact review-vs-push race the script's own comment names as the
reason for the fail-closed branch, and the branch defends only against a
*wrong* SHA blocking a match, not against a coincidentally *current* one
passing a stale one through.
No confirmed instance of it exists here; the argument is about the
mechanism's soundness, not a reported failure, and finding one would need a
systematic search this fragment has not run.
So treat a "no review at this HEAD" result as **inconclusive**, not as a
settled negative, and treat a clean discharge as the *likely* reading
rather than a certified one.
A needless re-dispatch is still the expensive mistake the first block above
already warns about, since it can cancel a review already in flight under
`concurrency: cancel-in-progress` --- so weigh both readings against that
cost rather than reflexively re-checking either.

This also rules out the fix a reader might otherwise reach for: asking
reviewers to cite their head SHA more consistently would close the
no-SHA cases and leave the wrong-SHA case exactly as broken, since a body
can already cite a SHA and still be citing the wrong one.
The only sound surface is the one the blocks above already name --- the
run's own metadata, never the body.

Settle it in one call, using the rules two blocks above rather than the
comment body: read the flagging run's `event`, `head_branch`, and
`head_sha`.

```bash
gh api repos/<owner>/<repo>/actions/runs/<run-id> \
  --jq '{event, head_branch, head_sha, created_at}'
```

A push- or pull_request-triggered run's `head_sha` is the reviewed commit
unconditionally.
A workflow_dispatch run's `head_sha` is reliable only when it was dispatched
with an explicit `--ref` naming the PR branch --- confirm `head_branch`
matches the PR's own branch, not `main` --- since a dispatch with no `--ref`
runs against `main` by default and its `head_sha` then names that instead,
per the `workflow_dispatch` rule two blocks above.

(`Morrison-Lab/ai-config#1213` tracks the underlying script defect, filed
2026-08-06 against `#1207`.
Three instances, same root cause, each drawn from a **merged** PR whose head
is therefore frozen --- adding a row for an open PR ties the row to a SHA
that the next push retires, which is exactly the staleness this whole file
warns against:

| PR | verdict | SHA(s) in body | head | script result |
| --- | --- | --- | --- | --- |
| `#1207` | clean | none | `3e702562` | no match |
| `#1448` | clean | none | `8316d121` | no match |
| `#1450` | clean | `2b943b1a` (an earlier commit, cited for its message, not its diff) | `f73a9a3f` | no match |

`#1448`, 2026-08-13: run `31673022785` was dispatched `workflow_dispatch`
with `--ref ums/duplication-check-misses-merged` at `06:12:59Z`, 53 seconds
after the PR's head commit.
Its own metadata reads `head_branch: ums/duplication-check-misses-merged`
and `head_sha: 8316d12106b9f8393832c2dd561fad2b5334ff96`, matching the PR's
`headRefOid` exactly.
The posted verdict was **Ready for merge**, no findings, 0
`CHANGES_REQUESTED` reviews, 0 inline comments, and its body carried no SHA
at all.

`#1450`, 2026-08-13: the round-2 verdict, on run `31718638916`, was
**Ready for merge**.
Its body's only commit-shaped hex token, `2b943b1a`, names the oldest of the
branch's three commits, cited because that commit's own message carried a
stale count --- an observation about the commit's prose, not a reference to
the head.
The branch's actual head, `f73a9a3f`, appears nowhere in the body.)

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

The several distinct ways a review job's check color, or the presence and
content of a posted comment, can diverge from a genuine, complete, correct
verdict --- the "eight numbered cases" this file used to walk through
inline --- now live in
[`review-verdict-pitfalls.md`](review-verdict-pitfalls.md), split out per
ai-config#1236 once that material pushed this file past the size gate.

## Exit 0 is not the whole answer either: read the `verdict scan:` line

**Exit 0 is not the whole answer either: read the `verdict scan:` line the checker prints, because it can say `0 bore a verdict, latest = NONE` on a run that exits clean.**

Four independent decisions have to line up for that, and every one of them is the script working as designed --- which is why reading the source afterwards confirms the behaviour rather than correcting it, and why no part of the run looks wrong at the time.

1. A quota-or-credential **skip notice** is posted by `github-actions[bot]`, so the comment loop's author test admits it.
2. The notice carries a `View run` link, and `_resolve_run_head_sha` resolves that run's `head_sha` to HEAD --- so a comment stating explicitly that no review happened is counted as a review *evaluating HEAD*.
   That resolution is the right fix for the stale-body-SHA problem this file documents.
   It simply has no opinion about what the comment says.
3. The notice contains none of `finding_patterns`, so the HEAD-matching half prints its tick.
4. `check_latest_verdict()` returns `True`, because it blocks on exactly one value --- `not-clean` --- and an empty verdict is not that value.

The last step is deliberate and correct on its own terms: a long, evidence-dense comment that never concludes must not supersede an earlier verdict, which is why `classify_verdict()` returns `""` rather than guessing.
What the exit status then does is collapse "nothing objected" and "nobody looked" into the same 0.

The printed scan line is therefore the load-bearing surface rather than a progress message, and the script says so itself.
`check_latest_verdict()`'s docstring states that it prints what it examined alongside what it found, "so a zero here cannot be read as an all-clear when the real cause is that nothing was examined", citing [`fail-fast`](../principles/fail-fast.md).
The instrument already reports the distinction.
Only the exit status discards it.

So `0 bore a verdict` and `latest = NONE` mean **unreviewed**, which is [`self-review-fallback`](self-review-fallback.md)'s territory.
Note that this is the fragment's own skip-notice rule reaching one layer down: a skip notice does not supersede prior findings, and it equally does not constitute the review that criterion 2 requires --- but the instrument built to enforce criterion 2 counts it as one.

## The author filter gates formal reviews and not comments

**The author filter gates formal reviews and not comments, so a human-authored comment enters that same scan on body text alone.**

Only the formal-review loop consults `_is_bot_author` on its own, and its in-code comment gives the reason: a formal review carries a real `commit.oid`, so admitting one attributes it to HEAD with no body-content check --- hence the tight author gate there.
Comments have no oid, so they are admitted first on markers and matched to HEAD afterwards.
The asymmetry is a consequence of that design rather than an oversight, which is what makes the wrong generalization so easy: the strict loop's rule reads like the function's rule.

Admission and classification also read **different copies of the same body**.
`is_review_header` matches the raw body, while `classify_verdict()` scans `strip_cited_finding_vocab(body)`.
A comment can therefore be admitted *because* it quotes a verdict inside a code span and then contribute no verdict, since the span it was admitted on is blanked before classification.
Both rules are behaving correctly and they compose badly: the quoted-vocabulary guard (#1202) does its job, and the population it guards was widened by a marker test it never sees.

What keeps such a comment out of `matching_items` afterwards is only whether it cites the current SHA --- a property of what you wrote, not of who you are.
So "no human comment appeared in `matching_items`" is evidence about that comment's text and not about the filter.
