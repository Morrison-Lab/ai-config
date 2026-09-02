# Rationale: PR on claim

The mechanism, evidence, and argument behind the rules in
[`pr-on-claim.md`](pr-on-claim.md),
moved here to keep it out of the auto-loaded `CLAUDE.md` context.
Each heading mirrors the fragment's own section, and each passage
opens with the bold rule statement it argues for, repeated from the
fragment; the fragment's copy is authoritative.

**Why up front.** The claim comment on the issue is easy to miss, and it isn't
what other sessions check. The authoritative in-flight signal is the issue's
cross-referenced **open PRs** --- the check `gi` runs before grabbing an issue.
Until a PR exists, a parallel issues-sweep can grab the same issue and build a
duplicate. An open PR closes that window: it shows in `gh pr list` and the
issue's timeline, and links the issue via `Closes #N`. An open PR is the
clearest "someone is working this" signal there is --- stronger than a comment.
This is the strong form of the "open and link the PR promptly" note in
[`claim-pr`](claim-pr.md).

The empty commit gives the branch a diff so the PR can open with no code yet.
In a remote/web session where `gh` is absent, push the empty commit and open
the PR with the GitHub MCP tools instead (`mcp__github__create_pull_request`
with `draft: true`).

**Draft, not ready-for-review --- deliberately.** A draft doesn't trigger the
`@claude` review bot, so no review round is spent on an empty or half-finished
diff. Implement on top, pushing commits to the same PR; when the change is
complete and the repo's checks pass, mark the PR **ready for review**
(`gh pr ready <N>`, or `mcp__github__update_pull_request` with `draft: false`).
Marking it ready is what kicks off ARDI.

