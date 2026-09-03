Continuation of [`fully-clean.md`](fully-clean.md)'s criterion 2: the several
distinct ways a review job's check color, or the presence and content of a
posted comment, can diverge from whether a genuine, complete, correct verdict
actually exists on the PR --- the "eight numbered cases" that file's own text
points at. Split out per ai-config#1236, once this material pushed the parent
file past the size gate; moved verbatim, so an "above" or "below" inside this
file still means what it said before the split, except where noted.

Worked-example case records for the rules below live in
[`fully-clean.cases.md`](fully-clean.cases.md), moved out of the auto-loaded
context, same as `fully-clean.md`'s own.

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
comment's `created_at` inside the **review** step's own `started_at` and
`completed_at`.
A comment written while that step was running is a comment that run produced.
Comparing it against the guard step's `started_at` instead does not
discriminate, since the guard always runs after the review step in the same
job, so a stale comment from any earlier round clears that bar just as easily.

**That field reads `created_at` deliberately, and it used to read
`updated_at`, which is wrong in the one direction the bracket exists to
catch.**
Correcting it visibly rather than silently, since a reader who applied the
older wording got a false negative and has no other way to learn that.

The reusable workflow ends each review with a step named
`Collapse previous Claude review comments`, and its own source says the run
that wins the per-PR concurrency race must fold the earlier pushes' review
comments "or they linger".
So every round after the first **minimizes** every earlier round's verdict
comment, and `updated_at` advances to whenever the newest round finished.
Only the newest comment on a PR still satisfies a bracket keyed on it.
Every earlier one reports `updated_at` outside its own producing run and
reads as though no run produced it.

The mechanism is worth stating precisely, because it makes the warning
sharper rather than weaker.
That step's only mutation is the GraphQL `minimizeComment` mutation with
`classifier: OUTDATED`, which marks a comment collapsed and outdated.
It issues no REST `PATCH` and rewrites no text, so **nothing about the
comment's content changes at all** and `updated_at` still moves.
A reader who expected the timestamp to track edits has no surviving reason
to trust it: it advances on a bookkeeping action that leaves the body byte
for byte identical.
`created_at` is the only field the fold cannot touch.

Nothing in the comment's text reveals the fold, which follows from the
mutation rather than being a separate mercy.
It adds no `<details>` wrapper and no supersession note: measured on the
comment below, a `grep -cE '<details|<summary'` over the folded body returns
`0`.
Confirm the same from the API rather than from the rendered page, since
GraphQL exposes both halves of the claim on one object and REST exposes
neither.

The same drift defeats the cheaper check a reader reaches for first, comparing
a verdict comment's timestamp against a commit's.
An `updated_at` later than a push is **not** evidence the review saw that
push, because the fold that advanced it can postdate the push by any amount.

```bash
NODE=$(gh api repos/Morrison-Lab/ai-config/issues/comments/5227428537 \
  --jq '.node_id')
gh api graphql -f id="$NODE" -f query='query($id: ID!) {
  node(id: $id) { ... on IssueComment {
    isMinimized minimizedReason lastEditedAt createdAt updatedAt } } }'
gh api repos/Morrison-Lab/ai-config/actions/runs/31270501058/jobs \
  --jq '.jobs[] | select(.name == "review / claude-review")
        | {started_at, completed_at}'
```

Measured on `Morrison-Lab/ai-config#1299`, 2026-08-08.
Round 2's verdict comment reports `created_at 18:08:08Z` and
`updated_at 18:26:27Z`, against a producing job that ran `17:52:49Z` to
`18:08:14Z`.
`created_at` falls inside that window and matches the run's own
`Post review comment` step (`18:08:08Z` to `18:08:09Z`) exactly.
`updated_at` falls 18 minutes past the job's end, inside the round 3 run
(`31271746935`, `18:21:56Z` to `18:26:38Z`), two seconds after round 3 posted
its own verdict at `18:26:25Z`.
The two commits round 2 never saw, `a60d967f` and `d426bf83`, landed at
`18:10:48Z` and `18:11:44Z`, so they fall after that `created_at` and before
that `updated_at`: the two fields answer the did-it-see-this-push question
oppositely, and only `created_at` answers it correctly.
That same comment reports `isMinimized true`, `minimizedReason outdated`, and
`lastEditedAt null`, so its body was never edited at any point while
`updated_at` moved 18 minutes.
[`memories/claude-bot-workflows.md`](../../memories/claude-bot-workflows.md)'s
permissions-argument bullet cited the same pair as evidence and was narrowed
to `created_at` in the same change.

The step's source is `Morrison-Lab/gha`'s
`.github/workflows/claude-code-review.yml` at `origin/main`, where
`Collapse previous Claude review comments` begins on line 914 and its only
mutation is the `minimizeComment` call on line 941.
The one `PATCH` in that file, on line 975, belongs to a different step,
`Explain and fold tracking comment when canceled` on line 954, which runs only
`if: cancelled()` and prepends a warning to the **current** run's own tracking
comment.
It never touches an earlier round's verdict, so it is not the mechanism behind
the drift measured above.

- **Do:** read the PR's own comments before accepting that a failed review run
  produced no verdict.
- **Do:** read a guard's failure branch to learn whether its red is evidence
  about the artifact at all, rather than keeping "go look" as a habit to
  remember.
- **Do:** bracket a verdict comment's `created_at`, never its `updated_at`,
  inside the producing review step's window.
- **Do:** read an older review comment that renders as collapsed or outdated as
  expected housekeeping, rather than as a tampered or refreshed verdict.
