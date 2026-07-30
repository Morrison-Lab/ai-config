---
name: clean-worktrees
description: "Clean Worktrees: sweep dead git worktrees in the current repo — prune admin stubs for already-deleted dirs, then remove linked worktrees whose branch merged into main (or is gone) and whose tree is clean. Never touches the main or current worktree, a dirty tree, a locked worktree, or one with a live session-lock session. Presents a dry-run plan first. Use when asked to 'clean worktrees', 'cw', 'prune worktrees', 'clean dead worktrees', 'remove stale worktrees', or 'tidy up worktrees'."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Clean Worktrees (aka CW / prune-worktrees)

Sweep **dead git worktrees** out of the current repo. Agent isolation and the
`session-lock` skill spin up worktrees under `.claude/worktrees/<name>/` (or
`<repo>.worktrees/<name>/`); after a PR merges or a session ends, the worktree
lingers on disk with a merged or `[gone]` branch. This skill removes the dead
ones safely and leaves everything live untouched.

This is the **worktree** counterpart to `clean-branches` (which sweeps
*branches*). A worktree holds a branch checked out into its own directory, so
the two are complementary: remove the dead worktree here, then `clean-branches`
deletes the now-free branch (or this skill deletes it inline).

## When this fires

- "clean worktrees", "cw", "prune worktrees", "prune-worktrees"
- "clean dead worktrees", "remove stale worktrees", "tidy up worktrees"
- "which worktrees can I delete?"
- After a batch of PRs merge and the `.claude/worktrees/` dir has grown.

## What a worktree is (and why they pile up)

`git worktree` checks a branch out into a *second* working directory that shares
the repo's `.git`. Sources in this setup:

- **Agent isolation** — the `Agent` tool's `isolation: "worktree"` and the
  harness's per-session worktrees (`.claude/worktrees/<name>/`). Auto-removed
  *if unchanged*, but a worktree that got any commit is left behind.
- **`session-lock`** — `ai-session.sh worktree <branch>` isolates a top-level
  session into its own worktree.
- **Manual** — `git worktree add`.

None of these self-clean once they have commits, so they accumulate.

## Definitions

| Category | Criteria | Action |
|----------|----------|--------|
| **Prunable stub** | Worktree *record* whose directory no longer exists on disk (removed manually) | `git worktree prune` |
| **Dead** | Linked worktree, **clean** tree, branch **merged into `origin/main`** OR upstream **`[gone]`** with no unique unpushed commits, **no live session**, not the current/main worktree | `git worktree remove` + delete its branch |
| **Dirty** | Uncommitted changes, or unique commits not on `origin/main` and not pushed | **Skip** — flag; only `--force` after explicit confirmation |
| **Active** | Live `session-lock` session registered, the **current** worktree, the **main** worktree, an open PR on its branch, or last commit < 7 days old | **Skip** — never touch |
| **Locked** | `git worktree list` marks it `locked` | **Skip** unless the user confirms; then `git worktree unlock` before removing |

"Clean tree" and "branch landed" must **both** hold for **Dead** — a clean tree
whose commits never merged is **Dirty** (unpushed work), not dead.

## Procedure

### 1. List worktrees

```bash
git worktree list --porcelain
```

Each block gives `worktree <path>`, `HEAD <sha>`, and `branch <ref>` (or
`detached` / `locked` / `bare`). Note the **main** worktree (the repo root —
`dirname` of `git rev-parse --git-common-dir` when `.git` is a directory) and
the **current** worktree (`git rev-parse --show-toplevel`). Never remove either.

### 2. Prune admin stubs (safe)

`git worktree prune` only drops records for worktrees whose directory is already
gone — it never deletes a directory. Preview, then prune:

```bash
git worktree prune --dry-run -v
git worktree prune -v
```

### 3. Classify each linked worktree

Refresh remote-tracking state **once** up front so the merged / `[gone]` checks
below are accurate:

```bash
git fetch --prune origin
```

Then, for every worktree except the main and the current one:

#### a. Dirty check — uncommitted work

```bash
git -C <path> status --porcelain    # any output → DIRTY, skip (or --force only on confirmation)
```

#### b. Unpushed / unmerged check — unique work that lives nowhere else