**Marking a draft ready is a push-landed checkpoint, so verify the
implementation actually reached the branch head before `gh pr ready`.**
[`ardi`](ardi.md) already forbids claiming a fix is pushed until it is on the
PR's head commit, and its pre-push checklist makes `git rev-parse HEAD
origin/<branch>` agreeing a killer item --- but both fire *after a push* or
*before a status report*, and neither fires on the draft-to-ready transition.
That transition is where the gap bites: implementing on top of the empty
`start:` scaffold commit, running self-review, and updating the PR body all feel
like the work, so `git push` is the one step with nothing downstream to prompt
it.
The head then stays at the empty scaffold, every check is green on the empty
diff (per [`ardi`](ardi.md)'s "a PR whose branch carries no implementation is
green on every check"), and the reviewer correctly reports a zero-file diff.

So immediately before `gh pr ready`, confirm both: `git rev-parse HEAD` equals
`git ls-remote origin <branch>` (the implementation was pushed), and
`gh pr diff <N> --name-only` is non-empty (the branch carries a diff).

**Request the external reviewer in the same stride.** Opening a PR or marking a draft ready can trigger the repo's own review workflow, but that does not summon every reviewer.
For a repository whose Copilot review isn't already scheduled automatically (see the caveat below), Copilot only reviews when explicitly requested with the requested-reviewers API or the equivalent UI action --- the `REQUEST_COPILOT_REVIEW` operation token (`tool-mappings.md`):

```bash
gh api -X POST "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'   # REQUEST_COPILOT_REVIEW
```

Then, in a **separate** call (see the sole-command rule below), verify it landed:

```bash
gh pr view <N> --json reviewRequests,reviews
gh pr checks <N>
```

In a remote/web session without `gh`, use the equivalent tool
(`mcp__github__request_copilot_review`) instead.

**Run that `requested_reviewers` POST as the sole (or last) command in its Bash call.**
The [`no-unreviewed-pr`](../../hooks/no-unreviewed-pr.py) Stop hook discharges the reviewer-request obligation only on positive evidence the request itself succeeded, and the one reliable success signal is the whole Bash call's exit status --- which belongs to that call's **last** command.
So chaining the verification reads (`gh pr view ... --json reviews`, `gh pr checks`) *after* the POST in the same call makes the request non-last, which the hook treats as ambiguous: it keeps warning even though the POST returned 200.
Run the POST alone, then do the pending/reviews/checks verification in a **separate** later call.
This is [`fail-fast`](../principles/fail-fast.md)'s "a combined result cannot attribute a per-step outcome" applied to a review request;
the same rule governs a `gh pr ready` draft transition the hook tracks.

**"Nothing chained after it" includes a pipe added purely to trim the output.**
The rule above is stated in terms of *verification reads*, which is how it is usually broken and is also the version a reader recognizes themselves in.
A formatting pipe does not feel like chaining a second step --- `| tail -3` or `| jq` is a decision about how much of one command's output to look at, not an extra command in a sequence --- so it slips past a reader who has just agreed with the rule as written.
The shell does not draw that distinction: the last command in the pipeline owns the exit status either way, so `gh api ... | tail -3` leaves the POST non-last exactly as a chained `gh pr view` does.
Use `--silent`, or `--jq` **inside** the `gh api` call, when the output needs narrowing.
Both keep the POST the last command.

**A PreToolUse block for this was considered and rejected -- the Stop hook stays the only guard.**
After hitting this exact mistake (a `--silent` POST followed by `&& echo`, chained in one call), the natural next question is whether a **PreToolUse** hook should refuse to run the compound command at all, rather than let it run and catch the omission afterward at Stop.
It was investigated and rejected, so record the reasoning here rather than re-deriving it the next time someone proposes it.

The Stop hook's `last`-computation is deliberately biased toward "ambiguous means not last": when `_simple_commands` cannot confirm a request is the final simple command, the hook keeps the PR tracked rather than risk a silent wrongful discharge, per [`fail-fast`](../principles/fail-fast.md)'s safe/dangerous asymmetry.
That bias costs nothing at Stop time -- a false "not last" just means one more nag, and re-running the POST alone clears it in a single extra call, as it did here.
The identical bias in a PreToolUse **block** costs something different: it would refuse a genuinely solo, well-formed command whenever the shlex-based parser could not positively confirm it was alone.
A POST whose payload contains `$(...)` command substitution is the concrete case -- `(` and `)` are control-operator tokens to `_simple_commands`, so such a command can get mis-split into more than one "simple command" and read as chained when nothing follows the real request.
Reusing the Stop hook's own parser for a block would therefore inherit a bias calibrated for a safe, low-cost consequence and apply it to an unsafe, high-cost one.

[`hooks/no-unauthorized-merge.py`](../../hooks/no-unauthorized-merge.py) is the concrete evidence for how much engineering a *correctly calibrated* PreToolUse block over arbitrary shell-command structure costs in this repo: six review rounds (ai-config#1279, #1287) closing false-negative gaps in what counts as a command position, with its own comments stating the enumeration "cannot be finished."
That investment is proportionate there because the thing being prevented is an unauthorized merge.
It is not proportionate here, because the thing this new hook would prevent is a single wasted Bash call with a working safety net already in place -- the Stop hook already protects the actual invariant (no PR ships without a review request) and gives a one-round, self-explanatory fix.

[`hooks/flag-unchained-branch-switch.py`](../../hooks/flag-unchained-branch-switch.py) already reached the same conclusion for a structurally similar "does this command chain something after a step whose success matters" concern, choosing to warn rather than block, on the same grounds: a blocking guard that misfires on a legitimate compound command is worse than the miss it exists to prevent.

**Some repos schedule Copilot automatically, and this step is redundant there.**
A repository ruleset can carry a `copilot_code_review` rule with
`review_on_push: true` (and optionally `review_draft_pull_requests: true`),
which re-requests Copilot on every push with no explicit request from anyone
--- see [`memories/gh-cli.md`](../../memories/gh-cli.md)'s "Required checks are
not the only thing a ruleset carries" section for how to read that off a
repo's rulesets.
When that applies, an explicit request lands while Copilot is already a
pending reviewer, which the API can (unreliably) answer with either `201` or
`422` --- don't spend a call resolving which; either response is consistent
with the ruleset already having asked.
Where you can't tell whether the repo has such a ruleset, request explicitly
anyway --- a redundant request spends one call, the accepted risk, while
skipping it on a repo without automatic review leaves Copilot unrequested.

Run that request immediately after `gh pr create` for a non-draft PR, or immediately after `gh pr ready` for a draft PR, before writing any status report.
Verify the request landed: the POST response should include the requested reviewer, then a fresh read should show either a pending review request or a new review/check from that reviewer on the current head.
A POST response alone is not enough; if the pending request disappears and no current-head review appears after a short poll, treat the reviewer request as blocked and start the documented fallback.
Do not leave it as "review owed".

**That blocked-request test has a false positive, and it fires on more repos than the section above describes.**
Where a ruleset auto-requests Copilot, the POST returns success naming the reviewer and `reviewRequests` reads **empty** moments later.
That is the literal signature the test above calls blocked --- request gone, no review yet --- so the two paragraphs contradict each other, and the earlier one is the one that is wrong.

The auto-requesting ruleset was offered as the likeliest reconciliation, and it is now **ruled out as the general explanation**.
`Morrison-Lab/ai-config` produces the identical signature while carrying no `copilot_code_review` rule at all, at either repository or organization scope.
Measured 2026-08-06 on PR #1219: the POST returned `HTTP/2.0 201 Created` with a `Location` header, and a read five seconds later returned `["the repository owner"]` with Copilot absent, reproduced twice.
A separately-issued `the repository owner` request persisted in that same list, so nothing is wiping the list structurally --- only Copilot's entry goes.

*Why* the entry disappears is still unexplained, and this section deliberately declines to name a replacement mechanism.
What is measured is the disappearance, and nothing yet accounts for it.
Do not upgrade a guess about it into a finding, and do not probe it harder than the question deserves --- each probe consumes the per-user Copilot quota that is usually the real reason Copilot is absent, so the experiment damages the thing it would explain.

**The operative point is that three surfaces fail to discriminate here, and only a fourth one does.**
The pending-reviewer list empties whether or not a ruleset asked.
The ruleset query comes back negative whether or not the request reached Copilot.
The reviewer's own check run goes green whether it reviewed, refused, or stayed silent, per [`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s fifth case and its silent-reviewer sibling.
Only the posted review **body** distinguishes those outcomes.

