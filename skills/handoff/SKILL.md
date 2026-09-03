---
name: handoff
description: "Snapshot state to forge and memory."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# handoff

Capture everything the next session (or a context reset) needs to resume this
work cleanly, then **post it on the forge** --- GitHub, GitLab, or whichever
tracker owns the work --- and keep a copy as a **project memory**.

The forge post is the required half, and the memory file is the backup.
A memory file lives on one machine, under one account, in a directory no
teammate and no other session can read, so a handoff that exists only there is
invisible to everyone it was written for.

This is the manual trigger for the standing "always leave handoff notes
proactively when pausing" policy in `memories/preferences.md`: *always* leave
pick-up notes when pausing, especially with long-running jobs in flight. Run it
on demand, or fire it yourself proactively when you're about to pause and
something is still running.

## When this fires

- The user ends or pauses a session: "handoff", "leave myself notes", "pause
  and save state", "wrap up for now", "I'm stopping here".
- **Proactively**, without being asked, whenever you pause while a job outlives
  the session — SLURM arrays, long builds, CI runs, background tasks, remote
  agents.

Skip it for a clean stopping point with nothing outstanding (no jobs, no
unpushed commits, no open decisions) — there's nothing to hand off.

## Step 1 — Snapshot the state

Gather the facts. Run what's relevant; don't invent values.

```bash
TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z" # local-time stamp (Pacific)
git rev-parse --abbrev-ref HEAD                  # branch
git log --oneline -1                             # local HEAD
git log --oneline @{u}..HEAD 2>/dev/null         # UNPUSHED commits
git rev-parse --short @{u} 2>/dev/null           # pushed HEAD on remote
git status --short                               # dirty / untracked
squeue -u "$USER" 2>/dev/null                    # SLURM jobs (if on a cluster)
```

Also note anything not visible to git: background tasks you launched (IDs +
output paths), CI runs you're waiting on, archived/backup directories, and any
**open decisions** the user still has to make.

## Step 2 — Write (or update) the handoff memory

This is the backup copy, and Step 3 posts the same content somewhere others can
read it.

Write to the project memory directory
(`~/.claude/projects/<project-slug>/memory/`). Reuse an existing in-flight
handoff file if one already covers this work (update it in place) rather than
creating a duplicate. Frontmatter `type: project`. Convert relative dates to
absolute. Capture, concretely:

- **Where things stand** — current verdict/CI state, what's done vs pending.
- **Unpushed/uncommitted work** — commit SHAs held back and *why*.
- **In-flight jobs** — exact IDs, how to check status, expected outputs + paths,
  rough ETA.
- **Backups/archives** — paths to anything moved aside, and when it's safe to
  delete.
- **Open decisions** — questions still owned by the user.
- **Pick-up steps** — a numbered, copy-pasteable sequence to resume. End with a
  one-line "next session, in one line" summary.

Link related memories with `[[name]]` (e.g. any runtime-quirk memory the
pick-up steps depend on). Then add a one-line pointer to `MEMORY.md` (or update
the existing one).

## Step 3 --- Post the handoff on the relevant forge thread(s)

Post the handoff every time, including when no PR/MR is in play.
The forge is the one place a later session, a reviewer, and the user all
already look, so it is where the pick-up state belongs.
Route by what the work actually has:

- **An open PR/MR** --- comment on it, in the paused-claim form below.
- **An issue and no PR/MR** --- comment on the issue, or edit the issue body
  when the state describes the work rather than reporting on it.
- **Neither** --- file an issue carrying the handoff, per
  [`issue-first`](../../shared/workflow/issue-first.md), and comment there.
- **State that outlives the thread** --- commit it to a file in the repo (a
  runbook, a design note) and link that file from the comment.

Combine these freely: a committed file for the long-lived detail, an issue for
the open decisions, a PR comment for the paused claim.
End every comment you post with the agent-disclosure marker, per
[`disclose-agent-authorship`](../../shared/workflow/disclose-agent-authorship.md).
On GitLab, `glab` mirrors each `gh` command below.
[`AGENTS.md`](../../AGENTS.md)'s membership gate still governs the post: verify
membership in that repository first, and where it is unverified, keep the
memory file and ask the user before posting.

If the work has an open PR/MR and you've **claimed** it (see `claim-pr`), the
note also stops the `@claude` bot and other sessions pushing conflicting
changes --- especially when you have unpushed local commits or running jobs.
Post it only when that PR still passes `memories/reviewing-prs.md`'s scope
test: a claim confers no scope, so if the PR has since fallen out of scope,
skip the note, route the handoff to the issue instead, and report the PR to
the user.

```bash
gh pr comment <N> --body "⏸️ **Local session paused** (<local timestamp>) — still claimed.

<the Step 2 handoff content: where things stand, in-flight jobs + IDs, unpushed
local commits and why held, open decisions, numbered pick-up steps>

Please hold off on pushing to this branch in the meantime.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_PR
```

