# also

`/also <instructions>` means: **finish everything that came before this, then also do `<instructions>`.** The `/also` text is a tail task appended to the queue — it does not interrupt, reprioritize, or replace the work already underway.

It is the lowest-priority non-sticky slot in the queue family:

- `/first` — head of queue; may pause in-progress work to run now.
- `/next` — immediately after the current (in-progress) task.
- `/before <target>` — immediately before the referenced queued task.
- `/also` — tail of queue.
- `/last` — sticky tail; stays last even as new `/also` tasks arrive.

## What fires this

The user types `/also` followed by one or more instructions, e.g.:

- `/also run the spellchecker before you wrap up`
- `/also add a test for the new helper`
- `/also update the changelog once everything else is done`

The instructions after `/also` are the **deferred task**. Everything the user asked for *before* the `/also` (earlier in this message, or in earlier messages that you haven’t finished yet) is the **preceding work**.

## How to handle it

1.  **Identify the preceding work.** Look back over the current message and any still-unfinished requests from earlier in the conversation. If a task is in flight (mid-refactor, mid-render, waiting on a verification), that is preceding work.
2.  **Finish all of it first.** Do not start the `/also` task while anything that came before it is incomplete. The whole point of `/also` is “last, not now.”
3.  **Then do the deferred task.** Once the preceding work is genuinely done — verified, not just attempted — carry out the `/also` instructions as a normal request.
4.  **Report both.** In your wrap-up, make clear that the preceding work completed and then the `/also` task was done (or surface anything that blocked it).

## Edge cases

- **Nothing precedes it.** If there is no outstanding work (the `/also` is the only live request), just do it immediately — there is nothing to wait for.
- **Multiple `/also`s.** Handle them in the order given, all after the preceding non-`/also` work. They form a FIFO tail queue.
- **The deferred task depends on the preceding work.** That is the normal case and exactly why it is deferred — e.g. “spellcheck before wrapping up” needs the edits done first. Run it against the finished state.
- **The preceding work fails or is blocked.** Surface that first. Only skip ahead to the `/also` task if it is genuinely independent and still useful; otherwise tell the user why you stopped before reaching it.

## What this is not

- Not a priority bump — `/also` lowers urgency (do it last), it does not raise it.
- Not a reason to drop or shortcut the preceding work to get to the deferred task faster.
- Not a silent hand-off — always confirm the deferred task’s outcome in your recap.
- Not the sticky-tail variant — `/last` stays last even as new `/also` tasks arrive; `/also` tasks can be displaced by a later `/also`.

Back to top
