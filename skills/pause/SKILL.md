---
name: pause
description: "Pause the session; hooks stop demanding work."
user-invocable: true
allowed-tools:
  - Read
  - Write
---

# pause: stop new work until the user writes again

The user wants the session to stop starting new work for now:
no new agents, pushes, reviews, issues or hooks to write.
A bare `pause` or `/pause` counts.
So does a short note (at most 80 characters) after `/pause`, or after `pause` and a punctuation mark (`pause, back after lunch`).
`pause the video` is an ordinary request, not a pause.

## What the pause switches off

While the user's most recent prompt is a pause command, the Stop hooks below stop
asking the agent to act
([ai-config#3911](https://github.com/Morrison-Lab/ai-config/issues/3911)).
Eighteen other Stop hooks still block on their own while paused;
[ai-config#5901](https://github.com/Morrison-Lab/ai-config/issues/5901) tracks them.
`scripts/lib/session_pause.py` decides this from the transcript,
so there is no marker to write and nothing to clean up.

- Stop hooks that go through `stop_notice` in `scripts/lib/agent_notice.py`
  (`require-stopping-point`, the UMS reminders and most others)
  still show their note to the user, but no longer block the stop.
- `no-unshipped-commit` and `no-mistake-without-a-hook`,
  which block on their own, stay silent.

Hooks that only **refuse** an action stay on,
such as `no-unauthorized-merge` and `no-clobbering-push`.
A refusal never forces work, so a pause has no reason to turn one off.

## Procedure

1. Stop starting work: launch no agent, push nothing, post nothing new.
   Leave running background work alone unless the user asked to stop it too.
2. Write where things stand in the session notebook
   ([`session-lab-notebook`](../../shared/workflow/session-lab-notebook.md)),
   so the next prompt can pick up from it.
3. Reply in two or three lines:
   say the session is paused,
   name what is unfinished (an unpushed commit, an open PR, a running agent),
   and say that the next message from the user ends the pause.
   Name the Stop hooks that are quiet, so the pause is visible.

## Ending the pause

Any later prompt from the user ends it, including `back`, `resume` or new work.
The hooks fire again from that prompt on,
so pick up the unfinished items listed in step 3.
