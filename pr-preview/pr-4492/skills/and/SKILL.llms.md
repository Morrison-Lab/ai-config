# and

`/and <revision>` amends the **previous command** — it folds `<revision>` into the instruction the user just gave, rather than queuing a separate task. Think of it as editing the last request in place: same target, same queue position, now with the added or changed detail.

## What fires this

The user types `/and` followed by a revision to what they just asked, e.g.:

- (after “make the header blue”) `/and bold`
- (after “/also add a test”) `/and put it in tests/testthat/`
- (after “remove that paragraph”) `/and the one above it too`

## How to handle it

1.  **Identify the previous command** — the most recent explicit instruction the user gave within the current exchange (the one immediately before this `/and`), whether it is done, in progress, or queued. If the nearest explicit instruction is more than a few turns back or the target is ambiguous, ask the user to clarify rather than guessing.
2.  **Merge the revision into it.** Treat the previous command + `/and <revision>` as a single combined instruction.
    - Previous command **not yet started** → update the queued task in place (same position) with the revision.
    - **In progress** → apply the revision as part of the same work.
    - **Just completed** → redo/adjust that work to incorporate the revision; don’t start an unrelated new task.
3.  **Do not change its queue position.** `/and` revises; it does not reprioritize. (Use `/first` / `/next` / `/before` / `/also` / `/last` to position a *new* task.)
4.  **Report the amended result**, not two separate outcomes.

## Edge cases

- **No clear previous command.** If nothing precedes it, treat the `/and` text as a standalone instruction and say so.
- **Chained `/and`s.** Each one revises the same previous command, accumulating revisions onto that single task.
- **The revision conflicts with the previous command.** The `/and` wins for the conflicting part (it is a revision); keep the rest.
- **Ambiguous whether it is a revision or a new task.** If `/and <x>` reads as an independent task rather than an amendment, ask — or treat it as `/also` and note the assumption. Default to `/also` (tail) rather than a higher-priority slot so a misread never preempts work the user already queued.

## What this is not

- Not a queue-position command — those are `/first` / `/next` / `/before` / `/also` / `/last`. `/and` edits the previous task; it doesn’t add or move one.
- Not a new task by default — it extends the previous one.

Back to top
