"Fully clean" is the terminal state the ARDI review loop drives toward.
A GitHub PR is **fully clean** when **both** of these hold, verified via `python3 scripts/check-pr-fully-clean.py --quorum <number-of-reachable-providers> <pr-number>`.
For a GitLab MR, establish the same criteria from GitLab's current-head pipeline, review, and discussion APIs;
`check-pr-fully-clean.py` queries GitHub and cannot verify a GitLab MR.

**Active monitoring and polling are required after every push until fully clean.**
Reaching fully clean requires an active polling loop or scheduled wake mechanism after each push.
Do not pause passively or assume check runs and reviews will complete without polling.
Actively query the current head's CI/pipeline runs and review verdicts (`gh` for GitHub, `glab` for GitLab) until each round reaches a terminal state, re-arming the poll while work remains.

- **Do:** actively poll and re-arm monitoring after every push until CI and review reach a terminal state at the current head.
- **Don't:** stop polling while CI or reviews are in flight, or assume automated pipelines completed without querying the forge.

**A forge's `mergeable` result is an integration-state signal, not a review verdict.**
It can be true while a reviewer has left resolvable findings open.
Do not report a PR/MR fully clean, ready to merge, or merge it until the review thread sweep is also clear.

- **Do:** for a GitLab MR, page through `projects/<project>/merge_requests/<iid>/notes` and confirm that every resolvable, actionable `DiffNote` is resolved before reporting it fully clean.
  The notes endpoint is authoritative because it can expose unresolved diff notes absent from a discussion-level sweep;
  use `discussions` to resolve the thread after finding it.
- **Do:** for a GitLab MR, obtain the current head SHA and page through every pipeline on that SHA;
  confirm each has completed successfully or was skipped.
- **Do:** accept a GitLab review verdict as current-head evidence only when its body names that SHA or its diff discussion has `position.head_sha` equal to it;
  then read every review note's full body for a clean verdict.
- **Do:** re-read the GitLab MR head SHA immediately before reporting fully clean;
  when it changed during the sweep, restart the pipeline, review, and discussion checks against the new head.
- **Do:** state an MR is *mergeable but not fully clean* when CI and merge status are green but an actionable review thread remains open.
- **Don't:** treat GitLab's `detailed_merge_status: mergeable` as a substitute for a current clean review verdict and resolved discussion threads.
- **Don't:** treat an unresolved clean final verdict as an actionable finding;
  GitLab can mark that all-clear note resolvable too.
- **Don't:** treat a resolved GitLab discussion sweep as a clean current-head review;
  findings can appear in an overall review note without a resolvable discussion.
- **Don't:** let an earlier review's green pipeline or later code push erase an unresolved finding without a reviewer-confirmed clean round.

**Finding a cause for an aggregate rollup signal is not finding all of its causes, and a satisfied explanation is what stops you looking for a second one.**
`mergeable_state: unstable` (GitHub) or a comparable aggregate integration
signal is a single value computed from several independent inputs --- a
pending status check, a stale branch, an unresolved review, more than one
provider's own required-checks list.
Chasing it down to one genuine, checkable cause (a pending third-party
status, say) explains the value completely from the inside: the signal was
`unstable`, a cause was found, the cause was real, and the reasoning closes.
Nothing about that chain tests whether it was the *only* input, because a
rollup does not report which of its several inputs are currently non-passing,
only that at least one is.

- **Do:** after explaining an aggregate signal with one confirmed cause, ask
  what else the same rollup can mean before treating it as accounted for ---
  and re-derive the rollup once the confirmed cause clears, rather than
  reading its earlier `unstable` reading as now resolved.
- **Don't:** read "I found a cause for this and it checks out" as "I found
  the cause" for a value that is, by construction, an aggregate of several
  independent signals.

(Morrison-Lab/ai-config#3084, 2026-09-03: `mergeable_state: unstable` was
chased to a pending `jules/review` commit status, which was real and
correctly diagnosed.
When that status cleared, `unstable` was treated as explained and the PR was
merged.
A Copilot formal review carrying a real, unaddressed finding --- posted to
the PR's `reviews` list, not as an inline thread --- had submitted on the
exact head that merged, 4 minutes 47 seconds earlier, and was never read: the
pre-merge check called `get_review_comments` for threads, never `get_reviews`
for the formal review itself, and two of those threads being resolved read as
the review question settled.
The defect reached `main` and needed a follow-up PR.)

