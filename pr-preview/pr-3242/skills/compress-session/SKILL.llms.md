# compress-session — deliberate pre-compaction distillation

Claude Code auto-compacts long conversations on its own once the context window fills up (see [What survives compaction](https://code.claude.com/docs/en/context-window#what-survives-compaction)). The automatic pass guesses what to keep. This skill runs **before** that happens so a higher-fidelity, structured distillation — one the agent actually controls — is what carries forward, using two mechanisms Claude Code already provides rather than any custom hook:

1.  **Auto memory (`MEMORY.md`)** is re-injected from disk automatically after any compaction — no hook needed. Writing the distillation there is enough to survive compaction.
2.  **A focused manual `/compact`** — running `/compact focus on <what matters>` before the automatic pass kicks in lets the summary keep what you choose, instead of what the automatic pass guesses.

## When this fires

- “compress the session”, “distill context before compacting”, “summarize before compaction”
- Proactively, without being asked, when the conversation is visibly long and compaction looks imminent (many tool calls, a long back-and-forth, an explicit context-limit warning from the harness)

## What this is not

- Not `checkpoint` — that’s a deliberate mid-task snapshot triggered by task *phase*, written to its own topic file under the same memory directory (not `MEMORY.md` itself, since it doesn’t need to survive compaction automatically the way this skill’s distillation does). See `checkpoint`’s distinction table.
- Not `handoff` — that’s for ending/pausing the session; this skill doesn’t end anything, it just makes sure the parts worth keeping survive the *next* compaction, automatic or manual.
- Not a way to keep the raw conversation — compaction still replaces message history with a summary regardless. This skill only makes sure a deliberately-chosen distillation, not just the automatic pass’s guess, is what that summary (or `MEMORY.md`) preserves.

## Procedure

### 1. Write the distillation into `MEMORY.md`

`MEMORY.md` lives at `~/.claude/projects/<project>/memory/MEMORY.md` (the same auto-memory directory `handoff`/`checkpoint`/`memorize` use) and its first 200 lines or 25KB, whichever is smaller, are re-injected into context automatically after every compaction — this is the load-bearing property this skill relies on. Keep the entry itself short and move real detail into a separate topic file in the same directory (referenced from `MEMORY.md`), since only `MEMORY.md` itself is guaranteed to reload after compaction — topic files reload only when Claude reads them again.

Capture, concisely:

- **The task and its current state** — what’s being done, what’s done, what’s left.
- **Decisions made and why** — especially anything the automatic pass might compress away as “detail” but that later steps depend on (a chosen approach, a ruled-out alternative and why).
- **Concrete facts gathered this session** — file:line pointers, PR/issue numbers, verified claims (e.g. from a research pass) that would be expensive to re-derive.
- **Next action** — the specific next step.

Update the existing `MEMORY.md` entry for this task in place rather than appending a new one each time — `MEMORY.md` has a strict size budget for what auto-reloads, so a growing pile of stale entries pushes the current, relevant one past the 200-line/25KB cutoff.

### 2. Trigger a focused compact yourself, rather than waiting

Once the distillation is written, you can additionally run `/compact focus on <what to keep>` right away instead of waiting for the automatic pass. Per [context-window.md’s “When your context fills up” section](https://code.claude.com/docs/en/context-window#when-your-context-fills-up): “The summary keeps what you choose instead of what the automatic pass guesses is important.” This is optional (step 1 alone already protects the distillation), but worth doing when you know compaction is imminent and want the *conversation summary itself* — not just `MEMORY.md` — to reflect a deliberate choice.

### 3. Confirm briefly

State that the distillation was written to `MEMORY.md` (and whether a focused `/compact` was also triggered). Don’t produce a long report — this is meant to be a quick, low-ceremony action.

## Relationship to other skills

- **`checkpoint`** — the deliberate, phase-triggered sibling that writes to its own topic file rather than `MEMORY.md` itself, because it doesn’t need the auto-reload-after-compaction property. See its distinction table for the trigger/scope difference.
- **`handoff`** — the session-end/pause counterpart; run that instead when the session is actually stopping, not just compacting.
- **`memorize`** — general-purpose fact persistence via the same auto-memory mechanism; this skill is the specialized “protect the highest-value facts against the next compaction” case, with the added `/compact focus` trigger.

## Anti-patterns

- ❌ Assuming a custom `PreCompact`/`SessionStart` hook is needed to survive compaction — auto memory already re-injects `MEMORY.md` automatically; don’t add hook complexity for something the harness already does.
- ❌ Writing the distillation to a topic file only, with nothing in `MEMORY.md` itself — topic files don’t auto-reload after compaction, only `MEMORY.md`’s first 200 lines/25KB do.
- ❌ Appending a new `MEMORY.md` entry per compaction instead of updating the task’s existing entry in place — bloats `MEMORY.md` past its auto-load budget and pushes the current entry out.

Back to top
