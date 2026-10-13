# Don't get sidetracked from your primary task

Ezra (d-morrison), 2026-10-13 (ai-config#4488):
when you have a primary task, don't get sidetracked, including by the user's input;
if a tangential or irrelevant task or information gets added, do something to both stay on your main task and not lose track of the other topic;
delegate it to a subagent, fork your session, defer it for later through a tracking issue, add it to your to-do list, and/or use any other means available to you to keep independent lines of thought separate without losing track of any of them.
If the user explicitly tells you to change focus, that's a different case.

## Why

When an agent is executing a primary task, tangential ideas, minor auxiliary defects, or conversational remarks from the user frequently appear.
Abandoning or delaying the primary task to follow these tangents derails momentum, fragments worktrees, and leaves the original task unfinished.
Conversely, ignoring or dropping tangential insights entirely loses valuable context, discoveries, and follow-up work.
The solution is active separation:
maintain relentless progress on the critical path of the primary assignment while immediately capturing or delegating independent lines of thought.

## How

Keep independent lines of thought separate using the appropriate boundary mechanism:

- **Delegate to a subagent:**
  Dispatch an asynchronous subagent to investigate, research, or draft a tangential item while you keep working on the primary task.
- **Fork your session:**
  In harnesses that support session branching or forks, spin off a dedicated thread for the new line of inquiry.
- **Defer via tracking issue:**
  File a forge issue using [`defer-issue`](../../skills/defer-issue/SKILL.md) to record the reproduction steps, context, and follow-up scope so it can be picked up in a subsequent session.
- **Add to session task list:**
  Queue the item in your session's pending list or notes to execute sequentially once the primary task finishes.

### The explicit redirect exception

If the user explicitly directs you to stop, switch priorities, or change focus (e.g. "stop working on this, do X instead"),
obey that explicit instruction.
Even when changing focus on explicit user direction,
snapshot or stash the current worktree state first so progress is preserved.

## Summary

- **Do:** stay on your primary task until it reaches a clean stopping point or completion.
- **Do:** capture tangential topics immediately via subagents, tracking issues, or task lists so nothing is lost.
- **Do:** switch focus when the user explicitly instructs you to redirect priorities.
- **Don't:** chase tangential questions or minor side quests during primary task execution.
- **Don't:** drop or forget off-topic information and discovered defects when maintaining focus.

See [`defer-issue`](../../skills/defer-issue/SKILL.md), [`use-subagents`](use-subagents.md), and [`standing-habits-from-ezra`](standing-habits-from-ezra.md).
