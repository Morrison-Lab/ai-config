# GitHub Actions outages: detecting one, and cleaning up after it

A platform incident and its wreckage, kept together because the two halves are
one topic and each is unreadable without the other: an outage presents as
**absent** checks rather than failing ones, and after it clears the PRs it hit
are left in states that look like ordinary failures.

Detecting one also means ruling one out, so the outage's commonest lookalike
lives here too --- a change to shared configuration, which fails across every
repo at once exactly as an outage does.

Split out of [`github-actions.md`](github-actions.md), which keeps the generic
Actions-authoring material.

## Check the GitHub status page when workflows stall across several PRs at once

A platform incident presents as **absent** checks, not failing ones.
The workflows a repo normally runs simply never start, so every affected PR
reports a near-empty check list, `mergeStateStatus: BLOCKED`, and nothing red
to point at.
That shape is the opposite of what a reader expects an outage to look like, and
it is why the per-PR explanations get reached for first.

`https://www.githubstatus.com/` answers it, and the JSON endpoints are far
cheaper to parse than the page.
Both were verified working on 2026-08-06:

```bash
curl -s https://www.githubstatus.com/api/v2/summary.json |
  jq -r '.status.description, (.components[] | select(.status != "operational") | "\(.name): \(.status)")'

curl -s https://www.githubstatus.com/api/v2/incidents/unresolved.json |
  jq -r '.incidents[] | "\(.name) | \(.impact) | \(.created_at) | \(.incident_updates[0].body)"'
```

The first prints the overall description plus every degraded component; the
second prints each open incident with its impact, its **start time**, and its
latest update text.
That start time is load-bearing for the confounding half below, so read it
rather than only the headline.

**The tell is plural and repo-wide, which is what separates it from every
per-PR explanation.**
Reach for the status page when checks are absent or truncated across
**several unrelated PRs at once**, and a repo-wide
`gh run list -R <owner>/<repo> --limit 15` shows a workflow type that used to
run and now does not.
The second half is what makes the finding falsifiable: a timestamp earlier the
same day where the full workflow set ran normally, and nothing of that type
since.