**In a remote/web session the instrument still runs, and hand-checking the
axes in its place is not acceptable** (user directive, 2026-08-29,
ai-config#2441).
Those sessions have no `gh` CLI, and an MCP tool cannot be called from inside
a Python subprocess, so the split is that the **agent** retrieves and the
**script** judges: gather the PR's state via MCP, write it to a file, and pass
`--from-json <file>`.

Build that file with the repo's own builder rather than by hand:

```bash
python3 scripts/build-pr-payload.py OWNER/REPO N out.json
python3 scripts/check-pr-fully-clean.py N -R OWNER/REPO --from-json out.json
```

`scripts/build-pr-payload.py` (ai-config#2908) assembles the whole payload
from plain REST, which a remote session's proxy does reach even where its
GraphQL surface is pinned.
The table below documents the payload's shape so the builder can be checked
and extended, and is the fallback when the builder itself cannot run;
it is not an instruction to transcribe MCP output by hand.
A session that did transcribe it by hand had the transcribing commands
denied three times and reported the gate as blocked for hours, while the
one-line builder was named in the instrument's own `--help`
(ai-config#2938).

| Payload key | Gather with | Notes |
| :--- | :--- | :--- |
| `repo` | the `OWNER/REPO` under check | Or pass `-R` instead. |
| `pr` | `pull_request_read` (`get`, `get_reviews`, `get_comments`) | See the field list below. |
| `check_runs` | `pull_request_read` (`get_check_runs`) | Bare list or the REST `{"check_runs": [...]}` envelope. |
| `actions_runs` | `actions_get` (`get_workflow_run`), keyed by run id; `build-pr-payload.py` fills it from each check run's run id ([#1697](https://github.com/Morrison-Lab/ai-config/issues/1697)) | Omitting it changes verdicts --- see below. |

`pr` needs `headRefOid`, `headRefName`, `state`, `reviewDecision`, and
`commits[].committedDate`, plus two nested shapes the scan reads directly:
each entry of `reviews[]` needs `state`, `submittedAt`, `body`,
`commit.oid`, `author.login`, and `authorAssociation`, and each entry of
`comments[]` needs `body`, `author.login`, `createdAt`, and
`authorAssociation`.
`commit.oid` is the exact-SHA gate, and `submittedAt`/`createdAt` order the
latest-verdict selection, so a payload omitting them is accepted and scored on
weaker evidence.

The field names are `gh pr view --json`'s rather than the MCP tool's, so a
small mapping is needed --- `head.sha` becomes `headRefOid`, and an author
becomes `{"author": {"login": ...}}`.
That mapping is the agent's job precisely because it is the part that differs
between session kinds.

**Page through `pull_request_read`.**
It caps at 100 per page, and a truncated `comments[]` is indistinguishable
from a complete one --- so dropping a later standing not-clean yields a
**false clean**, which is the one error this instrument exists to prevent.

**`actions_runs` is optional but not inert.**
Omitting it disables the ai-config#2277 suppression of a `cancelled` run
superseded by a later success, and disables run-based attribution of a verdict
whose comment cites its run URL rather than a SHA.
Both omissions push toward a false **not**-clean, which is the safe direction
--- but if a PR reads not-clean for a reason you cannot see in its checks or
reviews, gather this key before concluding anything.
Never add entries until the verdict flips: that is tuning the instrument to
agree with you.

**Unusable payload data exits 2, never 1.**
Exit 1 is the script's real not-clean verdict, so a data problem reported as
exit 1 would be indistinguishable from a finding about the PR.
That covers a missing or wrong-typed top-level key, a `pr` missing
`headRefOid`, malformed JSON, and --- while `--from-json` is active --- any
other exception, since none of them can be a statement about the PR.

Note what the rationale is *not*: an absent `check_runs` read as `[]` does not
score clean.
`check_ci_runs` already reports "No check runs found" and returns not-clean.
Refusing absent data is still right, because substituting an empty value would
manufacture a *finding bullet* out of missing data, which is worse than a
crash rather than better.

Extended rationale --- the mechanism, evidence, and argument behind
each rule below --- lives in
[`fully-clean.rationale.md`](fully-clean.rationale.md),
moved out of the auto-loaded context.
Each rule here keeps its statement and its Do/Don't pair;
read the companion when the reasoning or the evidence is the question.

Worked-example case records for the rules below live in
[`fully-clean.cases.md`](fully-clean.cases.md), moved out of the auto-loaded context.

1. **All CI workflows and check runs are green AND completed.** Every workflow and check run passes --- not just the required checks and not just the review job.

   **`status` itself can be stale, so never infer a job's *duration* from it.**

   - **Do:** read elapsed time from log timestamps whenever the length of a
     run is the thing being judged.
   - **Don't:** conclude a job is still running, or has passed some duration
     threshold, from `in_progress` plus the wall clock.

   **When you are waiting for a job rather than timing one, poll its step list
   instead of its status --- the steps are not subject to the same lag.**

   - **Do:** poll `actions/jobs/<id>`'s `steps[]` when waiting on a specific
     job, and treat its terminal step completing as the signal.
   - **Do:** report which step the job is on, so a stalled job is
     distinguishable from a slow one.
   - **Don't:** poll a check run's `status` in a loop and read repeated
     `in_progress` as evidence the job is still working.

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "Poll a job's step list, not its check-run status".

   **A `BlobNotFound` / HTTP 404 on the job-log fetch means the job has not completed, not that it has hung.**

   - **Do:** read a 404 / `BlobNotFound` on the job-log endpoint as "the job has not finished", and wait for completion (or read the live UI log) before judging its outcome.
   - **Do:** take a job's real state from its `status`/`conclusion`, since the same 404 covers a still-running job and a completed-with-no-logs one.
   - **Don't:** read a 404 on the log fetch as positive evidence of a hang or a stall --- it is the opposite, evidence the job is still running.
   - **Don't:** file an issue reporting a review job as hung or "no verdict produced" while its log fetch still 404s and its status is `in_progress`.
   - **Don't:** run the rule backwards: a log URL being **served** is not evidence the job completed.
     The blob can exist mid-run, so a successful log fetch and a still-running job coexist.
     Completion comes from `status`/`conclusion` alone, in both directions.

   **A hung check is a distinct state from a crashed one, and the step list is what tells them apart.**
   `status`/`conclusion` look identical for both --- empty and `in_progress` either way --- so the remedies above for a *finished* check that misled you do not apply here: there is no failure yet to `rerun_failed_jobs`, and a fast-crash signature has nothing to match against a job that has not crashed.
   Read the step list instead: which step is `in_progress`, and for how long relative to that step's usual duration.
   A retry step stuck for tens of minutes where its sibling attempt finished in under a minute is a hang, not a slow-but-normal run.

   - **Do:** read the job's step list when a check runs unusually long, and name which step is hung and for how long.
   - **Do:** state a hung check as a tooling status when another reviewer has already given a verdict at the same head, rather than either declaring clean or chasing it as a finding.
   - **Don't:** try to re-run an `in_progress` job, or apply a fast-crash remedy to a hang --- neither condition has fired yet.
   - **Don't:** infer from `status: in_progress` alone that the check is merely slow;
     read the step list before concluding either way.

   See [`fully-clean.cases.md`](fully-clean.cases.md), "A hung retry step, not a crashed one".

   **`gh pr checks` is not a complete enumeration of a head's check runs, so
   read the commit check-runs endpoint before deciding that everything has
   finished.**
   GraphQL `statusCheckRollup` is the same kind of short surface for a
   *progress* report --- not enough for a terminal "fully clean" /
   "ready to merge" claim.
   That claim needs `scripts/check-pr-fully-clean.py`
   (ai-config#2277, 2026-08-26).

   **`--paginate` is load-bearing, not tidiness.**

   **The endpoint covers check runs only, so a repo that still uses legacy
   commit statuses needs a second query.**

   **Why the two surfaces disagree is unexplained, so do not assert a
   mechanism for it.**

   **`commits/<sha>/status` reports the combined state of an EMPTY status set
   as `pending`, not `success` or absence --- so a gate that tests the rollup
   `state` alone reads every PR with no legacy commit statuses as not-clean,
   which is most PRs in a repo that has none configured.**
   The condition has to be on the members, not the rollup: `total_count == 0`
   means no commit statuses exist, which is the ordinary case and not a
   blocker, while `total_count > 0` with any member `pending` or `failure` is
   genuinely not-clean --- name the offending `context` when it is.
   The same `pending` state means opposite things depending on `total_count`
   alone: `state: pending, total_count: 0, statuses: []` is silence, and
   `state: pending, total_count: 1, jules/review -- "Jules is reviewing..."`
   is a real in-flight reviewer.

   - **Do:** take the check-run half of criterion 1 from the paginated
     check-runs endpoint, and add `commits/<sha>/status` where the repo uses
     commit statuses, rather than treating either query as sufficient alone.
   - **Do:** branch on `total_count`, not on the combined `state` alone, when
     reading `commits/<sha>/status` --- an empty set reports `pending` and is
     not a finding.
   - **Do:** report both counts when the endpoint and the rollup disagree, so
     the gap stays visible to whoever reads the status next.
   - **Do:** re-derive check state from that endpoint on the PR's current
     head when a completion notification wakes you, having first compared
     the wake's own `head_sha` against that head.
   - **Don't:** read `0 pending` from `gh pr checks` as evidence that nothing
     is still running.
   - **Don't:** drop `--paginate` --- an unfinished run on page 2 returns the
     same empty result as a finished head.
   - **Don't:** offer a reason for the omission --- none was established.
   - **Don't:** read a wake reporting check suites finished as an all-clear
     --- [`ardi`](ardi.md)'s superseded-head case is a **red** wake inviting
     a needless fix, and this is its **green**-sounding mirror, inviting a
     needless merge.
   - **Don't:** treat an empty `commits/<sha>/status` response's `pending`
     state as a finding --- the check has to read `total_count`, not the
     rollup, or the ordinary case (no commit statuses at all) reads as
     blocking on every PR.

   (Morrison-Lab/ai-config#3106, 2026-09-03: the issue's own suggested fix
   proposed treating a `pending` combined state as not-clean, then a
   follow-up comment on that same issue caught that the suggestion would
   misfire on most PRs, an hour after it was written --- the rollup-versus-
   population bug this section already warns about, reintroduced into the
   proposed fix for it.)

   **A paginated sweep with an inconsistent page size silently skips items, and every response still reads as complete coverage.**
   `--paginate` above is the CLI answer;
   the same failure reaches a manual REST/GraphQL sweep (an MCP tool taking explicit `page`/`perPage` arguments, say) when the page size changes partway through --- `page: N` is relative to whatever size was last requested, so changing it mid-sweep silently renumbers what "page 2" means, and a page fetched at the wrong offset that way returns real, green data with nothing in the response flagging the gap.
   Both API surfaces hand you the check for free (`total_count` on REST, `pageInfo.hasNextPage`/`endCursor` on GraphQL), so this is a count to assert, not a judgment call.

   - **Do:** hold the page size constant across a paginated sweep, and assert items seen equals `total_count` before drawing a conclusion from it.
   - **Do:** prefer cursor pagination (`after`/`endCursor`) where offered, since a cursor cannot be invalidated by a page-size change.
   - **Don't:** change the page size between pages of the same sweep.
   - **Don't:** treat "every item I looked at was green" as "every item is green" without the count check --- the same mistake made while sweeping review threads (below) is worse, since a skipped range there means an unresolved thread reads as a clean PR.

   See [`fully-clean.cases.md`](fully-clean.cases.md), "A paginated sweep with inconsistent page size skipped 8 of 30 items and read as complete".

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "A `check_suite.completed` wake at a superseded head".

   **A polling loop needs the same negative control a sweep does, because an
   EMPTY check list satisfies "nothing is pending" exactly as well as a
   finished one.**
   The rules above that concern the check list each found one that came back
   **short**; this is the case where it comes back **empty**, which none of
   them reaches.
   "Not yet started" and "finished successfully" produce an identical reading,
   which is [`fail-fast`](../principles/fail-fast.md)'s
   pass-path-equals-failure-path shape failing in the dangerous direction ---
   it reports a PR ready.
   [`batch-merge-and-resolve`](batch-merge-and-resolve.md) states the
   governing rule for a **sweep**, and a sweep and a poll do not resemble each
   other from the inside --- one feels like a measurement, the other like
   waiting --- so that rule loads and matches nothing here.

   A non-empty population is necessary and **not sufficient**, because the
   population grows while the poll runs.
   Measured on the corrected run: the total went 13, then 16, 17, 18 across
   two minutes, as later workflows registered their checks.
   So a threshold only rules out the empty case, and a poller that happened to
   observe zero pending at total 13 would have exited before five further
   checks existed.
   Require the terminal reading to repeat --- zero pending **and** an
   unchanged total across two consecutive polls --- and print the total each
   tick, so growth is visible rather than inferred.

   - **Do:** require a non-empty population before reading zero-pending as
     done, and report how many check runs were examined.
   - **Do:** confirm the total is unchanged since the previous poll, since the
     population grows as workflows register.
   - **Don't:** arm a poller assuming the push already created the checks ---
     a draft-to-ready transition creates them on a separate event, so a
     poller armed at push time can run entirely inside a zero-check window.
   - **Don't:** treat a single zero-pending reading as terminal, however large
     the population was when you took it.

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "A poller exited on an empty check list".

   **The population also grows LATE, from a job PASSING rather than from
   registration lag, so a total that has been stable for many polls is not
   evidence the set is final.**
   The paragraph above measured growth in the two minutes after a push, as
   workflows registered --- 13 to 18 across t=150s to t=270s --- and that
   shape invites reading the growth window as bounded by the push.
   It is not.
   A job gated on `needs:` creates its checks only when its dependency
   **completes**, so a green job is a cause of new checks rather than one
   fewer thing to wait for.

   That inverts what a stable total means.
   Under registration lag a stable total is at least weak evidence the set
   has settled, because registration is contiguous with the push and then
   stops.
   Under a gated successor the total is stable *because* the spawning job has
   not finished, so the stretch that looks most settled is the one
   immediately preceding the growth.

   The two-poll rule above held in the case below, and for a reason that does
   not generalize: the spawning job sat inside the polled set and was itself
   pending, so no poll could have read zero.
   A spawner outside that set --- a job in another workflow, a
   `workflow_run` trigger --- leaves the guard nothing to see.
   So the reading that licenses a merge is one taken **at the merge
   decision**, not a count carried forward, however many polls agreed on it.

   - **Do:** re-read the check list at the moment of the merge decision, and
     compare its total against the one the earlier polls agreed on.
   - **Do:** read a job completing as a reason to expect new checks.
   - **Don't:** read a long-stable total as evidence the set is final --- the
     stable stretch is where a gated successor is still waiting to appear.
   - **Don't:** generalize the two-poll rule's success here; it depended on
     the spawner sitting inside the polled set.

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "A passing job spawned three more checks".

   **A bot comment on the PR is not evidence that the job posting it has
   finished, because a step writes that comment partway through the job.**
   A preview-deployment comment, a coverage report, a benchmark table: each
   is emitted mid-job, so its existence establishes that one step ran and
   says nothing about the steps after it.
   One job can post two such comments, minutes apart, and finish after both.

   It is the comment rather than the check row that gets read this way for a
   structural reason: the comment is the most visible thing the job produces
   and it lands in the thread already open, while the check list has to be
   fetched.
   [`efficient-pr-babysitting`](efficient-pr-babysitting.md) compounds that by
   telling you to work from CI's own report rather than re-deriving it, which
   is right about the comment's **content** and silent about its **timing** ---
   so trusting the content makes the timing inference feel already licensed.
   This is
   [`verify-the-right-artifact`](verify-the-right-artifact.md)'s
   neighbour-for-the-target shape: a real artifact of the right job, read for
   a property it does not carry.

   - **Do:** take job completion from the check list, and read a bot comment
     only for what it measured.
   - **Don't:** date a job's completion from a comment that job posted.

   See [`fully-clean.cases.md`](fully-clean.cases.md),
   "A preview comment read as a finished docs job".

   **A check-run NAME is not unique across workflows, so a name alone does not
   identify which check passed.**
   Two workflows in one repo can each define a job with the same name, and
   `gh pr checks` prints the bare name with no workflow attached --- so a
   passing row can belong to a workflow you were not asking about.
   The ambiguity is invisible in the output, which is what makes it dangerous:
   nothing in a duplicated name looks different from a unique one, so no
   prompt to check ever arrives.

   Resolve it from the run behind the check rather than from the name:

   ```bash
   gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" --paginate \
     --jq '.check_runs[] | select(.name == "<name>") | .html_url'
   gh run view <run-id> -R <owner>/<repo> --json workflowName --jq .workflowName
   ```

   Cross-check against the workflow's own job list too.
   A matrix leg gated on `needs:` may not have started at all, so its absence
   from a run's jobs contradicts any same-named row reported as passing.

   `check-pr-fully-clean.py` annotates a duplicated name with the run URL only
   on the lines it actually reports --- a run still pending, or one that
   finished badly.
   A **passing** duplicated name produces no line at all, so it is never
   annotated, and the manual lookup above is the only thing that resolves it.
   That is precisely the case this section was written from: the passing row
   belonged to the wrong workflow, and nothing in the script's output would
   have said so.

   - **Do:** take the workflow from the check run's own URL before attributing
     a pass or a failure.
   - **Don't:** read a job name as identifying a workflow --- it identifies a
     job, and two workflows may define the same one.

   (Measured 2026-08-21 on `ucdavis/bcs`: `ubuntu-latest (release)` exists in
   both `R-CMD-check.yaml` and `check-readme`.
   On a PR fixing an `R CMD check` failure, the passing row was
   `check-readme`, while `R-CMD-check.yaml`'s matrix legs had not started ---
   they are gated on `needs: [matrix, update-snapshots]`.
   Reporting the regression fixed on that row would have cited an unrelated
   workflow.)

   **Every subsection above explains a per-PR failure in reading the check
   state --- a short or empty list, a lagging status surface, an ambiguous
   name --- and a platform outage produces the same shape for a reason none
   of them can reach.**

   **A job's conclusion is set by whichever step failed, which need not be the step whose verdict you read.**
   Most rules above concern an enumeration that came back incomplete.
   This one's enumeration is complete and terminal, and the answer you read came from the wrong member of it.
   A workflow can carry a guard step that decides what a run *meant* --- a review guard classifying an outcome, a summarizer, a status resolver --- and that step can conclude "this is fine", write its output, and end `success`, while the job is red because an earlier step failed without `continue-on-error`.
   Reading the guard's own log line then reports the opposite of the check.
   So when a red job's log carries a green verdict, do not treat it as a contradiction to explain: enumerate the steps and find the one whose conclusion is `failure`.
   The same reading also settles what to do next: whether a fix to the classifier can clear the check at all, since a classifier the job does not consult is fixable without changing anything the reader sees.

   - **Do:** identify the failing *step* before diagnosing a failing job, rather than reasoning from whichever step's output you happened to read.
   - **Do:** treat a green guard step beside a red job as evidence about the wiring, since the two were decided by different steps.
   - **Don't:** read a guard step's own log line as the job's verdict --- the two are decided by different steps, so agreeing is a coincidence rather than a confirmation.
   - **Don't:** claim a fix to a classifier clears a check until you have confirmed the job's conclusion actually depends on that classifier.

   See [`fully-clean.cases.md`](fully-clean.cases.md), "A green guard step beside a red job".

   **One SHA can carry two check runs of the same name, from the same workflow, with opposite conclusions --- because a workflow gated on a base-ref diff runs VACUOUSLY on `push` and meaningfully on `pull_request`.**
   The subsection above covers a green step inside a red job.
   This is the mirror at the run level, and it is worse, because nothing about the green one looks partial: it reports the same check name, it completed, and it passed.

   The mechanism is a workflow that needs a base to diff against.
   `check-new-line-breaks.yml` passed `base-ref` only when `github.event_name == 'pull_request'`, so the `push`-triggered run of the identical workflow had no base, examined zero added lines, and passed having measured nothing.
   In this repository the `new-line-breaks` job in `validate.yml` is now gated with `if: github.event_name == 'pull_request'` ([ai-config#1730](https://github.com/Morrison-Lab/ai-config/issues/1730)),
   so its push run reports `skipped` rather than `success`.
   That closes the missing-base push case only:
   a `pull_request` run can still skip with the same warning when the diff cannot be computed,
   so read the job log before trusting a green run whose base could have been unreachable.
   The rest of this subsection still governs any workflow of this shape that lacks the guard.
   Both runs attach to the same commit, so `gh pr checks` prints two rows with one name, one `pass` and one `fail`, and reading the list top-down finds whichever came first.

   The vacuous run is the one to discard, and the trigger event is the only field that separates them.
   `gh api "repos/<owner>/<repo>/actions/runs/<id>" --jq '.event'` settles it in one read per run.
   A `pass` from a run whose event supplies no base is [`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s zero-matrix problem arriving as a green check.
   That fragment states it as "a matrix of zeros is indistinguishable from a detector that never ran", and prescribes a negative control before trusting any zero.
   The same remedy applies here, and the trigger event is what supplies it: a run given no base examined nothing, so its `pass` is the zero rather than a result.

   Note that this is not the same as [ai-config#1870](https://github.com/Morrison-Lab/ai-config/pull/1870)'s ambiguity, where two *different* workflows contribute check runs sharing a name.
   Here it is one workflow, and the disambiguator is the event rather than the workflow name --- so a fix keyed on `workflowName` cannot see it.

   - **Do:** read the `event` of any run whose verdict you are about to rely on, whenever the same check name appears twice on one head.
   - **Do:** take the verdict from the `pull_request`-triggered run for any check that diffs against a base.
   - **Don't:** read a `pass` as evidence the check examined anything --- ask what population it was given first.
   - **Don't:** resolve a same-name disagreement by workflow name.
     On this shape both runs carry the same one.

   (Measured 2026-08-21 on [ai-config#1884](https://github.com/Morrison-Lab/ai-config/pull/1884).
   Run `32545283504` (`event=push`) and run `32545289903` (`event=pull_request`) both had `head_sha=8c456074`, both were named `new-line-breaks / check-new-line-breaks`, and they concluded `success` and `failure` respectively.
   The push run was read first and taken as the verdict.
   The PR run was the one carrying four real findings.)

2. **Every reviewer's latest verdict is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.
   A later all-clear from a different reviewer does not clear another reviewer's standing not-clean, nits included.

**In a local CLI session, "external reviewer" means the bot reviewers, not the human one.**
`gh`/the MCP server authenticate as the same human account that owns the repo, so a formal review *request* against that human always 422s (`request-pr-review`'s own edge case) --- not occasionally, structurally, on every PR such a session opens.
That does not relax criterion 2; it changes which providers can satisfy it.
The pinned quorum below is still required in full, and it is answerable entirely by the bot reviewers (`claude-review`, `jules/review`, Copilot) --- none of which is the human the deadlock-escalation ladder in `CLAUDE.md`'s "Address every in-scope review comment, even non-blockers" section (and [`skills/ardi/SKILL.md`](../../skills/ardi/SKILL.md)) points to.
So read that ladder's "request the human reviewer" step, in a local session, as "post an `@`-mention with the impasse" instead: the mention still notifies and still counts as re-checking reviewer reachability right before declaring clean, which criterion 2 requires regardless of session type.

- **Do:** treat the bot quorum as the external-reviewer requirement in a local session, and re-check its reachability before calling a PR clean.
- **Do:** escalate a deadlock with an `@`-mention comment in a local session, in place of a review request that would 422.
- **Don't:** read the 422 as a transient failure worth retrying, or as evidence the PR cannot reach criterion 2.
- **Don't:** assume a remote/web session is exempt --- per `memories/github-mcp-tools.md`, that session's authenticated identity varies by container and client, and can itself be the repo owner, in which case the identical 422 fires there too;
  settle it from an actual write's attributed author rather than from the session type alone.

**Criterion 2's test is the absence of findings, not the presence of a verdict
line saying so.**

So when the two disagree inside one comment, **the findings win**.
Read to the end of the comment before calling anything clean, and count the
items under every heading, whatever that heading is called ---
[`address-every-comment`](address-every-comment.md) already establishes that
"informational", "non-blocking", "nit", "minor", and "optional" are prioritization labels rather
than a pass, and a reviewer files findings under exactly those words in the
section that contradicts its own verdict line.

**Final approval requires a clean verdict from every available provider in the pinned quorum.**
A single agent's clean verdict does not clear criterion 2 on its own;
it must be joined by a clean verdict from the rest of the quorum.

This is a directive rather than a derivation, so treat it as a standing preference.
What it settles is when a PR is reported **ready** for merge.

The reason it needs stating is that multiple verdicts are indistinguishable from a single one to the CI review gate.
Every agent posts the same shape --- a summary, some analysis, a positive closing line.
So a findings-free report from just one agent turns the review-gate check green,
even while other providers' reviews are pending or blocked.

Two failure modes make the preference concrete, and both have recurred:

- **A clean verdict over tooling that errored.**
  A report can open by saying its own grep failed and then approve on the
  strength of the analysis that grep was supposed to support.
  The error line sits above the verdict, so it reads as a caveat rather than as
  the verdict's foundation collapsing.
- **A clean verdict at a head another agent finds a real defect in.**
  Not a difference of opinion about a nit --- a checkable factual error, at the
  same commit, that the clean verdict passed over.

So when the pinned quorum is reachable, their verdicts are the ones to report on:

- **Do:** dispatch reviews to the quorum and wait for all verdicts before reporting a PR ready,
  whatever one agent has already said.
- **Do:** name which agents produced the verdicts you are reporting,
  so "clean" is attributable rather than anonymous.
- **Do:** treat any agent's findings as real findings ---
  every provider's objections count.
- **Don't:** report a PR ready on a single clean verdict while the quorum is still reachable and pending,
  however thorough that report reads.
- **Don't:** read a green review-gate check as settling this;
  the gate does not know how many agents answered,
  only that one did.

**A disagreement among reviews vetoes merge, including under `mwc`.**
Criterion 2 is every reviewer's latest verdict, not the globally last comment.
If one review is all-clear and another raises blocking issues, nits, minor
items, or any other flagged heading, the findings win.
ARD every item from every review, then request fresh reviews.
A later all-clear from a different reviewer does not supersede a standing
not-clean; only a later clean from the same reviewer does
(the ordinary ARDI iterate path).
`check-pr-fully-clean.py` encodes the per-reviewer scan
(ai-config#2274).

- **Do:** ARD the union of findings from every review, then request a fresh
  round from the reviewers that spoke.
- **Don't:** merge on one reviewer's all-clear while another still has a
  standing not-clean, even with `mwc` active.

This is a different question from how much two reviewers **agreeing** is worth,
which [`self-review-fallback`](self-review-fallback.md)'s cross-vendor section
settles: there, same-vendor agreement measures a shared blind spot, and a
cross-vendor split is a prompt to check the item yourself.
That section weighs corroboration; this one names whose approval is terminal.
They compose --- a cross-vendor reviewer is always required, and every clean
verdict is necessary before a PR is reported ready while the quorum is
reachable.

Where a quorum provider is genuinely unreachable --- quota-skipped, a stub with no stated
verdict, or not configured --- fall back per
[`self-review-fallback`](self-review-fallback.md), which already governs that
case.
Note that merging autonomously under `mwc` (merge-when-confident) strictly requires
genuine clean automated review verdicts from the reachable quorum evaluating the HEAD commit;
a fallback self-review or reviewer skip notice allows the ARDI iteration loop to proceed,
but NEVER satisfies the MWC autonomous merge gate.

**One more gate stacks on top (user directive, 2026-08-25):
no merge under any grant, `mwc` included,
without a 100% all-clear adversarial verdict at the shipping head from a
reviewer meeting [`adversarial-self-review`](adversarial-self-review.md)'s
independence bar.**
It composes with the external-reviewer requirement above ---
neither satisfies the other.
When the external reviewer self-skips by design (workflow modification is
the known case), autonomous merging stays blocked:
human approval is the only path.
Specification and mechanics live in that fragment.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"Two agents, one head, opposite verdicts".

**Both criteria are per-PR, and a stack is where that stops being automatic.**

- **Do:** derive a verdict per PR number, and name the PR beside each one.
- **Do:** treat a refusal from one reviewer on one PR as evidence about that reviewer on that PR, and nothing else.
- **Don't:** report a stack's review state from a single read --- "I read the review" is a per-PR claim, and the stack is what makes it read as a claim about the work.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"Both criteria are per-PR, and a stack is where that stops being automatic".

**The disagreement is measurable, and it is not a wording problem.**

**A reviewer's own verification block can be wrong while its verdict is
right.**

- **Do:** re-derive a posted verification's groups, not just its total.
- **Do:** fix the wording that invited a wrong reconstruction, even when
  nothing in the diff was false.
- **Don't:** let the word "verification" stand in for having verified.
- **Don't:** read a table that sums as one that partitions correctly.

**A clean verdict can ratify an enumeration instead of testing it, and then it
reads as independent corroboration of a false scope claim.**

- **Do:** derive any enumeration you publish with a command, and publish the
  command beside it.
- **Do:** treat a reviewer restating your count as that count still being
  unverified.
- **Don't:** read a clean verdict as evidence that a scope claim in the diff is
  complete --- a reviewer can only check the members you named.
- **Don't:** count a reviewer's agreement as independent when its population
  came from your own prose.

**What "an approving review" means here is not a review state.**

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

- **An out-of-diff finding never becomes a thread.**
  A finding about a line the diff did not touch cannot be attached as an
  inline comment, so it appears only in the body --- reviewers say so
  explicitly ("inline comments were unavailable for out-of-diff lines").
  A thread count therefore cannot see it.
  Zero unresolved threads is not evidence of zero findings.
- **A notification that truncates the body hides exactly that finding.**
  The rule above says to read the body, and assumes you are reading the body.
  A CI-monitor or webhook event delivers the review as *quoted text*, capped
  at some length, and the inline findings are enumerated first because they
  are numbered --- so what gets cut is the tail, which is where an out-of-diff
  finding and the verdict both live.
  The event is honest about it, and that is the trap: it prints a marker like
  `[truncated --- full text: gh api repos/<owner>/<repo>/issues/comments/<id>]`,
  which reads as a courtesy rather than as an instruction, and the visible
  portion looks like a complete, well-structured review.
  Acting on the inline comments alone then feels like having addressed the
  round, and the thread sweep confirms it, because the missed finding was
  never a thread.
  So run that command before treating a finding list as complete, whenever the
  review reached you through a notification rather than through a direct read.
- **An empty body hides the mirror case.**
  A review can post a completely empty top-level body and carry its entire
  finding in one inline comment, so a body-only read finds nothing to act on
  and concludes there is nothing.
- **A clean overview can hide a collapsed findings block.**
  Copilot can say it "generated no new comments"
  and create zero inline comments
  while placing substantive findings inside a collapsed
  `<details>` suppression block in the review body.
  Match case-insensitively on `suppressed` **inside the `<summary>`
  heading**, not anywhere in the body.
  See [`fully-clean.cases.md`](fully-clean.cases.md),
  "The collapsed-block case (Morrison-Lab/ai-config#1029)".
- **"No verdict" is its own state, distinct from "a verdict with no
  findings".**
  A review job can fail having posted *nothing* --- not a stub, not an empty
  comment.
  Zero findings and zero review are indistinguishable by any count, and they
  call for opposite responses: one is done, the other needs a self-review and
  a re-run.
  Read the job's step outcomes when a review is missing rather than inferring
  from the absence of comments.

- **The notification that wakes you carries a SUBSET of the findings, and
  nothing in it says so.**
  Every case above is a surface *on GitHub* that a query can reach.
  This one is the channel that tells you to look in the first place: a
  `pull_request_review_comment.created` wake delivers **one** comment, and a
  review posting five of them wakes you five times, asynchronously, with no
  count and no "1 of 5".
  So the first wake is indistinguishable from the only wake, and acting on it
  reads as responsive while leaving the rest unaddressed.
  It is worse than an ordinary partial read because the thread then *looks*
  handled: a reply and a resolved thread sit under the one finding you saw.
  Re-fetch `get_review_comments` on every review wake and act on the whole
  set, never on the wake's own payload.

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
- **Don't:** act on a review wake's own payload --- it is one comment out of
  however many the round posted, and it never says which.

**A comment can be evidence-dense, correct throughout, and state no verdict at
all --- and its density is what gets read as the conclusion.**

**A later comment stating no verdict does not supersede an earlier one.**

- **Do:** identify the last statement that actually states a verdict, and treat
  that as the standing one.
- **Do:** scan the whole review history for it, not only items matching HEAD.
- **Don't:** read a verification section, however rigorous, as an approval ---
  it is evidence, and a verdict is a conclusion about evidence.
- **Don't:** treat a later comment's silence on the verdict as superseding an
  earlier "Needs more work".

See [`fully-clean.cases.md`](fully-clean.cases.md),
"A later comment stating no verdict does not supersede an earlier one".

**A reviewer skip notice (e.g. for workflow edits or quota exhaustion) does NOT clear or supersede prior review findings.**

When a review run skips
(e.g. self-modification workflow guard or quota limits)
and falls back to a self-review or human review per
[`self-review-fallback`](self-review-fallback.md),
that fallback lets the ARDI iteration loop proceed
in the absence of prior unresolved findings.
It never satisfies an autonomous merge gate ---
autonomous merging under `mwc` remains blocked per the merge gate above,
and human approval is the only path.
It does NOT wipe the slate clean,
does NOT license merging over an unaddressed `Needs more work` verdict
or open finding list from an earlier or concurrent review run,
and does NOT clear the all-clear merge gate above.

- **Do:** scan the complete PR review comment history for any `Needs more work` verdicts or open finding sections before declaring a PR clean or ready to merge.
- **Do:** address, rebut (with convincing acceptance), or defer every previously raised finding even if the most recent review run skipped.
- **Don't:** treat a reviewer skip notice or self-review fallback as an all-clear or as permission to ignore open findings on the PR.

**Another surface,
and the one that defeats the gate itself:
the review check can pass on a blocking verdict.**

- **Do:** grep the verdict body for its own conclusion, and treat a
  `require-review` pass as orthogonal to whether the PR is clean.
- **Don't:** let a green review-gate check stand in for reading what the
  review said.

**`check-pr-fully-clean.py` itself has the mirror false positive: it can report
NOT clean over a clean verdict.**

- **Do:** read the verdict's own conclusion when the script reports findings
  against a review whose prose merely discusses finding vocabulary.
- **Don't:** treat a `contains findings (matched pattern ...)` line as a real
  finding without reading the verdict body it matched.

**One shape of that false positive is deliberate, and the fix for it is on the
reviewer's side: a resolution log filed under a `Findings` heading.**
A confirming review that writes
`### Findings --- all three from the prior rounds are now resolved` and lists
`1. **Previously: X.** Now fixed --- <explanation of the fix>` scores as open
findings, because the explanation after the verb is free prose and no lexical
rule can tell "Now fixed; the pathspec is quoted" from "Now fixed; the query
leaks memory on every call".
The same comment's structured `CLEAN` payload does not change that, since it is
the same author's verdict line in JSON, and the rule above says findings win.
Two narrowing attempts, a caveat word-list and a payload gate, were withdrawn
in [#2950](https://github.com/Morrison-Lab/ai-config/pull/2950); the tests
that pin the safe behaviour are in `scripts/test_check_pr_fully_clean.py`
([#2945](https://github.com/Morrison-Lab/ai-config/issues/2945)).
What reads clean today is the format the checker was built for: resolved
prior findings under a heading that is not a `Findings` heading
(`### Resolved since the last round`), and `### Findings` reporting `None.`
A resolution whose whole disposition closes the line
(`**Previously: X.** Now fixed in abc1234.`) also resolves, provided the
`Findings` heading itself is marked resolved or non-blocking; under a bare
`### Findings` heading even a closing-line item stays open, since the heading
is what admits the section to the item test.

- **Do:** when a review of yours must recount resolved prior findings, file
  them under a non-`Findings` heading and keep `### Findings` for open ones.
- **Don't:** ask the checker to read a free-prose explanation as a resolution;
  the human reading the verdict body is the fallback the rule above names.

**Calling the checker is not consuming it: grepping its PROSE instead of
reading its EXIT STATUS re-opens the whole failure one layer up.**

The rule above and `no-handrolled-verdict-parse.py` both govern *bypassing* the
instrument.
This is the case where you run it, correctly, on the right PR --- and then
decide what it said by matching a string in its output.

`check-pr-fully-clean.py` answers twice.
It prints findings for a human, and it exits 0 for clean and non-zero
otherwise.
Only the second is a stable interface.
The prose is free to gain a line, split across two lines, or word a finding
differently, and every one of those silently changes what a `grep` decides.

Two properties make this worse than an ordinary parsing slip.

**It fails toward clean.**
The natural spelling is a positive test for the bad state ---
`if output matches "NOT fully clean" then not-clean, else clean` --- so *any*
failure of the match, including the check erroring or printing its header
separately, lands in the `else` branch and reports clean.
A missed match and a genuinely clean PR are the same observable, which is
[`fail-fast`](../principles/fail-fast.md)'s pass-path-equals-failure-path shape
arriving through a tool built to prevent exactly this.

**It launders.**
The report reads as the instrument's verdict rather than as your reading of it,
so "the checker says clean" is what reaches the human --- and nothing in that
sentence exposes that a `grep` stood between the two.

**The status is three-valued, and collapsing it to a boolean is the same
mistake one layer further in.**
`check-pr-fully-clean.py` exits **0** clean, **1** not clean, and **2** for a
usage or environment error.
That third code is deliberate --- its own source says `USAGE_EXIT = 2` exists
so "a usage or environment error would have been read as a verdict about the
PR" --- so `if ! checker; then not_clean` throws away the distinction the
script went out of its way to provide.

The cost is a **false regression**: a transient `gh` failure, a rate limit, a
network blip in a polling loop, all report a PR as having gone not-clean.
That is the mirror of the grep bug above, which failed toward clean; this one
fails toward alarm, and both are a two-branch reading of a three-branch answer.

This is the rule
[`errexit-is-not-uniform`](../coding/errexit-is-not-uniform.md) states as 0, 1,
and anything else being three answers and not two --- itself a paraphrase of
[`fail-fast`](../principles/fail-fast.md)'s hand-check guidance to treat 0 as
found, 1 as clean, and anything else as the check having failed to run.
It applies to a purpose-built checker exactly as it does to `grep`.

**But `2` does not cover every non-verdict, so the three-way read is necessary
and still not sufficient.**
`USAGE_EXIT = 2` is raised by `die()`, on the paths the script anticipated.
An **unhandled exception** exits **1** --- the code reserved for "not clean" ---
so a crash is indistinguishable from a verdict by status alone.

That is why the status read has to be paired with a look at the output rather
than replacing it.
A genuine not-clean prints `  - ` finding bullets; a crash prints a traceback.
One `grep -q '^  - '` separates them, and unlike the phrase search above it is
keyed on the report's *structure* rather than on its wording.

**The wrong-repo case is the one to expect**, because the script resolves the
repo from the **current working directory** unless `-R/--repo` is passed.
A background poller inherits the session's cwd, which on a multi-repo session
is routinely not the repo the PR lives in --- so the same command answers
correctly by hand and crashes in the loop.
Pass `-R OWNER/REPO` explicitly in anything that is not a one-off typed inside
that checkout.
See [`fully-clean.cases.md`](fully-clean.cases.md), "Checker unhandled exception on wrong repo".

**A remote or web session has no `gh` at all, so the checker cannot answer there
--- and that is a property of the session rather than of the PR.**
The wrong-repo case above is a mistake you can stop making.
This one is not: `check-pr-fully-clean.py` shells out to `gh`, and a
remote/web Claude Code session has no `gh` on `PATH`, so the script refuses
with ``` `gh` is not installed or not on PATH ``` and exits **2** on every
invocation, whatever the PR's real state.

That lands in the third branch of the read above, which is the right answer and
an easy one to skip past, because the mandated instrument failing feels like a
step to work around rather than a result to report.
Two things follow.

**Say that the checker did not run.**
[`ardi`](../../skills/ardi/SKILL.md)'s fully-clean exit checklist opens by
requiring exit `0` from it, so reporting a PR clean without noting the
substitution asserts a check that never happened.
The substitution itself is ordinary --- root `CLAUDE.md`'s "Skills that call
gh/glab: fall back to tool-mappings.md in remote sessions" already governs it
--- so establish both criteria from the GitHub MCP surfaces instead: the
paginated check-runs endpoint for criterion 1, the review body and thread list
for criterion 2.

**Do not read the `2` as a verdict in either direction.**
It is neither "not clean" nor a licence to assume clean.
It is the check declining to answer, which is exactly what the three-valued
read above exists to preserve.

- **Do:** state which surfaces supplied the verdict when the checker could not
  run, so "clean" stays attributable.
- **Don't:** report the checklist item satisfied on a session where the script
  exits 2 --- it did not run.
- **Don't:** treat the refusal as a PR problem, or spend a round diagnosing it;
  the absence of `gh` is the whole cause.

**The mirror case is worse: a review job running the checker on the PR it is
reviewing gets an answer, and the answer is always not-clean.**
The section above is the checker declining to answer, which is loud and exits
`2`.
This one exits **`1`** --- a verdict --- and it is wrong every time.

A review job querying its own PR's check state observes itself as
`in_progress`, and the checker requires that a completed automated review exist
on the current head.
The reviewer is the thing that would produce that review, so the predicate is
unsatisfiable by construction: it cannot authorize itself in advance, at any
round, on any PR, however clean the diff.

The failure is quiet in the way the `gh` case is not.
Exit `2` announces itself as a non-answer; exit `1` is indistinguishable from a
real finding, and it reaches the PR as a withheld verdict that blocks merge
under [`mwc`](../../skills/mwc/SKILL.md)'s Scope Limit --- on a PR the
same review just declared sound.

**It also poisons the rounds after it.**
Re-triggering does not clear it, which is the natural first remedy and the
wrong one: once a `Needs more work` comment exists for that head, the next
round's verdict scan reads a standing not-clean and the loop cannot converge.
Each attempt costs another paid review.

The discrimination to make is between two different claims:

- *"The diff is sound, and I cannot observe my own completion"* --- a statement
  about the **instrument**, which belongs in the report.
- *"This needs more work"* --- a statement about the **diff**, which is the
  verdict field and the thing that blocks.

Routing the first into the second is the defect.
It is the same conflation
[`verify-the-right-artifact`](verify-the-right-artifact.md) names elsewhere: an
inability to measure is being reported as a measurement.

- **Do:** state the instrument's status in the report, and keep the verdict a
  judgment about the diff.
- **Do:** exclude the calling run when a reviewer evaluates its own PR, or say
  the check was not applicable rather than running it.
- **Don't:** put "cannot determine cleanliness" in the verdict field --- it
  blocks merge and reads as a finding to everyone who does not read the
  reasoning.
- **Don't:** re-trigger to clear it; the standing not-clean comment makes the
  next round worse rather than better.

(Measured 2026-08-27 on
[ai-config#2442](https://github.com/Morrison-Lab/ai-config/pull/2442).
Three rounds found one hyperlink nit, one citation-order nit, then nothing.
The instrument reported not-clean in all three, naming
`review / claude-review` (itself) among the pending checks --- and the verdict
field carried that into a block in **two** of them.
The third round said so explicitly: "not due to any content defect", "no
further content changes are needed on my end".
CI was 10/10 green and `require-review` passed.
The three rounds cost $4.60 between them, and the PR merged only on an explicit
user decision to treat the verdict as non-blocking.

The round that did **not** block is the most useful of the three.
It is the same reviewer, on the same PR, reaching the same instrument result
and keeping it out of the verdict field: it returned `Ready for merge` and put
the caveat in a note beneath it.
So the discrimination this entry asks for is achievable rather than merely
desirable, and the two rounds that blocked were not forced to by anything about
the instrument.
That round is also the reason to state the split precisely: the first draft of
this record said all three blocked, and review caught it --- an unverified count
in prose, inside an entry about an unverified count.
Tracked as [ai-config#2441](https://github.com/Morrison-Lab/ai-config/issues/2441).)

(Measured 2026-08-19 on a remote session driving
[ai-config#1673](https://github.com/Morrison-Lab/ai-config/pull/1673).
Tracked as
[ai-config#1679](https://github.com/Morrison-Lab/ai-config/issues/1679), which
weighs teaching the script a REST fallback against documenting the branch;
until one lands, every remote-session ARDI run hits this.)

So read the status, and read all three of it:

```bash
python3 scripts/check-pr-fully-clean.py "$n" -R "$OWNER/$REPO" >/tmp/fc.txt 2>&1
rc=$?
case $rc in
  0) echo "#$n CLEAN" ;;
  1) if grep -q '^  - ' /tmp/fc.txt; then
       echo "#$n NOT clean"; cat /tmp/fc.txt
     else
       echo "#$n CHECK CRASHED (rc=1, no finding bullets) -- not a verdict"
       tail -3 /tmp/fc.txt
     fi ;;
  *) echo "#$n CHECK FAILED (rc=$rc) -- not a verdict"; cat /tmp/fc.txt ;;
esac
```

- **Do:** branch on the checker's exit status, treating 0 as clean, 1 as a
  verdict of not-clean, and anything else as the check having failed to answer.
- **Do:** re-verify the agent and the head yourself before reporting ready,
  since the exit status is necessary and this file's own SHA-surface caveats
  still apply.
- **Don't:** grep a purpose-built checker's output for a phrase --- its prose
  is a human-facing report, not an API.
- **Do:** pass `-R OWNER/REPO` from any poller or script, since the repo comes
  from the working directory otherwise and a background loop inherits whatever
  cwd the session happened to be in.
- **Don't:** collapse the status to a boolean either; `rc != 0` reports a
  broken check as a regressed PR, which is the same conflation wearing the
  remedy's clothes.
- **Don't:** read `1` as a verdict without checking the output has finding
  bullets --- an unhandled exception exits 1 too, so `2` is not the only
  non-verdict code.
- **Don't:** read "I called the right instrument" as having consumed it; the
  bypass guard fires on the call, and nothing fires on the misreading.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"Three PRs reported clean by grepping the checker's own output".

**Exit 0 is not the whole answer either: read the `verdict scan:` line the checker prints, because it can say `0 bore a verdict, latest = NONE` on a run that exits clean.**
The three-way read above governs every status that is *not* 0, so it cannot reach this one --- the false clean arrives as exit **0**, the one value nothing above tells you to look behind.
`check_latest_verdict()` blocks on `not-clean` alone, and an empty verdict is not `not-clean`, so a head reviewed by nobody takes the clean return.
A reviewer's own **skip notice** is enough to occupy the slot.

- **Do:** read the `verdict scan:` line on every invocation, including the ones that exit 0.
- **Do:** treat `latest = NONE` as no review at all, and fall back per [`self-review-fallback`](self-review-fallback.md).
- **Don't:** read exit 0 as "a reviewer approved this" --- it says only that nothing blocking was found, and an empty review history finds nothing.
- **Don't:** count a skip notice as the review;
  it is admitted as a review item and states no verdict, which is exactly the state that exits 0.

**The author filter gates formal reviews and not comments, so a human-authored comment enters that same scan on body text alone.**
The comment loop admits on `is_bot_author or is_review_header`, and `is_review_header` matches `### verdict`, `verdict:`, and `code review` with no author check --- so your own disposition comment, or any reply quoting a reviewer's verdict line, can be counted as a review item.
Reading the formal-review loop and generalizing its author check to comments is [`verify-the-right-artifact`](verify-the-right-artifact.md)'s "a neighbour for the target" shape applied to source.

- **Do:** read the loop that handles the artifact class you are making a claim about --- comments and formal reviews are separate populations here.
- **Do:** check a comment's admission against its body markers, not its author.
- **Don't:** generalize one loop's filter to a neighbouring loop in the same function.
- **Don't:** read "no human comment appeared in `matching_items`" as evidence that human comments are excluded;
  the SHA test is what excluded it.

See [`fully-clean.rationale.md`](fully-clean.rationale.md) for both mechanisms, and [`fully-clean.cases.md`](fully-clean.cases.md), "A skip notice exits the checker clean over an empty verdict scan".

**A classifier written to EXCLUDE driver-status comments from the verdict scan is itself a matcher, and its negative guards protect only the dialect they were written against.**
The section above is a comment wrongly *admitted*;
this is the mirror, a comment wrongly *dropped*.
A driver-ledger classifier recognizes a session's own status comment (claim wording, an ARD disposition table, a self-imposed hold like "hold off ...") from broad English markers, then protects genuine reviews with negative guards -- a `### Verdict` heading, a `Reviewed-Commit:` fingerprint, a `**Claude finished` marker -- that must all be absent before the exclusion applies.
Every one of those guards is keyed on Claude's and Cursor's own report structure.
A Copilot review comment carrying a real, blocking finding phrased as "hold off on merging until X is added" emits none of that structure: the broad marker matches, every guard abstains, and the finding is dropped from the verdict scan entirely -- reported FULLY CLEAN.
This is [`fail-fast`](../principles/fail-fast.md)'s "Guarding an unsound pattern with a second pattern, rather than replacing it" and "A guard's discharge fires on positive success, not the absence of failure" sections, arrived at independently in this checker: negative guards defending an over-broad matcher inherit exactly the ambiguity the matcher already had.

**Inverting the gate to a POSITIVE signature was tried next, and refuted the same day, which is the more useful half of the lesson.**
The candidate signature was the agent-disclosure marker, on the premise that every driver comment carries it and no reviewer report emits it.
Neither half holds.
[`self-review-fallback`](self-review-fallback.md) requires a dispatched or cross-vendor review to be published verbatim WITH that marker, so a genuine not-clean review carries it too, and gating on it dropped that review instead.
And [`disclose-agent-authorship`](disclose-agent-authorship.md) exempts a comment posted under a genuine bot identity, so even the first half is a convention this corpus asks for rather than a property a gate can rely on.
Both attempts failed the same way.
Every discriminator available in a comment body is one some real reviewer also emits, so no body-shape test can safely decide to DROP an item -- and a positive signature is not safer than a negative one merely for being positive.
A third design stopped dropping anything.
It blanked the single shape that actually caused the misread --- a prior round's verdict quoted in a bare parenthetical after a cited SHA --- inside `strip_cited_finding_vocab` instead.
It was refuted too, on a body where the parenthetical IS the live verdict and the explanation follows it outside the blanked span.
Nothing shipped in the checker: all three were reverted.
The fix went to [`ard`](../../skills/ard/SKILL.md)'s summary step instead (#2448) --- a disposition comment backticks any verdict phrase it quotes, so the code-span rule #1202 already established neutralizes it, and the instrument gains no new fail-open surface.

- **Do:** prefer fixing the input at the author's end over teaching the checker to guess -- three checker-side designs were refuted here, and a pair of backticks was not.
- **Do:** derive, by execution, which line of a body actually produced the verdict, before building a classifier for the parts you assume did.
- **Do:** confirm a proposed signature's population against every producer the checker sees, and treat "no reviewer emits this" as a claim to check against the corpus rather than a premise.
- **Do:** read a driver-comment classifier's guard list as a dialect list, and ask what a differently-formatted reviewer's report looks like against it.
- **Don't:** protect an over-broad exclusion marker with negative guards keyed on one producer's output format -- they abstain on every other producer, which is exactly where the marker is most wrong.
- **Don't:** read a positive gate as inherently safer than a negative one -- both were tried here, and both dropped a real reviewer's finding.
- **Don't:** trust a driver-comment classifier's `0 dropped` (or silence) as evidence nothing was excluded;
  the failure here produces no error, just a lower "examined N items" count.

See [`fully-clean.cases.md`](fully-clean.cases.md), "A driver-comment classifier drops a Copilot finding it has no guard for".

**Dropping an item from the verdict scan is a distinct fail-open route from misreading one that IS scanned, and it leaves no trace in the output at all.**
Every case in this file up to here is about an item that entered the scan and was then misread -- a stale SHA, a truncated body, a wrong author filter.
A dropped item never enters the scan, so the "examined N items" line the checker prints simply reads one lower, which is indistinguishable from a PR that genuinely received one fewer review comment.

- **Do:** when a verdict scan reports fewer items than the PR thread has comments, ask what was dropped and why, not just what the scanned items said.
- **Don't:** read a clean scan, however many items it examined, as evidence every review comment on the thread was considered.

**A verdict comment quotes verdict phrases, so a phrase search identifies
nothing --- and it misreads in both directions at once.**

- **Do:** call `check-pr-fully-clean.py` for a sweep's verdict column, exactly
  as [`ardi`](ardi.md) requires for one PR.
- **Do:** anchor on the last `### Verdict` heading when parsing by hand, after
  selecting candidates on the `**Claude finished` marker.
- **Don't:** take the first verdict phrase in a body as that body's verdict ---
  quoting other verdicts is part of what a review comment does.
- **Don't:** assume such a misread has a safe direction; one sweep produced a
  false-clean and a false-blocked.

**That "anchor on the last `### Verdict` heading" line describes the by-hand
method, not what `check-pr-fully-clean.py` itself does --- the script has no
heading anchor at all.**
It matches verdict *phrases* with a regex
(`Verdict:\s*(?:Clean|Approved|Ready)\b` and its not-clean counterpart), never
a `^###\s*Verdict` heading line, so a doubled or malformed `### Verdict`
heading in a review comment cannot break something the script never checks.
Reading this fragment's hand-parsing advice as a description of the script's
own mechanism produces a confident, wrong claim about our own tooling ---
worth naming because the fragment sits right next to the script it is easy to
assume it summarizes.

- **Do:** read `scripts/check-pr-fully-clean.py` itself when the claim under
  test is about what the script does, even when this fragment already
  describes the by-hand procedure.
- **Do:** treat "anchor on the last `### Verdict` heading" as guidance for a
  human parsing a comment, distinct from the script's own phrase-matching
  logic.
- **Don't:** infer the script's parsing mechanism from this fragment's
  by-hand advice --- verify against the script's source before filing an
  issue that names a mechanism.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"A fragment's by-hand parsing advice mistaken for the script's own mechanism".

**A review comment's header SHA can be stale, so take the reviewed commit from
the run's own `head_sha`.**

- **Do:** follow the job link in the comment and read that run's `head_sha`.
- **Don't:** treat the SHA in a comment's heading as the commit reviewed.

**That remedy assumes the run checked out the PR head, and a `workflow_dispatch`-triggered review run does not.**

- **Do:** check a `workflow_dispatch` review's `event` field before reaching for `head_sha` --- on that trigger type the field names the dispatch ref, not the reviewed commit.
- **Do:** cross-check a stale-suspected verdict's specific claims against the file directly, rather than only against run metadata.
- **Don't:** trust `head_sha` as "the commit reviewed" on a workflow-dispatch-triggered run --- that guarantee only holds for push/pull_request-triggered runs, which check out the PR head by construction.

**A third surface names a commit the run never read, and unlike the two above
it points the confident direction: the run object's own
`pull_requests[].head.sha`.**

- **Do:** settle which commit a review read from a discriminating claim in its
  own body, since that is the only surface separating the candidates.
- **Do:** read `pull_requests[].head.sha` as a fact about the PR's current
  head, useful for nothing else.
- **Don't:** read that field naming your latest commit as evidence the review
  covered it --- it names the current head unconditionally.
- **Don't:** read an empty `pull_requests` as evidence about the run; the array
  empties when the PR closes.

See [`fully-clean.cases.md`](fully-clean.cases.md), "`pull_requests[].head.sha`
named a commit pushed after the run started".

**A fourth surface is the one a script parses first, and it can name a commit
that exists on no branch: the `commit_sha` field inside the review's own
structured JSON block.**
That field reports whatever `git rev-parse HEAD` returned in the reviewer's
checkout, and on a `pull_request`-triggered run that is the synthetic merge
commit GitHub builds at `refs/pull/N/merge`, not the branch tip.
The `Reviewed commit:` trailer the workflow appends beneath the JSON named the
branch tip in every case observed.
The same reviewer emits a trustworthy field on one trigger and a
misleading one on the other, with nothing in the comment saying which.
The failure this produces is a needless re-request: a script comparing
JSON `commit_sha` against the PR's `head.sha` reads a verdict on the current
head as a verdict on an unknown commit.

- **Do:** take the reviewed commit from the `Reviewed commit:` trailer, and
  fall back to the run's `head_sha` per the surfaces above.
- **Do:** when the JSON field and the trailer disagree, resolve the JSON's
  SHA with `git fetch origin <sha>` and read its parents before concluding
  anything; a two-parent commit whose second parent is your tip is the
  merge ref, and the verdict covers your tip.
- **Don't:** compare the JSON `commit_sha` against the PR head to decide
  staleness --- on a `pull_request`-triggered review it never matches, even
  when the review is current.
- **Don't:** read the two repositories' agreement or disagreement as a
  property of the repository; it is a property of the trigger.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"The review JSON's `commit_sha` named the synthetic merge commit".

**`check-pr-fully-clean.py` uses the same unreliable body-text surface, and
whichever SHA that text happens to contain --- present, absent, or wrong ---
is incidental to which head the run actually reviewed.**

- **Do:** read a flagging run's `event`, `head_branch`, and `head_sha`
  before treating "no review at this HEAD" as a genuine gap.
- **Do:** treat the script's discharge as the likely reading, since the
  withholding direction dominates in practice, but not as a certified one.
- **Don't:** re-dispatch a review, or fall back to self-review, on this
  signal alone when the flagging run's own metadata already shows it
  evaluated the current head.
- **Don't:** read a body's SHA, present or absent, as evidence about which
  head a review covered --- it is evidence about what the prose happened to
  discuss.
- **Don't:** conclude that reviewers citing their head SHA more consistently
  would fix this; a body can already cite a SHA and still be citing the
  wrong one.

**A review citing a SHA that is not the PR's head is usually an intermediate commit, not a fabricated one --- resolving it locally settles which.**
The cases above are about which SHA to trust when several are in play;
this one is about a body citing a SHA that matches none of them, which first reads as a hallucinated citation.
A round with more than one commit --- a fix plus a later `Merge origin/main` on top, say --- has a real, resolvable commit for the fix that is not the round's head, and a reviewer naming that commit is often the more useful citation of the two.

- **Do:** run `git cat-file -t <sha> && git show -s --format='%h %an %s' <sha>` on a cited SHA that does not match the head before concluding it is fabricated.
- **Do:** read a resolvable SHA that sits in the branch's own history as a legitimate citation of an intermediate commit, not a hallucination.
- **Don't:** treat a claim about **PR state** ("this was already merged", "CI already passed") the same as a claim about **which commit** did something --- the former still deserves the API check this file opens with;
  a bare SHA mismatch does not.
- **Don't:** re-push a fix already present in the cited commit because the SHA did not match what you expected.

See [`fully-clean.cases.md`](fully-clean.cases.md), "A review cited the fix commit, not the round's merge-topped head".

**A clean CI run and a clean review verdict are a snapshot, not a standing
guarantee of mergeability.** `main` can advance after your last check ---
including gaining its own independent addition that collides with yours
(see `sync-with-main.md`'s "two PRs append the same numbered subsection" case)
--- so re-verify the branch still merges cleanly against current `main`
before reporting a PR ready, not just trust the last green run.

`mergeStateStatus: CLEAN` means conflict-free plus passing commit status (GitHub's `mergeable` field), not merge-ready.
A PR without a clean review verdict on the latest commit is not merge-ready.

**A head green on its own branch can turn `main` red on merge, when the base gained a new CI check after the PR's latest CI run.**
A `pull_request` run uses the workflow definition current at that run,
so the gap opens when `main` gains a check afterwards
and no new PR event re-runs CI.
A check added to `main` after that run never fires on the PR until a new PR event synthesizes a fresh `refs/pull/N/merge`,
so there is nothing red to see: the check simply never ran.
Measured 2026-09-01 (Pacific) on [#2965](https://github.com/Morrison-Lab/ai-config/pull/2965).
That branch added hook bindings to `hooks/hooks.json` before [#2967](https://github.com/Morrison-Lab/ai-config/pull/2967) landed the generated `skills/ai-config-hooks/hooks/hooks.json` and its `gen-hooks-plugin.py --check` gate on `main`.
`check-pr-fully-clean.py` reported [#2965](https://github.com/Morrison-Lab/ai-config/pull/2965) FULLY CLEAN,
a GIA session merged it under `mwc`,
and `validate` on `main` went red at `da1a2d03` until [#2983](https://github.com/Morrison-Lab/ai-config/pull/2983) regenerated the manifest.
The head-only verdict cannot see this, and no path diff can prove the base gained no check through a script or a reusable workflow,
so for a direct merge the rule is the one [`sync-with-main`](sync-with-main.md) already states: a stale merge-base means update first.
Under a merge queue where every clean-gate check both executes for `merge_group` and is required (or aggregated behind a required check),
the queue's speculative merge test will cover this once [#3030](https://github.com/Morrison-Lab/ai-config/issues/3030) defines the queue form of the gate,
and [`merge-queue`](merge-queue.md) forbids the manual update loop there.
Until then a base that requires a merge queue stops the merge.
The conditions below are what that form has to prove.
A `pull_request`-only workflow added to the base does not run on the queue's branch,
and a workflow that lists `merge_group` can still carry a job or step whose `if:` skips that event,
which branch protection then counts as passing.
This corpus's clean gate counts every check, not only the required ones,
while the queue advances on the required checks alone ([`merge-queue`](merge-queue.md)),
and a failing non-required check has been measured to leave a PR mergeable ([`github-actions`](../../memories/github-actions.md), the bcs `test-coverage` entry).
So two conditions hold before the manual update is skipped:
every clean-gate check executes for `merge_group`, job and step conditions included,
and every clean-gate check is a required status check on the base, or is aggregated behind one that is.
A clean-gate check the queue cannot block on is a check the queue does not run as a gate.
`gh pr checks --required` (present in `gh` 2.98.0) lists the required checks among those in the current rollup, but a required check absent from that rollup, one the base gained after the head's last run, is exactly the case here, and no `gh pr checks` output says whether a check executes on `merge_group`, so the rules query and the workflow read below are what settle both ([`gh-cli`](../../memories/gh-cli.md) carries the same distinction).
Those two conditions are the specification the queue form of this gate has to prove ([#3030](https://github.com/Morrison-Lab/ai-config/issues/3030)), and until it lands the exception is unavailable: a base that requires a merge queue stops the merge, since a required check supplied by a GitHub App cannot be verified from workflow files at all.
The proof will read the required checks from `gh api --paginate "repos/<owner>/<repo>/rules/branches/<base-encoded>"` (encode the base name as one path segment, `jq -rn --arg b "<base>" '$b|@uri'`, since `release/1.x` would otherwise split into two, and paginate, since the first page can omit rules), and each clean-gate workflow's `on:` block and job and step `if:` conditions for `merge_group`.

The rule splits by merge mode: a direct merge from a session with `git` and `gh`, a direct merge from a remote session without `git`, and, once [#3030](https://github.com/Morrison-Lab/ai-config/issues/3030) lands, a merge queue.
It is GitHub-specific as written (`headRefOid`, `gh`, the compare endpoint, the update-branch and merge pins), so a GitLab merge has no equivalent gate until [#3021](https://github.com/Morrison-Lab/ai-config/issues/3021) supplies one, and `merge-it`, `mwc`, and `chores` inherit that scope.
It binds every direct-merge path, including the dependency-bump merges in [`chores`](../../skills/chores/SKILL.md), not only `mwc` and `merge-it`.
For a bot bump, the gate to rerun after an update is CI plus conflict state, which is what those PRs are gated on, since `@claude` review is skipped on them by design.
`chores` states that form.
A deferred merge (`gh pr merge --auto`, or a `@dependabot` merge command) stays out of every direct-merge path.
Auto-merge stays enabled across a later push by anyone with write access (GitHub disables it only for a push from someone without write permission, or a base switch) and fires on required checks alone, so a pin on the enabling request protects nothing after it, and the sync-only-push rule in this fragment already forbids arming it after a new head.
Merge synchronously, right after the check, with the merge command pinned.

- **Do:** for a direct merge from a session with `git` and `gh`, record `headRefOid` and `baseRefName` before the clean gate runs, so the gate's verdict is tied to one head and one target.
  Then, before the merge command, confirm the live `baseRefName` is still the recorded one, fetch that base, confirm the live PR head is still the recorded SHA, and confirm the merge-base with it is that base's current tip.
  A retarget to another branch at the same tip during the gate would otherwise pass both the ancestry check and the head pin with a verdict produced for the old target.
  A concurrent push after the gate can already contain the base tip, so an ancestry check alone would admit a head no verdict covers.
  Until [#2982](https://github.com/Morrison-Lab/ai-config/issues/2982) wires this into `check-pr-fully-clean.py`, which [`mwc`](../../skills/mwc/SKILL.md) already runs, both [`mwc`](../../skills/mwc/SKILL.md) and [`merge-it`](../../skills/merge-it/SKILL.md) name it as a manual step after their readiness check and before the merge command:
  `url=$(gh repo view "<owner>/<repo>" --json url -q .url) && b=$(gh pr view "<N>" -R "<owner>/<repo>" --json baseRefName -q .baseRefName) && [ -n "$url" ] && [ -n "$b" ] && [ "$b" = "<pinned-base>" ] && git fetch "$url" "$b" && tip=$(git rev-parse --verify FETCH_HEAD) && git fetch "$url" "refs/pull/<N>/head" && head=$(git rev-parse --verify FETCH_HEAD) && [ "$head" = "<pinned-sha>" ] && [ "$(git merge-base "$tip" "$head")" = "$tip" ] && echo "$tip"`,
  where `<pinned-sha>` and `<pinned-base>` are the `headRefOid` and `baseRefName` recorded before the gate ran.
  The trailing `echo` prints the tested base tip: record it as `<pinned-tip>` before the gate reruns, since a shell variable does not survive into the later tool call that makes the pre-merge comparison.
  The live base name is compared to the pin rather than trusted, so a retarget fails the check instead of steering the fetch.
  `git merge-base` needs both tips' history: in a shallow clone the two can appear disjoint ([`claude-code-consumer-wiring`](../../memories/claude-code-consumer-wiring.md) records the bogus merge-base), so run `git fetch --unshallow` (or `--deepen=<n>` with a depth that reaches the common ancestor) first, or use the compare endpoint, which is unaffected.
  Both fetches name the repository the `-R` reads came from, not the checkout's `origin`, which in a fork or another checkout can be a different repository whose same-numbered PR would let the gate compare unrelated commits.
  Each result is assigned inside the `&&` chain so an unresolved branch or a failed command fails the check rather than comparing two empty strings as equal.
  Reading `FETCH_HEAD` after each fetch uses the tip the fetch just returned and writes no remote-tracking ref, so it holds in a single-branch clone (where a bare `git fetch origin` leaves `origin/<branch>` stale) and under `fetch.prune=true` (where an explicit `branch:refs/remotes/origin/branch` refspec was measured to delete the ref and fail `rev-parse` on its first run).
  The base comes from the PR, not from the repository's default branch: a stacked or release PR targets another branch, and [`merge-it`](../../skills/merge-it/SKILL.md) already warns not to assume `main` for those.
- **Do:** for a direct merge from a remote session without `git`, re-read the PR's `headRefOid` and `baseRefName` and require both to equal the recorded pins, then read the compare endpoint instead of `git merge-base`, `gh api "repos/<owner>/<repo>/compare/<base-encoded>...<head-sha>"`, with the base name encoded as one path segment (`jq -rn --arg b "<base>" '$b|@uri'`, so `release/1.x` does not split the path), and require `behind_by` of 0.
  The pin comparison is the same one the local path makes, since `expectedHeadSha` on the merge protects the head and nothing protects the target branch.
  When `behind_by` is 0, record the response's `base_commit.sha` as `<pinned-tip>` (the base tip at that moment, equal to `merge_base_commit.sha` in that state).
  The pre-merge comparison re-reads the same endpoint and requires both `behind_by` of 0 again and `base_commit.sha` equal to `<pinned-tip>`, since with an unchanged head `merge_base_commit.sha` keeps the old ancestor after the base moves and would compare equal on its own.
  Without that record the remote path has nothing to compare.
  Measured 2026-09-02 (Pacific) on [#2989](https://github.com/Morrison-Lab/ai-config/pull/2989): `behind_by` was 0 and `base_commit.sha` and `merge_base_commit.sha` were both the base tip, the same answer the `git merge-base` form gives.
  Where no raw API call is available either, as in an MCP-only session whose tools expose neither endpoint, the gate cannot run, so do not merge from that session until [#2982](https://github.com/Morrison-Lab/ai-config/issues/2982) supplies the tool.
  That is the fail-closed direction, per [`fail-fast`](../principles/fail-fast.md).
- **Do:** when the merge-base is not that tip and the merge is direct, update the branch pinned to the recorded head (the `expected_head_sha` update call, or `update_pull_request_branch` with `expectedHeadSha` remotely), then rerun the whole clean gate on the new head, review included, before merging.
  The update is a new head, so a clean verdict on the old one no longer counts, per [`sync-with-main`](sync-with-main.md).
  The update is asynchronous: the REST endpoint answers `202 Accepted` while the merge is still in progress, and the MCP tool reports that answer as success, so a gate rerun started at once can read the old head.
  Pin the update itself to the head that failed the currency check.
  Locally that is `gh api -X PUT "repos/<owner>/<repo>/pulls/<N>/update-branch" -f expected_head_sha="<pinned-sha>"`, since the `gh pr update-branch` wrapper has no flag for it in `gh` 2.98.0.
  Remotely it is `expectedHeadSha` on the MCP `update_pull_request_branch` tool.
  A `422` whose message names an expected-head mismatch means the head already moved.
  Match on the substring `expected head sha`, since the live text carries a curly apostrophe and a trailing period that this ASCII rendering cannot show.
  That is the another-writer signal, so it routes to the ownership rule (settle who owns the branch per [`claim-pr`](claim-pr.md)) instead of merging the base into someone else's push.
  The endpoint uses `422` for other validation failures too, so any other message is a failed update: stop and read it rather than treating it as a moved head.
  Measured 2026-09-02 (Pacific) on [#2989](https://github.com/Morrison-Lab/ai-config/pull/2989): a deliberately wrong `expected_head_sha` returned `422` with a message reading "expected head sha didn't match current head ref." (curly apostrophe in the live text) and changed nothing.
  Then poll `headRefOid` until it changes, with a deadline (five minutes is generous for a merge commit GitHub has accepted), and treat expiry as a failed update to stop on and report, since a `202` can be returned without a new head ever appearing.
  Once it changes, record that SHA, rerun the base-currency check on it, and only then rerun the gate, pinned to that SHA.
  The gate itself takes minutes, so the base can advance again while it runs, and so can the head: a concurrent push that already contains the current base passes a currency-only recheck while the gate's verdict belongs to the earlier SHA ([`github`](../../memories/github.md) records that unpinned-head race).
  So immediately before the merge command, check that the live `headRefOid` still equals the pinned SHA, that `baseRefName` is still the branch the gate ran against (a retarget to another branch at the same commit would otherwise pass a tip comparison), and that the live base tip still equals `<pinned-tip>`, and repeat the update-and-gate cycle when any of them moved.
  Then make the merge itself carry the pin: `gh pr merge --match-head-commit "<pinned-sha>"` (measured 2026-09-02 (Pacific) in `gh` 2.98.0: the flag is documented as the commit SHA the head must match to allow the merge), or `expectedHeadSha` on the MCP `merge_pull_request` tool, so a push in the seconds after the read is refused by the API rather than merged.
  A remote session's bash has neither: `gh` is absent, and the MCP tool belongs to the agent rather than to the shell.
  The third form is plain REST, and it takes the pin as `sha`:
  `curl -X PUT -H "Authorization: Bearer $GITHUB_TOKEN" ".../repos/<owner>/<repo>/pulls/<N>/merge" -d '{"merge_method":"squash","sha":"<pinned-sha>"}'`.
  That `sha` is the same guarantee the other two spell differently --- the API refuses the merge when the head has moved --- so a session without `gh` is not thereby excused the pin.
  Measured 2026-09-03 on [#3035](https://github.com/Morrison-Lab/ai-config/pull/3035) and [#3043](https://github.com/Morrison-Lab/ai-config/pull/3043), both merged this way after `gh` returned `command not found`.
  It merges but does not tidy: `--delete-branch` has no REST counterpart here, and `DELETE /git/refs/heads/<branch>` is refused by the agent proxy itself, so the remote branch outlives the merge and only the local one can be cleaned up.
  The pre-merge read still runs first, because it is what says which ref moved.
  The pin closes only the head side: no merge API pins the base, so the base can still advance between that read and the merge, and a direct merge on a base without an up-to-date-branch requirement keeps that window open.
  **Sync with `git` rather than `update-branch` where the review gate excludes bot senders**, since the update makes the new head *bot-authored* and the gate then skips the very verdict this rule goes on to require.
  `Morrison-Lab/gha`'s `claude-code-review.yml` gates on `github.event.sender.type != 'Bot'`, so a head produced by the API call reports every review job `skipped` while CI stays green --- a state that reads like a review not yet started rather than one that will never run.
  Rebasing onto the base and force-pushing (with `--force-with-lease --force-if-includes`) reaches the same base currency and triggers the review normally, because a `git` push carries a User identity where a REST write does not ([`github-remote-sessions`](../../memories/github-remote-sessions.md)).
  Confirm the rebase preserved the change rather than assuming it: compare the tree hashes when the base did not move, and the diff against the base when it did.
  The `expected_head_sha` machinery above still applies to the API route, which stays correct wherever the gate admits bot senders.
- **Do:** measure the base's merge interval against one gate cycle before starting a third sync, rather than chasing.
  `git log origin/<default-branch> --first-parent -8 --format='%ct'` gives the interval and the review run's own timestamps give the cycle;
  when the interval is the shorter of the two, serial syncing cannot converge ([`batch-merge-and-resolve`](batch-merge-and-resolve.md)), and each attempt spends a paid review round.
  Measured 2026-09-02 on [#3035](https://github.com/Morrison-Lab/ai-config/pull/3035): a median interval of 221s against a ~6 min cycle, three merges landing inside 30s, and four review rounds spent before the base held still long enough to merge.
  The escape is to wait for a quiet window and sync then --- which is a real strategy rather than a stall, since the cadence is bursty --- or to raise the server-side closure with whoever owns the ruleset.
  Read a repository's `rulesets` endpoint rather than assuming: `strict_required_status_checks_policy` false and no merge-queue rule means the closure this rule points to does not exist there, and branch protection may read `403` for the session's own token.
  Where the base must be stable, only a server-side gate closes it, a merge queue or the up-to-date-branch requirement (with every clean-gate check required or aggregated, per the exception above), and the direct-merge entry points say so.
  The cycle repeats for either ref, so a repeat says which one to look at rather than which remedy applies.
  When the base moved twice it is advancing faster than the gate runs, which [`batch-merge-and-resolve`](batch-merge-and-resolve.md) measures: stop chasing and merge under strict up-to-date protection (or through a merge queue once [#3030](https://github.com/Morrison-Lab/ai-config/issues/3030) lands), or batch the pending merges per that fragment.
  When the head moved, another writer is pushing to the branch, and no queue or protection setting stabilizes that: find the writer per [`claim-pr`](claim-pr.md) and settle who owns the branch before rerunning.
- **Do:** on a base that requires a merge queue, stop and report rather than merging: the queue form of this gate (the coverage proof, a retarget check before enqueue, and the asynchronous enrollment state machine) is [#3030](https://github.com/Morrison-Lab/ai-config/issues/3030), and until it lands no agent path in this corpus merges through a queue.
  Whether the pinned base requires one is read before any merge command, from the same rules query: `gh api --paginate "repos/<owner>/<repo>/rules/branches/<base-encoded>" --jq '[.[] | select(.type == "merge_queue")] | length'`, a nonzero count being the stop.
  The merge command cannot serve as the probe, since `gh pr merge` enqueues rather than refuses.
  Measured 2026-09-02 (Pacific) on this repository's `main`: the count is 0 and the rule types present are `deletion`, `non_fast_forward`, `pull_request`, `required_linear_history`, and `required_status_checks`.
  A manual update repairs neither case, since it cannot make a check block or make a workflow run on `merge_group`.
  Make every clean-gate check required (or aggregated behind one) and `merge_group`-triggered, or merge directly where the repository permits it, with the direct-merge checks above.
- **Don't:** read a head-only FULLY CLEAN verdict as a merge-safe verdict when the base has advanced.
- **Don't:** substitute a path diff of `.github/workflows/` for the update.
  It cannot see a check that arrived through a script or a reusable workflow.

Tracked as [#2982](https://github.com/Morrison-Lab/ai-config/issues/2982).

- **Do:** always check for merge conflicts (e.g., using `gh pr view <number> --json mergeable` or `gh pr checks`) at the same time you check for CI and review status.
- **Do:** report a PR as blocked on review when HEAD has no authentic clean verdict, even if GitHub says `CLEAN`.
- **Don't:** treat green CI plus a clean review as sufficient without independently re-checking merge-conflict state.
- **Don't:** describe a PR that lacks a clean HEAD review as merge-ready, ready to merge, or "green and merge-ready."

**Because a clean CI run and a clean review verdict are a snapshot, a reading
you took over a live PR cannot be re-derived later --- so capture the command
and its output verbatim at the moment a decision starts to rest on it.**

"A clean CI run and a clean review verdict are a snapshot" says the state
moves; this is what that costs when you try to explain a reading afterwards.
Re-running the command answers a question about the PR *now*, and it is
presented in exactly the form of an answer about the PR *then*, so a
disagreement between the two invites a hunt for a cause --- a tool version, a
change in wording, a bug --- when the only established fact is that the PR
moved.
That hunt is expensive and it converges on something plausible, because
plausible explanations for a tool disagreeing with itself are cheap.

It is worse than an ordinary lost measurement because a remembered reading and
a mis-remembered one are indistinguishable from the inside, and the reading is
usually the whole basis for whatever was decided next.

- **Do:** paste the command and its verbatim output --- exit status included ---
  into the issue, PR, or notebook entry at the moment you act on it, as
  [`algorithmatize-checks`](algorithmatize-checks.md) and
  [`grep-is-not-coverage`](grep-is-not-coverage.md) already require for a
  derived figure; what is new here is that a live PR makes the reading
  unrepeatable, so the paste is the only copy there will ever be.
- **Do:** report the cause as not established when a later re-run disagrees and
  nothing was captured, rather than naming the likeliest mechanism.
- **Don't:** treat a re-run as reproducing an earlier reading over a live PR ---
  the input differs, so the two are separate measurements.
- **Don't:** file or record a diagnosis whose only evidence is a reading you can
  no longer produce.

(Measured 2026-09-02 on `Morrison-Lab/ai-config`: differing
`check-pr-fully-clean.py` readings across `Morrison-Lab/gha#811`, `#814` and
`#820` were attributed first to a vocabulary false positive and then to a stale
checker.
A controlled re-run varied the checker version and held the three PRs fixed:
the stale clone at `240650120` and a worktree at `origin/main` each returned
`#814` rc=0, `#820` rc=0, `#811` rc=1 --- every PR the same under both
versions.
That is a direct test of the stale-checker explanation, and it fails.
It is no test at all of the wording explanation, which is a claim about
readings that no longer exist.
What the re-run leaves is the residual --- the PRs' own state moved between the
original runs --- which ai-config#3031 records as the remaining explanation.
That is elimination rather than measurement, and this section's own bullets say
to report it as such.
What it cannot establish is which reading each original run produced, because
none was captured.
ai-config#3022 was closed after review falsified two successive stated causes,
and ai-config#3032 for that plus a guard that was a no-op at a third layer.)

**A sync-only push invalidates a clean verdict just as thoroughly as a code push, and arming auto-merge after a sync violates the HEAD review gate.**
When `main` moves and a direct merge is refused because the branch is not up to date,
merging `origin/main` in and pushing creates a new HEAD commit ref.
Arming `gh pr merge --auto` immediately after that sync push ---
reasoning about it as scheduling a merge already verified rather than authorizing an unreviewed head ---
violates [Pattern 12](../../memories/mistake-patterns.md).
GitHub auto-merge fires the moment CI passes,
racing ahead of and potentially merging before any automated or adversarial reviewer can evaluate the new HEAD commit.
The sync is content-free (no author code changes),
which is why it does not feel like a new head needing a new verdict,
but the new HEAD commit ref is completely unreviewed until a fresh review round posts for that exact SHA.

- **Do:** re-run `scripts/check-pr-fully-clean.py <N>` against the new HEAD commit after any sync push,
  wait for clean reviews and green CI at that HEAD,
  and merge directly/synchronously.
- **Do:** accept that a fast-moving `main` may require repeating the sync-and-verify cycle rather than attempting to bypass it with auto-merge.
- **Don't:** arm `gh pr merge --auto` after a sync-only push under the impression that prior verification at an older commit carries forward.
- **Don't:** assume GitHub auto-merge will wait for review comments ---
  it gates only on native branch protection checks.

See [`fully-clean.cases.md`](fully-clean.cases.md),
"Auto-merge armed after a sync-only push, having verified the previous head (#2556)".

**Re-check version parity in that same sweep, not only conflict-freedom.**

**Threads:** at fully-clean, every **inline** review thread is resolved, and the only conversation left open is the final all-clear exchange --- the reviewer's all-clear comment and your reply to it. (The all-clear is usually a top-level PR comment, not an inline thread.)

**One finding can own two threads, so sweep by thread id rather than by
finding.**

**Deadlock -> escalate to a human.** If you and the reviewer(s) can't reach consensus on an item (a rebuttal was exchanged and neither side is budging), don't loop forever and don't unilaterally override the reviewer --- request a **human reviewer**, `@`-mention them in a comment summarizing the impasse, and surface the open item.

**An automated reviewer's verdict on a disputed factual/technical claim is not stable across independent runs, even with identical evidence available each time.** Don't treat one round's "settled, no need to keep arguing" as durable: the very same review job, re-triggered later with no new code changes, can re-raise a claim it previously retracted --- and then retract it again on a subsequent run --- purely from re-deriving the question differently each time, not from anything changing in the PR. This means a rebuttal thread's outcome (however many rounds of citations and counter-citations) doesn't itself resolve a genuine deadlock the way a human's decision does; only escalating per the bullet above actually settles it. The one thing that DOES help going forward: fold the authoritative citation/evidence directly into the code or doc being reviewed (a comment, not just a PR conversation reply) --- a fresh reviewer run re-deriving the claim from scratch is more likely to find the citation sitting right next to what it's evaluating than to dig through prior thread history for it, though even that is not a guarantee against a bot that ignores context already in front of it.

**Algorithmic safeguards:** Algorithmic checks and hooks can only invalidate, not validate, a PR.
You still need to use your own judgment in addition to satisfying the algorithmic safeguards;
they are a safety net, not a gold standard.
