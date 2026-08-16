# learn — low-friction staged capture

Jot down a candidate learning **without** deciding right now whether it belongs in committed memory. This is the staging half of a two-stage pipeline; [`promote-memory`](../../skills/promote-memory/SKILL.llms.md) is the review gate that later decides which staged candidates actually get promoted.

## Why a staging step at all

`record-learnings` and `memorize` both write straight into committed memory (`CLAUDE.md`, `memories/*.md`, or a repo’s project memory) the moment something looks worth remembering. That’s the right call when you’re confident — an explicit user correction, a clearly general fact. But not every candidate is that clear-cut mid-task: a pattern that might be a one-off, a preference stated once that might not generalize, a workaround whose root cause isn’t confirmed yet. Committing those immediately risks polluting the corpus with noise that later has to be found and pruned. `learn` defers that judgment call to a dedicated review pass instead of making it under time pressure mid-task.

## When this fires

- “log a learning”, “stage this as a learning”, “note this for later”, “jot this down”
- Proactively, for a discovery that seems worth keeping but you’re not confident enough to commit directly — genuinely uncertain generality, unconfirmed root cause, or a preference stated only once
- **Not** for a case `record-learnings`/`memorize` already handles confidently — an explicit “remember that…” instruction, or a clearly general, well-evidenced fact. Use those directly; staging is for the uncertain middle ground, not a mandatory detour for everything.

## Procedure

### 1. Write a raw candidate entry

Append (never overwrite) an entry to the staging file: `~/.claude/projects/<project-slug>/memory/learn-staging.md`. This is the same auto-memory directory `handoff`/`record-learnings`/`memorize` already use — it’s local to this machine and was never going to be committed regardless, so it’s a natural staging area distinct from the ai-config repo’s actual committed corpus (`CLAUDE.md`, `memories/*.md`).

Each entry is a dated bullet, not a polished write-up — capture speed matters more than form here:

``` markdown
- 2026-07-06: [candidate] <what you noticed, one or two sentences, with the
  concrete evidence — a command, a file:line, a quoted user statement>
```

Don’t categorize, don’t decide a destination file, don’t check for duplicates against the committed corpus — that’s `promote-memory`’s job, not this step’s. The entire point of `learn` is that logging it costs almost nothing.

### 2. Confirm briefly

One line: “logged to staging” is enough. Don’t produce a report.

## Relationship to other skills

- **`promote-memory`** — the review gate this feeds. Staged entries sit in `learn-staging.md` until that skill runs (on demand, or periodically) and decides promote / discard / hold for each.
- **`record-learnings`** / **`memorize`** — the direct-write path for learnings confident enough not to need review. `learn` doesn’t replace either; it’s the additional path for the uncertain middle ground both of those skip past by writing immediately.
- **`ums`** — a full-session sweep that also writes directly to committed memory. `promote-memory` can absorb a `learn-staging.md` review as part of a `ums` pass, or run standalone.

## Anti-patterns

- ❌ Using `learn` for everything “to be safe” — most learnings are clear enough for `record-learnings`/`memorize` to write directly; reserve staging for genuine uncertainty, or the staging file becomes a dumping ground no one reviews.
- ❌ Deciding a destination file or checking for duplicates at staging time — that’s `promote-memory`’s job; keep this step fast and undecided.
- ❌ Losing track of a staging file that never gets reviewed — if `learn-staging.md` is piling up unreviewed, run `promote-memory` rather than letting it grow indefinitely.

Back to top
