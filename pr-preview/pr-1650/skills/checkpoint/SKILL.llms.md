# checkpoint — deliberate mid-task snapshot

Bank a durable snapshot of where a long task stands **without stopping the session** — the user keeps working, or the agent keeps going, right after writing it. This is the lightweight, frequent counterpart to [`handoff`](../../skills/handoff/SKILL.llms.md): `handoff` is a heavier session-end/pause snapshot (branch state, unpushed commits, running jobs, a PR note); `checkpoint` is a quick “here’s what’s been decided and done so far,” written mid-task so a crash, a context compaction, or a session restart doesn’t lose the plan.

## When this fires

- “checkpoint”, “save a checkpoint”, “snapshot where we are”, “note our progress”
- Proactively, without being asked, at natural stop-points inside a long task:
  - right before a risky or hard-to-reverse step (a force-push, a destructive migration, a large refactor) — so the pre-step state is recoverable
  - immediately after finishing a distinct phase of a multi-phase task (e.g. “design agreed, starting implementation”)
  - before a long-running operation whose completion you might not be present for (kicking off a background build, handing work to a subagent, before a `ScheduleWakeup`)

Skip it for short tasks with no distinct phases — there’s nothing worth snapshotting yet.

## Distinction from `compress-session` and `handoff`

Three different triggers, three different jobs — don’t conflate them:

| Skill | Trigger | Session continues? | What it captures |
|----|----|----|----|
| `checkpoint` | Deliberate, mid-task | Yes | Plan state, decisions, next actions |
| `compress-session` | Approaching auto-compaction | Yes (context shrinks) | A structured distillation of the whole conversation so far |
| `handoff` | Ending/pausing the session | No | Full resumption state: branch, unpushed commits, running jobs, PR note |

A `checkpoint` note is a strict subset of what `handoff` captures — it skips the branch/job/PR-note mechanics because the session isn’t ending. If you’re about to genuinely stop, run `handoff` instead (or in addition, if the checkpoint predates the stop by a while and the state has moved on).

## Procedure

### 1. Write the checkpoint note

Capture, concretely, in a short note (not a session history — this is a snapshot, not a transcript):

- **What’s been decided** — the plan or approach agreed on so far, and any option explicitly ruled out (so it isn’t re-litigated later).
- **What’s done** — concrete progress: files touched (`path:line` pointers, not just names), commits made, PRs/issues opened.
- **What’s next** — the specific next action, not a vague “continue implementing.”
- **Anything fragile** — a value that might go stale (a fetched API result, a timestamp), an assumption worth re-verifying if much time has passed before resuming.

Save it as a topic file in the project’s auto-memory directory (the same one `handoff`/`memorize` write to, and Claude’s own auto memory uses for `MEMORY.md`): `~/.claude/projects/<project-slug>/memory/checkpoint-<slug>.md`. Unlike `MEMORY.md` itself, a topic file isn’t auto-reloaded after compaction (only `MEMORY.md`’s first 200 lines/25KB are) — that’s fine here, since a checkpoint’s job is resuming after a deliberate pause, not surviving mid-session compaction (that’s `compress-session`’s job). Reuse (update in place) an existing checkpoint file for the same task rather than piling up one file per checkpoint — a checkpoint supersedes the last one for the same task, it doesn’t append to a log.

### 2. Confirm briefly

One or two lines: what was checkpointed, and where. This isn’t a session wrap-up, so don’t produce a long report — the point is that it happened, not a recap of it.

## Relationship to other skills

- **`handoff`** — the heavier session-end/pause counterpart; see the distinction table above.
- **`compress-session`** — the pre-auto-compaction counterpart; see the distinction table above. The two can coincide (a checkpoint written just before compaction hits also happens to serve as compression fodder), but they’re triggered independently.
- **`wrap-up`** — closes out the *whole* session (every open PR/issue/branch) plus a UMS pass; `checkpoint` is scoped to the current task’s plan state, not the whole session’s state.
- **`memorize`** — general-purpose fact persistence; `checkpoint` is the specialized “resumable task state” case, structured like `handoff`’s note rather than a single durable fact.

## Anti-patterns

- ❌ Writing a checkpoint for every trivial step — reserve it for genuine phase boundaries or risky steps, or it becomes noise no one reads back.
- ❌ Treating a checkpoint as a full `handoff` — it doesn’t need branch/job/PR state; if you need that too, run `handoff`.
- ❌ Appending a new file per checkpoint instead of updating the task’s one checkpoint file in place.

Back to top
