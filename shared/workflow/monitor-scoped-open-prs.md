# Monitor scoped open PRs and MRs

Continuously derive and monitor open pull requests and merge requests in repositories the agent is actively working in.

Do not sweep every repository the agent can access.
Within an active repository, monitor only items that pass the PR scope test,
including items the agent opened, pushed to, or was explicitly handed to drive.
A repository is active only while the current session has a user-requested task there or is driving a scoped PR/MR there.
Repository access or a checked-out worktree alone does not make a repository active.
A cross-repository task explicitly requested by the user makes each named repository active for that task.

## Re-query at every wake

After each state-changing action and at every available wake,
re-query the scoped open set and inspect each item's mergeability, current-head CI, and review state.
When an item is terminally failed or has actionable feedback,
drive the appropriate repair, review, and verification cycle
only when repository membership is verified and the item passes the scope test.
Otherwise report the state to the user without mutating the item.
Continue monitoring until the item merges, closes, or the user explicitly releases the agent from it.
Queued, pending, or `waiting_for_resource` work is in progress, not an endpoint.

- **Do:** derive the scoped open PR/MR set in each repository the agent is actively working in at every monitoring pass, and start or re-arm a persistent monitoring loop using the session's available wake mechanism.
- **Do:** act on terminal CI failures, merge conflicts, and new review findings without waiting for a status prompt when repository membership is verified and the item passes the scope test.
- **Don't:** sweep or monitor every repository the agent can access, stop monitoring a scoped PR/MR because it was opened by someone else, because a job is queued, or because the latest action only started CI or review.
