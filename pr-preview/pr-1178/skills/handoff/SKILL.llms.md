# handoff

Capture everything the next session (or a context reset) needs to resume this work cleanly, then persist it as a **project memory** and — if a PR/MR is in play — a paused-state note on the thread.

This is the manual trigger for the standing “always leave handoff notes proactively when pausing” policy in `memories/preferences.md`: *always* leave pick-up notes when pausing, especially with long-running jobs in flight. Run it on demand, or fire it yourself proactively when you’re about to pause and something is still running.

## When this fires

- The user ends or pauses a session: “handoff”, “leave myself notes”, “pause and save state”, “wrap up for now”, “I’m stopping here”.
- **Proactively**, without being asked, whenever you pause while a job outlives the session — SLURM arrays, long builds, CI runs, background tasks, remote agents.

Skip it for a clean stopping point with nothing outstanding (no jobs, no unpushed commits, no open decisions) — there’s nothing to hand off.

## Step 1 — Snapshot the state

Gather the facts. Run what’s relevant; don’t invent values.

``` bash
TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z" # local-time stamp (Pacific)
git rev-parse --abbrev-ref HEAD                  # branch
git log --oneline -1                             # local HEAD
git log --oneline @{u}..HEAD 2>/dev/null         # UNPUSHED commits
git rev-parse --short @{u} 2>/dev/null           # pushed HEAD on remote
git status --short                               # dirty / untracked
squeue -u "$USER" 2>/dev/null                    # SLURM jobs (if on a cluster)
```

Also note anything not visible to git: background tasks you launched (IDs + output paths), CI runs you’re waiting on, archived/backup directories, and any **open decisions** the user still has to make.

## Step 2 — Write (or update) the handoff memory

Write to the project memory directory (`~/.claude/projects/<project-slug>/memory/`). Reuse an existing in-flight handoff file if one already covers this work (update it in place) rather than creating a duplicate. Frontmatter `type: project`. Convert relative dates to absolute. Capture, concretely:

- **Where things stand** — current verdict/CI state, what’s done vs pending.
- **Unpushed/uncommitted work** — commit SHAs held back and *why*.
- **In-flight jobs** — exact IDs, how to check status, expected outputs + paths, rough ETA.
- **Backups/archives** — paths to anything moved aside, and when it’s safe to delete.
- **Open decisions** — questions still owned by the user.
- **Pick-up steps** — a numbered, copy-pasteable sequence to resume. End with a one-line “next session, in one line” summary.

Link related memories with `[[name]]` (e.g. any runtime-quirk memory the pick-up steps depend on). Then add a one-line pointer to `MEMORY.md` (or update the existing one).

## Step 3 — Post a paused-state note on the active PR/MR

If the work has an open PR/MR and you’ve **claimed** it (see `claim-pr`), post a short note so the `@claude` bot and other sessions don’t push conflicting changes — especially when you have unpushed local commits or running jobs.

``` bash
gh pr comment <N> --body "⏸️ **Local session paused** (<local timestamp>) — still claimed, paws off.

<2-4 bullets: in-flight jobs + IDs, unpushed local commits and why held, what runs next>

Please don't push to this branch in the meantime."   # COMMENT_PR
```

If the work is genuinely *finished* (merged/closed, nothing outstanding), post a closing/unclaim note instead per `claim-pr` — don’t leave a stale “paused” claim.

## Step 4 — Confirm

Give the user a compact recap: what was snapshotted, where the memory lives, the PR note link, and the one-line pick-up summary. Include a local-time stamp.

## Relationship to other skills

- `memories/preferences.md` (the “always leave handoff notes proactively” bullet) — the *policy* (when to hand off automatically); this skill is the *action*.
- `memorize` / `remember` — general fact persistence; `handoff` is the specialized “save session state” case.
- `claim-pr` — owns the claim/unclaim lifecycle; `handoff` posts the *paused* note within an existing claim.
- **`checkpoint`** — a lighter, deliberate mid-task snapshot for a session that *isn’t* ending: plan state, decisions, next actions, no branch/job/PR mechanics. Run `handoff` when actually stopping; `checkpoint` when just banking progress mid-task.
- **`compress-session`** — distills the conversation into auto memory before the context window fills up, so a compaction (not a session end) doesn’t lose what matters. `handoff` ends the session; `compress-session` keeps it going with a smaller, curated context.

Back to top
