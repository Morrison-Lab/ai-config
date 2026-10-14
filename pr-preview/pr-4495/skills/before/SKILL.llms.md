# before

`/before <target> <instructions>` inserts `<instructions>` into the queue **immediately before** `<target>` — an existing queued task — instead of at a fixed position. It is the positional member of the queue family:

- `/first` — head of queue; may pause in-progress work to run now.
- `/next` — immediately after the current (in-progress) task.
- `/before <target>` — immediately before the referenced queued task.
- `/also` — tail of queue.
- `/last` — sticky tail; stays last even as new `/also` tasks arrive.

## Resolving `<target>`

The word(s) right after `/before` name the task to insert ahead of:

- **`that`** — the most recently added/queued task (the common case: `/before that <instructions>`).
- **A short description** — match it against the queued tasks (“/before the render”, “/before the spellcheck”). Pick the best match; if two are equally plausible, ask which.
- If no target resolves (nothing queued, or no match), treat it like `/next` — do it right after the current task — and say so.

## How to handle it

1.  **Locate the target task** in your working queue (the todo list).
2.  **Insert the new task immediately before it**, pushing the target and everything after it back one slot. Do not preempt the in-progress task (that is `/first`).
3.  **Finish the current task**, then work the queue in the new order — the inserted task now runs just before its target.
4.  **Report the placement** — note that you slotted it in before `<target>`.

## Edge cases

- **Target is the in-progress task.** “Before” something already running means interrupting it — that is `/first`, not `/before`. Point the user there, or treat it as `/first` if they clearly mean “do this now.”
- **Multiple `/before that` in a row.** Each `that` refers to the most recently added task at the moment it is issued, so they chain naturally in front of it.
- **Target already done.** If the referenced task has completed, there is nothing to go before — fall back to `/next` and say so.

## What this is not

- Not head-of-queue (`/first`) or tail (`/also` / `/last`) — it is relative positioning before a named task.
- Not an interrupt — the current in-progress task still finishes first.

Back to top
