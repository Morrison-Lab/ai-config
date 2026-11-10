Keep at least one agent working while any project repo has an open issue backlog.

Ezra, 2026-11-05 ([ai-config#4967](https://github.com/Morrison-Lab/ai-config/issues/4967)): "while there's an issue backlog in any of our project repos, keep at least one agent working on something".

## The rule

When any project repo has an open issue that no thread, open PR or claim comment owns, the coordinator starts a thread on the top such issue.
A busy thread does not satisfy the rule.
With any thread busy, an issue filed as owed follow-up would never be picked up (gha#1563, 2026-11-07: filed, no owner, nothing moved;
[ai-config#5056](https://github.com/Morrison-Lab/ai-config/issues/5056)).
Each P1 issue, and each issue a thread files as owed follow-up, gets an owner within one hour of being filed.
Rank by priority label (`P1`, then `P2`, then `P3`), then by age.
Check the tracker, the live threads and project memory first, as [`triage-new-asks`](triage-new-asks.md) says.

An idle agent with an unowned backlog is a defect, not a rest.

- **Do:** give each P1 and each owed follow-up an owner within an hour, while other threads are busy, because the issue waits on its own clock and not on theirs.
- **Don't:** write or apply a trigger such as "when no thread is working" to an issue that has a deadline.

The check is [`scripts/check-unowned-issues.py`](../../scripts/check-unowned-issues.py) (below), and the reviewer layer is the "Filed issues with no owner" item in [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md#filed-issues-with-no-owner).

## A backlog thread keeps going

The thread that takes the top issue does not stop after one issue or one batch while unowned backlog remains (coordinator correction, 2026-11-05: a backlog thread stopped after finishing one split and a few closes, and had to be told to continue).
When the next issues are large, pick the most tractable and break off a small first slice that ships on its own, then continue to the next.
Stop only when every remaining issue is owned, waits on a person's decision, or cannot be worked with the access the session has, and say which of those it is.
Do not stop merely because the remaining issues look large.

## Finding the unowned issues

Run `python3 scripts/check-unowned-issues.py` for the list.
It reads open P1 and P2 issues, and any issue labeled `owed-followup`, in lds, mds, pds, sds, mcs, psw, ai-config, gha and macros, and drops each one with a linked open PR or a claim comment.
It exits 1 when a P1 issue, or an issue labeled `owed-followup`, has been unowned for more than an hour.
It cannot see threads, so the coordinator checks the live thread list for each issue it reports before starting a thread on it.
It exits 2 when a repo cannot be read, after reporting the rest.
The check works on its own: it does not depend on the scheduled task.

## Deciding whether an agent is working

Do not rely on `list_threads` with `state: "working"` alone, because it can return an empty list while threads are active (measured 2026-11-05).
Also count any thread with a post or a PR event in the last 15 minutes, and read the live thread list rather than memory.

## What the rule does not license

- It does not license merges.
  Merging still needs Ezra's `mwc`, except in repos with a standing grant for fully clean PRs.
- It does not relax the other limits: issue first, small PRs, no scope creep, FERPA, no browser, no force-push, no push to main.
- It does not apply when every open issue is owned.
  Then there is no unowned backlog to work.

## Owners stay active

Checking that some thread is working is not enough ([ai-config#5088](https://github.com/Morrison-Lab/ai-config/issues/5088)).
On 2026-11-07 the ids owner thread sat idle from 09:56Z to 19:20Z while its repo had open issues and PRs, and the check said "no action" because other threads were working.

Every hourly run also reads the last activity of each owner thread listed in project memory.
It restarts any owner with no post or PR event in the last 60 minutes whose repo has an open issue or PR, by messaging that thread or starting a replacement.
An owner whose repo has nothing open is left alone.
"Any thread working" never ends the run early.

## Mechanism

An hourly scheduled task, `trig_01N2XJVzro32Mtpv6ZrGLKPu`, fires into the project coordinator session ([ai-config#4968](https://github.com/Morrison-Lab/ai-config/issues/4968), created 2026-11-05 with Ezra's OK).
Each firing has the coordinator run the check above.
The coordinator starts a thread on every issue the check reports as overdue, whether or not other threads are working.
It also starts a thread on the top unowned issue, whether or not other threads are working.
Its prompt exists only in the scheduled task, so this file holds the source text, and the task is updated from it.
Prompt as of 2026-11-07:

> Hourly backlog check (Ezra's rule, ai-config#4967 / #4968 / #5088).
> Step 1, owners: read the last activity of every owner thread listed in project memory with read_thread, not list_threads with state "working", which can return empty.
> Restart any owner with no post or PR event in the last 60 minutes whose repo has an open issue or PR, by message_thread or a new thread, and say which you restarted.
> Step 2, backlog, whether or not any thread is working: run `python3 scripts/check-unowned-issues.py` from an ai-config checkout and start a thread on every issue it reports OVERDUE.
> Then find the top open issue that no thread, open PR or claim comment owns, across the project repos (lds, mds, pds, sds, mcs, psw, ai-config, gha, macros): rank by P1, P2, P3 label, then by age, and check live PR and thread state first rather than trusting memory.
> Start a thread on it.
> Standing limits apply: issue first, small PRs, no merges without mwc or a standing grant, FERPA, no browser use, never Codex, never force-push or push to main.
> Reply "no action" only after step 1 restarted nothing and step 2 found nothing to start.

Hooks do not run in cloud sessions ([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)), so the scheduled task is the only enforcement there.
Update or delete that task rather than adding a second one.

## While a PR waits, report hourly and keep working

[ai-config#5116](https://github.com/Morrison-Lab/ai-config/issues/5116).
On 2026-11-08 an owner thread posted nothing for 90 minutes while its PR waited in the merge queue, and the coordinator's hourly check could not tell a queued thread from a stalled one.

- **Do:** while a PR waits, take the next backlog item, and post one status to the coordinator per hourly check, naming the PR, its head and what it waits on.
- **Don't:** go silent because the PR is queued, or merge main into a queued PR that is already clean.

`hooks/no-owner-silence-while-pr-waits.py` blocks a stop once per user turn when the thread has created or subscribed to a PR, has not resolved itself, and its last `post_message` or `message_coordinator` is over an hour old.
A Stop hook can read that time, because every transcript entry carries a timestamp.
It cannot read whether the PR is still open, so a merged PR in an unresolved thread also triggers it.
Hooks do not run in cloud sessions ([#2004](https://github.com/Morrison-Lab/ai-config/issues/2004)), so the hourly check above is the enforcement there.