So an empty pending list after a 201 supports one conclusion and not a second.
It is **not** evidence the request was blocked.
It is **also not** evidence that a review is coming, which is a separate claim and an unsupported one.
At ai-config what follows is a refusal rather than a review, so the two claims come apart there in the clearest possible way.
Note that this point is indifferent to *why* the reviewer refused --- quota, a platform incident, anything else --- because a refusal is not a verdict whatever produced it.

Route to the self-review fallback on a **read refusal body**, never on an empty pending list.
[`review-verdict-pitfalls`](review-verdict-pitfalls.md) is explicit that a refusing reviewer is not "reachable", so a refusal legitimately hands the external-verdict requirement to whichever other reviewer is working.
An empty pending list hands it to nobody, because it has established nothing either way.
Note also that a refusal body is itself proof the request **arrived**, which is the cleanest available disproof of "blocked".

Read the ruleset anyway --- it is one cheap call, and on a repo that does carry the rule it explains the disappearance outright --- but read it for what it can actually tell you.
`ucdavis/bcs` is the known example, per [`memories/gh-cli.md`](../../memories/gh-cli.md): ruleset `19248641` returns `{"review_on_push":true,"review_draft_pull_requests":true}`.
The effective-rules endpoint covers organization-level rulesets alongside the repository's own, in a single call, which the per-ruleset loop in [`memories/gh-cli.md`](../../memories/gh-cli.md) does not (that file's own note on org-level rulesets says why):

```bash
gh api "repos/<owner>/<repo>/rules/branches/<branch>" \
  --jq '[.[] | select(.type=="copilot_code_review")]'
```