- **Don't:** read a moved `updated_at` as evidence that anything in the comment
  changed; `minimizeComment` moves it while editing nothing.
- **Don't:** infer that a run produced nothing from a true report that it ended
  in an error.
- **Don't:** treat "the guard did not misfire" as establishing that its red is
  informative.
- **Don't:** compare a comment's `updated_at` against a push time to decide
  whether the review saw that push.
- **Don't:** conclude from an out-of-window `updated_at` that no run produced a
  comment; on any PR that reached a second round, that is true of every earlier
  comment.

**A third case, distinct from either misfire above: some checks are designed to NEVER fail regardless of their own posted content, so their green color carries zero signal at all.** A CI-runner-relative benchmark check that gates a soft threshold (e.g. "regressed beyond 20% vs. baseline") may deliberately report success/pass at the GitHub-check level even when it posts a `:warning:` regression comment, precisely because the project has decided that threshold is "a human call, not an auto-block" rather than a hard gate. `gh pr checks` (or the equivalent status API) showing this check as PASS is consequently not evidence there is nothing to look at --- it only means the check ran, not that its content was clean. Read the check's own posted comment body every time, the same discipline the review-job case above already demands, but don't expect the check's pass/fail conclusion to ever flip for this class of check even on a real, large regression.

**The third case has a variant whose green is not even about its own content: a check that reports only that a DISPATCH succeeded.**
The benchmark case above is a check that ran the work and declined to gate on what it found, so reading its posted comment recovers the signal.
A dispatcher runs no review at all.
It selects a reviewer and fires a second workflow, and its green says that call returned 200 --- whether the review then starts, fails, or posts a verdict is recorded in a different run, which by construction cannot colour this check.

That makes it worse than the benchmark case on the one axis that matters for a reader.
There the content is on the PR and merely ungated; here there is no content to read, and the check's own name usually says "review", so a status sweep that reports it green is reporting the truth about a step nobody cares about.
The absence is also the ordinary steady state rather than an anomaly, per [`pr-on-claim`](pr-on-claim.md)'s dispatch-only section --- so nothing about a green dispatcher and an empty comment list looks wrong.

The tell is in the workflow rather than in the check: a job whose last step is `gh workflow run` or an `actions_run_trigger` call has told you its conclusion is about the trigger.
Trace the dispatched run and read its verdict, per [`memories/claude-bot-workflows.md`](../../memories/claude-bot-workflows.md)'s "trace the whole dispatch chain" bullet, and take the verdict from the comment rather than from either check.

- **Do:** read a check's own workflow to see whether its final act is dispatching something else, before treating its green as a review result.
- **Don't:** count a green dispatcher toward criterion 2 --- it establishes that a reviewer was asked, which is the state [`pr-on-claim`](pr-on-claim.md) already says never discharges the review.

(`ucdavis/bcs`, 2026-08-13: `ai-review / select-and-review` read green on two PRs while the gemini run it had dispatched failed and no verdict existed on either.
Filed upstream as `ucdavis/bcs#619` and `#620`.)

**Second occurrence of this class, and a harder one: the dispatcher can itself report `skipped`, so even the trace-the-workflow discriminator above has nothing to follow into.**
The case above assumes the dispatcher ran and fired something, so tracing its workflow finds the run it fired.
A dispatcher gated by its own `if:` --- a trusted-sender check, a self-edit guard, a fork or draft exclusion --- can decide not to fire at all, and then it reports `skipped` rather than `success`, with no downstream run for anything to trace into.
That makes the review's own terminal checks --- `review / claude-review`, `require-review`, `require-clean-verdict`, or whatever names criterion 2's gate on a given repo --- not merely uninformative, they are **absent from the check-runs population entirely**, on a head where every check that did run is green.
`gh pr checks`, or any status sweep asking only "is anything red", reads that exactly like an ordinary benign skip.

That is a stronger version of the near-miss [`fully-clean.md`](fully-clean.md) names for an empty `check_runs` payload: there the whole population is empty, so the instrument refuses to score it.
Here the population is real, complete, and fully green, and the one member that would have said "reviewed" is simply not in it.
A question of the shape "are any checks failing" cannot see the difference, because absence and success answer it identically --- so the population itself, by name, is the only thing that discriminates them.

- **Do:** derive criterion 2 from the terminal review-gate checks' presence in the check-runs population, by name, on the exact head SHA --- not from the absence of red among whatever checks happen to be there.
- **Don't:** read a fully-green rollup as satisfying criterion 2 without confirming the review check is a *member* of it;
  a skipped dispatcher and a passed review both leave nothing red to notice.

(Second occurrence, `ucdavis/bcs`, 2026-09-03, and the measurement carries a time because the state did not survive being found.
Two populations, kept apart here because conflating them is how an earlier draft of this entry miscounted.
On the branch: zero `claude-code-review.yml` workflow runs, and two `ai-code-review.yml` runs, both `event: pull_request` and both `conclusion: skipped`.
On PR #891's head `e49d47a1d828a108a0aa01bdda7274b0ab5a05c5`: 31 check runs, and none of them `review / claude-review`, `require-review` or `require-clean-verdict`.
Three of those 31 concluded something other than `success` --- `ai-review` and `redaction-gate`, the skipped jobs of the dispatcher named above, and a `copilot-pull-request-reviewer` run that concluded `cancelled`.
None concluded `failure`, which is the point: a sweep asking whether anything is red gets "no" from a head that no reviewer had read.
The repair was to dispatch `ai-code-review.yml` by hand at 06:42:42 UTC, run `33724497297`, which is the deliberate override that workflow's own header documents.
It then selected and fired `claude-code-review.yml`, and that run produced the three missing checks, all of them clean by 06:46:20 UTC.
Note which workflow was dispatched by hand: the dispatcher, not the review workflow beneath it, which was bot-triggered as a consequence.
An earlier draft of this very paragraph named the wrong one, in an entry whose whole subject is telling a dispatcher apart from what it dispatches.
So a reader who queries the PR today finds those three checks green where this entry says none existed, which is the repair rather than a refutation.
Filed upstream as `ucdavis/bcs#897` at 06:43:14 UTC, half a minute after the dispatch rather than before it.)

