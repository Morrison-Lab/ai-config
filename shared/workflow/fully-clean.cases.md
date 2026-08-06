# Case records: fully-clean

Worked-example case records for the rules in
[`fully-clean.md`](fully-clean.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A posted verdict doesn't mean the review check has finished

(ai-config#712, 2026-07-24: the round-2 verdict posted at `04:06`, about two minutes before its own `claude-review` job completed at `04:06:56` and `require-review` at `04:07:03`.)

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

## A review comment's header SHA can be stale

(Morrison-Lab/ai-config#957, 2026-07-31: the `Ready for merge` comment is
captioned "Review of `de72464`" while the run it links, `30614782680`, records
`head_sha: c8d5d8a` --- the PR's head at the time, since a `main` merge had
superseded `de72464` 64 seconds earlier.
Both facts came from `get_workflow_run`; the caption was never rewritten, and
the cancelled prior run `30614715159` is the one that actually ran at
`de72464`.)

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

(`UCD-SERG/serocalculator#392`, 2026-07-25; filed as [`d-morrison/gha#312`](https://github.com/d-morrison/gha/issues/312), which proposes unwrapping the pattern before posting.)

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
So the service was fine and the `d-morrison` credential was not, which no
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
`d-morrison/qwt` run 30391041128 (28s) reached the model and returned
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