A `review_on_push: true` result means the disappearance is expected on that repo, and that the next push re-requests automatically.
An empty result means only that no ruleset explains the disappearance.

The deriving queries, so a later reader re-measures rather than inheriting this:

```bash
# No copilot_code_review rule, at either scope (returns an empty array here).
gh api "repos/Morrison-Lab/ai-config/rules/branches/main" \
  --jq '[.[] | select(.type=="copilot_code_review")]'

# Every Copilot review object is a refusal (returns 0 substantive here).
# `submittedAt` is selected so the two timestamp aggregates below derive from
# this same call rather than from a claim the query cannot reproduce.
gh api graphql -f query='{search(query:"repo:Morrison-Lab/ai-config is:pr is:merged", type:ISSUE, last:60){nodes{... on PullRequest{reviews(first:20){nodes{author{login} submittedAt body}}}}}}' \
  --jq '[.data.search.nodes[].reviews.nodes[]
         | select(.author.login=="copilot-pull-request-reviewer")]
        | {total: length,
           refusals:    ([.[] | select(.body | test("unable to review|quota limit"; "i"))] | length),
           substantive: ([.[] | select(.body | test("unable to review|quota limit"; "i") | not)] | length),
           since_override:  ([.[] | select(.submittedAt >= "2026-08-04")] | length),
           before_incident: ([.[] | select(.submittedAt <  "2026-08-06T15:22:49Z")] | length),
           latest: ([.[].submittedAt] | max)}'
```

**Requesting Copilot discharges nothing when the repo's own reviewer runs on `workflow_dispatch` alone.**
Everything above concerns *which* reviewer to ask for, resting on this section's opening premise that opening a PR or marking it ready at least starts the repo's own review workflow.
That premise is a property of the repo rather than of GitHub, and it is one `on:` block to check.

A review workflow carrying `pull_request` fires on every push, so a review arrives without anyone asking, and a session working such a repo learns to treat reviews as something that *arrives*.
A review workflow carrying only `workflow_dispatch` never fires by itself.
A PR there sits at all-green CI with zero pending checks and no review at all, because nothing failed and nothing was ever queued.

The near-miss is requesting Copilot and reading that as the review obligation discharged.
It is a genuine reviewer request and it succeeds, so nothing about it looks like a shortcut.
On a dispatch-only repo it is also the *only* reviewer that was ever going to read the diff, so Copilot refusing leaves the PR reviewed by nobody with every surface green --- which is why the preceding paragraphs' insistence on reading the refusal **body** matters twice as much here.

So read the review workflow's own trigger block rather than recalling it, and dispatch when no push-based trigger exists:

```bash
sed -n '/^on:/,/^[a-z]/p' .github/workflows/<review-workflow>.yml
gh workflow run <review-workflow>.yml -R <owner>/<repo> --ref <PR-branch> -f pr_number=<N>
```

Take the input's name from that same file rather than assuming it, since a wrong `-f` name fails the dispatch outright.
It is `pr_number` both in `Morrison-Lab/ai-config`'s `claude-review.yml` and in `ucdavis/bcs`'s dispatch caller, measured 2026-08-06.
A trigger block is exactly the kind of configuration that changes, so re-read it rather than trusting that pair.

The general rule the two shapes share: **request the AI review at the moment you judge the PR ready, rather than waiting for one to arrive.**
Waiting costs nothing where a trigger exists and costs the entire review where none does, and the PR page looks identical either way.

**The `Stop` hook cannot catch this, and its silence is why the rule has to be stated in prose.**
[`hooks/no-unreviewed-pr.py`](../../hooks/no-unreviewed-pr.py) tracks precisely this obligation --- a PR opened or readied with no successful reviewer request after it --- and discharges on any successful request, Copilot's included.
That discharge is satisfied while the repo's actual reviewer never runs, which is the over-broad discharge condition [`algorithmatize-checks`](algorithmatize-checks.md)'s "A reminder guard's discharge condition is a second matcher, and its failure is silence" section names as the dangerous direction: the guard goes quiet, and quiet reads as compliance.
Tightening it so a `requested_reviewers` POST cannot discharge on a dispatch-only repo is tracked in `Morrison-Lab/ai-config#1249`.