**A fourth case: a review job can post a syntactically valid, confidently stated verdict that is nonetheless invalid because it rests on a hallucinated premise about the PR's own state --- not a stub (no verdict) and not a misfire (guard-script/check-conclusion mismatch), but a fabricated fact baked into an otherwise well-formed review.** A reviewer that infers PR state from a commit message rather than querying the PR's actual `state`/`merged` API fields can mistake a routine `Merge remote-tracking branch 'origin/main' into <PR-branch>` commit --- pushed to resolve a sync conflict on the still-open PR branch itself --- for evidence the *PR* was merged into `main`, and confidently report "PR is closed, no action taken" while never actually reviewing the diff. This reads exactly like a legitimate all-clear (a `### Verdict` section is present, the job reports success), so the stub-detection guards described in CLAUDE.md's "Do the review yourself when the @claude workflow doesn't produce a verdict" section don't catch it. Sanity-check any surprising verdict --- especially "nothing to review" or "already merged/closed" --- against the PR's real API state before trusting it, and re-trigger for a genuine review rather than accepting a verdict-shaped comment built on a false premise.

**The fourth case has a variant that hides better, because the false premise is not about the PR at all --- it is about which commits the round was reviewing.**
Sanity-checking a *surprising* verdict is the fourth case's remedy, and it cannot fire here: this verdict is the least surprising thing on the page, a clean re-approval of a round that changed almost nothing.

The false premise lives in the incremental section --- "What changed since the last review", or whatever the reviewer calls it.
Whatever produces that section, the range it names is a **claim** rather than a derivation you can check --- why the claim went wrong is not established, and this incident says nothing about the reviewer's internals.
A wrong one licenses a **shortened** round --- shortened in what it accounts for, which is all you can observe: naming one commit where the range holds two, quoting a `git diff --stat` that omits a source file, and concluding "no substantive logic changes" before returning Ready for merge.
The one behaviour change in the round is then unaccounted for, under a verdict that correctly names the current head.

No check in this repository catches it as of 2026-08-28 --- the range comparison below does, which is why it has to be run by hand.
[`fully-clean.md`](fully-clean.md)'s whole family of SHA checks is satisfied --- the verdict is dated, clean, and stamped with the head it reviewed --- and `scripts/check-pr-fully-clean.py` reported the PR fully clean, correctly by its own rules as of 2026-08-28.
The defect is in the verdict's account of *what it read*, which no SHA test can reach.
The section that exists to spare a re-review from re-reading everything is exactly the section whose error costs the most.

The check is mechanical and takes one command, so run it rather than judging:

```bash
git log --oneline <reviewed-in-previous-round>..<head>
git diff --stat <reviewed-in-previous-round> <head>
```

Compare that against the commits and files the review says it looked at.
A disagreement proves the account is wrong;
it does not establish what the reviewer read, since a summary can omit a file it inspected.
What it costs you is the ability to tell --- coverage becomes unproven rather than demonstrably short --- and an unproven range is not one to accept a clean verdict on.

- **Do:** derive the incremental range yourself and compare it against the review's own account, on every round after the first.
- **Do:** re-dispatch when they disagree, and say on the PR which commits the review did not account for.
- **Do:** send the unaccounted-for range to a *different* reviewer rather than re-running the one that shortened the round --- on 2026-08-28 a re-run against the unchanged head restated the same account and deferred to it, while a cross-vendor pass at that head returned the findings.
  [`self-review-fallback`](self-review-fallback.md)'s cross-vendor section is the standing rule;
  this is one more situation that calls for it.
- **Don't:** push a commit so the next round has a range it will accept --- that changes what gets reviewed instead of getting the unaccounted-for range reviewed.
- **Don't:** read a clean re-approval as covering the round --- an incremental round's coverage is bounded by the range it accounted for.
- **Don't:** reach for the fourth case's surprise test here.
  This verdict is unsurprising by construction, which is why it needs a mechanical check instead.

