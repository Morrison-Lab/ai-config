# Token failures of the `@claude` bot workflows

Satellite of [`claude-bot-workflows.md`](claude-bot-workflows.md),
split at the 1200-line gate (ai-config#1228).
The sections below moved verbatim; the parent keeps the bot's run behaviour.

## `pull_request_target` is rejected by the App-token exchange

Anthropic's `github-app-token-exchange` endpoint rejects OIDC tokens minted for
`pull_request_target` events, with
`App token exchange failed: 401 Unauthorized - Invalid OIDC token`.
The job dies in about 25 seconds, before the model is reached.

The trap is that the action's **own** side supports the event.
claude-code-action#347, "Can't use action in workflow triggered by
`pull_request_target`", is closed as completed, and `docs/security.md` carries a
section on using the action with that trigger --- so the workflow reads as both
correct and documented.
Only the server side refuses it.
(Issue #713's body credits the support to "PR #759".
That number is an unrelated open bug report in the same repo, so cite #347
instead of repeating it.)
Tracked as
[anthropics/claude-code-action#713](https://github.com/anthropics/claude-code-action/issues/713),
open since 2025-12-02, whose stated workaround is to use `pull_request`.

So `pull_request_target` is not an available fix for fork PRs, whatever else
recommends it.
Nor would it be sufficient if the exchange worked: the action still refuses to run
for a contributor without write access unless `allowed_non_write_users` is set,
which `docs/security.md` documents as a significant security risk.
Read a proposal to switch a review workflow to this trigger as a regression, and
leave a comment in the workflow naming the upstream issue so it does not get
re-applied.

Three messages arrive at that same exchange step, and only the first two are
401s.
The message is what separates them:

- `Invalid OIDC token` --- the trigger event, this entry.
- `User does not have write access on this repository` --- the triggering actor is
  not a collaborator, e.g. the Copilot coding agent
  (`UCD-SERG/ucd-serg.github.io#84`).
- `Workflow validation failed ... identical content to the version on the
  repository's default branch` --- usually the self-mod skip when the action exits
  0, but it can also be a red stale-branch block.
  The green form means a PR edited the review workflow and the action deliberately
  skipped itself.
  The red form can appear on a PR that edits no workflows at all, when the branch
  is behind a `main` commit that changed `.github/workflows/`.
  **Do:** compare `.github/workflows/` against `origin/main` and merge `main`
  before rerunning when this message appears on a non-workflow PR.
  **Don't:** treat the message's "new repository" / "workflow changes" text as
  exhaustive, or spend `rerun_failed_jobs` before bringing the branch current.
  See the self-mod skip section in [`claude-review-dispatch.md`](claude-review-dispatch.md)
  for gha's own guard against the green form,
  and `review-verdict-pitfalls.md` for the stale-branch red form.

(Morrison-Lab/ai-config#981, 2026-07-31/2026-08-01: a non-workflow PR
was 30 commits behind `main` after #998 changed `claude-review.yml`.
Its `claude-review` attempt 2 failed in 16 seconds with this validation text and
`Error is not retryable, giving up immediately`; merging `origin/main` was the
whole fix.
Morrison-Lab/ai-config#994's earlier 5m26s stub looked similar in the queue, but
it ran before #998 merged and was a different bug.)

This is a fourth distinct cause in the short-duration band that
[`review-verdict-pitfalls`](../shared/workflow/review-verdict-pitfalls.md) already
records three for, under "That duration signature does not run backwards".
Three of the four run 25 seconds or less, and none of them is about credentials,
which is that section's point: a short run corroborates a credential hypothesis
you already hold on other grounds, and never produces one.

Three of the four are on `UCD-SERG/ucd-serg.github.io` and one is on
`Morrison-Lab/qwt`, so the band is the thing they share rather than the repo.
Saying otherwise would be the grouping-by-symptom overreach that same section
warns about, in the entry invoking its authority.

(`UCD-SERG/ucd-serg.github.io`, 2026-07-31: PR #83 switched the review workflow to
`pull_request_target`, and all five subsequent runs failed this way while the two
`pull_request` runs immediately before it succeeded.
Reverted in #89, tracked as #88.
The revert PR's own two runs are the cleanest demonstration available, because the
trigger is the only variable between them.
Run 30680266779 (`pull_request_target`) was rejected at the token with
`401 Invalid OIDC token`.
Run 30680266785 (`pull_request`) had its token *accepted* and got as far as
workflow validation, where it skipped and exited 0 --- so its check reads
`success` while the action never reviewed anything.
Same repo, same secret, 15 seconds apart.

That second run is also a worked example of the self-mod skip section, now in
[`claude-review-dispatch.md`](claude-review-dispatch.md), and of how it
misleads a careful reader.
Round 2 of this PR's own review read that `success` conclusion and reported the
sentence describing it as a fabricated claim, on the reasoning that a run which
succeeded cannot have stopped early.
It can, and this one did: the log carries
`Skipping action due to workflow validation` and `Exiting due to workflow
validation skip`.
Read the log rather than the conclusion, on any job whose action can exit 0
without doing its work.)

A further failure state, and the only one that leaves no message at that step at
all: the run reaches the model, produces a review, and is **denied when it tries to
post it**.

`pull-requests: read` in the workflow's `permissions:` block is enough to cause
this.
The action's app token covers its own bookkeeping, but the review is posted by
Claude's tool calls running under `GITHUB_TOKEN`, so a read-only token loses the
review after paying for it.
The tell sits in the execution output rather than in any error:
`"permission_denials_count": 8` alongside `is_error: false`.

That makes **two** green-but-no-review states on this workflow: denied at posting,
and skipped at workflow validation.
The two 401s above are red, so they announce themselves; these two do not, which is
what makes them worth enumerating separately from the messages.
Only the log tells them apart.

But the question that settles both at once is not about any mechanism.
**Ask whether a `claude`-authored comment exists on the PR**, which is one query,
rather than reasoning about which token ought to be able to post.

- **Do:** grant `pull-requests: write` to a review workflow on the `pull_request`
  trigger.
  GitHub forces a read-only `GITHUB_TOKEN` on fork PRs regardless, so this widens
  nothing for untrusted contributors.
- **Don't:** infer from a green check, or from an argument about token scopes, that
  a review was posted.

(`UCD-SERG/ucd-serg.github.io`, 2026-08-01: `pull-requests: read` had been in that
workflow since its first commit, and `claude` had **never** posted a review comment
on the repository --- PRs #78, #79, #80, and #86 all ran green with zero.
It surfaced only because #89 restored `read` while asserting it was safe on the
grounds that "the action posts with its own app token".
Two Copilot reviews on that PR restated the premise without objection.
Fixed in #91.
A single query for a `claude` comment on any earlier PR would have caught it at any
point in the preceding month.)