A **single** PR with slow or missing checks is a different question, and the
per-PR explanations are the right ones there --- a job gated behind an earlier
one, a draft that suppresses the review workflow, a check run the rollup omits
(see [`fully-clean`](../shared/workflow/fully-clean.md)'s criterion 1).
Do not reach for the status page on one PR, and do not reach for those on
several.

**The near-miss is a plausible known per-PR cause, which is worse than having
no explanation at all.**
A repo that already carries a recorded pattern explaining late checks supplies
a reading that is real, fits the symptom, and is per-PR --- so it sends you to
investigate each PR in turn, one at a time, while the actual cause is upstream
of all of them.
The scope of the symptom is the discriminator, not its shape: a per-PR cause
cannot explain PRs whose only common factor is the platform.

- **Do:** check the status page as soon as several PRs show absent checks
  together, before opening any of them.
- **Do:** corroborate with a repo-wide `gh run list`, naming the workflow type
  that stopped and the last time it ran.
- **Don't:** diagnose per-PR when the repo has a plausible known per-PR
  explanation --- that explanation is the trap, and its fit is not evidence
  against an outage.
- **Don't:** retry a workflow dispatch or wait on CI during a declared Actions
  outage; the incident's own updates say when jobs will run again.

**An incident disclosed LATE can retroactively supply a rival cause for
something you already diagnosed, and accepting it is not obviously right
either.**
An incident's update text names the services it affects, and that list can
include a component whose behaviour you explained hours earlier on other
grounds.
The official-sounding new explanation then looks like a correction, so the
natural move is to revise --- which can discard a correct diagnosis.

What settles it is whether your evidence **predates the incident start**.
Evidence gathered before the incident began cannot have been caused by it, so a
diagnosis resting on that evidence survives regardless of what the incident
says.
Only the observations falling inside the incident window are newly ambiguous.

A second discriminator, where it exists: **specific wording**.
A failure whose message names a particular condition is distinguishable from a
generic error, and the specific one is unlikely to be what a broad outage
produces.

- **Do:** compare every timestamp in your evidence against the incident's
  `created_at` before revising a diagnosis it appears to contradict.
- **Do:** treat a specifically-worded failure as distinguishable from the
  generic errors an outage produces.
- **Don't:** revise a diagnosis because an official announcement arrived later
  and mentions the same component.
- **Don't:** treat the observations inside the incident window as settled
  either --- those really are ambiguous, and saying so is the honest report.

(`ucdavis/bcs` #594, #597, and #591, 2026-08-06.
All three reported `mergeable: MERGEABLE`, `mergeStateStatus: BLOCKED`, and
exactly one check run each; on #594 that one run was CodeQL's
`Analyze (python)`, `completed/cancelled` after 15m1s.
None of R-CMD-check, Check for PHI, Version increment check, Check
Non-Standard Characters, Lint Markdown, or Claude Code Review had started.
`gh run list --limit 15` showed every one of those running normally at
08:30:47Z that morning, and from 18:34Z onward only `Code Quality: PR #NNN`
runs existing.
The session was about to diagnose this per-PR against that repo's recorded
"check runs appear late" pattern, where the platform matrix waits on an
`update-snapshots` job.
The real cause was the incident "Incident with Actions", impact `critical`,
`created_at` 2026-08-06T15:22:49Z, still unresolved about three and a half
hours later, with `Actions` and `Pages` both at `major_outage`.

Its 18:46:37Z update also named "Copilot code review" as affected, which
retroactively offered a rival explanation for ten Copilot review refusals the
same session had already attributed to quota and called thoroughly established.
Ten refusal timestamps were 2026-08-05T23:53:11Z, and on 2026-08-06 at
00:35:07Z, 05:00:01Z, 05:07:13Z, 05:32:35Z, 05:51:48Z, 06:37:17Z, 06:42:16Z,
18:39:33Z, and 18:46:31Z.
Eight of the ten predate 15:22:49Z, so quota was independently established and
the original diagnosis stood; only the last two fall inside the window.
The refusal bodies also carried quota-specific wording --- "because the user
who requested the review has reached" --- rather than a generic error.)

## A repo-wide failure need not be an outage --- a shared-config change looks the same

The section above separates a platform incident from a per-PR cause, and its
discriminator is **scope**: plural and repo-wide versus single.
That test leaves a third category unaddressed, and the third category passes
it.
A change to configuration every repo consumes --- a marketplace manifest, a
reusable workflow, a pinned action, an org secret --- fails everywhere at once,
so it is plural and repo-wide exactly as an outage is.
The status page then comes back clean, which reads as ruling out the only
repo-wide explanation on offer.

Two things separate it from an outage, and both are cheap.
A config break usually produces **failing** checks with a specific message,
where an outage produces **absent** ones --- the shape distinction the section
above already draws.
And the shared repo's own recent merges are a short list: `gh pr list -R
<shared-repo> --state merged --limit 10 --json number,title,mergedAt` covers
the window in one call.

### Build the timeline from the commits that govern each transition

Once a config change is the suspect, the diagnosis becomes a timing claim, and
the misleading evidence is no longer a log.
It is a set of timestamps and identifiers that sit *near* each transition
without governing it, and each one reads as the fact you wanted.

- **A commit's own date is not when it reached the default branch.**
  `git log`, `gh api repos/<o>/<r>/commits/<sha>`, and the commit page all show
  the author and committer dates, stamped when the work was written on a
  branch.
  The change lands when its PR merges, and the interval between those two is
  exactly the window a propagation-delay or cache-lag story fills.
  Read `gh pr view <N> --json mergedAt`, or the merge commit's own committer
  date, and treat the commit's date as saying nothing about the default branch.
- **A log line that also appears in the passing run is not evidence about the
  failure.**
  A tool that prints `Refreshing cache` every time it does the thing prints it
  on success too, so quoting it from the failing run establishes only that the
  tool ran.
  Grep the last known-good run for the same line before citing it.
- **A run's `head_sha` is what says which version it exercised.**
  A success after the fix merged is the expected post-fix state rather than a
  counterexample to the diagnosis, and a success from before the defect landed
  ran code that never contained it.
  Read the SHA, then place it against the merge times above.

The last two fail in the direction of feeling like *extra* rigor, which is why
they survive a careful session.
Quoting a log line is more concrete than asserting a mechanism, and hunting for
a case that should also have broken is the disconfirming move this corpus keeps
asking for --- so each arrives as evidence being gathered rather than as a step
being skipped.
Neither discriminates until you check which population the line or the run
belongs to.

The cost is larger than a wrong sentence, because a timing explanation *is*
triage guidance.
"A latent break that surfaces gradually" tells the next reader that repos will
fail at staggered times and that a recent success is not evidence against the
diagnosis.
Both are the opposite of true when the break is immediate, so the wrong
mechanism spends the one check that would have settled it.

- **Do:** check the shared repo's recent merges when several repos fail
  together and the status page is clean.
- **Do:** take every transition time from the merge that performed it ---
  `mergedAt`, or the merge commit's committer date.
- **Do:** grep the last passing run for any log line you are about to cite as
  evidence of the failure.
- **Do:** read a run's `head_sha` before reading its outcome as evidence about
  a defect, in either direction.
- **Don't:** read a clean status page as ruling out a repo-wide cause.
- **Don't:** read a commit's author or committer date as when it landed on the
  default branch.
- **Don't:** explain a gap between a change and its first failure before
  confirming the gap exists.

(Morrison-Lab/ai-config#1248, 2026-08-07: `claude-review` failed in every
consumer repo after #1238 lowercased the plugin marketplace's `name` while the
shared workflow still installed `ai-config@Morrison-Lab`.
The issue diagnosing it carried a section headed "Why it did not break
immediately", asserting that the rename "landed at 02:53Z" while a review still
succeeded at 03:37Z, so runners "were serving a cached manifest under the old
name until the cache turned over".
`02:53:17Z` is commit `6dc0cb49`'s author and committer date on its branch;
`gh pr view 1238 --json mergedAt` returns `2026-08-07T05:32:15Z`, so the rename
was not on `main` at 03:37 and that success needs no explaining.
The first failure, at 05:43Z, is 11 minutes after the merge rather than three
hours after the commit, so the break was immediate.
The two cache lines the issue cites are in the passing run verbatim:
`gh run view 31144863822 -R UCD-SERG/serocalculator --log` prints
`Refreshing marketplace cache` and `Cleaning up old marketplace cache` at
`03:37:16.549`, immediately before `Successfully added marketplace:
Morrison-Lab`, and again a second earlier for a different marketplace.
A later success at 06:11Z was then read as disconfirming the caching story;
that run's `head_sha` is `1a21df1e`, the fix commit from #1247, merged at
06:05:10Z, so it was the expected post-fix state and evidence about neither
hypothesis.)

## After an Actions outage clears, the wreckage has two shapes and they need different recoveries

Detecting a live incident and cleaning up after one are different jobs.
The section above covers **detection**.
This one starts where it stops: the incident has resolved, and the PRs it hit
are still broken in two different ways that call for two different fixes.

**Shape 1 --- the push was swallowed entirely.**
No `pull_request` or `push` event was ever processed, so the head has no check
runs, and `gh run list --branch <b>` still shows the newest runs sitting at the
**previous** head.
There is nothing to rerun, because nothing ever ran.
Recovery is to trigger the workflow yourself
(`gh workflow run validate.yml --ref <branch>`), or to push again.

**Shape 2 --- the jobs were cancelled mid-flight.**
A run exists, its run-level conclusion reads `failure`, and every job inside it
reads `completed/cancelled` with an **empty steps array**.
Recovery is `gh run rerun <run-id>`, with no code change.

**The discriminator is the steps array, not the conclusion.**
A job that is `completed/cancelled` having recorded **zero steps** never ran a
line, so it is an outage casualty rather than a real failure.
Read the steps:

```bash
gh api "repos/<owner>/<repo>/actions/runs/<id>/jobs" \
  --jq '.jobs[] | "JOB \(.name) \(.status)/\(.conclusion) steps=\(.steps|length)", (.steps[]? | "    \(.number). \(.name) => \(.conclusion // "-")")'
```

Add `/attempts/<n>` before `/jobs` to inspect a superseded attempt after a
rerun has already repaired the run, which is the only way to re-measure this
once recovery has happened.

**A second surface disagreement, distinct from the one already recorded.**
For a run in shape 2 the commit check-runs endpoint reports `cancelled` while
`gh run list` reports `failure`, because an all-cancelled run rolls up as a
failed one.
Neither is wrong, and a reader who consults only the run list sees `failure`
and starts debugging a validation error that never happened.
[`fully-clean`](../shared/workflow/fully-clean.md)'s criterion 1 already
establishes that `gh pr checks` and the check-runs endpoint disagree about
**which checks exist**, and that the endpoint is authoritative for
enumeration.
This is a different disagreement, between the **run list** and the check-runs
endpoint, and about a run's **conclusion** rather than about enumeration ---
so do not treat the recorded rule as already covering it.

**Do not read `commits/<sha>/status` as evidence for shape 1 on this repo.**
An empty statuses array looks like the swallowed-push signature and is the
baseline here: `fully-clean`'s criterion 1 records that
`Morrison-Lab/ai-config` returns `{"state": "pending", "n": 0}` on **every**
head checked, because the repo posts no commit statuses at all.
Re-measured 2026-08-07 on PR #1219's head, fully recovered and carrying six
successful check runs, it still returns `{"n":0,"state":"pending"}`.
The discriminating reads for shape 1 are the empty **check-runs** list plus a
`gh run list` still parked at the previous head.

**Sweep after the incident resolves, and re-derive the PR set.**
Both shapes leave a PR sitting quietly with nothing red, so neither announces
itself; a swallowed push in particular can sit green-but-unrun indefinitely.
Take the open-PR set from a live query rather than from memory, per
[`derive-dont-enumerate`](../shared/workflow/derive-dont-enumerate.md), and
check each PR for both shapes, since the recoveries differ.

- **Do:** read a job's steps array before believing its conclusion --- zero
  steps plus `cancelled` is an outage casualty, not a failure.
- **Do:** rerun a shape-2 run and re-trigger a shape-1 push, and say which one
  you did, since only the rerun is a genuine no-op control.
- **Don't:** debug a `failure` from `gh run list` before checking whether every
  job under it was cancelled.
- **Don't:** cite an empty `commits/<sha>/status` as evidence of anything on a
  repo that posts no statuses; it reads the same before and after recovery.

(2026-08-06/07, `Morrison-Lab/ai-config`, during the `critical` "Incident with
Actions" that PR #1223's case record dates to 2026-08-06T15:22:49Z.
PR #1219's head `8e1c9014` was pushed during the incident and had no check runs
at all, with `gh run list` still at the previous head; it recovered only once
the workflow was dispatched explicitly, and now carries six `completed/success`
runs.
PRs #1222 and #1223 hit shape 2: `validate` runs `31126751339` (head
`73a4b3b7`) and `31127119863` (head `dce14361`) each read `completed/failure`
at the run level while both of their jobs --- `validate` and
`new-line-breaks / check-new-line-breaks` --- read `completed/cancelled` with
`steps=0`, printing two JOB lines and no step lines.
`gh run rerun` restored both with no code change; each now reports
`run_attempt=2`, `completed/success`, and a `previous_attempt_url`, which is
what makes the recovery re-measurable after the fact.
The check-run-mirrors-job claim was confirmed directly on head `73a4b3b7`,
where both jobs and both check runs report `success` under the same names.)

## An API outage is not an Actions outage, and it presents as the opposite shape

Everything above describes an **Actions** incident, whose signature the first
section states outright: checks are **absent** rather than failing, because the
workflows never start.

A GitHub **API** outage inverts that signature completely.
Actions is healthy, so runners spin up, jobs start on schedule, and steps
execute --- and then any step that calls `api.github.com` fails with `HTTP 503`.
The result is a full check list where jobs report `failure` at ordinary-looking
steps, which is the shape this file's opening paragraph tells you an outage
does *not* have.

So the detection heuristic above --- plural, repo-wide, **absent** checks ---
returns a false negative here, and it does so while reading as a positive
diagnosis: the checks are all present, so the reader concludes correctly that
this is not an Actions incident, and then incorrectly that it is therefore a
per-PR problem.

The discriminator is the **error text inside the failing step**, not the shape
of the check list.
A `503` from `api.github.com` names the platform in the one place a per-PR
cause cannot reach.

### The prescribed instrument may be unreachable from the session

The status-page recipe above is the right first move and it can simply fail.
An agent session behind an egress proxy may be refused outright:

```console
$ curl -s https://www.githubstatus.com/api/v2/summary.json
curl: (56) CONNECT tunnel failed, response 403
```

That is a property of the session's network, not evidence about GitHub, and
retrying it is wasted.
When the status page is unreachable, the failing step's own log is the
remaining instrument, so read it rather than concluding nothing can be known.

### A session-side API call is not a probe of the runner's API access

The tempting substitute is to call the API from the session --- an MCP read, a
`pull_request_read` --- and infer the platform's health from whether it
answers.
It does not transfer.
The session and the runner are different clients on different networks with
different credentials, and a session's MCP reads can succeed continuously
while every runner's `gh` call returns `503`.

Only the negative direction is sound.
A session-side failure is evidence of a problem somewhere; a session-side
success is evidence about the session alone.

### Probing by dispatch is cheap when the outage is total and expensive when it is partial

This refines the existing "**Don't:** retry a workflow dispatch or wait on CI
during a declared **Actions** outage; the incident's own updates say when jobs
will run again" bullet, which is right for the incident it names and wrong
here.

Quoted in full deliberately.
An earlier draft of this paragraph paraphrased it as "a declared outage",
dropping the word **Actions** --- in a section whose entire purpose is to
separate an Actions outage from an API one, so the paraphrase erased the
distinction it was written to draw and left the original bullet looking as
though it already covered both.

A review workflow that calls the API in an **early guard step** fails closed
within seconds, long before any billable model step runs, so a dispatch during
a **total** API outage costs approximately nothing and is the cheapest
available probe.
The expensive case is the **partial** recovery: the guard passes, the review
runs to completion, and the final post-the-comment step then `503`s --- burning
a full round and losing the verdict it just produced.

You cannot tell which regime you are in before dispatching, which is the whole
difficulty.
What follows is not "never probe" but "probe, and expect the cost to be
bimodal": re-dispatch freely while the guard is still failing early, and treat
the first run that clears the guard as the one that might cost a full round.

- **Do:** read the failing step's own log for a `503` naming `api.github.com`
  before diagnosing a full-but-failing check list per-PR.
- **Do:** treat a `CONNECT tunnel failed` from the status page as a fact about
  the session's egress, and fall back to the job log.
- **Do:** re-dispatch cheaply while the failure is still landing in an early
  guard step.
- **Don't:** read absent-versus-present checks as settling whether a platform
  incident is under way --- an API outage produces present, failing ones.
- **Don't:** offer a session-side API success as evidence the runners can reach
  the API.
- **Don't:** carry a tool-availability finding forward across rounds; per
  [`challenge-the-assignment`](../shared/workflow/challenge-the-assignment.md)'s
  "A brief you re-send each round carries a measurement", re-derive it, since a
  tool that failed during the outage answers normally afterward.

(2026-08-17, `Morrison-Lab/ai-config` PR #1584.
Every figure below is derived from `list_workflow_runs` on `claude-review.yml`
filtered to the PR's branch, plus each failing job's own `steps[]`, rather than
from recollection --- see the correction at the end for why that distinction is
the case record's main lesson.

| run | dispatched | head | `gather-context` | `claude-review` | failed at |
| --- | --- | --- | --- | --- | --- |
| 32048542962 | 17:02:43Z | `e5b948f1` | success | success | --- verdict posted |
| 32049426027 | 17:14:15Z | `82c434f4` | success | failure | step 20 |
| 32050823564 | 17:33:00Z | `a35b7d72` | success | failure | step 20 |
| 32053702550 | 18:11:17Z | `a35b7d72` | **failure** | skipped | guard, step 2 |
| 32058414399 | 19:05:28Z | `a35b7d72` | success | success | --- verdict posted |

**Three** dispatches lost a verdict, between 17:14Z and 18:12Z.
Two of them are the expensive regime: step 11, "Run Claude Code Review",
succeeded --- 3m25s and 3m50s respectively --- and step 20, "Post review
comment", then failed within a second, so a complete review existed and was
discarded.
The third is the cheap regime: `gather-context`'s step 2, the fork/Dependabot
guard, failed in **one second**, and the whole job in four, well before any
model step.
`review / require-review` went red on all three, and on 32050823564 step 24,
"Re-assign reviewers after Claude finishes", failed too, dropping the pending
review request.

The outage deepened rather than merely persisting: partial, partial, total,
then clear.
Recovery was abrupt --- at 19:05:44Z the guard passed, `claude-review` ran
3m34s, and the verdict posted at 19:09:14Z for **$5.02**.
The follow-up review on PR #1595 cost **$4.80**, so a lost step-20 round is
worth roughly five dollars, not the twelve this session had been assuming.

`https://www.githubstatus.com/` was unreachable from the session throughout ---
`CONNECT tunnel failed, response 403` --- while the session's own GitHub MCP
reads answered normally, which is what made a session-side probe look
informative and left the outage's scope unmeasured for three rounds.

**The correction is the part worth keeping.**
This record's first draft said five dispatches were lost, that rounds 2 to 4
failed at step 20, and that the guard "passed for the first time since round 1"
at recovery.
A reviewer caught that the last two of those contradict each other --- a run
cannot reach step 20 without its `gather-context` having passed --- and
deriving the timeline to repair the contradiction showed the count was wrong as
well, which no reading of the prose could have revealed.
The numbers came from a check-in brief this session had written and re-sent
each round, so they had been restated often enough to feel measured.
They were not: `get_check_runs` on the PR shows only the runs at its *current*
head, so the two earlier heads' runs were never in view, and the brief's
round-numbering was invented to fill the gap.
`list_workflow_runs` filtered by branch is the query that answers it, and it
takes one call.)
