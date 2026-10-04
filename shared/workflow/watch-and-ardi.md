# Watch and ARDI every PR you touch --- don't ask first

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#watch-and-ardi-every-pr-you-touch-----dont-ask-first) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

"Touch" here means driving the branch: you opened it, were asked to iterate or take it to clean, or are pushing fixes.
A request to post a review and leave findings, with no request to edit, is not that kind of touch.

**Driving.**
The persistent-loop standing yes lives in `AGENTS.md` and applies to every agent.
This file is only the Claude-specific half: how this harness wakes, and how it must not double-trigger review.

When you open (or are handed) a PR/MR to drive, in any repo, subscribe to its activity and run the ARDI loop to clean **automatically** --- never ask "should I watch this?" or "should I iterate it?" first.
That answer is a standing yes across all PRs you are driving.
Subscribe with `subscribe_pr_activity` when that tool exists (provided by the GitHub MCP server in remote/web sessions), or babysit locally.
A subscription does not replace the persistent loop: PR-activity webhooks do not deliver CI success, new pushes, or merge / merge-conflict transitions (see [`memories/github-mcp-tools.md`](../../memories/github-mcp-tools.md)).
Claude's wake is a `/loop`, `send_later`, `CronCreate`, or schedule timer, per `AGENTS.md`.
Re-arm it periodically, since webhooks can't fill that gap --- and word each re-arm against a re-derivable set of PRs rather than a fixed number, per `ardi.md`'s "A scheduled check-in can outlive the PR it names" section.
Drive every review round to fully-clean.

This watch process never formally invokes the `ardi` skill, so read `skills/ardi/SKILL.md` step 6 for the re-request-review mechanics before pushing a fix: after a push, the push itself already triggers the review --- don't also post "@claude review again" in the same round.
On workflows with `concurrency: cancel-in-progress`, the two triggers race and cancel each other, leaving the latest commit's review canceled and `require-review` red for no code reason.
Only post the mention when a round pushed no code (all Rebut/Defer).

Surface to me only when an item is ambiguous, architecturally significant, or deadlocked (the `ardi` skill's escalation rule still applies), or when the PR is clean.
Stop watching only when the PR merges or closes, or I tell you to back off.

**Subscribe only with the returned PR number, never a predicted one.**
Subscribe to a newly opened PR only after `create_pull_request` returns,
using the exact number or URL it returned.
Never batch `subscribe_pr_activity` with `create_pull_request`,
and never predict or compute the PR number in advance (such as "last PR + 1").
Issues and PRs share a single monotonic numbering sequence in GitHub,
and concurrent sessions or human maintainers open items in the same repository
simultaneously.
Batching a subscription call on a predicted number results in silently
subscribing to another session's PR,
leaving the intended PR unwatched and unaware of CI failures or review findings
(Issue #4090, 2026-09-28 on Morrison-Lab/pds).
See also [`report-mistakes-proactively`](report-mistakes-proactively.md).

- **Do:** invoke `subscribe_pr_activity` only after `create_pull_request` returns,
  passing the exact number returned by the create call.
- **Don't:** batch a PR subscription tool call with the PR creation call.
- **Don't:** compute or predict a PR number based on recent repo activity.

**Review-only.**
Do not start ARDI, do not push fixes, and do not merge.
Leave the findings and stop unless asked to iterate.
A later request to iterate is a driving request.
The review you post still carries both representations, per `AGENTS.md`'s own review-only rule.

(UCD-SERG/shigella#31, 2026-08-25.)