The per-repo trigger table for `Morrison-Lab/ai-config` lives in [`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md), which owns the repo-specific facts.
This entry owns the cross-repo rule and the hook gap, neither of which that file states.

This is part of opening the PR, not a follow-up task.
A status sentence like "review owed on #N" is the anti-pattern: it names a debt that should already have been discharged, the same way an offer to file an issue names work instead of doing it.
The sentence is the trigger to request the review now.

**A REDACTION PR is the one case where requesting the reviewer is the harm, and it needs recording rather than silence.**
Everything above assumes the reviewer's input is a diff worth reading.
On a PR whose whole change is deleting a secret or a participant identifier, the reviewer's input **is the secret**: removing the literal is the change, so it sits on the removed side of every hunk and reaches the model whatever the merged file ends up saying.
`ucdavis/bcs#610` is the concrete instance --- the `@claude` reviewer quoted a network user id back into a PR comment while reviewing the PR that redacted it.

The carve-out is about **content**, which is what separates it from the draft one directly below.
A draft defers review because there is nothing worth reviewing **yet**, so the deferral expires when the work does.
A redaction PR is complete, wants a **human** reviewer, and must never reach an automated one --- and drafting it to dodge the question makes things worse, since a draft stalls its own ARDI loop.

An automatic gate is not enough on its own, because this rule routes around it.
`ucdavis/bcs#614` merged a `redaction-gate` job that skips **automatic** AI review on such a diff.
An explicit `requested_reviewers` POST is a different path, and the gate never sees it.

So hold the AI review, say so on the PR, and record the exemption where a machine can read it --- a label the repo's own review workflow honours, applied before anything else asks:

```bash
gh pr edit "<N>" -R "<owner>/<repo>" --add-label no-ai-review
```

Run that as its own command, for the same reason the reviewer-request POST above must be its own command.
A label add chained ahead of anything else shares one exit status with whatever follows it, so the label genuinely lands and the guard cannot attribute the outcome --- it keeps warning.
Chaining it *after* a push is fine, since it is then the last command.

Where the repo has no such label, assert it instead, in the env-prefix form this corpus's guards already use:

```bash
ALLOW_UNREVIEWED_REDACTION_PR=1 gh pr view "<N>" -R "<owner>/<repo>" --json number
```

[`hooks/no-unreviewed-pr.py`](../../hooks/no-unreviewed-pr.py) reads both, so a correctly-withheld review has a discharge rather than only a refusal to repeat.
Its exemption is per-PR rather than per-head, since the removed side still carries the literal after the next push.

**Don't mark ready within seconds of the final push --- the two review runs race
and the WRONG one can get cancelled.** On repos whose review workflow runs on
`pull_request` (`synchronize`, `ready_for_review`) with `concurrency:
cancel-in-progress`, a push followed immediately by `gh pr ready` fires two
runs a second apart: the ready-event run (recorded against the pre-push head)
and the push's synchronize run (recorded against the new head). The
cancellation can land on the **newer** run, leaving the current head with a
cancelled review job and a red require-review check --- while the surviving
older run can still post a genuine, current verdict: a reviewer that fetches
the PR's diff at review time (sparta's does, via `gh pr diff` per its own run
transcript) sees the pushed code even though the run is nominally tied to the
pre-push head. Read the posted review and confirm it actually discusses the
current head's changes before trusting it. If this happens, don't push or
re-mention: `gh run rerun <cancelled-run-id>` re-reviews the same head and
turns the head's own checks green. Prevention: push the implementation first,
wait until the synchronize-triggered review run appears in GitHub Actions,
then mark ready as its own later step.
(Hit on `Lacaedemon/sparta#898`, 2026-07-15.)

