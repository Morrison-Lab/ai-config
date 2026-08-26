When a PR you're managing has its `@claude` review workflow fail to produce a usable verdict --- whether because it was **skipped for quota** or because it **ran to completion but never stated a verdict** (a "stub review") --- don't stall the ARDI loop waiting for it --- **do the review yourself and post it** as a PR comment.
Apply the same review standards the bot would (the SERG lab manual and the repository owner's modular/idiomatic priorities), then keep iterating to fully-clean on your own findings.
Neither failure mode is an approval --- an unreviewed PR stays unreviewed regardless of why the bot didn't weigh in.

**Never write the bot's at-mention in that comment.**
The gate is a raw substring test, so backticks and descriptive framing leave it live; say `claude-review` or "the Claude reviewer".
See [`memories/mention-triggers.md`](../../memories/mention-triggers.md).

**Quota-skipped:** surfaces as a bot comment --- either `Claude review skipped --- API quota exhausted` (the review workflow) or `You've hit your org's monthly spend limit` (the agent workflow).
Both mean no bot will respond on this run; re-running the workflow only helps once the quota actually resets.

**Stub review:** the review job reports success (`is_error: false`, real cost/turns logged) but the posted comment never states a `### Verdict` --- the run genuinely executed but got cut short before reaching a conclusion (e.g. by escalating permission denials on tool calls it needed).
This looks superficially fine (green check, a comment exists) so it's easy to mistake for a real review --- read the comment body for an actual verdict section before trusting it.
Re-running the same workflow can reproduce the same stub pattern repeatedly rather than self-resolving;
if a retry doesn't help within a round or two, treat it as this failure mode and self-review rather than continuing to re-trigger.

**No review workflow configured at all is a third failure mode, and the one nothing signals on its own.**
Quota-skipped and a stub review both require a review workflow to exist and attempt to run.
Some repos have none: no `@claude` job wired into CI at all, so there is nothing to time out, quota-skip, or stub.
CI stays green because it never ran anything meant to notice, and the PR/MR simply accrues zero review comments.

Check for this once per repo, right after the first push, rather than waiting to notice its absence: grep the repo's own CI config for the review job or template it would come from (a GitHub Actions workflow file, or a GitLab `.gitlab-ci.yml`'s `include:` list) rather than assuming a sibling or template repo's setup carried over.
Treat "not configured" the same as the other two failure modes: self-review immediately, held to the same fact-check rigor "A fallback self-review is prone to being shallow, so hold it to the same bar as the bot it stands in for" requires (fact-check-prose, the cause check, the cited-source rule).
Because a genuine config gap is a standing property of the repo rather than a one-off outage, also file a tracking issue on it per [`report-mistakes-proactively`](report-mistakes-proactively.md) --- wiring up review coverage is worth fixing, not just working around on every push.

**Post the self-review before doing anything else --- don't stall the PR waiting for the bot.
Then, before writing the check off as permanently broken, try one manual re-run of the failed job --- even after the workflow's own built-in same-run retry (e.g. gha#185's stub-retry) also stubbed.**
Two stubs back to back is a stronger signal than one, but it's still not conclusive: a separately-triggered re-run (`rerun_failed_jobs` via the GitHub Actions API/MCP tool, not just re-reading the same run) is an independent LLM invocation, and the failure modes behind stubs (permission-denial spirals, timing) don't always repeat.
If the check is a **required** one, spend the one manual re-run before reporting the workflow as broken for that PR.