If the work is genuinely *finished* (merged/closed, nothing outstanding), post a
closing/unclaim note instead per `claim-pr` — don't leave a stale "paused" claim.

- **Do:** post the handoff to the forge thread that owns the work every time
  you pause, and keep the memory file as the backup copy.
- **Do:** route to the issue --- filing one when none exists --- when the work
  has no open PR/MR to comment on.
- **Do:** end each posted comment with the agent-disclosure marker.
- **Don't:** treat a written memory file as a completed handoff; nobody but
  this account on this machine can read it.
- **Don't:** skip the post because there is no PR --- an issue thread, a
  committed file, or a new issue is the route.
- **Don't:** post to a repository whose membership is unverified --- hold the
  handoff in memory and ask the user.

## Step 4 --- Confirm

Give the user a compact recap: what was snapshotted, where the memory lives,
links to every forge thread the handoff was posted on, and the one-line pick-up
summary.
Include a local-time stamp.

## Step 5 --- Retire a handoff once its state is resolved

A handoff is a **snapshot with an expiry**, not a durable record.
Everything it carries --- a branch, an unpushed commit, a running job, an open
decision --- either resolves or is superseded.
Once all of it has, the handoff is not merely redundant.
It is **actively misleading**, because a later reader meets it as orientation
and cannot tell which parts still hold.

**You may clear an out-of-date handoff without asking.**
Standing permission, given 2026-08-16.
The judgment worth exercising is whether it is genuinely stale, not whether you
are allowed to remove it.

Staleness is derivable rather than a matter of taste, so derive it.
Take every PR, issue, branch, and job id the handoff names, and check each:

```bash
grep -oE '#[0-9]+' <handoff> | sort -u | while read -r n; do
  printf "  %s %s\n" "$n" "$(gh pr view "${n#\#}" --json state -q .state 2>/dev/null \
    || gh issue view "${n#\#}" --json state -q .state 2>/dev/null || echo '?')"
done
grep -oE '`[a-z]+/[a-z0-9-]+`' <handoff> | tr -d '`' | sort -u | while read -r b; do
  printf "  branch %-40s %s\n" "$b" \
    "$(git ls-remote --heads origin "$b" | wc -l | sed 's/^0$/GONE/;s/^1$/EXISTS/')"
done
```

Every PR merged or closed, every branch gone, every job finished --- clear it.
Anything still open or still running --- keep it, and say which item held it.

**An open *issue* it references does not keep it alive.**
A handoff's value is the in-flight state it captured; an issue is tracked in the
tracker, which is where a reader should meet it.
Judge on the in-flight items.

### A handoff written as a repo-root file is a staging hazard

The rest of this skill persists the snapshot as a **project memory**, which is
outside the repo and cannot be committed by accident.
A handoff written instead as a repo-root `HANDOFF-*.md` is untracked **and**
usually unignored, which is precisely the combination that lets a bare
`git add -A` sweep it into a PR.

That is not hypothetical.
It is the shape of `ucdavis/bcs`'s 2026-07-30 incident, where an
untracked-and-unignored directory was staged that way and pushed a credential.

So prefer the project-memory form.
Where a repo-root file already exists, either retire it under the rule above or
add a `.gitignore` entry --- and read its contents before doing either, since a
stale handoff can carry a rule the project has since **reversed**, which is
worse than one that is merely out of date.

- **Do:** derive staleness from the state of every item a handoff names, and
  clear it once they have all resolved.
- **Do:** read a stale handoff before deleting it, in case it states a
  convention the project has since changed.
- **Don't:** keep a handoff alive because it mentions an open issue --- the
  tracker owns that.
- **Don't:** leave a repo-root handoff untracked and unignored; that is the
  `git add -A` hazard, not merely clutter.

## Relationship to other skills

- `memories/preferences.md` (the "always leave handoff notes proactively"
  bullet) — the *policy* (when to hand off automatically); this skill is the
  *action*.
- `memorize` / `remember` — general fact persistence; `handoff` is the
  specialized "save session state" case.
- `claim-pr` — owns the claim/unclaim lifecycle; `handoff` posts the *paused*
  note within an existing claim.
- **`checkpoint`** — a lighter, deliberate mid-task snapshot for a session
  that *isn't* ending: plan state, decisions, next actions, no branch/job/PR
  mechanics. Run `handoff` when actually stopping; `checkpoint` when just
  banking progress mid-task.
- **`compress-session`** — distills the conversation into auto memory before
  the context window fills up, so a compaction (not a session end) doesn't
  lose what matters. `handoff` ends the session; `compress-session` keeps it
  going with a smaller, curated context.
