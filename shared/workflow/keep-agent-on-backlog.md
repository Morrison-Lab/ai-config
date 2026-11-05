Keep at least one agent working while any project repo has an open issue backlog.

Ezra, 2026-11-05 ([ai-config#4967](https://github.com/Morrison-Lab/ai-config/issues/4967)): "while there's an issue backlog in any of our project repos, keep at least one agent working on something".

## The rule

When the last working thread or session goes idle, and any project repo has an open issue that no thread, open PR or claim comment owns, the coordinator starts a thread on the top such issue.
Rank by priority label (`P1`, then `P2`, then `P3`), then by age.
Check the tracker, the live threads and project memory first, as [`triage-new-asks`](triage-new-asks.md) says.

An idle agent with an unowned backlog is a defect, not a rest.

## A backlog thread keeps going

The thread that takes the top issue does not stop after one issue or one batch while unowned backlog remains (coordinator correction, 2026-11-05: a backlog thread stopped after finishing one split and a few closes, and had to be told to continue).
When the next issues are large, pick the most tractable and break off a small first slice that ships on its own, then continue to the next.
Stop only when every remaining issue is owned, waits on a person's decision, or cannot be worked with the access the session has, and say which of those it is.
Do not stop merely because the remaining issues look large.

## Deciding whether an agent is working

Do not rely on `list_threads` with `state: "working"` alone, because it can return an empty list while threads are active (measured 2026-11-05).
Also count any thread with a post or a PR event in the last 15 minutes, and read the live thread list rather than memory.

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