(Measured 2026-08-28 on [d-morrison/altdoc#125](https://github.com/d-morrison/altdoc/pull/125): the round named `118c22d9` as the only commit since `453a3252`, where `git log --oneline 453a325..118c22d` returns two and `git diff --stat` names `R/rd_source_files.R` alongside the test file the review quoted.
The unreviewed commit loosened two regexes in a parser.
Reported to the workflow's own repo as [Morrison-Lab/gha#709](https://github.com/Morrison-Lab/gha/issues/709), which weighs deriving the range in `gather-context` against treating a "nothing substantive changed" claim as requiring the full review anyway.)

**A fifth case, and the one that decides what "reachable" means in criterion 2 of [`fully-clean.md`](fully-clean.md): an external reviewer can decline to review at all, posting a refusal in the shape of a review.**
Unlike the four cases above --- all of which are a review that ran and produced something misleading --- this is a reviewer that never ran, and says so in a `COMMENTED` review whose whole body is the refusal (e.g. Copilot's *"unable to review this pull request because the user who requested the review has reached their quota limit"*).
Three consequences for driving a PR to fully clean:

- **A refusing reviewer is not "reachable,"** so criterion 2's external-verdict requirement falls to whichever external reviewer *is* working.
  Don't stall a PR waiting for a reviewer that is refusing --- but don't quietly downgrade to self-review either while another external reviewer is answering normally.
- **Reviewers fail independently.**
  One can be quota-dead while another reviews the same head normally, so check each one rather than generalizing from the first refusal.
- **Keep re-requesting each round anyway.** A quota resets on its own schedule, so a reviewer that refused a few pushes ago can come back mid-session --- which is exactly what criterion 2's "re-check availability right before declaring clean" is for.
  Say so explicitly when reporting a PR ready: name which reviewer's verdict the clean call rests on, and which one never weighed in at this head.

The mechanics of detecting a refusal (it arrives as a posted review, not an API error, so the request call's success proves nothing) are in [`memories/copilot-reviews.md`](../../memories/copilot-reviews.md).

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
in [`fully-clean.md`](fully-clean.md), and the run itself can be green with
no review behind it.

That second mode is the sharper one, and it is the newly evidenced one.
On #1008 `copilot-pull-request-reviewer` completed `success` while Copilot
posted no review on that PR at all.
On #1056 it completed `success` at head `cbf39b64`, while both of its actual
reviews sit at earlier commits, `252d8fb5` and `1e17d166`.
A green Copilot check therefore attests that the app ran, never that it
reviewed the current head --- which is exactly the inference a reader scanning
checks will draw from it.

Note which remedy already in [`fully-clean.md`](fully-clean.md) the silent
state defeats.
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
  That rollup omits it, per criterion 1 in [`fully-clean.md`](fully-clean.md).
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
That disagreement also vetoes merge, including under `mwc`.
ARD every item from every review, then request fresh reviews.
A later all-clear from a different reviewer does not supersede a standing
not-clean (ai-config#2274).

- **Do:** sweep a silent-since-earlier reviewer's prior findings against the current head before reporting clean, treating a stale-head or suppressed finding as live until checked.
- **Do:** ARD the union of findings, then request a fresh round, when reviews disagree.
- **Don't:** read one reviewer's clean verdict as evidence that a different reviewer's earlier backlog is empty.
- **Don't:** merge on that all-clear while another review still has standing findings, even with `mwc` active.

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
rather than from `status`, per criterion 1 in [`fully-clean.md`](fully-clean.md).

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

**The skip notice posted on the PR states that inference as prose, so the artifact hands you the diagnosis the section above tells you not to make.**
Everything above governs a reading *you* perform on the result object.
This is the same over-reading arriving pre-made, in a comment, under a `[!WARNING]` block:

> **Claude review skipped --- API credential or quota unavailable.**
> No `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` secret is configured, or account API quota is exhausted.

That sentence is the guard's **fallback wording for a failure class**, not a finding about this run.
It is emitted on an `is_error: true` execution failure that did no billable work, which is exactly the signature the section above establishes as necessary and not sufficient --- so the notice asserts, in words, the disjunction the numbers cannot support.

Measured on [ai-config#1841](https://github.com/Morrison-Lab/ai-config/pull/1841), 2026-08-21: the notice was posted five times while the secret **was** configured and passed into the workflow, at `total_cost_usd: 0`, `duration_ms: 249`, and `permission_denials_count: 0`.
Both of its named causes were unestablished, and the second was the one the reader is likeliest to act on, because a quota exhaustion is something you wait out.

The two wrong next actions are the ones the wording proposes: rotating a secret that is present, or opening the billing page.
Read the run's own `Run Claude Code Review` step instead, which is where an execution failure's actual error surfaces --- the guard prints its notice above that, on a branch that never asks.

- **Do:** read the failing run's `Run Claude Code Review` step before acting on a skip notice.
- **Do:** treat the notice as evidence that the run errored with no billable work, which is all its trigger condition establishes.
- **Don't:** rotate a credential or check billing on the notice's wording alone;
  on #1841 the secret was present and the account was not exhausted.
- **Don't:** read a notice repeated across pushes as corroboration --- it is one condition firing repeatedly, not several observations agreeing.

(Filed upstream as [Morrison-Lab/gha#561](https://github.com/Morrison-Lab/gha/issues/561), which proposes the notice distinguish its cases.
[ai-config#1048](https://github.com/Morrison-Lab/ai-config/issues/1048) tracks the repo-wide failure it was masking.)

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
[`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md)
already covers the more familiar workflow-validation case, a green skip on a
PR that edits the review workflow itself.
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
none of them --- and the run list therefore cannot say which PR any dispatched
run belongs to.
Counting adjacent rows there attributes other PRs' reviews to yours, and since
the group is keyed on the PR number, a run for another PR cannot have collided
with yours however close in time it sits.
Attribute each in-flight run from its own `gather-context` log instead:

```bash
jid=$(gh api "repos/<owner>/<repo>/actions/runs/<run-id>/jobs" \
  --jq '.jobs[] | select(.name=="gather-context") | .id')
gh api "repos/<owner>/<repo>/actions/jobs/$jid/logs" |
  grep -oE 'PR_NUMBER: [0-9]+' | head -1
```

[`memories/github-actions.md`](../../memories/github-actions.md)'s "A caller
with no `concurrency:` block can still have its runs cancelled" carries the
mechanism.
It generalizes past this one property, too: `permissions`, `timeout-minutes`,
and job-level `if` gates can equally be declared in a callee, so read the chain
rather than the caller whenever a workflow's behaviour is the question.
That file sits at exactly its 1200-line advisory threshold, which is why this
paragraph lives here rather than beside the section it extends; splitting it is
tracked in ai-config#811.

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

**The cheap version of that pre-check asks the PR instead of the runs, and it
is sound only when the dispatch attached the run to the PR.**
The check above is actor-indexed: it lists the review workflow's runs and then
has to attribute each one, which is the step `gh run list` cannot do and which
the `gather-context` walk buys back at two API calls per run, each needing the
job to have started.
Asking the artifact looks strictly better, because a check run attached to the
PR's head commit belongs to that PR by construction and needs no attribution at
all:

```bash
head=$(gh pr view <N> --repo <owner>/<repo> --json headRefOid --jq .headRefOid)
gh api --paginate "repos/<owner>/<repo>/commits/$head/check-runs?per_page=100" \
  --jq '.check_runs[] | "\(.status)/\(.conclusion // "-")  \(.name)"'
```

That reasoning is sound, and this file and
[`metacognitive-monitoring`](metacognitive-monitoring.md) both already
recommend the move --- go read the artifact, since the distinguishing fact is
on the PR rather than in the run data.
It carries a precondition none of those statements state, and this case fails
it: **an artifact-indexed query sees only actors that write to that index.**

A `workflow_dispatch` run invoked without `--ref` runs against the default
branch, so its `head_sha` is `main`'s tip and every check run it produces
attaches there --- never to the PR head, at any status, at any time.
The query above then returns the PR's own push-triggered checks and nothing
else, which reads as "no review in flight" and is what it returns whether or
not one is.
That is the dangerous direction: a vacuous all-clear on the one question the
pre-check exists to answer.
Reading check runs at the dispatch ref instead does not rescue it, since that
is where every PR's reviews pool, which is the attribution problem the
artifact-indexed query was reached for to escape.

The test that catches it is already written down, one direction over.
[`metacognitive-monitoring`](metacognitive-monitoring.md)'s "A retraction is
only as good as the instrument's reach" is aimed at withdrawing a true claim on
a null result, and its question is direction-neutral: could this check have
returned anything else, if the thing I am looking for were there?
Run it against a **completed** review you know belonged to the PR, and where
that review does not appear either, the null is silent rather than reassuring.

**`--ref` is what decides it.**
[`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md)
records that gha#286 root-caused exactly this and fixed it upstream by passing
`--ref <PR-branch>` explicitly, so a re-dispatched review's check runs do
attach to the PR's head commit.

Two paths reach that dispatch.
The manual command in [`ardi`](../../skills/ardi/SKILL.md)'s step 6 and
[`preferences.md`](../../memories/preferences.md) omitted `--ref` until this
entry was written, so the instrument was vacuous on the very command the
corpus told people to run --- the worst place for a precondition to go
unstated.
Both are fixed alongside this section, so an agent following either now
dispatches with the ref.
The mention-driven path gained `--ref` in #1000 (`claude.yml@v2`).

The mention-driven path was the residual when this section was written:
`claude-bot.yml` pinned `claude.yml@v1`, which omitted `--ref`.
Issue #1000 moved that pin to `@v2`, which passes `--ref "$BRANCH"` (gha#286),
so a human `@claude review` now lands on the PR head the same way a
manual dispatch does.
The measured table below is the pre-#1000 state.
Fork PRs still omit `--ref` (gha#289), because the head branch does not
exist in this repo.

Dispatch with the ref, and the one-call pre-check becomes available --- for
the runs you dispatch:

```bash
gh workflow run claude-review.yml --ref <PR-branch> -f pr_number=<N>
```

Some mechanical caveats before relying on it.
`--paginate` is load-bearing, for the reason criterion 1 in
[`fully-clean.md`](fully-clean.md) already gives about page-2 runs.
Read `status` before `conclusion`, since an in-flight run has no conclusion to
be misled by.
And the workflow file must exist on that ref, because it is the ref's copy that
runs --- so a PR editing `claude-review.yml` dispatches its own modified
version.

One further caveat decides how far the pre-check can be trusted, and this
passage's earlier paragraph already supplies it without drawing the
conclusion.
`--ref` is yours to pass, so it used to fix only the dispatches you control.
Until #1000, a human `@claude review again` routed through `claude.yml@v1`
and landed on the default branch, invisible at the PR head.
The pre-check was therefore sound against your own dispatches and silent
about a concurrent mention-driven one --- the worse half, because that run
is the one whose cancellation costs somebody else their review.
With the pin at `@v2`, mention-driven runs also pass `--ref` and appear at
the PR head.
Keep the `gather-context` attribution as well: the pre-check is still racy
(see below), and a fork PR still omits `--ref` (gha#289).

That residual is worth naming rather than filing away, since it is this
section's own subject recurring one level up: a check whose scope is narrower
than the claim made for it, with the shortfall on the side that reads as an
all-clear.

The pre-check is also **racy**, which is a separate limit from the scope one
above and is not fixed by widening what the check can see.
Checking and dispatching are two calls, so a run created between them is
invisible to a check that was correct when it ran.

That is not hypothetical.
Writing the paragraph above, the pre-check ran and returned three in-flight
runs, attributed to three other PRs.
Six seconds later a dispatch went out, and it cancelled a fourth run created
in between --- a mention-driven one, for this very PR, belonging to a human.
The listing had been right: that run did not exist yet when it was taken.

So a pre-check narrows the window and cannot close it, and no amount of
instrument quality changes that --- the gap is between the two calls rather
than inside either.
Two things follow.
Treat the pre-check as reducing the odds rather than as establishing safety,
and say which it did when reporting.
The mention path now carries a ref (#1000), so those runs are visible at the
PR head.
The remaining gap is the race between the two calls, plus fork PRs that still
omit `--ref` (gha#289).
A dispatch is still a small bet that nothing was created in the last few
seconds.

- **Do:** confirm the class of run you are looking for can appear at the PR
  head at all, before reading its absence there as an all-clear.
- **Do:** validate that with a completed run you know belonged to the PR, which
  is the positive control the null result needs.
- **Do:** pass `--ref <PR-branch>` when dispatching a PR-scoped review, which
  both supersedes the PR's own stale review check and makes the one-call
  pre-check sound **for the runs you dispatch**.
- **Don't:** substitute a check-runs query at the PR head for the
  `gather-context` attribution above while the dispatch omits `--ref` --- it
  answers a narrower question and answers it reassuringly.
- **Don't:** read your own `--ref` discipline as clearing the field for a
  fork PR, or for a mention-driven run from before #1000 --- those land on
  the default branch, and a colliding dispatch can still cancel them.
- **Don't:** report a pre-check as having established that nothing was in
  flight --- it establishes that nothing was in flight *when it ran*, and a
  dispatch is a later event.
- **Don't:** read "query the artifact, not the actors" as unconditional; it
  presupposes the actor writes to the index you are querying.

(`Morrison-Lab/ai-config#1281`, measured 2026-08-08 against the same five
dispatches tabulated above.
The PR's head is `edc9cb8c`, and all three of its review runs --- `31232187007`,
`31232771312`, and `31232853975`, the last of which succeeded and posted the
verdict --- report `head_sha: 27bbe9be`, which is `main`'s tip at dispatch time
(`hooks: warn when a branch switch and a later mutating git command are
unchained (#1274)`).
Every job on the successful run carries that same SHA.
`commits/edc9cb8c/check-runs` returns 6 check runs, of which 0 match
`review|claude` --- so the run that reviewed #1281 to completion never appeared
at #1281's head, which is the positive control the bullets above ask for.
`commits/27bbe9be/check-runs` holds 9 `review / claude-review` entries, 6
successful and 3 cancelled, pooled across several PRs.
The run object offers no attribution either: `pull_requests` is empty,
`head_branch` is `main`, and `display_title` is the workflow name.
This repo's `claude-bot.yml` pinned `claude.yml@v1` while `claude-review.yml`
pinned `claude-code-review.yml@v2`, so the gha#286 fix was present on one
leg of the chain and not the other. #1000 moved the agent pin to `@v2`.

The `--ref` half is measured rather than inherited, against the neighbouring
PR whose review happened to be dispatched with one:

| PR | head | dispatch | run's `head_sha` | review check runs at the PR head |
| --- | --- | --- | --- | --- |
| #1281 | `edc9cb8c` | no `--ref` | `27bbe9be`, `main`'s tip | 0 of 6 |
| #1285 | `fd02b494` | `--ref ums/reusable-workflow-concurrency` | `fd02b494`, the PR head | 3 of 10 |

Same repo, same workflow, adjacent PRs, one variable.
Run `31234176429` is the second row, and its `head_branch` reads
`ums/reusable-workflow-concurrency` rather than `main`, which is the one case
where `gh run list`'s branch column does attribute a dispatched run --- so
passing the ref repairs the actor-indexed view and the artifact-indexed one
together.)

**Whether to cancel a slow review turns on whether the head has moved, not on
how slow it is.**
Every entry above governs a run that has already **ended** --- errored,
stubbed, refused, or been cancelled by something else.
A run still in flight and simply taking a long time is a different decision,
and the difference is that nothing has gone wrong yet: no error, no missing
verdict, nothing to diagnose.
The only question is whether to keep waiting, and duration is the tempting
criterion for it.

Duration is the wrong criterion, and the right one is already written down.
[`fully-clean`](fully-clean.md)'s criterion 2 requires a verdict to sit at the
**current head**, so the question to ask is **whether the verdict would still
be usable if it arrived** --- which the head settles, and settles cheaply:

- **The head moved after the run started.**
  Its verdict cannot satisfy the current-head criterion whatever it says, so a
  fresh dispatch is owed regardless.
  Cancelling therefore forfeits only that run's findings, and waiting buys a
  verdict you would have to discard anyway.
- **The head has not moved.**
  A verdict that arrives is valid, so cancelling discards it outright and buys
  nothing but a second full review.

Note this is decidable rather than a matter of judgment: one read of the PR's
commit timestamps against the run's `run_started_at` answers it, which is what
a duration threshold can never be.

**Don't substitute a runtime baseline for that question, because the baseline
goes stale --- and a run past the old maximum is evidence of exactly that.**
The argument for a threshold is that a run far past this workflow's usual
runtime is probably stuck.
It is at least as likely that the usual runtime has changed, and nothing
distinguishes the two from the run in front of you.
Measured on one workflow in one repo, the successful runs preceding the first
long one ran a 3.0-to-19.4-minute spread; the same afternoon produced two
successful runs at 35.8 and 27.6 minutes, 1.8x and 1.4x that maximum.
Both would have failed any threshold drawn from the history available when
they started.

A **neighbours** check --- did runs starting just before and just after this
one complete normally --- is genuine evidence of a per-run anomaly, and is
worth running.
Treat it as suggestive rather than deciding, since a slow-but-healthy run has
fast neighbours too.

**Price the round before cancelling it, because a review is the most expensive
thing on the PR.**
[`efficient-pr-babysitting`](efficient-pr-babysitting.md) argues for batching
pushes on CI minutes and on the review-round race, and both are real.
The direct cost is larger than either: on the run measured below, one review
round billed **$42.92**, against **$5.91** for the confirming re-review of the
same PR --- a factor of 7.3.
So a cancellation taken to avoid waiting is not free, and the slowest run is
liable to be the one that costs most to repeat.

Why some runs ran long is **unexplained**, and is deliberately left that way
here.
Four durations with no tested hypothesis do not support a mechanism, and
naming one would license a threshold through the back door.

- **Do:** compare the PR's latest commit timestamp against the run's
  `run_started_at`, and let that decide whether to cancel.
- **Do:** cancel promptly once the head has moved, since that run's verdict is
  already unusable and a dispatch is owed either way.
- **Do:** read a run past the historical maximum as evidence the baseline may
  be stale, and say which of the two readings you acted on.
- **Don't:** cancel a run whose head has not moved --- a verdict that arrives
  is valid, and discarding it costs a full round.
- **Don't:** draw a duration threshold from this workflow's own history; two
  runs here cleared the prior maximum by 1.8x and completed successfully.
- **Don't:** report a neighbours check as having established that a run is
  stuck.

(`Morrison-Lab/ai-config`, measured 2026-08-12, two runs of `claude-review.yml`
about an hour apart, same repo and same workflow.

| PR | run | head during the run | duration | action | outcome |
| --- | --- | --- | --- | --- | --- |
| #1395 | `31603739873` | **moved**, `4c5d71e6` -> `b11fe4a9` at `14:10:50Z` | 43.6 min | cancelled | correct; its verdict was already unusable |
| #1407 | `31604997356` | stable at `205967ad` | 35.8 min | held | correct; completed with two real findings, both confirmed fixed |

The run on #1395 started at `13:52:47Z` against `4c5d71e6`, and commit
`b11fe4a9` landed 18 minutes later, so the run spent its second half reviewing a commit
that was no longer the head.
The in-flight note on #1407 reasoned partly from a baseline --- "a median of
7.0 and a max of 19.4 minutes" --- and reached the right answer for the better
stated reason beside it, that "this head has not moved, so a verdict that does
arrive is valid at the current head and cancelling would discard it".

Durations are `updated_at - run_started_at` over the workflow's last 30 runs,
which is an upper bound on completion rather than `completed_at`; on the
slow run it overshoots the verdict comment's own timestamp by 16 seconds.

```bash
gh api "repos/Morrison-Lab/ai-config/actions/workflows/claude-review.yml/runs?per_page=30" \
  --jq '.workflow_runs[] | select(.conclusion=="success")
        | "\(.run_started_at) \(((.updated_at|fromdateiso8601)
          - (.run_started_at|fromdateiso8601))/60|floor) min \(.head_branch)"'
```

Over the 13 successful runs preceding `31603739873` that returns min 3.0,
median 7.6, max 19.4 minutes.
The two that cleared it are `31604997356` at 35.8 and `31606598676` at 27.6,
both `success`.
That slow run had neighbours at 9.0 and 11.7 minutes, both successful, so a
neighbours check would have called it anomalous.
The two costs are read from the PR's own cost comments, `$42.9192` on
`31604997356` and `$5.9109` on `31608602196`.)

**A ninth case: a review can block on its own still-running check.**
The eight cases above all turn on what a reviewer said about the *code* --- or,
in the fifth and eighth, on its saying nothing at all.
The seventh is the nearest neighbour, since its detector also fires on text
outside the diff; it differs in that re-triggering cannot clear it.
This one is a verdict that describes the *PR's state*, correctly, from inside a
run that cannot see itself.

The shape is specific.
The review body reports no findings at all --- every claim fact-checked, every
citation resolved, nothing to flag --- and then the verdict line reads
**Blocked on human review** or similar, on the stated grounds that some
automated check has not finished.
That check is the review's own run.
A job cannot report its own completion from inside itself, so the reviewer sees
one perpetually in-progress entry, correctly declines to call the PR clean over
an unfinished check, and blocks.
The check goes green moments later, when the job it belongs to ends.

**Read the reason, not just the verdict word.**
A strict reading of [`fully-clean`](fully-clean.md)'s criterion 2 treats any
non-clean verdict as blocking, which is right wherever the verdict names a
finding and wrong here: the blocking premise expires by the time you can act on
it, so waiting for it to clear is waiting for something that already happened.
The discriminator is whether the verdict names a **finding** or names a
**pending check**.
A finding is about the diff and survives; a pending check that is the
reviewer's own run does not.

**That block still is not an approval, so do not merge on it.**
The remedy is another round, which is cheap when the head has not moved.
**Why a fresh run usually returns an ordinary verdict is not established, so do
not assert a mechanism for it.**
The structural property above applies to every run alike --- a second run's own
check is in progress while it reads, exactly as the first one's was --- so
"the next run sees the previous check completed" is not available as an
explanation, and the observed case does not test it either: the round that
cleared #1744 ran at a *moved* head, with its own check still in flight, and
returned a clean verdict anyway.
That points at the run-to-run instability [`fully-clean`](fully-clean.md)
already documents rather than at anything about check visibility.
Expect a re-run to usually clear it, and be prepared to spend another round
when it does not.
What makes that remedy fragile is head churn: a base-sync merge from a parallel
session moves the head, so a verdict earned at one commit is not a verdict at
the next, and a PR taking a sync every few minutes can invalidate verdicts
faster than a round completes.
Check the reviewed commit against the current head before spending a round, and
if they differ, expect to spend another.

- **Do:** classify a non-clean verdict by what it cites --- a finding about the
  diff, or a check that has not finished.
- **Do:** re-run when the only blocker was the reviewer's own in-flight check,
  and treat a second block as a reason to look further rather than to keep
  re-running.
- **Don't:** report a PR ready on a "blocked" verdict, however self-referential
  its reason.
- **Don't:** treat the block as a standing state to wait out; nothing further
  will happen to it on its own.

**The re-run remedy above did not always converge, so the reviewer's own
prompt now closes the loop at the source.**
Measured 2026-08-27/28 on ai-config#2472, #2313, and #2341: consecutive
re-runs each read the previous round's status-conditioned block (directly, or
through `check-pr-fully-clean.py`'s exit) and reproduced it, some over an
explicit statement that no content defect existed --- so the cheap-another-round
remedy can loop indefinitely rather than clear
([ai-config#2475](https://github.com/Morrison-Lab/ai-config/issues/2475)).
The fix is upstream of the reader: ai-config's `claude-review.yml`
prompt-addendum now carries a **Verdict semantics** section telling the
reviewer that the verdict judges content, that its own run's in-flight
sibling checks and the checker's mid-run exit are the merge gate's business
rather than the verdict's, and that a check that finished red or a real
finding still blocks.
Everything above stays true for the *reader* of a verdict: classify by what
it cites, and never merge on a block.
What changes is the expectation --- a status-conditioned block from a
reviewer running that addendum is now a misfire worth reporting, not a
correct round to wait out.

(Measured 2026-08-20 on
[ai-config#1744](https://github.com/Morrison-Lab/ai-config/pull/1744).
Attempt 6 at head `5ec9cf26` reported "found nothing to flag" and then
"**Blocked on human review** ... depends on that still-unresolved automated
check", which was `review / claude-review` --- its own job, green within the
minute.
The head then moved to `2d263683` on a base-sync before that verdict could be
used.
Attempt 7 at the new head returned **Ready for merge** with zero findings,
having re-verified every citation independently rather than inheriting the
prior round's conclusion.
The PR's content was identical across both, at 2 files and 39 insertions.)

**A verdict that writes out its own discharging condition is the same block, and
it is the form that gets merged on.**
The case above is stated over a **bare** block --- a verdict naming a pending
check and stopping there.
The commoner shape names the check *and* says what would clear it: "Once
`review / claude-review` completes green with no new findings, this PR meets
this repo's `fully-clean.md` bar", or "Whoever reads this next should query that
job's conclusion themselves rather than relying on any characterization here."

Read as an instruction, that is an invitation to finish the reviewer's sentence.
It is not one, and the distinction is worth stating because nothing about the
wording signals it.
A reviewer can hand off a **fact-check** --- go read the job's conclusion, which
is a question with one right answer.
It cannot hand off the **verdict**, because a verdict is a judgment it did not
reach, and the conditional is a prediction about what it *would* have concluded
rather than a conclusion.
Querying the job is the right action either way; treating your answer as the
reviewer's approval is the step that does not follow.

The near-miss is what makes this worth a rule rather than more care.
Discharging the condition **is** a real verification: you read the job's
`conclusion`, it is `success`, the reviewer's own stated bar is met, and you can
show your work.
So the merge arrives carrying evidence, and every check you naturally run
afterwards asks whether the *reasoning* was sound --- which it was.
None asks whether the question was already settled.

The cost of compliance is one re-run at an unmoved head, a few minutes.
The cost of skipping it is not reconstructible afterwards: the PR never received
an unconditional approval, so "merged clean" is false of it, and nothing in the
merged history says so.

- **Do:** re-run when a verdict states a condition you could discharge, exactly
  as for a bare block.
- **Do:** query the job's conclusion --- that part the reviewer really did hand
  off.
- **Don't:** read a stated discharging condition as a conditional approval; a
  reviewer cannot pre-authorize a verdict it never reached.
- **Don't:** treat "I verified the condition and showed my work" as closing the
  gap --- that is what the condition invites, and it is not what it grants.

(Measured 2026-08-21 on ai-config
[#1749](https://github.com/Morrison-Lab/ai-config/pull/1749) and
[#1791](https://github.com/Morrison-Lab/ai-config/pull/1791), merged this way
28 seconds apart at `131f1377` and `d0682800` ---
`07:12:00Z` and `07:12:28Z`, read from each PR's own `merged_at`.
Both verdicts read **Needs more work** and named the reviewer's own
`review / claude-review` job as the sole blocker;
both jobs had concluded `success` before the merge, verified from the check-runs
endpoint.
The session that merged them never consulted this section.
It recognized the shape, reasoned the case out from first principles, and
reproduced this case's own "Read the reason, not just the verdict word"
argument --- that the blocking premise expires before you can act on it.
That is the premise this fragment grants and then rejects.
Reaching the midpoint of a settled argument reads from the inside as having
thought it through.
Tracked as [#1827](https://github.com/Morrison-Lab/ai-config/issues/1827), where
the alternative reading --- that a stated condition amounts to a conditional
approval --- was considered and declined:
a rule that survives only until someone finds its own reasoning persuasive is
not doing any work.)
