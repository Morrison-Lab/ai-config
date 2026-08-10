When a PR you're managing has its `@claude` review workflow fail to produce a usable verdict --- whether because it was **skipped for quota** or because it **ran to completion but never stated a verdict** (a "stub review") --- don't stall the ARDI loop waiting for it --- **do the review yourself and post it** as a PR comment.
Apply the same review standards the bot would (the SERG lab manual and d-morrison's modular/idiomatic priorities), then keep iterating to fully-clean on your own findings.
Neither failure mode is an approval --- an unreviewed PR stays unreviewed regardless of why the bot didn't weigh in.

**Quota-skipped:** surfaces as a bot comment --- either `Claude review skipped --- API quota exhausted` (the review workflow) or `You've hit your org's monthly spend limit` (the `@claude` agent workflow).
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

Either way: don't wait on the bot indefinitely --- do the review yourself and keep driving to fully-clean.

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

**A fallback self-review is prone to being shallow, so hold it to the same bar as the bot it stands in for.**
A self-review you post *because* the automated reviewer was unavailable --- quota-skipped, a stub, or erroring on an infra failure --- feels like a stopgap rather than the real review, so it tends to get a shallower pass than the round deserves.
The gap is specific and predictable: a shallow self-review checks *structure* --- a dogfood back-reference, ASCII punctuation, semantic line breaks --- and skips the prose *fact-check*, so a false mechanism claim or a misattributed citation sails straight through, since a structural pass has nothing to say about either.
Run the applicable prose-review skills against the diff's own factual claims, not just its shape: [`fact-check-prose`](../writing/fact-check-prose.md), the **cause** claim-type check in [`metacognitive-monitoring`](metacognitive-monitoring.md), and the read-the-cited-source rule in [`address-every-comment`](address-every-comment.md) --- a claim about *why* some mechanism behaves as it does gets asked what else would explain it, and a citation gets read against what the cited source actually says.
This is the fallback-specific sharpening of "Apply the same review standards the bot would" above: the standard does not relax because the reviewer it replaces happened to be absent.

- **Do:** run `fact-check-prose`, the **cause** check, and the cited-source check on a fallback self-review, exactly as on any pre-push self-review.
- **Do:** treat the fallback's stopgap feel as the cue to slow down, not as license to skip the semantic checks.
- **Don't:** let a fallback self-review stop at structural checks (dogfood, ASCII, line breaks) and report "no findings".
- **Don't:** read "the bot was down" as permission for a lighter review than the bot itself would have given.

