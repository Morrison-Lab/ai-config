Keep at least one agent working while any project repo has an open issue backlog.

Ezra, 2026-11-05 ([ai-config#4967](https://github.com/Morrison-Lab/ai-config/issues/4967)): "while there's an issue backlog in any of our project repos, keep at least one agent working on something".

## The rule

When the last working thread or session goes idle, and any project repo has an open issue that no thread, open PR or claim comment owns, the coordinator starts a thread on the top such issue.
Rank by priority label (`P1`, then `P2`, then `P3`), then by age.
Check the tracker, the live threads and project memory first, as [`triage-new-asks`](triage-new-asks.md) says.

An idle agent with an unowned backlog is a defect, not a rest.

## What the rule does not license

- It does not license merges.
  Merging still needs Ezra's `mwc`, except in repos with a standing grant for fully clean PRs.
- It does not relax the other limits: issue first, small PRs, no scope creep, FERPA, no browser, no force-push, no push to main.
- It does not apply when every open issue is owned.
  Then there is no unowned backlog to work.

## Mechanism

An hourly scheduled task, `trig_01N2XJVzro32Mtpv6ZrGLKPu`, fires into the project coordinator session.
When no thread is working, it has the coordinator start one on the top unowned issue ([ai-config#4968](https://github.com/Morrison-Lab/ai-config/issues/4968), created 2026-11-05 with Ezra's OK).
Hooks do not run in cloud sessions ([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)), so the scheduled task is the only enforcement there.
Update or delete that task rather than adding a second one.
