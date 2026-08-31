# Deconflicting parallel local AI sessions

Multiple AI agent sessions can end up working the **same local repo checkout**
at once — two Claude Code CLI tabs, a CLI plus the IDE extension, two cloned
terminals, or a CLI session alongside a background agent. Sharing one working
tree, they clobber each other:

- one session `git checkout`s a branch out from under another's uncommitted edits;
- two edit the same file and the later write silently wins;
- two push the same branch and one is rejected or force-overwrites the other;
- two launch the same expensive render/build/test in the same directory.

This repo ships a small system to make those collisions **visible and
avoidable**. It is the local-filesystem counterpart to
[`claim-pr`](../skills/claim-pr/SKILL.md), which deconflicts on the *remote* (a
GitHub/GitLab PR or issue) via comment claims.

## Pieces

| Piece | Path | Role |
|-------|------|------|
| Registry CLI | `skills/session-lock/scripts/ai-session.sh` | the system: register / check / list / worktree / release / prune |
| Skill | `skills/session-lock/SKILL.md` | how an agent should use it |
| Optional hook | `skills/session-lock/hooks/session-start-register.sh` | auto-register on `SessionStart` and surface conflicts |

Once `bootstrap.sh` has run, the script lives at
`~/.claude/skills/session-lock/scripts/ai-session.sh`.

## How it works

### The registry lives under `.git/`

Session records are written to:

```
$(git rev-parse --git-common-dir)/ai-sessions/<session-id>.session
```

That location is chosen deliberately:

- **machine-local** — git never tracks anything under `.git/`, so records are
  never committed or pushed; there is nothing to add to `.gitignore`;
- **repo-scoped** — one registry per repository;
- **worktree-wide** — every `git worktree` of a repo shares the same *common*
  git dir, so a session in one worktree still sees sessions in the others. This
  is what lets the system both *detect* same-checkout collisions and *resolve*
  them by moving a session into its own worktree.

Each record is a tiny `key=value` file: id, agent, host, the long-lived agent
PID (best-effort), worktree path, branch, start time, heartbeat, and a one-line
task. Writes are temp-file-then-rename (atomic on one filesystem) and each
session owns exactly one file, so there is **no daemon and no lock file** to
manage — readers simply tolerate the rare concurrent write.

### Conflict classes

- **Same working tree** (exit `3`): two live sessions share the exact checkout.
  This is the dangerous one — uncommitted edits and branch switches collide.
  Resolve by isolating one session into its own worktree.
- **Same branch, different worktree** (exit `4`): pushes may race; coordinate or
  use distinct branches.

### Crash recovery without babysitting

A record is **stale** (and auto-pruned) when either:

1. its PID is on **this host** and the process is gone (`kill -0` fails) — the
   immediate signal for a closed local CLI; or
2. it has no probe-able PID (different/unknown host) and its heartbeat is older
   than `AI_SESSION_STALE_SECONDS` (default `1800`).

So on a single machine a closed session frees its claim at once; heartbeats are
only the fallback for cross-host/container cases.

## Day-to-day use

```bash
S=~/.claude/skills/session-lock/scripts/ai-session.sh

$S register --id cli-fix-auth --task "fix the auth bug"   # start of write session
$S check    --id cli-fix-auth                             # exit 3/4 ⇒ collision
$S worktree fix-auth                                      # isolate on a conflict
$S list                                                   # who's working where
$S release  --id cli-fix-auth                             # end of session
```

Pick a short, stable `--id` at session start and reuse it (each Bash call is a
fresh shell, so the id is how invocations stay tied together). Or set
`AI_SESSION_ID` / rely on `CLAUDE_SESSION_ID`.

## Optional: auto-register via a hook

To register every session automatically and flag conflicts the moment a session
opens, add the bundled hook to a repo's `.claude/settings.json`. It reads the
real `session_id` and `cwd` from the hook payload and is non-fatal (it exits 0
if anything is missing, so it never blocks a session):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "bash \"$HOME/.claude/skills/session-lock/hooks/session-start-register.sh\"" } ] }
    ]
  }
}
```

Add the same entry under `UserPromptSubmit` if you also want each prompt to
refresh the heartbeat (handy for long sessions on hosts where the PID can't be
probed).

> Note: this repo's own `SessionStart` hook (`.claude/hooks/session-start.sh`)
> intentionally does **not** call the registry. That hook runs only in remote
> (web) sessions, where every session gets a fresh, isolated clone and can never
> share a checkout — so there is nothing to deconflict there. The system targets
> *local* multi-session use, where the hook above is opt-in per repo.

## Relationship to the other coordination skills

- **`claim-pr`** — remote claim on a PR/issue (cross-machine, plus the `@claude`
  CI bot). Use alongside this for any PR work.
- **`sync-pr-branch`** — reconcile your branch with `origin` before pushing, so
  commits made by another session/machine aren't lost.
- **`session-lock`** (this) — local working-tree/branch contention on one
  machine.

Together: `claim-pr` for the remote, `session-lock` for the local checkout,
`sync-pr-branch` to keep the two in step.
