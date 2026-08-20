When a PR you're managing has its `@claude` review workflow fail to produce a usable verdict --- whether because it was **skipped for quota** or because it **ran to completion but never stated a verdict** (a "stub review") --- don't stall the ARDI loop waiting for it --- **do the review yourself and post it** as a PR comment.
Apply the same review standards the bot would (the SERG lab manual and d-morrison's modular/idiomatic priorities), then keep iterating to fully-clean on your own findings.
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
Copilot beside `claude-review` is the common pairing, and the corpus already owns two more:
[`agy-review-workflow`](../../skills/agy-review-workflow/SKILL.md) wires up the Google Antigravity review workflow, and
[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) runs a separately-billed ChatGPT-plan CLI.
Re-dispatching the reviewer that already ran is the weakest of the available options, since it re-reads the same diff through the same model.

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

**"Reachable" is a property of the session as well as of the reviewer, and the second kind is not a fallback case at all.**
Everything above treats reachability as a fact about the *reviewer* --- quota-exhausted, unlicensed, rate-limited, not configured --- so the remedy is always to re-check it later, on the reasonable assumption that whatever ails it may lift.
There is a fourth state that wording does not reach, and it never lifts on its own: the reviewer is working perfectly, and **this session** cannot summon it.

The distinction decides the disposition, which is why it is worth separating rather than folding into "unavailable".
A reviewer that is down hands the verdict to a self-review, per this whole fragment.
A reviewer that is up and unreachable-by-you hands it to **a human**, in one step, and a self-review substitutes for nothing --- so reporting the PR ready on one would assert an all-clear that a working reviewer was never asked for.

The tell is a **permission or identity** answer rather than a capacity one:
a `403 Resource not accessible by integration` on a dispatch (the token lacks `actions: write`),
or a comment-triggered run reporting **skipped** rather than failed, which means its job `if:` rejected you ---
usually an `author_association` allowlist, against a session whose comments post under a bot identity as `CONTRIBUTOR`.
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

**A fallback self-review is prone to being shallow, so hold it to the same bar as the bot it stands in for.**
A self-review you post *because* the automated reviewer was unavailable --- quota-skipped, a stub, or erroring on an infra failure --- feels like a stopgap rather than the real review, so it tends to get a shallower pass than the round deserves.
The gap is specific and predictable: a shallow self-review checks *structure* --- a dogfood back-reference, ASCII punctuation, semantic line breaks --- and skips the prose *fact-check*, so a false mechanism claim or a misattributed citation sails straight through, since a structural pass has nothing to say about either.
Run the applicable prose-review skills against the diff's own factual claims, not just its shape: [`fact-check-prose`](../writing/fact-check-prose.md), the **cause** claim-type check in [`metacognitive-monitoring`](metacognitive-monitoring.md), and the read-the-cited-source rule in [`address-every-comment`](address-every-comment.md) --- a claim about *why* some mechanism behaves as it does gets asked what else would explain it, and a citation gets read against what the cited source actually says.
This is the fallback-specific sharpening of "Apply the same review standards the bot would" above: the standard does not relax because the reviewer it replaces happened to be absent.

- **Do:** run `fact-check-prose`, the **cause** check, and the cited-source check on a fallback self-review, exactly as on any pre-push self-review.
- **Do:** treat the fallback's stopgap feel as the cue to slow down, not as license to skip the semantic checks.
- **Don't:** let a fallback self-review stop at structural checks (dogfood, ASCII, line breaks) and report "no findings".
- **Don't:** read "the bot was down" as permission for a lighter review than the bot itself would have given.

