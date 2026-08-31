---
name: clean-worktrees
description: "Clean stale git worktrees."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Clean Worktrees (aka CW)

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

- "clean worktrees", "cw", "prune worktrees"
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
| **Active** | Live `session-lock` session registered, the **current** worktree, the **main** worktree, an open PR on its branch, or last commit < 7 days old **and its PR has not merged** | **Skip** --- never touch |
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

**A detached worktree has no branch, so the squash-merge escape hatch above
does not apply to it --- and the naive check it falls back to is the one that
is wrong in a squash-merge repo.**
Every landed-detection route in 3b and 3c keys on a branch name: `gh pr list
--head <branch>`, `git branch --merged`, `<branch>@{upstream}`.
A detached HEAD answers none of them, so classification silently drops to the
ahead-of-main count --- which the warning above already establishes is
meaningless here, since a squash merge guarantees it is nonzero.

The result reads as the *safe* answer while being the wrong one.
`ahead=5` with no branch and no upstream looks exactly like commits that exist
nowhere else, so the worktree is labelled **Dirty** and kept indefinitely,
when in fact its work merged hours earlier.

Diff the content instead, which needs no branch:

```bash
h=$(git -C <path> rev-parse HEAD)
git diff --name-only origin/main "$h" -- <files the unique commits touched>
```

Scope it to those files.
A bare `git diff origin/main <head>` reports every file `main` has gained
since the worktree was cut, which in an active repo is hundreds --- all of it
`main`'s drift rather than the worktree's work, and it buries the answer.
Get the file list from the worktree's own commits first, then diff only
those:

```bash
git log --name-only --format='' "origin/main..$h" | sort -u
```

Note the `$h` rather than `HEAD`.
A detached worktree's head is not the head of wherever you are running the
command, so a bare `HEAD` silently reports on the current checkout instead ---
and without `--name-only --format=''` the command prints commit messages
rather than the file names the next step needs.
An empty diff means the content is on `main` and the worktree is **Dead**.

(2026-07-29, the same ai-config sweep: two detached worktrees showed
`ahead=5` and `ahead=2` and were classified Dirty on that basis.
Narrowed to the files their own commits touched, both diffed **empty**
against `main` --- one was PR #804's review fixes, already squash-merged, and
the other's two commits were both present in `jules-review.yml` on `main`.
The whole-tree diff for the same pair reported 222 and 221 changed files,
which is why the narrowing matters.)

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

A worktree is **Dead** when 3a is clean, 3c says landed, 3d finds no live
session, and 3e is older than 7 days.

**A merged PR overrides the recency guard: a branch whose PR merged can go
however recent it is, provided it carries no unpushed work.**
The guard exists to protect work that is still in progress, and a merged PR
is the definitive statement that it is not.
Holding a worktree for six more days on the strength of a date, when its own
PR closed hours ago, is the guard firing on the one case it was never
written for --- and it is the *common* case in an active session, where the
worktrees most worth sweeping are the ones created that week.

So the age check only decides worktrees whose landed status is unknown.
Once 3c has answered, age adds nothing.

**Verify the no-unpushed-work half rather than assuming it from the merge.**
The natural check --- does `origin/<branch>` still exist --- answers a
different question in a repo that deletes head branches on merge, since
every merged branch reports `remote=GONE` there.
That is equally consistent with "merged and cleaned up" and with "merged,
then you committed something else locally", and only the second is unsafe.

Compare the branch tip's date against the PR's `mergedAt`:

```bash
tip=$(git log -1 --format='%ct' "<branch>")                          # epoch seconds
merged=$(gh pr view <N> --json mergedAt --jq '.mergedAt|fromdateiso8601')   # VIEW_PR
[[ "$tip" -lt "$merged" ]] && echo "OK (tip predates merge)" || echo "tip AFTER merge -- inspect"
```

Compare **epochs**, not the ISO strings.
`%cI` renders the commit's date in the machine's local zone while `mergedAt`
is UTC, so a lexicographic `<` between them compares clock faces from two
different zones.
It fails in the unsafe direction: west of UTC, a tip committed *after* the
merge still sorts first, reports `OK`, and the worktree gets removed with
that commit on it.
Verified with `tip=2026-07-30T18:00:00-07:00` against
`merged=2026-07-30T23:00:00Z` --- the tip is two hours later in real time and
the string comparison says it predates.
`%ct` and `fromdateiso8601` put both on the same absolute scale, and
`fromdateiso8601` is available in the jq that `gh --jq` embeds.

A tip predating the merge cannot carry anything the merge did not see.
A tip *after* it is the case worth stopping for, and it is the same orphaned
commit that
[`CLAUDE.md`](../../CLAUDE.md)'s merge-race note describes --- work pushed
onto a branch whose PR had already closed.

- **Do:** treat a merged PR plus a tip predating its merge as Dead, whatever
  the age.
- **Do:** compare timestamps, since `remote=GONE` is uninformative wherever
  head branches are auto-deleted.
- **Don't:** skip a worktree for recency alone once its PR has merged.
- **Don't:** read a deleted remote branch as proof nothing local was added
  after the merge.

(2026-07-29, an ai-config sweep: four worktrees, all clean, all four remotes
gone, and PRs #625/#643/#782/#810 all merged.
Two were 1 and 2 days old, so the recency guard alone would have kept them.
Every tip predated its own merge by 7 to 14 hours, and the maintainer's
standing rule is that branches from merged PRs can go unless they have
unpushed work.)

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

A standing [`daytb`](../daytb/SKILL.md) grant lifts this confirm step for the safe cases --- removing a stale worktree is one of the local-git housekeeping actions that grant explicitly covers.
The skill's own safety preconditions are unchanged, and anything carrying commits reachable from no remote still asks.

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

**A branch that was ever pushed as a PR head is recoverable after deletion**,
so a `-D` here is far less consequential than it looks: GitHub retains
`refs/pull/N/head` permanently, and it still resolves once the branch is gone
(`git fetch origin refs/pull/<N>/head`).
See `memories/git-branches.md`, "GitHub keeps `refs/pull/N/head` forever".
The exception is the one that matters --- a branch **never pushed** has no such
ref, which is why an unpushed worktree branch still needs confirmation.

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
  Unless the branch's PR has merged and its tip predates that merge, in which
  case age is irrelevant (step 3e).
- `git worktree prune` is safe (records only, never directories) — but still
  report what it pruned.

## Relationship to other skills

- **`session-lock`** — *creates* the worktrees this
  skill cleans up; consult its registry (step 3d) so you never remove one a
  live session holds. Its own teardown is `git worktree remove` at session end;
  this skill is the bulk sweep for the ones that slipped through.
- **`clean-branches` / `cb` / `prune`** — the **branch** counterpart. Run it
  after this skill (or let step 5 delete branches inline) so a removed
  worktree's branch doesn't linger. Same dry-run-then-confirm discipline.
- **`clean-git`** --- the combined sweep.
  It runs this skill and then `clean-branches`,
  behind one dry-run plan and one confirmation,
  and owns the ordering constraint that makes worktrees-first mandatory.
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
