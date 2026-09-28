# Keep a running on-disk session lab notebook

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#keep-a-running-on-disk-session-lab-notebook) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Maintain a "lab notebook" for each session --- a dated, append-only file written to *as work happens*, not only when pausing --- so that if the session is interrupted with no clean exit (compaction, a forced `/clear`, a crash, a SLURM walltime death), the trail is already on disk and a later session (or I) can pick it up.
The whole point is surviving an interruption that never gives you a clean stop, so the file must live on disk and be updated frequently, not held in context and flushed at the end.

**Where.** In the session's project auto-memory directory, as a `session-YYYY-MM-DD[-slug].md` file, with a one-line pointer added to that directory's `MEMORY.md` like any other memory.
One notebook per session; start it near session start and keep appending.

**Cadence --- frequently, and to disk right away.**
Append a short, timestamped entry at each state change worth resuming from: a task or subtask started, a decision made or a question I answered, a PR/issue opened, a branch cut, a job launched (SLURM/background/CI, with its id), a blocker hit, a checkpoint reached.
Not every tool call --- that's noise --- but every step whose loss would cost real reconstruction.

**What each entry carries.** Enough for a cold reader to resume without this conversation: what we're doing and why, what's done versus in flight (branches, open PRs/issues, running jobs and their ids), open questions and decisions, and the next concrete step.

**Relationship to the pause-time and context conventions.** The notebook is the *running recorder*; the others are point-in-time:

- `handoff` writes a single snapshot *when you pause cleanly* --- the notebook is its always-current substrate, so a handoff can finalize or point at the notebook instead of rebuilding state from scratch.
- `compress-session` distills the *conversation context* to survive compaction --- the notebook is a durable on-disk trail, not a context-window optimization.
- [`CLAUDE.md`'s `/clear` flag](../../CLAUDE.md#flag-good-moments-to-clear-in-long-running-sessions) is about *choosing* a clean stop --- the notebook is insurance for the stops you don't choose.

Fold a finished session's notebook into durable memory (or prune it) during UMS once its content is captured elsewhere, so the memory directory doesn't accumulate stale logs.