**Check whether the race can even arise before paying for that wait --- on
many repos it cannot, and the check is one field.**
The race needs *two live runs*.
But the paragraph above sits in tension with this fragment's own
premise that "a draft doesn't trigger the `@claude` review bot": where that
holds, the push's synchronize run **skips** rather than running, so there is
nothing in flight for the `ready_for_review` run to cancel.
Which way a given repo behaves is visible directly --- read the review job's
conclusion on the push's own run before marking ready:

- `skipped` -> no live run, mark ready immediately, no wait needed.
- `in_progress`/`queued` -> the sparta case; wait for it to finish first.

Read it with `gh pr checks <N>`, or `pull_request_read` `get_check_runs` in a
session without `gh` (see [`tool-mappings.md`](../../tool-mappings.md)).
Mind the casing split
[`fully-clean.rationale.md`](fully-clean.rationale.md) warns about: REST
returns lowercase `status`/`conclusion` (`completed`, `skipped`), while
`gh pr checks`/GraphQL return uppercase `state` values.

Don't generalize from either repo. sparta#898 is real, and so is the opposite;
the deciding factor is whether that repo's review workflow gates on
`github.event.pull_request.draft`, which is a property of the workflow, not
something to assume. (d-morrison/altdoc#55, 2026-07-25: the draft's
synchronize-triggered `review / claude-review` reported `skipped`, so marking
ready seconds after the push was safe and the subsequent `ready_for_review`
run posted a normal verdict.)
`Morrison-Lab/ai-config` behaves the same way: its draft synchronize run
reports `review / claude-review` and `review / require-review` as `skipped`,
so no wait is needed there either.
(ai-config#754, 2026-07-28.)

**Reading the caller's `on:` block is not reading the workflow's trigger
conditions, because a reusable workflow gates independently --- at job level,
in another repo.**
The paragraph above is right that the draft gate is "a property of the
workflow, not something to assume", and it leaves open *which file* to read.
[`ardi`](ardi.md) answers that with "read the review workflow's `on:` block",
which is complete for a self-contained workflow and incomplete for a thin
caller.

A caller that delegates via `uses:` carries the `on:` block and frequently
carries no gating at all.
`on: pull_request: types: [opened, synchronize, ready_for_review, reopened]`
therefore looks like an unconditional trigger while the reusable workflow it
calls refuses drafts in its job `if:`, one repo away.
So the conclusion drawn from the caller alone is not merely unsupported, it is
**inverted**: the trigger list is the widest thing in the file, and the
narrowing lives somewhere the file only names.

Two things make the incomplete read feel finished.
An `on:` block is what a reader is *told* to check, so finding one satisfies
the instruction.
And the caller usually opens with a comment explaining what it delegates and
why, which reads as the file having accounted for itself.

The `uses:` line is the tell, and it names the ref to read at.
Resolve it and grep the job-level `if:`, per
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md)'s rule about
reading a dependency at the ref a run actually used rather than at `main`:

```bash
grep -nE '^\s*uses:.*\.github/workflows/' .github/workflows/<review-workflow>.yml
git clone --depth 1 --branch <ref> https://github.com/<owner>/<repo> /tmp/rw
grep -nE 'draft|if:' /tmp/rw/.github/workflows/<called-workflow>.yml
```

An out-of-scope repo still clones, since the git proxy serves anonymous public
reads --- see [`memories/github-remote-sessions.md`](../../memories/github-remote-sessions.md)'s
ladder, which covers the same fallback for ref lookups.

**Working several issues in one session? Verify you actually switched branches
before writing the second issue's code.** The `git checkout -b <type>/<slug>
origin/main` you ran for issue 1 doesn't carry over to issue 2 --- you have to
run it again with a new branch name for each new issue. Forgetting leaves the
working tree on issue 1's branch, so issue 2's edits land in the same
commit/PR as issue 1's --- silently, since nothing errors (there's no reused
branch name here to trigger `git checkout -b`'s own "already exists" error).
Run `git branch --show-current` immediately
before the first edit for every new issue, not just the first one in the
session, and confirm it matches the branch you just created for *this* issue.
