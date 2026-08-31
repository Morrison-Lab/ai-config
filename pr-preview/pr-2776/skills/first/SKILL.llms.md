# first

`/first <instructions>` means: **do this before anything else — even before finishing what you’re in the middle of.** It is the counter to [`also`](../../skills/also/SKILL.llms.md): `/also` appends to the tail of the queue, `/first` jumps to the head and can **preempt in-progress work**.

This is the highest-priority slot in the queue family:

- `/first` — head of queue; may pause in-progress work to run now.
- `/next` — immediately after the current (in-progress) task.
- `/before <target>` — immediately before the referenced queued task.
- `/also` — tail of queue.
- `/last` — sticky tail; stays last even as new `/also` tasks arrive.

## What fires this

The user types `/first` followed by one or more instructions, e.g.:

- `/first the build is broken on main — fix that before continuing`
- `/first revert the last edit, it was wrong`
- `/first answer this quick question, then go back to what you were doing`

## How to handle it

1.  **Pause in-progress work at a safe point.** Don’t abandon the current task in a broken state — finish the edit-in-hand, let a running command settle, or note exactly where you stopped. You are pausing, not discarding.
2.  **Do the `/first` task now**, ahead of the in-progress task and everything queued behind it.
3.  **Then resume.** Pick the displaced in-progress task back up where you left off, then continue the rest of the queue in its existing order.
4.  **Report the interruption.** Make clear you jumped the queue for the `/first` task, what its outcome was, and that you returned to the prior work.

## Edge cases

- **Nothing in progress.** If you’re idle, just do it immediately — it’s first by default.
- **Preempting would break something.** If stopping right now leaves the repo or a render half-done, reach the next safe checkpoint before switching — “safe point” beats “this instant.” Say so if it causes a brief delay.
- **Multiple `/first`s.** The most recent `/first` goes to the very head; earlier `/first`s sit just behind it (LIFO at the head), all still ahead of the displaced work.
- **The `/first` task depends on the in-progress work.** Then it can’t truly go first — tell the user, finish the prerequisite, and do the `/first` task as soon as it’s unblocked.

## What this is not

- Not a tail task — that’s [`also`](../../skills/also/SKILL.llms.md). `/first` raises urgency to the max.
- Not “next after the current task” — that’s [`next`](../../skills/next/SKILL.llms.md). `/first` may interrupt the current task; `/next` waits for it to finish.
- Not permission to leave things broken — pause cleanly, then resume the displaced work; never silently drop it.

Back to top