```bash
git -C <path> rev-parse --abbrev-ref HEAD                 # the branch
gh pr list --head <branch> --state open --json number,url  # LIST_PRS — open PR? (glab mr list on GitLab)
git rev-list --count origin/main..<branch>                # commits ahead of main
git rev-list --count <branch>@{upstream}..<branch> 2>/dev/null \
  || echo "no-upstream"                                   # unpushed commits (or no remote)
```

Evaluate in this order so the label matches the Definitions table:

1. **Open PR** → **Active**, skip (short-circuits — takes precedence even if the
   branch also has unpushed commits).
2. Else ahead of main **and** (unpushed or no upstream) → **Dirty** (unpushed
   work), skip.
3. Else ahead of main but fully pushed → **Active**, skip.

#### c. Branch-landed check — is the work safely on main?

```bash
# --format gives plain names — plain `git branch --merged` prefixes a branch
# checked out in a linked worktree with `+` (not two spaces), so a fixed-column
# grep would miss every branch this skill evaluates. -Fxq: fixed string + whole
# line, so a branch name with regex metachars (`.`, `+`, `*`) can't match loosely.
git branch --merged origin/main --format='%(refname:short)' \
  | grep -Fxq "<branch>" && echo MERGED
# -Fx: fixed string + whole line, so a branch name with regex metachars
# (`.`, `+`, `*`) can't match loosely. for-each-ref emits exactly "<branch> [gone]".
git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads \
  | grep -Fxq "<branch> [gone]" && echo GONE
```

Merged into `origin/main`, or upstream `[gone]` with **no** unique commits (3b
returned 0) → the work has landed.

**Squash-merge repos break both checks above — verify via PR state instead.**
A squash merge rewrites the branch's commits into one new commit on `main`, so
the branch's own commits are never ancestors of `origin/main`: `git branch
--merged` won't show it as MERGED, and step 3b's ahead-of-main count won't be
0, so the `[gone]`-with-no-unique-commits path won't fire either — both landed
checks silently fail on every squash-merged branch, misclassifying it as
**Dirty** (unpushed work) instead of **Dead**. Don't trust local ancestry for
landed detection in a squash-merge repo (check `git log --oneline -5
origin/main` for single-commit messages — GitHub's default squash-commit
subject is `"<title> (#N)"`, though a repo can configure a different template
(e.g. `Lacaedemon/sparta` uses `"PR #N: ..."`) — or just try it, the false
positive is cheap to spot once you know to look). Use the PR's own merge
state as the authoritative signal instead:
```bash
gh pr list --head <branch> --state all --json number,state,mergedAt --jq '.[0]'
```
A `"state": "MERGED"` entry means landed regardless of what the ahead/merged
checks above say. (Hit on `Lacaedemon/sparta`, 2026-07-02: ~40 of 48 worktrees
slated for cleanup showed `ahead=2` to `ahead=15` on the naive check — every
one had actually merged via squash minutes to hours earlier.)

#### d. Live-session check — is another session using it?

```bash
# Plain `list` (NOT `--all`) — it prunes stale records and shows only LIVE
# sessions, so a worktree whose session already died won't be flagged Active.
~/.claude/skills/session-lock/scripts/ai-session.sh list 2>/dev/null \
  | grep -F "<path>"        # a live record on this worktree → ACTIVE, skip
```

(If `session-lock` isn't installed, skip this check — fall back to the dirty and
recency guards.)

#### e. Recency check — too fresh to judge

```bash
git -C <path> log -1 --format='%ci'    # last commit < 7 days → Active, skip
```

A worktree is **Dead** only when 3a is clean, 3c says landed, 3d finds no live
session, and 3e is older than 7 days.

### 4. Present the plan (dry run) — wait for confirmation

```
## Worktree Cleanup Plan — <timestamp>

