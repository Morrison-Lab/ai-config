When starting a **new** piece of work, go **issue-first**: before branching,
editing, or opening a PR, make sure a tracking issue exists. Search the tracker
first; if no open issue covers the task, **file one** (`gh issue create` /
`glab issue create`), then proceed. Never jump straight into a PR without a
tracking issue behind it.

The issue is the durable record of intent, scope, and "done" criteria --- it
gives reviewers context, lets the PR auto-close it via `Closes #N`, and keeps
the work discoverable even if the PR stalls. Skip only when the task is already
tracked by an open issue.

This rule settles *whether* something is tracked, not *where* it goes.
An item whose deliverable is a decision rather than a diff belongs on the
discussion board instead, per
[`choose-issue-or-discussion`](choose-issue-or-discussion.md) --- so read "file
one" here as "file one in the right venue", which for actionable work is the
tracker.

When the issue is a **bug report**, include a minimal reproducible example
(a reprex --- <https://reprex.tidyverse.org/>) whenever you can. A reprex is
what a maintainer needs to confirm and fix the bug, and it's what they'll ask
for anyway, so providing it up front saves a round trip. The `reprexes` skill
helps reduce the problem to a minimal, self-contained example.

When filing an issue that contains a list of independent subissues, file each
subissue as a child issue linked under the parent (GitHub sub-issues feature:
`mcp__github__sub_issue_write` in remote sessions, or `gh api` with the
sub-issues endpoint in local sessions).

**That splitting rule has teeth, and they are worth stating: a PR's
`Closes #N` closes the whole issue, including every item in it the PR never
addressed.**
Read as tidiness, the rule is easy to skip when the second item feels like a
footnote.
The actual consequence is that GitHub cannot partially close an issue, so the
residual items are not deferred and not reopened --- they are silently gone,
and nothing in the merge, the PR, or the closed issue reports that anything
was dropped.

It is worse than an ordinary lost to-do, because a closed issue is *evidence
that the work was handled*.
A later reader searching the tracker finds it closed and reasonably concludes
every item in it was dealt with, so the loss is not merely silent but
actively misleading.

So before writing `Closes #N`, re-read #N and confirm the diff covers all of
it.
When it doesn't, either split the remainder into its own issue first, or
reference the parent with `Refs #N`, which links without closing.

- **Do:** split at filing time, or at the latest before the closing PR merges.
- **Do:** use `Refs #N` when a PR advances an issue without completing it.
- **Don't:** let `Closes #N` ride on an issue whose scope is wider than the
  diff.

(Morrison-Lab/ai-config#847, 2026-07-29: an issue was filed carrying a
primary bug and a secondary note, and the PR fixing the first said
`Closes #847`.
The second item survived only because the maintainer asked about it before the
merge, which is not a mechanism; it was split into #852 and shipped as #853,
and both PRs merged within the following half hour.
The splitting rule directly above already existed and was simply not applied
when #847 was filed, which is the argument for stating its consequence rather
than only its instruction.)
