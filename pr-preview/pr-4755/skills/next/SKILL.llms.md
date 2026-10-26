# next

`/next <instructions>` means: **finish what you’re doing now, then do this before anything else that’s queued.** It slots a task immediately after the currently in-progress task — jumping the rest of the queue, but not interrupting work already in flight.

It sits between its siblings in the queue family:

- `/first` — head of queue; may pause in-progress work to run now.
- `/next` — immediately after the current (in-progress) task.
- `/before <target>` — immediately before the referenced queued task.
- `/also` — tail of queue.
- `/last` — sticky tail; stays last even as new `/also` tasks arrive.

## What fires this

The user types `/next` followed by one or more instructions, e.g.:

- `/next once this refactor is done, run the tests before moving on`
- `/next after the current edit, tweak the table styling`
- `/next handle this right after, ahead of the other queued items`

## How to handle it

1.  **Let the in-progress task finish** — to its normal, verified completion. Do not pause or preempt it (that’s `/first`).
2.  **Do the `/next` task immediately after**, ahead of everything else still queued.
3.  **Then continue** with the remaining queue in its existing order.
4.  **Report it in sequence.** Make clear the current task finished, then the `/next` task ran ahead of the rest of the queue.

## Edge cases

- **Nothing in progress.** With no task in flight, `/next` is effectively “do it now” — start it as the current task.
- **Multiple `/next`s.** The most recent `/next` slots immediately after the current task; earlier `/next`s follow it (LIFO right behind the current task), all still ahead of the older `/also` queue.
- **The `/next` task is tightly related to the current one.** Common case — it’s fine to fold it into the same work unit (e.g. same file, same render) as long as the current task’s result is verified first.
- **The current task is long.** `/next` still waits for it; if the user wanted to interrupt, they’d use `/first`.

## What this is not

- Not an interrupt — that’s [`first`](../../skills/first/SKILL.llms.md). `/next` waits for the current task to finish.
- Not a tail task — that’s [`also`](../../skills/also/SKILL.llms.md). `/next` jumps ahead of the rest of the queue, just not ahead of the task in flight.

Back to top
