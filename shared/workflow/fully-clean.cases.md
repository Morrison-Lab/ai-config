# Case records: fully-clean

Worked-example case records for the rules in
[`fully-clean.md`](fully-clean.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A posted verdict doesn't mean the review check has finished

(ai-config#712, 2026-07-24: the round-2 verdict posted at `04:06`, about two minutes before its own `claude-review` job completed at `04:06:56` and `require-review` at `04:07:03`.)

## A routing job's own zero-cost error does not mean its dispatch step skipped

(Morrison-Lab/ai-config#1234, 2026-08-07: posting `@claude review` on this
repo triggers `claude.yml` in agent mode, not the dedicated review workflow
directly --- see `memories/claude-review-dispatch.md`'s note that this repo's
review has no push trigger.
Run `31140546175`'s own agent turn reported `is_error: true`, `num_turns: 1`,
`total_cost_usd: 0` --- the exact zero-cost signature this file's
credential-versus-quota section treats as ambiguous and worth investigating before
trusting.
The same job kept going anyway: its log shows an unconditional shell step
--- `Dispatching claude-review.yml for PR #1234 (@claude review comment)` ---
that fires on a pattern match against the triggering comment, independent of
whether the agent turn above it succeeded.
That dispatch (`workflow_dispatch` run `31140580678`) completed normally about
11 minutes later and posted a genuine, thorough "Ready for merge" verdict.
So a zero-cost `is_error: true` on `claude.yml`'s **agent-mode** run --- as
opposed to `claude-code-review.yml`'s own `claude-review` job --- is not
evidence the review pipeline failed.
Check for a `claude-review.yml` `workflow_dispatch` run triggered around the
same time before treating the routing job's own error as a credential or
quota problem needing a fix.)

## The check-run name collision

(`ucdavis/bcs#458`, 2026-07-29: a check-in found the three jobs it was
   watching all green and would have called the PR clean, except the count had
   gone from 17 to 20 --- `update-snapshots` had finished and spawned a
   cross-platform R CMD check matrix.
   Two of those three were still running, and one was a *second* check run
   named `ubuntu-latest (release)`, alongside the original that had succeeded
   14 minutes earlier.)

## "`status` itself can be stale" --- duration from log timestamps

(`d-morrison/altdoc#96`, 2026-07-30: `claude-review` had failed six times
   in ~26 seconds each, the signature of the model call failing at auth.
   A re-run was polled twice, three minutes apart, and read `in_progress`
   both times --- reported as "the reviewer has recovered", and acted on by
   firing a second re-run on the sibling PR.
   The log showed that job starting at `04:05:25` and cleaning up at
   `04:05:51`: 26 seconds, identical to the other six.)

## A 404 on the job-log fetch means not-yet-completed, not hung

(`Morrison-Lab/ai-config#1187`, 2026-08-06, a review dispatched by an `@claude review` mention: the `review / claude-review` job `92487132786` in run `31060459989` was checked at ~`00:55Z` with `status: in_progress`, `conclusion: null`, and `gh api .../jobs/92487132786/logs` returning `BlobNotFound` / 404.
   This was reported --- wrongly --- as a hang with "no verdict produced," and an issue was nearly filed against `Morrison-Lab/gha` on that false premise.
   The job in fact completed `success` at `00:57:00Z` after a legitimate ~16-minute review that started `00:41:00Z`, posting a real `**Claude finished review**` verdict ("Needs minor changes", cost $15.07) at `00:56:55Z`.
   The 404 had meant "still running"; every check before ~`00:57Z` was premature, and the job's own `timeout-minutes` was 60, so it was nowhere near timing out either.)

## Checker unhandled exception on wrong repo

Run from a checkout of the wrong repository,
`check-pr-fully-clean.py` raises `RuntimeError: Command failed (gh pr view ...)` and exits 1.
Paired checking of finding bullets (`grep -q '^  - '`) confirms whether exit code 1 represents genuine review findings or an unhandled exception.
Passing `-R OWNER/REPO` explicitly avoids relying on the current working directory.

## "`gh pr checks` is not a complete enumeration" --- the rollup gap

(`Morrison-Lab/ai-config#1056`, merged as `e1875ff7`, at head
   `cbf39b6452e33188524f3f8a233ba1a9190906ad`.
   On 2026-08-02 `gh pr checks 1056` returned 10 contexts and reported 0
   pending, while `commits/<sha>/check-runs` returned 11 --- the extra one
   being `copilot-pull-request-reviewer` at `status: in_progress`.
   Re-measured 2026-08-03, once every run had settled: `gh pr checks` still
   returns 10 and the endpoint returns 13, so the disagreement outlives the
   in-flight run that first exposed it.
   The three the rollup drops are `copilot-pull-request-reviewer`, plus one of
   the two check runs named `build / build` and one of the two named
   `claude / claude`.
   It keeps both copies of `validate` and both of
   `new-line-breaks / check-new-line-breaks` on the same head, so it is not
   collapsing duplicate names either.
   All 13 report `app.slug: github-actions`, so no app-level filter selects
   that subset, and every run had `status: completed` at the second
   measurement, so no in-progress filter does either.
   That is what disqualifies the candidate mechanisms above without supplying
   a replacement for them.)

## The rollup gap dropping a FAILING run, and the rule failing at composition time

The case above measured the disagreement on runs that were merely extra or in-flight.
This one is the consequential version: the run the rollup dropped had `conclusion: failure`.

`ucdavis/bcs#651` at `a5f4f3f2`, 2026-08-19.
`gh pr checks` printed 21 rows, every one `pass`, with nothing pending.
`commits/<sha>/check-runs?per_page=100` returned **24** runs, one of them:

```text
failure   review / antigravity-review
```

The PR was reported fully clean and ready to merge on the strength of the shorter list.
`check-pr-fully-clean.py` caught it on the next turn, exiting 1 with a single finding naming that run.

Two things make this worth a second case record rather than a line appended to the first.

**The omission is invisible by construction.**
A short list and a clean list are the same observable.
There is no gap in the output, no warning, and the counts look healthy --- 21 pass, 0 pending reads exactly like a finished head.
Nothing about the reading announces that it could not see everything.

**The prose rule already existed and was read the same session.**
The rule directly above this one had been loaded into context, and the reporting error happened anyway, on a check whose failures had been *watched* three times earlier in that same session.
Having seen the check red, the author reported a green count that did not contain it and did not notice the absence.

That is the pattern [`deterministic-tools`](../principles/deterministic-tools.md) describes:
a rule is consulted at read time and broken at composition time,
so re-reading it does not reach the moment it breaks.
The remedy was the hook `hooks/no-incomplete-check-enumeration.py`,
which fires on the decidable condition ---
a terminal clean claim,
a partial reading (`gh pr checks` or `statusCheckRollup`),
and no complete enumeration since the last push.

- **Do:** take a fully-clean verdict from `check-pr-fully-clean.py`.
  A paginated `commits/<sha>/check-runs` read covers the check-run half only
  (progress reports / criterion 1); it does not authorize a terminal claim.
- **Don't:** report a PR clean from `gh pr checks` counts,
  however current the reading is ---
  currency and completeness are different properties,
  and only one of them has a hook watching it.
- **Don't:** treat GraphQL `statusCheckRollup` as enough for a terminal claim either
  (ai-config#2277, 2026-08-26:
  a "Ready for merge" claim rested on the rollup;
  the rollup matched the endpoint 8==8;
  `check-pr-fully-clean.py` exited 1 for missing automated review;
  the hook now matches both partial surfaces).

## Criterion 2's verdict-vs-findings disagreement rate, measured

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

## A reviewer's own verification block can be wrong

(Morrison-Lab/ai-config#957 round 2, 2026-07-31: `claude-review` returned
**Ready for merge** with no findings, above a table partitioning the same 38
comments as 24 passes + 10 blocking + 4 unclear.
That sums, and the composition is wrong: the sample is 24 passes and 14
non-passes, with the four counted-out comments sitting inside those groups
(three passes, one non-pass) rather than beside them.
It balanced only because the four were subtracted from the wrong group.
Nothing in the diff was false, but "Four further comments" read as a disjoint
third bucket, which is how a careful reader reached the wrong partition.)

## A clean verdict ratifying an unverified enumeration

(Morrison-Lab/ai-config#1137, 2026-08-04: a `memories/tools.md` entry asserted
"The two `<(...)` uses already in this corpus were checked and are safe".
The corpus held three files, the third being
`references/cloud-setup/cloud-setup.sh:118`'s `done < <(grep -rlE ...)` redirect
--- safe for the same reason, so the conclusion held and only the scope was
false.
`claude-review` returned **Ready for merge** with no findings, listing among the
things it had verified "the accuracy of the two cited `<(...)` corpus usages",
and writing that "the two `<(...)` usages audited in the PR body ... are
correctly described as safe --- neither feeds a pipe".
Both statements are true of the two files they name.
Run `30886075254` started `07:00:24Z` against head `1c688889`, where that third
file was already present, so it was reachable throughout.
Nothing shipped: the author derived the set independently and pushed the
correction as `2229655d` at `07:05:28Z`, about ninety seconds before that
verdict posted at `07:06:55Z`.
So the only thing that caught it was `git grep -n '<(' -- ':!memories/'`, which
the entry now carries in place of the count.
Round 2 derived the set itself and confirmed the correction; the PR merged as
`bea50421`.)

## "What 'an approving review' means" --- Ready for merge over unresolved nits

(Morrison-Lab/ai-config#900, 2026-07-30: the verdict read "**Ready for merge.**
No hallucinations, fabricated references, or factual errors found", immediately
above a "Findings (all nits, non-blocking)" section naming three inline
comments and closing "None of these affect correctness or usability of the
guidance".
All three threads were unresolved at that point, so the PR failed both halves of
criterion 2 while carrying a verdict line that read like a pass.)

## The review check passing on a blocking verdict

(Morrison-Lab/ai-config#921, ucdavis/bcs#477, ucdavis/bcs#473, all 2026-07-30,
within hours of each other.
On #921 every mechanical check passed --- all CI green, zero unresolved
threads, verdict line reading "Ready for merge" --- and the PR was reported
clean twice while carrying an open out-of-diff finding.
On #477 the review body was empty and the finding was inline-only.
On #473 `claude-review` failed after its built-in retry, posting nothing at
all, so there was no body to read past and zero threads because zero
comments.)

## The review-gate case (ucdavis/bcs#468)

(The review-gate case, ucdavis/bcs#468, same night.
`require-review` passed, `claude-review` passed, all 18 checks were green,
and there were zero inline comments and zero threads --- while the verdict
read "Needs more work" over a blocking finding that the new section's own
safety rule was false on one code path.
The review's own closing line said as much, noting that because no
`--comment` argument was passed, it had not posted the findings to the PR.
Every count-based check called that PR ready.)

## The collapsed-block case (Morrison-Lab/ai-config#1029)

(The collapsed-block case,
Morrison-Lab/ai-config#1029,
2026-08-02.
From review round 3 onward,
Copilot's overview repeatedly read "generated no new comments"
and produced zero inline comment objects,
while the full review body carried severe findings under `Suppressed comments (N)`.
Round 7 posted at 2026-08-02T06:29:10Z,
about two minutes before the PR merged at 06:30:55Z,
and those real findings had to be carried forward to #1034.)

The heading moves across PRs:
PR #660 emitted `Comments suppressed due to low confidence (3)`,
while PRs #1029 and #1031 emitted `Suppressed comments (4)`.
A literal match for either phrase can return a false zero.
Matching case-insensitively on `suppressed` strictly inside `<summary>` headings prevents false positives against overview prose
(such as review 4837572117 whose summary table mentioned "suppressed Copilot findings" in uncollapsed text).

## A review comment's header SHA can be stale

(Morrison-Lab/ai-config#957, 2026-07-31: the `Ready for merge` comment is
captioned "Review of `de72464`" while the run it links, `30614782680`, records
`head_sha: c8d5d8a` --- the PR's head at the time, since a `main` merge had
superseded `de72464` 64 seconds earlier.
Both facts came from `get_workflow_run`; the caption was never rewritten, and
the cancelled prior run `30614715159` is the one that actually ran at
`de72464`.)

## A `workflow_dispatch` run's `head_sha` names the dispatch ref, not the reviewed commit

(Morrison-Lab/ai-config#1251, 2026-08-07: a `claude-review.yml` run dispatched
at 18:02:03Z reported `head_sha: 7d050a36...`, `main`'s tip at that moment, on
an `event: workflow_dispatch` run for PR #1251.
Its verdict claimed a specific wording fix was "unchanged in the current
diff," which `grep`ing the live file disproved --- the fix had landed in a
push before the verdict posted, sometime inside the run's own 18:02-18:08
execution window.
A second dispatch, triggered directly via `actions_run_trigger` rather than
by re-posting an `@claude` mention (which risks re-triggering the
credit-gated `claude-bot.yml` ack step on its own `contains(body, '@claude')`
gate), produced a genuine current-head verdict.)

## Re-check version parity, not only conflict-freedom

(`UCD-SERG/serocalculator#392`, 2026-07-25: the final pre-declaration check
found `main` had reached `1.4.1.9016`, exactly the branch's version, minutes
after a clean `Ready for merge` verdict on an otherwise all-green head.)

## One finding can own two threads

(`d-morrison/altdoc#61`, 2026-07-25: the round-4 re-raise of an unused fixture
parameter opened `PRRT_...TyfeQ` alongside the original `PRRT_...TyeRc`;
resolving the original left the re-raise outstanding, caught only by a
mechanical sweep of all seven threads.)

## A reviewer's verdict is not stable across independent runs

(Sparta#852, 2026-07-14: the same `@claude` review job's independent runs on this PR gave three different verdicts on the identical `gitglossary(7)`-backed pathspec claim across three re-triggers with no intervening code change to the claim itself --- "settled, accurate" -> "backwards, needs more work" -> "accurate after all, retracting my own prior finding" --- resolved only once the human merged it directly rather than by winning the argument with the bot.)

## A review job's pass/fail conclusion diverging from the posted verdict

(Learned on sparta#590/#594/#598, 2026-07-02: two independent PRs hit the inverse misfire in the same session, and an attempt to merge past the required check on verified-clean content was correctly blocked by the harness's own permission system.)

## The `is_error` guard failing without misfiring

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

## A benchmark check designed to never fail

(Sparta#995/#998/#999, 2026-07-19: `gh pr checks` reported `benchmark` as PASS across three separate PRs while the actual posted comment showed regressions of 45%, 38.8%, and 36.9% respectively against the CI-runner baseline --- two were real, fixable redundant-computation bugs; the third traced to a stale baseline that predated an earlier PR's own accepted cost increase and hadn't been refreshed yet, since the refresh workflow only runs on a weekly schedule, not on every main push.)

## A hallucinated "PR is closed" premise

(gha#293/gha#295, 2026-07-24: after a merge-conflict-resolution push, the re-triggered `claude-code-review` run reported "The PR is closed --- it was merged as commit `db11634`" even though the PR was still open and `db11634` was only the PR branch's own merge-with-main commit; re-triggering once more produced a genuine review of the actual diff.)

## A reviewer refusing to review at all, for quota

(`ucdavis/rampp#111`, 2026-07-24/25: Copilot refused three times across two heads for quota while `claude-review` posted genuine verdicts at both; the PR was reported clean --- and merged --- on `claude-review`'s verdict, with Copilot's absence stated in the ready-for-merge comment rather than papered over.)

## The silent-reviewer state --- green check, no review posted

(`Morrison-Lab/ai-config`#1005 and #1008, 2026-07-31/08-01, both merged.
On #1005 `copilot-pull-request-reviewer[bot]` posted its quota refusal as a `COMMENTED` review at `23:59:46Z`, which is the refusal above exactly.
Under five hours later on #1008 it posted nothing at all.
`get_reviews` returned eight reviews there, four from the repo's own review bot and four from the maintainer, none from Copilot, with page 2 confirmed empty.
Neither PR's check **rollup** carries a Copilot-attributable context.
Re-measured 2026-08-03,
`gh pr checks` returns 8 contexts for #1005 and 9 for #1008,
and filtering either for a name matching `opilot` returns **0**.
Every other check on both heads was green,
so no signal short of the login-filtered review-list query
distinguished a reviewer that had approved from one that never spoke.
The commit check-runs endpoint disagrees with that rollup on both PRs,
returning 9 and 11 respectively,
the extra entries including one `copilot-pull-request-reviewer` run apiece.
Two figures in the paragraph above have since been corrected,
and the correction runs opposite to the one this record previously carried.
An earlier revision claimed Copilot's own check run
completed `success` at `04:50:41Z` on #1008,
a later revision retracted that as an invented particular,
and the retraction was the wrong one:
check run `91327863807` on `7abfed6b` is named `copilot-pull-request-reviewer`
and reads `completed_at: 2026-08-01T04:50:41Z`, `conclusion: success`.
It is worth leaving the whole chain visible rather than quietly deleting it,
because the retraction was produced by exactly the gap
criterion 1 now documents ---
a query against a surface that omits the check run,
read as establishing that the check run does not exist.
The record's other figure moved too:
the #1008 rollup count was written as 10 and re-measures at 9,
and why was not determined.)

## Sweep a silent reviewer's earlier findings before declaring clean

(Morrison-Lab/ai-config#1042, 2026-08-03: at head `8ac62ce` the counting reviewer (`claude-review`) returned "Ready for merge" with no findings, and `require-review` was green --- the PR read done.
A sweep of Copilot's earlier reviews (its last was several commits back, its findings in a suppressed block) surfaced two still-live in-scope items: a dangerous draft-clear silent-discharge and a README hook-catalog omission.
Both were fixed in `8b6eaf1`; neither had ever been flagged by the counting reviewer.)

## The reviewer posting its own tool invocation instead of the review body

(`UCD-SERG/serocalculator#392`, 2026-07-25;
filed as [`Morrison-Lab/gha#312`](https://github.com/Morrison-Lab/gha/issues/312), which proposes unwrapping the pattern before posting.)

## A false-positive injection-detector block that reproduces every round

(Morrison-Lab/ai-config#818, 2026-07-29: Jules returned `VERDICT: block` for
"prompt injection attempt in diff" on a new `shared/coding/` fragment's
`## In review` section, then repeated it verbatim at the next head without
engaging the rebuttal.
Eight of the eighteen existing fragments carry an identically-worded section.
`claude-review` returned Ready for merge at the same head.
The maintainer's call was to hold; the PR merged with `jules/review` red.)

## Read the log rather than the error message

(Morrison-Lab/ai-config#835, 2026-07-30: `jules/review` failed with a 404 on
`GET /v1alpha/sessions/<id>/activities`, reported as
"Check `JULES_API_KEY` is valid".
The log showed the key creating that session and confirming it *ready* 0.2s
earlier, so the 404 was a propagation race on the sub-resource, not auth ---
an invalid key fails at creation with 401/403.
Jules had already approved twice on the same key that session, and
`rerun_failed_jobs` with no code change returned `approve`.)

## A failure that names its own session id

(Morrison-Lab/gha#374, 2026-07-30: `jules/review` reported "Jules did not
return a review", with the 15-minute timeout and session
`4236561570323034536` in its own comment.
A review fix was already staged, so the push carried the re-trigger, and
Jules returned `VERDICT: approve` on the new head about four minutes later.)

## The cross-repo test that localizes a durable credential failure

(d-morrison/altdoc#95 / altdoc#96, 2026-07-30: `claude-review` failed seven
times across those two PRs -- six on #96, one on #95 -- each run finishing in
the 26-to-35-second band, with `is_error: true`, `total_cost_usd: 0`, and no
permission denials.
The nearest pair is 38 seconds apart: the run on altdoc#95 failed
`04:07:37Z -> 04:08:12Z`, and the same reviewer returned a full
`Ready for merge` verdict on Morrison-Lab/ai-config#858 over
`04:08:50Z -> 04:11:41Z`.
So the service was fine and the `the repository owner` credential was not, which no
number of re-runs would have shown.
Tracked in d-morrison/altdoc#99.)

## The zero-cost signature is necessary, not sufficient, for "quota"

(Morrison-Lab/wai#35, 2026-08-04: `claude-review` run `30960909084`
(`23:42:53Z -> 23:43:27Z`) returned `is_error: true`, `duration_ms: 372`,
`num_turns: 1`, `total_cost_usd: 0`, `permission_denials_count: 0`.
GitHub auth was fine, the log reading `App token successfully obtained` and
`Actor has write access: admin`.
A push retried it as run `30961183056` (`23:47:46Z -> 23:48:35Z`), matching on
every field the guard reads, at `duration_ms: 506`.
Morrison-Lab/ai-config's own `claude-review` runs created `23:43:21Z` and
`23:50:32Z` both succeeded, straddling the wai failure.
That was read at the time as ruling out the service **and** the account's
quota, which is the over-reading this entry is about: the two repos'
`CLAUDE_CODE_OAUTH_TOKEN` secrets were last written `2026-07-29T18:31:12Z` and
`2026-08-03T01:19:40Z` respectively, five days apart, so they are exactly the
"several sittings" case the docstring above says cannot be untangled.
Whether they were one account was, and remains, unknowable.

What actually settled it was the before/after on wai alone.
The secret was rewritten at `2026-08-05T00:05:40Z`, and the next
`claude-review` runs --- `30962961775` and `30962961774` at `00:20:21Z`, then
`30963459374` at `00:29:50Z` --- all succeeded, with nothing else changed.
The stale timestamp was the triage signal that said which repo to rewrite; the
run afterwards is the evidence.
Copilot **was** genuinely quota-limited throughout, on both repos, and said so
in words, which is the coincidence that made the quota reading feel confirmed.
Filed as Morrison-Lab/wai#36, a recurrence of wai#27.)

## A failed attempt is not the whole `run_id`'s final word

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

## Duration signature read backwards --- three unrelated bugs filed as one

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
`Morrison-Lab/qwt` run 30391041128 (28s) reached the model and returned
`is_error:true` after a workflow-modification denial.
Only the first was about permissions at all.)

## A scope-widening admission on symptom alone

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

## A stale branch failing workflow validation before the reviewer runs

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
PR #994 was 24 commits behind and would have hit the same block if rerun then, but
its existing 5m26s `is_error: true`, `subtype: "success"`,
`permission_denials_count: null` stub ran an hour before #998 merged, so it was
a different bug; merge first, then retry.)

## `num_turns` as the stopping rule for an expensive stub

(Morrison-Lab/ai-config#973, 2026-08-05: `claude-review` failed on heads
`ed5cd8d` and `cf824cc`.
Run `30645784194` **attempt 1** took `630325ms` and `$5.77`; run `30647021192`
**attempt 1** took `545700ms` and `$4.78` --- a 13% spread on duration and 17%
on cost.
The second run has only that one attempt, so its bare id resolves correctly
today; it is labelled anyway, because the first run's did too until someone
re-ran it.
Neither workflow set `max_turns` --- checked at the pinned
`Morrison-Lab/gha` sha `8ad0b14f` that produced both runs, and in the calling
workflow --- so 11 is a path, not a ceiling.
Both reported `num_turns: 11`, `is_error: true` with `subtype: "success"`,
`permission_denials_count: null`, exit 1, and no verdict posted.
Cite the attempt, per the `run_attempt` section above: that run's attempt 2
was cancelled after 73s for a higher-priority request, and a bare run id
resolves to the latest attempt, so an unqualified link lands on a `cancelled`
state that contradicts everything in this paragraph.
The PR touched `memories/`, where at that head `debugging.md` was 1115 lines,
`github.md` 1080, `github-actions.md` 865, and `r-quarto.md` 730.
A third run was declined on the matching turn count rather than attempted, so
the determinism is the observation and context exhaustion is the untested
hypothesis.
One datum since, from the PR that added this entry: a 62-line diff touching
only `shared/` drew a `claude-review` that ran `629s` and posted a full
verdict, at `$7.43`.
Same duration band, more spend, and it finished --- which rules out a budget
or wall-clock ceiling and leaves what the diff makes the reviewer read as the
live candidate.)

## A cancelled review can be the casualty of someone else's dispatch

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

## `pull_requests[].head.sha` named a commit pushed after the run started

(Morrison-Lab/ai-config#1384, 2026-08-10, merged as `edfab8d8`.
Review run
[31354330266](https://github.com/Morrison-Lab/ai-config/actions/runs/31354330266)
was a `workflow_dispatch` at `a0ef37c2`, started `04:03:25Z`.
Commit `7fe25776` was authored `04:05:18Z`, after the run began, and became the
PR's head.
The run's `pull_requests[0].head.sha` was reported during the session as
`7fe25776` --- the newer commit --- while its `head_sha` correctly read
`a0ef37c2`.

The body settled it.
That review's verification section quotes the prose figure as "40 to 151
seconds", which exists only at the older commit:

```bash
git show a0ef37c2:memories/claude-code-scheduling.md | grep -n '40 to 151'
#=> 189:`run_once_at + 24h` the same rows are off by 40 to 151 seconds, tracking each
git show 7fe25776:memories/claude-code-scheduling.md | sed -n '189p'
#=> `run_once_at + 24h` the same 18 rows spread from 0.6 to 556 seconds over.
```

Timing would also have caught this one, per the block above, since the run
predates the commit.
What the field added was **positive evidence pointing the other way**, which is
why it needed its own entry: it made "the verdict may already cover current
content" a live hypothesis rather than an idle one.

The specific reading is **not reproducible now**, because #1384 has merged and
the array empties on close --- all three of its review runs return
`pull_requests: []` today.
The general behaviour is reproducible, and was measured over the 60 most recent
runs in this repo on 2026-08-10:

```bash
curl -sS "https://api.github.com/repos/Morrison-Lab/ai-config/actions/runs?per_page=60" \
  > runs.json
python3 -c "
import json, urllib.request
runs = json.load(open('runs.json'))['workflow_runs']
cur = {}
def head(n):
    if n not in cur:
        u = f'https://api.github.com/repos/Morrison-Lab/ai-config/pulls/{n}'
        cur[n] = json.load(urllib.request.urlopen(u))['head']['sha']
    return cur[n]
ne = [r for r in runs if (r.get('pull_requests') or [])]
agree = sum(1 for r in ne if r['pull_requests'][0]['head']['sha'] == head(r['pull_requests'][0]['number']))
stale = sum(1 for r in ne if r['head_sha'] != r['pull_requests'][0]['head']['sha'])
print(f'examined {len(runs)}; non-empty {len(ne)}; field==current head {agree}; run head_sha differs {stale}')
"
#=> examined 60; non-empty 14; field==current head 14; run head_sha differs 8
```

So the field equalled the PR's current head in **14 of 14** cases, and in **8
of those 14** the run's own `head_sha` was a different commit.
The sharpest single instance is PR #1374, open at the time.
Eight of its runs span four distinct `head_sha` values (`8e7a2526`,
`af838843`, `158d311d`, `d1d02a19`), and every one of the eight reports
`d1d02a19` --- the PR's head at read time --- as its `pull_requests[0].head.sha`.

One limit on that measurement, stated rather than smoothed over.
The instrument is validated in both directions, since 14 of 60 runs returned a
non-empty array --- so an empty read is informative rather than a broken query.
But every `workflow_dispatch` run in that sample returned empty (10 of 10), and
none of them sat on a currently-open PR's branch, so the sample by itself could
not separate "dispatch runs never populate the array" from "the array empties
once the PR closes".
The branch-level split already favoured the second: branches whose PRs are open
returned non-empty in every case, and branches whose PRs had merged returned
empty in every case.

That ambiguity is now settled, by a counterexample this entry's own PR
produced.
`Morrison-Lab/ai-config#1388`'s review dispatch, run
[31357711790](https://github.com/Morrison-Lab/ai-config/actions/runs/31357711790),
is a `workflow_dispatch` on an **open** PR's branch, and it returns a
**non-empty** array:

```bash
curl -sS "https://api.github.com/repos/Morrison-Lab/ai-config/actions/runs/31357711790" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['event'], r['head_branch'], r['head_sha'][:8], [(p['number'], p['head']['sha'][:8]) for p in r['pull_requests']])"
#=> workflow_dispatch ums/pr1384-pull-requests-head-sha ede6b0a9 [(1388, '5bed1d61')]
```

That output is **read at 2026-08-10, when #1388's head was `5bed1d61`**, and
the second SHA is expected to differ on any later run.
`head_sha` is fixed at `ede6b0a9` for the life of the run; the array's entry
tracks the PR, so re-running the command reports whatever that PR's head is at
read time.
Read a mismatch between the two as the normal case rather than as a discrepancy
to reconcile.

So "dispatch runs never populate the array" is false, and the emptiness the
sample recorded is explained by PR **closure** rather than by trigger type.
One counterexample is enough here, because the hypothesis it refutes was a
universal.

The same run is a **second case record for the entry's own thesis**, and it
arrived by falsifying a sentence this file previously carried.
That sentence said the run was dispatched with `--ref` at the PR branch, so its
`head_sha` and the field agreed, and it therefore could not also illustrate the
two diverging.
Both halves were wrong.
`--ref` pins `head_sha` and does nothing to the other field, which re-resolves
on every read, so the agreement was never a guarantee --- only a fact about
dispatch time, before any further push.
Pushing the very commit that recorded the sentence is what separated them, and
the output above is the corrected reading.

What the run then shows is the field's usefulness **inverting** while its
behaviour stays constant.
On #1384 it pointed at a commit newer than the one reviewed, which made a
superseded verdict look current --- the confident direction, and the reason
this entry exists.
Here it points at a commit newer than the one whose `require-review` went red,
which correctly says the PR has moved past that commit and the red check is a
`cancelled` run at a superseded head.
Neither reading is wrong, because the field reports the PR's current head in
both.
What differs is the question being asked of it, which is the entry's thesis
stated twice rather than once.

The transferable lesson is one artifact further in than the PR-body staleness
that
[`address-every-comment`](address-every-comment.md) documents.
A sentence asserting that two **live** fields agree is a state claim with a
short shelf life, and where that sentence is written into a commit, the commit
is itself the event that can falsify it.
So a claim of agreement needs the time it was true at, or it needs to be a
claim about mechanism instead --- and mechanism is what to reach for, since
`--ref` supports a claim about `head_sha` alone.

- **Do:** date a claim that two live fields agree, or state the mechanism that
  makes one of them stable, rather than asserting the agreement flatly.
- **Don't:** infer from `--ref` that `pull_requests[].head.sha` is pinned; it
  pins `head_sha`, and the other field re-resolves on every read.)

## Poll a job's step list, not its check-run status

(`Morrison-Lab/gha#440`, 2026-08-09: a review check run read `in_progress`
for roughly ten minutes after its job had finished every step, "Post review
comment" included, so the verdict sat on the PR unread for that whole
stretch.
Twenty-one consecutive polls of the check run returned `in_progress`; one
read of the job's step list showed `Complete job` already `completed`.)

## A later comment stating no verdict does not supersede an earlier one

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

## Both criteria are per-PR, and a stack is where that stops being automatic

(`ucdavis/bcs`, 2026-08-13: two stacked PRs were reviewed 82 seconds apart, `16:26:16Z` on the stacked PR and `16:27:38Z` on its base.
The base's verdict was read, a Copilot quota refusal was seen on the stacked PR, and the pair was reported as one verdict plus one refusal.
The stacked PR's own review had posted and sat unread for 12 hours; the next round re-raised both of its findings and noted the file was byte-identical across the three intervening commits.)

## Two agents, one head, opposite verdicts

(`ucdavis/bcs#632`, 2026-08-16.
A one-file `NEWS.md` deduplication, reviewed by two agents at the same commit
`3fd3089e`, minutes apart:

| time (UTC) | agent | verdict |
| --- | --- | --- |
| 01:37:51 | Antigravity | positive, opening with `Encountered an internal error in running grep command.` |
| 01:52:23 | Antigravity | `The changes are clean, accurate, and completely satisfy the PR requirements. **LGTM.**` |
| 01:56:22 | Claude | `**Needs more work** --- one verified factual-accuracy issue` |

The finding Claude raised was real and checkable, not a matter of taste.
The PR's own `NEWS.md` bullet asserted that a form the removed changelog copy
documented was "not one the code accepts", and the code accepts it:
`data-raw/slurm-validation.R:35` rebinds the constant to that method's scalar
before use, `:51` passes that scalar on, and `R/slurm_seeds_for_chunk.R:9`
documents the parameter as a scalar.
All three lines were verified against source before the finding was accepted.

Two things make the case worth keeping.

The defect was **an inaccurate claim in a PR whose entire purpose was fixing an
inaccurate claim**, so a reviewer reading for factual accuracy is exactly what
it needed --- and the agent that approved it had just said its own grep failed.
That is the same shape recorded at `ucdavis/bcs#622`, where an Antigravity
review approved a report whose grep had errored, which is why the rule treats
it as recurring rather than as one bad run.

And nothing on the PR page distinguished the two.
Both agents post as `github-actions[bot]`, both produced a summary with
analysis and a positive closing line, and the review-gate check was green
throughout.
Only reading the bodies separates them.

The fix landed in `8cf34dce` and Claude's next round at that head returned
`Ready for merge`, having re-verified both cited source facts itself.)

Merging on Antigravity's LGTM while Claude's `Needs more work` still stood
is forbidden either way: the standing not-clean vetoes merge, `mwc` included.
On this PR the not-clean was last, so the old global-latest scan already
failed it.
The #2274 hole is the reverse order --- an earlier not-clean, then a later
all-clear from a different reviewer --- which that scan missed.
ARD the union, then request fresh reviews.
`check-pr-fully-clean.py` now fails that per-reviewer split too.

## Three PRs reported clean by grepping the checker's own output

(`Morrison-Lab/ai-config` #1561 / #1566 / #1575, 2026-08-16.
A background monitor polled all three with the right instrument and decided
what it said with a string match:

```bash
out=$(python3 scripts/check-pr-fully-clean.py "$n" 2>&1)
if echo "$out" | grep -q 'NOT fully clean'; then allclean=0
else echo "ai-config#$n is FULLY CLEAN"; fi
```

It announced all three clean, twice, and none of them was.
Run directly, the checker reported:

| PR | actual state |
| --- | --- |
| #1561 | verdict was at the pre-sync head |
| #1566 | `Latest verdict-bearing review statement ... is NOT clean` |
| #1575 | `No automated review comments or reviews found` |

The case that settles it as a defect rather than noise is #1566: a **blocking**
finding, reported to a human as clean.
And #1575 had **zero** verdict comments and was reported clean, which is the
`else`-branch failure at its plainest --- nothing to match, so the match
failed, so the branch fired.

Two details worth keeping.

The bypass guard could not fire.
`no-handrolled-verdict-parse.py` blocks matching a verdict phrase against a
PR's *review comments* when the checker has not answered, and here the checker
had answered --- the monitor called it correctly, on the right PR, every time.
The defect was entirely in reading the reply.

And the session that wrote the monitor had, minutes earlier, committed a rule
that final approval comes from Claude at the current head, and a hook whose
purpose is catching unverified claims about state.
Neither reached the monitor, because both govern what you *assert* and this was
a fault in what you *measured*.)

## The same conflation in the fix: `rc != 0` reported three clean PRs as regressed

(`Morrison-Lab/ai-config` #1561 / #1566 / #1575, 2026-08-16, roughly an hour
after the case above and in the same session.

The grep was replaced with a status read, and the status was read as a boolean:

```bash
python3 scripts/check-pr-fully-clean.py "$n" >/dev/null 2>&1 \
  || echo "REGRESSED: ai-config#$n no longer clean"
```

That fired on all three, twice.
All three were clean at the time and clean afterwards, verified by running the
checker directly.

The contract it discarded is three-valued, and measured rather than assumed:

| invocation | exit |
| --- | ---: |
| a clean PR | 0 |
| a not-clean PR | 1 |
| no argument (usage error) | 2 |

`scripts/check-pr-fully-clean.py:47-51` says why the third exists: `raise
SystemExit("message")` would exit 1, "which is this script's 'not clean' code
--- so a usage or environment error would have been read as a verdict about the
PR.
The exit code is set explicitly for that reason."
So the script anticipated exactly this conflation and provided the code needed
to avoid it, and the consumer collapsed it anyway.

Two things make the pair worth recording together rather than folding into one
entry.

The **direction inverted**.
The grep failed toward clean and hid a blocking finding; the boolean status
fails toward alarm and manufactures regressions.
A reader who takes only "read the exit status" from the first case lands
directly in the second.

And the second bug was introduced **by the fix for the first**, in the same
session, by someone who had just written the entry above.
That is what argues the remedy has to name all three codes rather than
contrast "status" with "prose": the contrast is what made a two-branch reading
feel like compliance.

**Correction, measured after the above was written: the `rc != 0` reading was
not the whole of it, and the transient-failure diagnosis was wrong.**
The non-zero was **deterministic**, and it was `1` rather than `2`.
The poller ran from the session's cwd --- a checkout of a *different*
repository --- and `check-pr-fully-clean.py` resolves the repo from the working
directory unless `-R/--repo` is given, so every poll asked the wrong repo about
these PR numbers:

```
RuntimeError: Command failed (gh pr view 1561 --repo ucdavis/bcs ...):
GraphQL: Could not resolve to a PullRequest with the number of 1561.
```

Measured three ways, same PR, same moment:

| invocation | exit | result |
| --- | ---: | --- |
| from the other repo's cwd, no `-R` | 1 | traceback |
| from the other repo's cwd, `-R Morrison-Lab/ai-config` | 0 | FULLY CLEAN |
| from the ai-config cwd | 0 | FULLY CLEAN |

Three things follow, and each corrects something stated above or nearby.

`USAGE_EXIT = 2` covers the paths `die()` handles.
An **unhandled exception exits 1**, so a crash is indistinguishable from a
verdict by status alone --- which means the three-way read this entry
prescribes is necessary and not sufficient.

The `rc >= 2` branch written to catch "the check failed" was therefore
**unreachable for the failure it was written for**.

And the belief that sent the poller there was stale rather than absent: a
memory note read "hard-codes `Morrison-Lab/ai-config`, ignores `-R`", which
`1c052457` ("resolve the repo instead of hardcoding it", #1462) had already
retired.
The script's own docstring says `-R` works.
So this is [`fail-fast`](../principles/fail-fast.md)'s "A sound checker pointed
at the wrong repository": a correct instrument returning a truthful answer about a
repository nobody asked about, with the subject never printed alongside the
verdict.)

## A green guard step beside a red job

(Morrison-Lab/gha#520 / #521, 2026-08-19.)

`d-morrison/rme#1072`'s `review / claude-review` check was red.
The cause was in the run's result object rather than in the PR.
Abridged below --- it also carried `terminal_reason: "api_error"` and `permission_denials_count: 42`.

```json
{
  "subtype": "success",
  "is_error": true,
  "num_turns": 13,
  "total_cost_usd": 4.100043149999999,
  "api_error_status": 429,
  "result": "You've hit your weekly limit"
}
```

The account's quota ran out 13 turns into the review.
The workflow already had a graceful path for quota exhaustion, and the guard script did not recognize this shape, because its detection keyed on `total_cost_usd: 0` plus `num_turns: 1` --- a request rejected before any work, not one cut off part-way through.

Fixing that alone would have left the check red, which the fix's own PR then demonstrated on itself.
With the guard hitting its **pre-existing** zero-cost branch, the log read:

```
##[warning]Claude review skipped -- quota or auth error (zero cost, turn 1).
##[end-action id=fail-check.run;outcome=success;conclusion=success]
```

and the job was red anyway, because a step above it had already failed:

```
##[error]Action failed with error: Claude execution failed: result is_error:true
##[end-action id=claude-review.run;outcome=failure;conclusion=failure]
```

The action exits 1 on an `is_error` result, and that step carried no `continue-on-error`, so its failure decided the job whatever the guard concluded afterwards --- making the graceful path unreachable for every exhaustion that got past the workflow's own `preflight-quota` step, which catches a missing credential before dispatch but cannot see an account that still had quota then.

Two things generalize.
The guard's `success` and the job's `failure` were never in tension.
They were two different steps' conclusions, and only a step enumeration distinguishes them.
And the first diagnosis was right about the classifier and still incomplete about the symptom: the shape genuinely was unrecognized, and recognizing it changed nothing the reader could see until the propagation was fixed too.

## A fragment's by-hand parsing advice mistaken for the script's own mechanism

(Morrison-Lab/ai-config#1690, 2026-08-20: on Morrison-Lab/ai-config#1687, a
round-2 review posted a **Ready for merge** verdict under a doubled heading,
`### ### Verdict`.
`check-pr-fully-clean.py` scored the PR not-clean, and the filed issue
asserted the doubled heading had broken the script's "anchor on the last
`### Verdict` heading" logic --- quoting this file's own by-hand parsing
advice as if it described the script.

It does not.
`grep -n "Verdict" scripts/check-pr-fully-clean.py` shows the script matches
verdict phrases with a regex, never a heading line, so nothing about a
doubled `###` prefix was in a position to break anything it checks.
The claim was falsified within the hour: round 3 on the same PR posted the
identical doubled heading and scored CLEAN.
What actually triggered the not-clean read was the plain quoted-phrase false
positive this file already documents elsewhere --- the round-2 comment's own
body quoted the *previous* round's "Needs more work" verdict while stating
its own "Ready for merge" one, and the phrase match picked up the quote.

The issue was retitled and the diagnosis retracted in a follow-up comment,
which is what surfaced the gap this case exists to close: this file's
by-hand guidance sits directly beside its description of the script, with
nothing marking the boundary between them.)

## A skip notice exits the checker clean over an empty verdict scan

(Morrison-Lab/ai-config#1841, 2026-08-21, head `158a82f2`.
Reproduced live rather than reasoned about:

```
$ python3 scripts/check-pr-fully-clean.py 1841 -R Morrison-Lab/ai-config
  verdict scan: examined 6 dated automated review item(s), 0 bore a verdict, latest = NONE
✓ Found clean review comment evaluating HEAD SHA 158a82f2
✅ Morrison-Lab/ai-config#1841 is FULLY CLEAN on HEAD 158a82f2!
$ echo $?
0
```

No reviewer had produced a verdict on that PR at any head.
The PR carried seven comments: five identical 363-character `claude-review` skip notices from `github-actions`, and two from `the repository owner` at 4226 and 4804 characters.
The notice reads "**Claude review skipped --- API credential or quota unavailable.**" followed by a `View run` link, and it is that link the checker resolves --- the run's `head_sha` equals HEAD, so a comment stating explicitly that no review happened is admitted as a review evaluating HEAD.
It carries none of `finding_patterns`, so the HEAD-matching half prints its tick, and `check_latest_verdict()` returns `True` because an empty verdict is not `not-clean`.

Six items rather than seven is the second finding, and it names which loop admits what.
Matching the comment loop's marker tuple against each body shows five admitted on author and exactly one on body text: the 4804-character `the repository owner` comment, whose first line is

```
## ARD --- cross-vendor review (Codex / GPT-5.1, `### Verdict: Needs more work`)
```

so it matched both `### verdict` and `verdict:`.
The 4226-character self-review matched no marker and was never admitted.
Neither human comment contains `158a82f2` or its 7-character prefix, so neither reached `matching_items`.
The admitted one bore no verdict because its verdict phrase sits inside a code span that `strip_cited_finding_vocab` blanks before `classify_verdict()` reads it, while `is_review_header` had matched the raw body.

The prior claim that only bot authors are admitted came from reading the formal-review loop --- which does consult `_is_bot_author` alone, for the reason its own in-code comment gives --- and generalizing it one loop up.
Tracked as ai-config#1719, which gained the skip-notice trigger the same day, and ai-config#1798.)

## A driver-comment classifier drops a Copilot finding it has no guard for

(Morrison-Lab/ai-config#2409 / #2429 / #2430, 2026-08-27.
`check-pr-fully-clean.py`'s verdict scan, on branch `fix/2409-driver-comments`, added a driver-ledger classifier so that a driving session's own status comments --- claim wording, an ARD disposition table, a self-imposed hold like "Do not merge.
Blocked on review of `<sha>`" --- would stop being admitted as standing reviewer verdicts, per #2409.
The classifier matches broad English markers (`hold off`, `back off`, a markdown table row carrying `Disposition`) and then abstains from excluding a comment when the comment also carries one of three NEGATIVE guards: a `### Verdict` heading, a `Reviewed-Commit:` fingerprint, or a `**Claude finished` marker.

Every one of those three guards is keyed on Claude's or Cursor's own report format.
A Copilot review comment carrying a real, blocking finding phrased as "hold off on merging until the null check is added" emits none of that structure -- Copilot's report has no `### Verdict` heading, no `Reviewed-Commit:` line, and no `**Claude finished` marker.
So the broad `hold off` marker matches, all three guards abstain, the comment is classified as a driver's own ledger, and it is dropped from the verdict scan before `classify_verdict()` ever sees it.
The PR reports FULLY CLEAN with a genuine not-clean finding sitting unexamined on the thread.

Reproduced by executing the classifier logic against `origin/main` directly (not read, not reasoned about): with the driver-ledger exclusion bypassed, the same Copilot comment correctly vetoes the PR.
With it active, the comment is dropped and the checker exits 0.

The general shape is [`fail-fast`](../principles/fail-fast.md)'s "Guarding an unsound pattern with a second pattern, rather than replacing it" and "A guard's discharge fires on positive success, not the absence of failure" sections, arrived at independently inside this one checker: negative guards defending an over-broad matcher inherit exactly the ambiguity the matcher already had, and they inherit it silently, because nobody tests a guard the way they eyeball a matcher's positive output.
Inverting the gate was the obvious next move, and it was tried and refuted within hours.
The candidate positive signature was the agent-disclosure marker, on the premise that every driver comment carries it per [`disclose-agent-authorship`](disclose-agent-authorship.md) and no reviewer report emits it.
Neither half survives: that fragment exempts a comment posted under a genuine bot identity, so even the first half is a convention rather than a guarantee.
Only the first half holds.
[`self-review-fallback`](self-review-fallback.md) requires a dispatched or cross-vendor review to be published verbatim WITH the marker appended, so a genuine not-clean review carries it as well, and a marker gate dropped that review exactly as the negative guards dropped Copilot's.
Both designs failed for one reason: every discriminator available in a comment body is one some real reviewer also emits, so no body-shape test can safely decide to DROP an item.

A third design was then built and refuted in turn, which is what settles the shape of the answer.
Executing `classify_verdict` over the #2341 comment's parts showed that neither the `Disposition` table nor the "Do not merge. Blocked on review of `<sha>`" hold produces a verdict at all --- the sole not-clean signal was the header's parenthetical citation of the round being disposed of, "Addressed GitHub Claude of `9508454e` (Needs more work)".
Both earlier classifiers had therefore been built to detect the parts that never mattered.
So the third design stopped dropping anything and instead blanked that citation inside `strip_cited_finding_vocab`, gated on the sentence opening with an ARD disposition verb AND the parenthetical holding nothing but the verdict phrase.
An adversarial round refuted it too: it blanked the live verdict in "Addressed the null-check nit in `9508454e` (Needs more work): the fix introduced a new NoneType dereference at foo.py:42", where the parenthetical IS this comment's verdict and the explanation sits outside the blanked span.

**Nothing shipped in the checker.**
All three designs were reverted, and `scripts/check-pr-fully-clean.py` is unchanged.
What shipped is a convention in [`ard`](../../skills/ard/SKILL.md)'s summary-comment step: a disposition comment backticks any verdict phrase it quotes, so the code-span rule #1202 already established neutralizes it.
That adds no new fail-open surface to the instrument at all, and when an author forgets, the PR reads not-clean --- the recoverable direction, on their own PR.
The guard that would catch a forgotten backtick at authoring time is #2443.

A second, smaller finding rode along: the driver-ledger classifier's own guard-test fixtures were hand-written from what each guard reads, and both omitted the disclosure marker that the two REAL driver comments the fix was built from (GitHub comment ids 5430672892 and 5430978306 on ai-config#2341) both carry.
Once a positive marker gate is added, a "this guard alone protects this fixture" test built that way passes through the new gate instead of through the guard it was named for, which is [`fixtures-are-not-evidence`](fixtures-are-not-evidence.md)'s "A regression fixture must contain something the bug would destroy" section one layer further in: the fixture is not too thin to reach the *bug*, it is too thin to reach the *guard*.
A per-guard neutering/mutation harness --- disabling one guard branch at a time and confirming at least one test fails specifically because that branch is gone --- is what surfaces which test protects which guard, per [`algorithmatize-checks`](algorithmatize-checks.md)'s mutation-outcome catalogue.

Neither finding was fixed in THIS session --- `scripts/check-pr-fully-clean.py` and its test file were owned by another session on `fix/2409-driver-comments` at the time, so both were filed as #2430.
That session then fixed both, which is where the refutations above and the shipped convention come from.
This documentation pass is tracked as #2429.)

## A review wake carried one finding out of five

(`Morrison-Lab/gha#571`, 2026-08-21/22.
The round-3 review posted **five** inline findings within about two minutes.
The first wake carried one of them, and a `get_review_comments` fetch made
seconds later returned four.
The fifth arrived on its own wake roughly two minutes after that, once the
first four had already been read, fixed, and their threads resolved.

So the count was wrong twice in the same round, in both directions: acting on
the wake alone would have missed four, and treating the first fetch as
complete would have missed the fifth.
Only the second fetch, made when a later wake arrived, produced the whole set.

The four that the wake did not carry were not minor.
One was a genuine bug in the diff --- an unanchored `*"$RUN_URL"*` substring
match, where a run id can be a numeric prefix of another
(`.../runs/325256962` inside `.../runs/3252569628`), so a failure comment
about a different run could decide this one.
Another caught a changelog fragment claiming a fix the PR explicitly did not
ship.

The general shape is the one this file's list already teaches for GitHub's own
surfaces, arriving through the delivery channel instead: a count you did not
derive is not a count.
Re-fetch on every wake, and treat a later wake as evidence that the earlier
fetch was incomplete rather than as a duplicate.)

## A `check_suite.completed` wake at a superseded head

(`ucdavis/bcs#732`, measured 2026-08-23.
Two wakes arrived reporting that no check suite was still running.
Each was true of a population that was not the one the session needed.

The first named suite head `4176bd5`.
That commit's own `R-CMD-check.yaml` run, `32613062007`, was cancelled at 02:40:52Z, ten seconds after the successor run `32613455542` was created against the new head `ab40071`.
That successor did not conclude until 03:20:15Z.
So the wake reported on a commit the PR had already left, while the live head's `R CMD check` still had most of forty minutes to run.

The second wake named the live head, and still arrived inside that window.

What the wake's body says about its own scope is not reproduced here, because it lives only in that session's transcript and no later reader can check it.
What is checkable is the pair of fields above: the event's `head_sha`, and a check-runs read on the PR's actual head.
Compare the first, then run the second.)

## A poller exited on an empty check list

Measured 2026-08-26 on
[wai#120](https://github.com/Morrison-Lab/wai/pull/120).

A background poller watching the PR head reported:

```
wai#120 CHECKS COMPLETE after 30s
--- reviews ---
0
```

with no conclusion lines between the two headings, because the check-runs
list was empty.
The terminal condition was:

```bash
pend=$(gh api ".../check-runs" --jq '[.check_runs[]|select(.status!="completed")]|length')
if [ "$pend" = "0" ]; then   # true before any check exists
```

Workflow runs for that head were created at `22:06:42Z`.
The poller had exited at about `22:03:30Z`.
It had been armed immediately after `git push`, while the PR was still a
draft, and the checks were created by the later `ready_for_review`
transition --- so it ran entirely inside a window where the head legitimately
carried zero checks, and read that as completion.

The corrected form asserts the population and prints what it examined:

```bash
[ "${total:-0}" -ge "$EXPECTED_MIN" ] && [ "$pend" = "0" ]
```

Re-armed that way, the same head reported its real state.

The corrected poller then exposed a second hole in the same loop.
Its per-tick trace was:

```
t=150s total=13 pending=1
t=180s total=13 pending=1
t=210s total=16 pending=2
t=240s total=17 pending=2
t=270s total=18 pending=1
```

The population is not fixed.
It grew from 13 to 18 while the poll ran, as later workflows registered their
checks.
A non-empty-population guard therefore rules out the empty case and nothing
else: had `pending` reached 0 at `t=180s`, the loop would have exited
satisfied, with 13 checks examined and five not yet created.

The guard that closes it is repetition rather than a larger threshold ---
zero pending **and** an unchanged total across two consecutive polls.
Printing the total each tick is what made the growth visible; a loop that
reports only its exit condition cannot show it.