| Worktree | Branch | Status | Action |
|----------|--------|--------|--------|
| `.claude/worktrees/loving-bhabha-1051e7` | `ums-…-clobber` | Dead (PR #56 merged, clean) | 🗑️ Remove + delete branch |
| `.claude/worktrees/pedantic-shamir-b52cab` | `claude/pedantic-…` | Active (open PR) | ⏭️ Skip |
| `.claude/worktrees/tender-feistel-5c7311` | `claude/tender-…` | Current worktree | ⏭️ Skip |
| `(stub) old-scratch` | — | Prunable (dir gone) | 🧹 Pruned in step 2 |

Proceed? (or pick specific worktrees)
```

No silent removals. Wait for confirmation; "just go" / "do it" → proceed with
all proposed removals.

### 5. Remove dead worktrees

```bash
git worktree remove <path>          # refuses on a dirty tree — a safety net; do NOT blindly --force
git branch -d <branch>              # -d refuses unless merged; the work landed, so this should pass
```

If `git worktree remove` reports the tree is dirty, that worktree was
misclassified — re-inspect, don't reach for `--force`. Only `--force` after the
user explicitly OKs discarding that worktree's changes.

**Exception — a worktree containing a submodule:** the error `fatal: working
trees containing submodules cannot be moved or removed` is a *different*
refusal, triggered by the submodule's presence alone, not by dirty state. If
`git -C <path> status --short` is empty (genuinely clean), `--force` here is
correct and safe — it isn't the dirty-tree case above, so don't treat it as a
misclassification signal.

If `git branch -d` refuses (squash/rebase merge can hide the merge), confirm the
PR merged (`gh pr list --head <branch> --state merged`) before `git branch -D`.

**A squash merge does not reliably force that refusal, so expect both outcomes
in one sweep.**
`git-branch(1)` checks the branch against its **upstream** --- "fully merged in
its upstream branch, or in HEAD if no upstream was set".
So a branch still tracking a live `origin/<name>` passes `-d` regardless of what
`main` contains, printing `warning: deleting branch 'X' that has been merged to
'refs/remotes/origin/X', but not yet merged to HEAD.`
Only once the remote ref is gone (auto-delete on merge, or
`gh pr merge --delete-branch`) does the check fall back to HEAD and refuse.
A sweep of 29 branches split 18 `-d` / 11 `-D` on that basis alone.
So don't read a needed `-D` as a red flag, and don't read a successful `-d` as
proof the work reached `main` --- step 3's classification is what establishes
that, not the deletion flag.

### 6. Final prune + report

```bash
git worktree prune -v               # clears any record left by the removals
```

```
## Worktree Cleanup Complete — <timestamp>

### Removed (dead)
- `.claude/worktrees/loving-bhabha-1051e7` (branch `ums-…-clobber` deleted; PR #56 merged)

### Pruned stubs (dir already gone)
- `old-scratch`

### Skipped (active / current / fresh)
- `.claude/worktrees/pedantic-shamir-b52cab` — open PR
- `.claude/worktrees/tender-feistel-5c7311` — current worktree

### Flagged — dirty / unpushed (left alone)
- `.claude/worktrees/wip-experiment` — 2 uncommitted files; your call
```

## Safety rules

- **Never remove the main working tree** (`git worktree remove` refuses anyway).
- **Never remove the current worktree** — the one you're running in
  (`git rev-parse --show-toplevel`).
- **Never `--force` a dirty worktree without explicit confirmation** —
  uncommitted or unpushed work exists nowhere else.
- **Never remove a worktree with a live `session-lock` session** — another
  agent is working there.
- **Always present the plan first** — no silent removals.
- **Don't remove worktrees newer than 7 days** — likely in-progress work.
- `git worktree prune` is safe (records only, never directories) — but still
  report what it pruned.

## Relationship to other skills

- **`session-lock` / `deconflict-sessions`** — *creates* the worktrees this
  skill cleans up; consult its registry (step 3d) so you never remove one a
  live session holds. Its own teardown is `git worktree remove` at session end;
  this skill is the bulk sweep for the ones that slipped through.
- **`clean-branches` / `cb` / `prune`** — the **branch** counterpart. Run it
  after this skill (or let step 5 delete branches inline) so a removed
  worktree's branch doesn't linger. Same dry-run-then-confirm discipline.
- **`post-merge`** — after a PR merges, removing its worktree is part of the
  tidy-up (step 2 there); that skill can hand off here for a repo-wide sweep.
- **`wrap-up`** — the session-level bookend surfaces leftover worktrees and
  offers to run this skill to sweep the dead ones.

## Anti-patterns

- ❌ `git worktree remove --force` on a dirty tree to "just clean it up" —
  silently destroys uncommitted work.
- ❌ Removing a worktree whose branch has unique unpushed commits (work lives
  only there).
- ❌ Removing a worktree another `session-lock` session is actively using.
- ❌ Removing worktrees without a dry-run plan and confirmation.
- ❌ Deleting the branch but leaving the worktree (or vice versa) — sweep both.
