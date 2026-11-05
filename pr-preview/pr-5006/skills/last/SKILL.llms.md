# last

`/last <instructions>` queues `<instructions>` after everything else — and, unlike `/also`, it *stays* last: a later `/also` slots in front of it, not behind it. Only another `/last` goes after a previous `/last`. It is the sticky tail of the queue family:

- `/first` — head of queue; may pause in-progress work to run now.
- `/next` — immediately after the current (in-progress) task.
- `/before <target>` — immediately before the referenced queued task.
- `/also` — tail of queue (a later `/also` goes after an earlier one).
- `/last` — sticky tail; stays last even as new `/also` tasks arrive.

## /last vs /also

Both go to the end, but they differ when *more* work arrives afterward:

- A task added with `/also` sits at the current tail; the next `/also` goes *after* it.
- A task added with `/last` sits behind all `/also` tasks and *stays* there — new `/also` tasks insert in front of it. Think “always run this at the very end.”

## How to handle it

1.  **Place the task at the very end** of the queue, behind any existing `/also` tasks.
2.  **Keep it pinned there.** When a new `/also` arrives later, insert that `/also` *in front of* the `/last` task, not after it.
3.  **Multiple `/last`s preserve order among themselves** — a second `/last` goes after the first (FIFO within the sticky-tail zone), and both stay behind all `/also` tasks.
4.  **Run it dead last**, once everything else (including later `/also` work) is done and verified. Report its outcome in the final wrap-up.

## Edge cases

- **Nothing else queued.** It is still last — which, with an otherwise empty queue, just means “do it after the current task.”
- **A `/first` or `/next` arrives later.** Those jump ahead (head / after-current as usual); the `/last` task stays at the very end regardless.
- **Good fits for `/last`:** final render, commit-and-push, cleanup, a wrap-up summary — anything that should bookend the session no matter how much more gets added.

## What this is not

- Not the same as `/also` — an `/also` task can be displaced from last by a newer `/also`; a `/last` task cannot.
- Not a priority bump — like `/also` it lowers urgency; it just guarantees the end position.

Back to top