**High-denial stub (gha#198): the denial count gates the automatic retry, not the job's outcome, so it is a label rather than a prognosis.**
A run whose parsed `permission_denials_count` exceeds `max_denials` (default 5) is classified as gha#198's pattern rather than gha#185's, and the workflow declines to mark it retryable.
That decides only whether the run retries *itself*, in the same invocation.
It says nothing about whether the manual re-run above will recover.

Measured on 2026-08-20, both far above the threshold and in opposite directions: [job 96505024829](https://github.com/Morrison-Lab/ai-config/actions/runs/32391984929/job/96505024829) on [ai-config#1689](https://github.com/Morrison-Lab/ai-config/pull/1689) completed and posted a real verdict at `permission_denials_count=72`, while [ai-config#1767](https://github.com/Morrison-Lab/ai-config/pull/1767) produced no verdict twice, at 12 and then 24.
Take such a figure from the job's own log rather than from the PR's comment history, which records 55 for a different attempt on that same PR --- the count is per attempt, so a PR-level number names no particular run.
So a high count is not evidence that the reviewer has given up on this PR, and the one manual re-run stays worth spending.

What the count cannot tell you is *which* tools were denied, and the log does not name them.
The execution-transcript artifact does, so download it rather than guessing --- [`memories/claude-bot-workflows.md`](../../memories/claude-bot-workflows.md) carries the route, and it works today, independent of [gha#540](https://github.com/Morrison-Lab/gha/issues/540).
What gha#540 would add is the names in the log itself, which saves the download rather than making the diagnosis possible.
So decide by the re-run's outcome rather than by the number: stop after a second no-verdict attempt, get the external verdict from a cross-vendor reviewer, and report the PR blocked on that verdict rather than ready.

- **Do:** read the denial count to classify which failure family you are in, then let the re-run's outcome decide what to do next.
- **Do:** stop re-triggering after the second no-verdict attempt, and get the external verdict from a cross-vendor reviewer.
- **Do:** download the execution artifact when you need to know which tools were denied, rather than inferring it from the count.
- **Don't:** call a high-denial run non-recovering --- one at 72 posted a real verdict the same day.
- **Don't:** read the workflow's refusal to mark a run retryable as advice against the manual re-run, which is a different retry.
- **Don't:** keep re-triggering the same reviewer past the second no-verdict attempt, and don't report the PR ready on a self-review while a cross-vendor reviewer is reachable.

**The built-in retry can be `skipped` rather than stubbing,
and then only one attempt ever ran.**
The "two stubs back to back" paragraph above anticipates the workflow's own same-run retry
*running and also stubbing*,
which is the case where two independent attempts agree.
A second signature reaches the same red check
having spent one attempt rather than two:
the retry step concludes `skipped`,
so "two stubs back to back" never applies,
and a manual re-run is the **first** retry rather than the second.

A parse failure is ONE of the causes, not the cause:
a genuinely parsed count above the threshold refuses the retry too, correctly.
Read the count before concluding which you have.
When the count cannot be parsed out of the execution result
the workflow substitutes a fail-safe sentinel of `999999`,
far above the stub-retry threshold of `5`,
so the run takes the gha#198 branch described above
without any real count ever having been measured.
Note which way the sentinel errs.
It defaults toward *not* retrying,
so a review whose real denial count would have qualified
is refused its second attempt.

So read the retry step's own conclusion
before deciding what a failed review means.
It is `skipped` when the gate refused.
`continue-on-error` is applied to the retry step upstream, so a retry that runs
and fails may not surface as `failure` there either --- which is why the denial
count, rather than the step conclusion, is what classifies this.
Reading that step conclusion is one API call --- `actions/jobs/<id>`, not
the job log the denial count comes from ---
and it changes what a manual re-run is worth ---
an independent second sample,
rather than a third after two that already agreed.

- **Do:** read the retry step's conclusion, and say whether the review was
  attempted once or twice.
- **Do:** spend the manual re-run on a `skipped` retry, since no second
  attempt has happened yet.
- **Don't:** read a red review check as "the retry also stubbed" --- that is
  one of two signatures, and the other spent half as many attempts.
- **Don't:** treat `999999` as a denial count; it is the parser's failure
  value, not a measurement.

See [`self-review-fallback.cases.md`](self-review-fallback.cases.md),
"The stub-retry skipped on a sentinel denial count".

Either way: don't wait on the bot indefinitely --- do the review yourself and keep driving to fully-clean.

**A self-review is dispatched to a separate subagent, never performed inline.**
Everything in this fragment governs *when* a self-review is owed and to what standard, and left *who performs it* to the author by default.
The author is the one party who cannot: the session that wrote the diff knows what it was meant to say, so it reads the artifact and recovers the intent, which is confirmation rather than review.
Dispatch [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) (foreground, read-only) against the diff, brief it with the standards rather than with your rationale for the change, and disposition its findings per [`ard`](../../skills/ard/SKILL.md).
See [`adversarial-self-review`](adversarial-self-review.md) for the full rule, including why a same-vendor subagent buys independence of intent and not of blind spot --- which is why the cross-vendor reviewer below is still worth chasing on top of it.

**The posted comment is that reviewer's report, not a recap the author writes around it.**
Dispatching and then composing a different comment is the same failure as
reviewing inline, one step later.
See [`adversarial-self-review`](adversarial-self-review.md)
("The posted fallback comment is the reviewer's report")
and [`memories/cursor.md`](../../memories/cursor.md).

- **Do:** post the dispatched reviewer's structured report
  (Summary / Findings / Verdict / Reviewed-Commit) as the fallback comment,
  then append the required disclosure marker.
  How Cursor Cloud obtains that report is in
  [`memories/cursor.md`](../../memories/cursor.md).
- **Don't:** wrap the verdict in the authoring session's ARD round-history
  recap in the same comment.
- **Don't:** omit the disclosure marker, or treat that marker as license to
  add an ARD ledger.
- **Don't:** paraphrase a missing reviewer body as Ready for merge.

**Self-review is the immediate fallback so the PR never stalls --
but declaring the PR clean still requires an external verdict whenever one is reachable.**
Don't wait to self-review: post it right away, same as above.
But also check, the same round, whether a *different* configured reviewer is reachable
(e.g. Copilot code review, if the repo/org has it) --
not just whether the `@claude` bot specifically produced a verdict,
since the two can fail independently (one quota-exhausted, the other working fine, or vice versa) --
and request it in parallel with posting the self-review, not after.
Re-check reachability every round:
a reviewer that was ineligible/quota-exhausted a few pushes ago (a missing license, a temporary rate limit)
can become reachable mid-session.
Before reporting a PR **fully clean** / **ready** (ARDI's own terminal-state terms -- see `fully-clean.md`),
confirm a genuine all-clear review is posted at the current head from an external reviewer, if one is reachable --
a self-review alone, or a clean state you inferred yourself from green CI and resolved threads,
doesn't satisfy this once an external verdict is obtainable.
Merging autonomously under `mwc` (merge-when-confident) unconditionally requires an automated clean Claude review verdict evaluating the HEAD commit;
a fallback self-review allows iteration and unblocks PR progress, but NEVER authorizes autonomous merge under MWC.

**Weight two reviewers' agreement by whether they share a vendor, and prefer a cross-vendor second reviewer over a second run of the same one.**
The section above says to check whether a *different* configured reviewer is reachable, and treats every second reviewer as interchangeable.
They are not.
Two reviewers built on the same vendor's models share their training and so share their blind spots, which means a defect both of them pass over is one neither was ever likely to catch.
Their agreement therefore measures the shared blind spot rather than the diff.

This corpus already makes the identical argument about **instruments**, so extending it to reviewers is a small step rather than a new claim.
[`algorithmatize-checks.rationale.md`](algorithmatize-checks.rationale.md) states it directly: "Two methods keyed on the same surface feature share a blind spot, so their agreement measures the blind spot rather than the truth."
[`fail-fast`](../principles/fail-fast.md) puts the same point in one line: "A second reading of the same stream is not a second opinion."

Two consequences follow.

**When chasing a second reviewer, prefer a different vendor.**
Copilot beside `claude-review` is the common pairing, and
[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) runs a
separately-billed ChatGPT-plan CLI.
Re-dispatching the reviewer that already ran is the weakest of the available options, since it re-reads the same diff through the same model.

**Antigravity is not one of these any more, and the difference matters here more
than anywhere else.**
It is permanently out of service (user directive, 2026-08-20), confirmed the
same day on a dispatched run that ended
`request failed (code 429): Your prepayment credits are depleted` and
`Execution failed: model unreachable`.
That is not the transient outage this fragment otherwise teaches you to re-check
each round --- re-checking it will never succeed.
So the pairing above is now Copilot and `delegate-to-codex`, and nothing else.
Those two are not interchangeable, which is why the preference still needs
reading rather than collapsing to one name.
Copilot is **requested** on the PR, and answers only where the org's licensing
reaches it.
`delegate-to-codex` is the only cross-vendor reviewer this corpus can
**dispatch** itself.
[`agy-review-workflow`](../../skills/agy-review-workflow/SKILL.md) is kept as
history rather than as an option; do not dispatch it, since a dispatch burns a
run and leaves a red check for a reviewer that cannot answer.
Tracked as ai-config#1776.

**Read a cross-vendor disagreement as a prompt to check the item yourself.**
A split means one reviewer surfaced something the other's approach did not, so the item is worth verifying rather than settling by majority or by whichever reviewer you trust more.
The split is not evidence that either side is right --- it is evidence that the question is live, which is exactly the state
[`address-every-comment`](address-every-comment.md) already says to resolve by checking the code rather than by weighing reviewers.
Keep this distinct from [`fully-clean`](fully-clean.md)'s instability rule, which governs **one** reviewer contradicting itself across runs on unchanged code: that is noise from re-derivation, whereas two vendors differing is two different readings of the same diff.

- **Do:** name the vendor when reporting that two reviewers agree, so a reader can weight the agreement.
- **Do:** spend a reachability check on a cross-vendor reviewer before re-dispatching one that already ran.
- **Don't:** read same-vendor agreement as independent corroboration.
- **Don't:** settle a cross-vendor split by majority or by reviewer preference.
  Check the item.

See [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "Where the cross-vendor directive came from".

**A CLEAN same-vendor verdict is the state this rule most applies to, and the one where nothing prompts it.**
Every trigger named above is a *failure* of the primary.
None of them fires on the case that leaves nothing outstanding: the primary answers, finds nothing, and reports the PR ready.
A clean verdict closes the loop and reads as permission to stop, which is [`learn-from-review-findings`](learn-from-review-findings.md)'s "a clean verdict discharges the round, and it does not discharge your own probing" arriving one reviewer further out.
There the unsearched space belongs to one reviewer's attention;
here it belongs to a whole vendor's blind spot, so no amount of attention inside that vendor reaches it.

The asymmetry is what decides it.
A same-vendor clean verdict is evidence that the diff survives the checks that vendor's models are good at, and it is not evidence of absence, because the defects a shared blind spot hides are exactly the ones no same-vendor round can report.
So same-vendor rounds do not accumulate into coverage.
Eleven rounds and one round make the same claim about whatever the vendor's models are poor at, which is why a round count reads as thoroughness while measuring only how much of the vendor's reachable region was covered.

- **Do:** run the cross-vendor pass on a clean same-vendor verdict, not only on a failed one.
- **Do:** report a same-vendor round count as coverage inside one vendor's reachable region, and say which reviewers supplied it, rather than as a bare measure of how thoroughly the diff was reviewed.
- **Don't:** read "the reviewer found nothing" as a reason the cross-vendor pass is unnecessary --- that is the reading the linked case record falsifies.
- **Don't:** treat many same-vendor rounds as substituting for one cross-vendor round;
  they are not the same measurement.

See [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "A clean same-vendor verdict over eight blocking cross-vendor findings".

**"Reachable" is a property of the session as well as of the reviewer, and the second kind is not a fallback case at all.**
Everything above treats reachability as a fact about the *reviewer* --- quota-exhausted, unlicensed, rate-limited, not configured --- so the remedy is always to re-check it later, on the reasonable assumption that whatever ails it may lift.
There is a fourth state that wording does not reach, and it never lifts on its own: the reviewer is working perfectly, and **this session** cannot summon it.

The distinction decides the disposition, which is why it is worth separating rather than folding into "unavailable".
A reviewer that is down hands the verdict to a self-review, per this whole fragment.
A reviewer that is up and unreachable-by-you hands it to **a human**, in one step, and a self-review substitutes for nothing --- so reporting the PR ready on one would assert an all-clear that a working reviewer was never asked for.

The tell is a **permission or identity** answer rather than a capacity one:
a `403 Resource not accessible by integration` on a dispatch (the token lacks `actions: write`),
or a comment-triggered run reporting **skipped** rather than failed, which means its job `if:` rejected you ---
usually an `author_association` allowlist, against a session whose comments post under a bot identity as `CONTRIBUTOR` or `NONE`.
The reviewer completing on somebody else's branch the same day settles that it is up.

Read the gate rather than inferring it, and note a caller that delegates via `uses:` gates in the **callee** at its pinned ref, so the caller's own `on:` block settles nothing (see [`pr-on-claim`](pr-on-claim.md)).
One read settles the identity half:
`gh api "repos/<owner>/<repo>/issues/comments/<id>" --jq '{user: .user.login, assoc: .author_association}'`.

Then post the self-review anyway, and report the PR **blocked on an external verdict** rather than ready, naming the one action that unblocks it.
Don't re-post a request that was skipped --- the gate that rejected it rejects the retry.
A recurring instance is a repo-level defect rather than a per-PR one, so file it, per [`report-mistakes-proactively`](report-mistakes-proactively.md).

- **Do:** classify a missing verdict as reviewer-down or session-blocked before choosing a disposition, and say which.
- **Don't:** read a `skipped` run as a failed one, or report a PR ready on a self-review when a working reviewer is one human action away.

See [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "A session that could reach none of four working reviewers".

**The commonest way the re-check above fails is a recurring brief that already calls the reviewer unreachable.**
A scheduled check-in restating a previous round's blocker as settled makes every later round read it as a premise,
so this rule stays loaded and never fires.
The "don't re-post a request that was skipped" instruction just above is the one most likely to harden that way,
since it is correct about the gate and silent about the capability claim underneath it.
Re-derive which of the two you are in each round rather than carrying the classification forward.
See [`challenge-the-assignment`](challenge-the-assignment.md)'s "A brief you re-send each round carries a measurement".

**Publish a dispatched review verbatim --- the posting session transports it, it does not edit it.**
When the reviewing subagent returns,
its structured report --- summary, findings, and verdict --- *is* the review.
Rewriting that report before posting
--- summarizing it, regrouping it,
translating it into the session's own status prose,
or softening the verdict ---
filters the artifact whose entire value
is independence from the authoring session.
A rewrite is authored by exactly
the party the separate reviewer exists to check.
A reader cannot tell filtered-out findings from absent ones,
so a softened publication reads as a cleaner review than occurred.

Post the reviewer's report as received:
the findings in its order and wording,
the summary and verdict lines intact,
attributed to the reviewer,
with the reviewed commit SHA
and a one-line header naming what produced it.
This is the same requirement as the Cursor Cloud route above;
this section adds that it holds wherever a dispatched review is published,
not only in that harness.
The session's own dispositions of the findings (addressed / rebutted / deferred)
go in separate follow-up comments or commit messages ---
never interleaved into the published review body.

- **Do:** publish the reviewer's findings and verdict verbatim, attributed, with the reviewed commit SHA.
- **Do:** post your dispositions as separate follow-ups, after the review is on the record.
- **Don't:** paraphrase, filter, reorder, summarize, or re-frame a review before publishing it.
- **Don't:** fold your own status framing or "ready" assessment into the published review body.

**A fallback self-review is prone to being shallow, so hold it to the same bar as the bot it stands in for.**
A self-review you post *because* the automated reviewer was unavailable --- quota-skipped, a stub, or erroring on an infra failure --- feels like a stopgap rather than the real review, so it tends to get a shallower pass than the round deserves.
The gap is specific and predictable: a shallow self-review checks *structure* --- a dogfood back-reference, ASCII punctuation, semantic line breaks --- and skips the prose *fact-check*, so a false mechanism claim or a misattributed citation sails straight through, since a structural pass has nothing to say about either.
Run the applicable prose-review skills against the diff's own factual claims, not just its shape: [`fact-check-prose`](../writing/fact-check-prose.md), the **cause** claim-type check in [`metacognitive-monitoring`](metacognitive-monitoring.md), and the read-the-cited-source rule in [`address-every-comment`](address-every-comment.md) --- a claim about *why* some mechanism behaves as it does gets asked what else would explain it, and a citation gets read against what the cited source actually says.
Hand that whole standard to the reviewer rather than applying it yourself: a fallback self-review is dispatched to the [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent like any other, per [`adversarial-self-review`](adversarial-self-review.md).
This is the fallback-specific sharpening of "Apply the same review standards the bot would" above: the standard does not relax because the reviewer it replaces happened to be absent.

- **Do:** dispatch the review to `adversarial-reviewer`, briefed to run `fact-check-prose`, the **cause** check, and the cited-source check, exactly as on any pre-push self-review.
- **Do:** treat the fallback's stopgap feel as the cue to slow down, not as license to skip the semantic checks.
- **Don't:** let a fallback self-review stop at structural checks (dogfood, ASCII, line breaks) and report "no findings".
- **Don't:** read "the bot was down" as permission for a lighter review than the bot itself would have given.

**Where a diff makes a claim about a TOOL's behaviour, check the tool's own documentation --- the prose fact-check above cannot reach it.**
The section above closes the structural-versus-semantic gap, and it has a blind spot of its own that only shows up on a diff encoding how some external tool behaves: a hook wrapping `git push`, a script parsing `gh` output, a workflow reading an Actions field.

`fact-check-prose` asks whether a sentence is true, and a sentence *describing* a tool can be perfectly true while the code beside it implements a different tool than the one that exists.
Verifying that means re-deriving the tool's contract --- reading `--help`, the man page, the release notes --- rather than re-reading the sentence, and re-reading is what a prose pass does.

Measured 2026-08-21/22 on [ai-config#1884](https://github.com/Morrison-Lab/ai-config/pull/1884), where the split was clean: a self-review ran the prose fact-check faithfully and found two real prose defects in its own diff, and found **none** of four force-push bypasses in the same diff --- each of which one line of `git push --help` or `git push -h` would have settled.
A cross-vendor reviewer found all four.

The tell is a diff that *quotes no source* for a behavioural claim.
"`--force-with-lease` compares against the remote-tracking ref" reads as settled fact.
`git push --help` saying so is what makes it one.

- **Do:** read the tool's own `--help`, man page, or release notes when a diff asserts how that tool behaves, and quote what you read.
- **Do:** enumerate the tool's real option set from its own output rather than from memory, when a diff parses one.
- **Don't:** count a clean `fact-check-prose` pass as having verified a behavioural claim --- it checks the sentence, not the tool.
- **Don't:** treat a plausible mechanism as checked because nothing in the diff contradicts it.

See [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "A cross-vendor reviewer found seven defects the primary never reached".


**A defect the self-review SURFACES and then dismisses
is worse than one it misses.**
The section above governs the defect a shallow pass never notices.
This one gets noticed, written down in the review body,
and closed out on your own judgment ---
"the exposure is narrow", "not worth another boundary change" ---
which reads as proportionate scoping
rather than as a decision to ship a defect you have already found.

It is worse than the miss on two counts.
The observation was already made,
so acting on it was the cheapest it was ever going to be,
and the dismissal spends that for nothing.
And the written finding *documents that you knew*,
so when an external reviewer then demonstrates it,
the record shows a defect identified and waved through rather than overlooked.

The missing piece is structural rather than a lapse of nerve.
A self-review has no second party to overrule the dismissal,
which is exactly what the disposition vocabulary supplies everywhere else.
[`ard`](../../skills/ard/SKILL.md) has four dispositions and narrows to three
for anything requesting a change, since Acknowledge is reserved for a comment
that asks for nothing ---
Address it,
Rebut it with an argument you would be willing to post to a reviewer,
or Defer it to a tracked issue.
A defect you found yourself requests a change by construction, so the fourth
is not available for it.
"Not worth fixing" is a Defer with no issue behind it,
and [`issue-first`](issue-first.md) already rules that out:
an untracked deferral is a dropped request
wearing the vocabulary of scope discipline.

- **Do:** give every defect your own self-review names one of the three
  dispositions, in writing.
- **Do:** file the issue in the same round when you defer, so a narrowness
  judgment is one someone else can disagree with.
- **Don't:** close a finding you raised yourself on your own estimate of its
  blast radius.
- **Don't:** read "I mentioned it in the review" as having handled it ---
  naming a defect is the input to a disposition, not one of them.
