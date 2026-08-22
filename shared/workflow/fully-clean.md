"Fully clean" is the terminal state the ARDI review loop drives toward.
A PR/MR is **fully clean** when **both** of these hold (and verified via `python3 scripts/check-pr-fully-clean.py <pr-number>`):

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

   **`gh pr checks` is not a complete enumeration of a head's check runs, so
   read the commit check-runs endpoint before deciding that everything has
   finished.**

   **`--paginate` is load-bearing, not tidiness.**

   **The endpoint covers check runs only, so a repo that still uses legacy
   commit statuses needs a second query.**

   **Why the two surfaces disagree is unexplained, so do not assert a
   mechanism for it.**

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

   **Every subsection above explains a check list that is short for a per-PR
   reason, and a platform outage produces the same shape for a reason none of
   them can reach.**

   **A job's conclusion is set by whichever step failed, which need not be the step whose verdict you read.**
   Every rule above is about an enumeration that came back short.
   This one is the opposite case: the enumeration is complete and terminal, and the answer you read came from the wrong member of it.
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
   `check-new-line-breaks.yml` passes `base-ref` only when `github.event_name == 'pull_request'`, so the `push`-triggered run of the identical workflow has no base, examines zero added lines, and passes having measured nothing.
   Both runs attach to the same commit, so `gh pr checks` prints two rows with one name, one `pass` and one `fail`, and reading the list top-down finds whichever came first.

   The vacuous run is the one to discard, and the trigger event is the only field that separates them.
   `gh api "repos/<owner>/<repo>/actions/runs/<id>" --jq '.event'` settles it in one read per run.
   A `pass` from a run whose event supplies no base is [`algorithmatize-checks`](algorithmatize-checks.md)'s zero-matrix problem arriving as a green check: a detector that never ran and a detector that found nothing are the same observable.

   Note that this is not the same as [ai-config#1870](https://github.com/Morrison-Lab/ai-config/pull/1870)'s ambiguity, where two *different* workflows contribute check runs sharing a name.
   Here it is one workflow, and the disambiguator is the event rather than the workflow name --- so a fix keyed on `workflowName` cannot see it.

   - **Do:** read the `event` of any run whose verdict you are about to rely on, whenever the same check name appears twice on one head.
   - **Do:** take the verdict from the `pull_request`-triggered run for any check that diffs against a base.
   - **Don't:** read a `pass` as evidence the check examined anything --- ask what population it was given first.
   - **Don't:** resolve a same-name disagreement by workflow name.
     On this shape both runs carry the same one.

   (Measured 2026-08-22 on [ai-config#1884](https://github.com/Morrison-Lab/ai-config/pull/1884).
   Run `32545283504` (`event=push`) and run `32545289903` (`event=pull_request`) both had `head_sha=8c456074`, both were named `new-line-breaks / check-new-line-breaks`, and they concluded `success` and `failure` respectively.
   The push run was read first and taken as the verdict.
   The PR run was the one carrying four real findings.)

2. **The latest review is totally clean:** no nits, and every item that wasn't directly **Addressed** is either **Deferred** to a tracked follow-up issue, or **Rebutted with a rebuttal that actually convinced the reviewer** --- i.e. the reviewer did *not* re-raise it on the next round.

**Criterion 2's test is the absence of findings, not the presence of a verdict
line saying so.**

So when the two disagree inside one comment, **the findings win**.
Read to the end of the comment before calling anything clean, and count the
items under every heading, whatever that heading is called ---
[`address-every-comment`](address-every-comment.md) already establishes that
"non-blocking", "nit", "minor", and "optional" are prioritization labels rather
than a pass, and a reviewer files findings under exactly those words in the
section that contradicts its own verdict line.

**Final approval comes from Claude where Claude is reachable.**
Another agent's clean verdict clears CI's review gate; it does not clear
criterion 2 on its own.

This is a directive rather than a derivation, so treat it as a standing
preference and not as a claim about any agent's general competence.
What it settles is which verdict a PR is reported **ready** on.

The reason it needs stating is that the two are indistinguishable from the PR
page.
Every agent posts the same shape --- a summary, some analysis, a positive
closing line --- so a findings-free report reads as approval whichever agent
produced it, and the review-gate check goes green either way.

Two failure modes make the preference concrete, and both have recurred:

- **A clean verdict over tooling that errored.**
  A report can open by saying its own grep failed and then approve on the
  strength of the analysis that grep was supposed to support.
  The error line sits above the verdict, so it reads as a caveat rather than as
  the verdict's foundation collapsing.
- **A clean verdict at a head another agent finds a real defect in.**
  Not a difference of opinion about a nit --- a checkable factual error, at the
  same commit, that the clean verdict passed over.

So when Claude is reachable, its verdict is the one to report on:

- **Do:** dispatch a Claude review and wait for its verdict before reporting a
  PR ready, whatever another agent has already said.
- **Do:** name which agent produced the verdict you are reporting, so "clean"
  is attributable rather than anonymous.
- **Do:** treat another agent's findings as real findings --- this ranks whose
  *approval* is final, not whose objections count.
- **Don't:** report a PR ready on a non-Claude clean verdict while Claude is
  reachable, however thorough that report reads.
- **Don't:** read a green review-gate check as settling this; the gate does not
  know which agent answered, and on a selector-based setup the agent is chosen
  at random.

This is a different question from how much two reviewers **agreeing** is worth,
which [`self-review-fallback`](self-review-fallback.md)'s cross-vendor section
settles: there, same-vendor agreement measures a shared blind spot, and a
cross-vendor split is a prompt to check the item yourself.
That section weighs corroboration; this one names whose approval is terminal.
They compose --- a cross-vendor reviewer is still worth chasing, and its clean
verdict still is not the one a PR is reported ready on while Claude is
reachable.

Where Claude is genuinely unreachable --- quota-skipped, a stub with no stated
verdict, or not configured --- fall back per
[`self-review-fallback`](self-review-fallback.md), which already governs that
case.
Another agent's clean verdict is worth more than nothing there, and it is still
not Claude's; say which one you have.

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

When a review run skips (e.g. self-modification workflow guard or quota limits) and falls back to a self-review or human review per [`self-review-fallback`](self-review-fallback.md), that fallback authorizes **merging** only in the absence of prior unresolved findings.
It does NOT wipe the slate clean, and it does NOT license merging over an unaddressed `Needs more work` verdict or open finding list from an earlier or concurrent review run.

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

**A clean CI run and a clean review verdict are a snapshot, not a standing
guarantee of mergeability.** `main` can advance after your last check ---
including gaining its own independent addition that collides with yours
(see `sync-with-main.md`'s "two PRs append the same numbered subsection" case)
--- so re-verify the branch still merges cleanly against current `main`
before reporting a PR ready, not just trust the last green run.

**Re-check version parity in that same sweep, not only conflict-freedom.**

**Threads:** at fully-clean, every **inline** review thread is resolved, and the only conversation left open is the final all-clear exchange --- the reviewer's all-clear comment and your reply to it. (The all-clear is usually a top-level PR comment, not an inline thread.)

**One finding can own two threads, so sweep by thread id rather than by
finding.**

**Deadlock -> escalate to a human.** If you and the reviewer(s) can't reach consensus on an item (a rebuttal was exchanged and neither side is budging), don't loop forever and don't unilaterally override the reviewer --- request a **human reviewer**, `@`-mention them in a comment summarizing the impasse, and surface the open item.

**An automated reviewer's verdict on a disputed factual/technical claim is not stable across independent runs, even with identical evidence available each time.** Don't treat one round's "settled, no need to keep arguing" as durable: the very same review job, re-triggered later with no new code changes, can re-raise a claim it previously retracted --- and then retract it again on a subsequent run --- purely from re-deriving the question differently each time, not from anything changing in the PR. This means a rebuttal thread's outcome (however many rounds of citations and counter-citations) doesn't itself resolve a genuine deadlock the way a human's decision does; only escalating per the bullet above actually settles it. The one thing that DOES help going forward: fold the authoritative citation/evidence directly into the code or doc being reviewed (a comment, not just a PR conversation reply) --- a fresh reviewer run re-deriving the claim from scratch is more likely to find the citation sitting right next to what it's evaluating than to dig through prior thread history for it, though even that is not a guarantee against a bot that ignores context already in front of it.
