---
name: clean-branches
description: "Clean dead or stale Git branches."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Clean Branches (aka CB / prune)

Audit branches in the current repo — **both your local checkout and the
remote**. Delete dead ones, rebase stale ones, open MRs for orphaned work, and
sweep up local-only stragglers — all without disrupting active sessions.

## When this fires

- User says "clean branches", "cb", "prune", "prune branches", "tidy up branches"
- User says "clear dead branches", "clean up the repo"
- User says "what branches can we delete?"

## Scope: local AND remote

Prune in both places — they accumulate junk independently:

- **Remote** branches — dead/stale/orphaned remote refs (the bulk of this skill).
- **Local** branches — branches that linger in your checkout after their PR
  merged, or whose upstream remote was deleted (`[gone]`). The remote pass
  alone won't catch a local branch whose remote is already gone, so there's a
  dedicated local pass (step 8).

## Definitions

| Category | Criteria | Action |
|----------|----------|--------|
| **Dead** | Purely behind main (no unique commits ahead), no open MR, no linked issue, not created in the last 7 days | Delete |
| **Stale** | Has unique commits ahead of main but is behind main, no recent activity (>30 days), not actively being worked on | Rebase on main, open MR if none exists |
| **Active** | Has an open MR, linked issue, recent commits (<30 days), or a claim comment | Skip — don't touch |
| **New** | Created in the last 7 days | Skip — too fresh to judge |
| **Local merged** | *Local* branch fully merged into main, or whose PR merged (upstream `[gone]`) | Delete locally (`git branch -d`) — step 8 |
| **Local-only unpushed** | *Local* branch with unique commits, never pushed, no MR | Flag — ask before touching (step 8) |

The first four rows apply to **remote** branches (steps 1–7); the last two are
the **local** pass (step 8). A branch can need both — e.g. delete the remote ref
*and* the leftover local tracking branch.

## Procedure

### 1. Detect the forge

```bash
git remote get-url origin
```

Determine GitHub (`gh`) vs GitLab (`glab`).

### 2. Fetch and list remote branches

```bash
git fetch --prune origin
git branch -r --merged origin/main | grep -v 'origin/main\|origin/HEAD'
git branch -r --no-merged origin/main
```

**First separate real remote branches from stray ref namespaces, or the
sweep's scope is wrong from its first command.**
A one-off `git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'` writes refs
that no configured refspec matches, so nothing updates them and `--prune`
never touches them --- but `git branch -r` counts them anyway.

```bash
git config --get-all remote.origin.fetch                                  # what is tracked
git for-each-ref --format='%(refname)' | grep -v '^refs/remotes/origin/'  # what is not
```

Anything outside the tracked namespace is local cruft rather than a branch:
`git push origin --delete` cannot touch it, and it belongs in a separate
`git update-ref --stdin` sweep, not in the plan below.

**Write ref patterns with `**`, because a single `*` does not cross a slash.**
`git for-each-ref 'refs/remotes/origin/*'` silently omits every slash-named
branch --- `feat/`, `fix/`, `claude/` --- which is every branch anyone named
conventionally, including the ones carrying open PRs.
Nothing errors; the count merely comes back smaller and entirely plausible.
Note this is the **opposite** of pathspec matching, where `*` does cross a
slash; see `memories/git-diffing.md`, "A ref pattern is not a pathspec".

```bash
git for-each-ref --format='%(refname:short)' 'refs/remotes/origin/**'
```

Give the enumeration a control before trusting a total: confirm a known
slash-named branch appears in the output.
A shortfall here is indistinguishable from a tidy repo.

### 3. Classify each branch

For each remote branch (excluding `main`, `HEAD`, protected branches):

#### a. Check if it's purely behind main (merged/dead)

```bash
# Commits on branch not on main (ahead count)
git rev-list --count origin/main..origin/<branch>

# If 0 → branch is purely behind main (already merged or never diverged)
```

#### b. Check recency

```bash
git log -1 --format='%ci' origin/<branch>
```

Skip if created/last-committed within the last 7 days (too new).

#### c. Check for open MR/PR

```bash
# GitLab
glab mr list --source-branch=<branch> 2>&1 | cat

# GitHub
gh pr list --head=<branch> --json number,title,state | cat   # LIST_PRS
```

If an open MR exists → **Active**, skip.

**Fetch every PR once and match locally, rather than querying per branch.**
A sweep of N branches costs N API round-trips this way, which is slow and
rate-limit-prone at repo scale; one call answers for all of them, and it also
supplies the *merged* and *closed-unmerged* states that b and f need.

```bash
gh pr list --state all --limit 2000 \
  --json number,headRefName,state,mergedAt,url,title > /tmp/all-prs.json   # LIST_PRS
```

Then index by `headRefName` and look each branch up in memory.
Raise `--limit` above the repo's total PR count and check the returned length
against it --- a silently truncated list marks live branches as having no PR,
which is the one error in this sweep that deletes something.

#### d. Check for linked issues

Look for branch naming patterns that reference issues:
- `fix/123-*`, `feat/123-*`, `issue-123-*` → check if issue #123 is open
- If the linked issue is open → **Active**, skip

#### e. Check for active work claims

```bash
gh pr view <N> --json comments \
  -q '.comments[] | select(.body | test("hold off|paws off|back off"; "i"))
      | select((.body | test("unclaim|released|PR is free|now mergeable"; "i")) | not)
      | "\(.author.login): \(.body)"'   # READ_PR_COMMENTS
```

If a claim comment exists within the last 24 hours → **Active**, skip.
This window is deliberately wider than
[`claim-pr`](../../shared/workflow/claim-pr.md)'s 2-hour claim expiration:
that rule decides who may *start work*, where the cost of over-respecting a
dead claim is a wait; this check gates branch *deletion*, which is
destructive, so it errs further toward keeping.

#### f. If the PR closed unmerged, diff the branch against main before believing it

Check c only asks whether an **open** PR exists, so a branch whose PR closed
unmerged falls straight through to a delete classification.
That is right for an abandoned branch and wrong for a superseded one, because a
closure rationale describes the PR's **stated purpose**, not an inventory of its
diff.
"Superseded by #260, all review findings addressed" is a claim about the
feature; it says nothing about an unrelated fix that happened to share the
branch.

The gap is easy to miss in exactly the case that matters, since the rationale is
usually accurate about the thing it names, and the leftover work is by
definition the part nobody was talking about.
Nothing else flags it either: `git branch -d` consults the upstream rather than
`main` (see the safety rules below), the superseding PR merged and closed the
issue, and the tracker looks clean.

So for any branch whose PR closed **unmerged**, compare the files rather than
reading the closure comment:

```bash
gh pr list --head <branch> --state closed \
  --json number,title,mergedAt,url | cat                     # LIST_PRS
gh pr diff <N> --name-only                                   # DIFF_PR
git diff --stat origin/main...origin/<branch>                # what is still unlanded
```

`mergedAt: null` on a closed PR is the trigger.
Then diff each file the branch touched against `main`;
anything still absent is unlanded work, and the branch is **Stale**, not Dead
--- rebase it and open an MR (steps 6--7), or file an issue for the salvageable
part and say so in the plan before deleting.

Weight the check by how far the branch's contents stray from its title: a branch
carrying commits unrelated to the PR that named it is the shape this catches.
`rescue-closed` is the deliberate, whole-tracker version of the same sweep; this
is the minimum owed before a deletion.

(2026-07-29: a bcs branch closed as superseded still carried an orthogonal
out-of-memory fix --- `geepack::geeglm` replaced by `glm` + `sandwich::vcovCL`
--- that the superseding privacy redesign never touched.
Deleting on the closure rationale would have discarded it silently;
filed instead as `ucdavis/bcs#466`.)

**Once you have found unlanded work, the deliverable is a tracking issue --- not
keeping the branch.**
On GitHub the branch is not the only copy: `refs/pull/N/head` is retained
permanently and still resolves after the head branch is deleted.
So the choice is not "delete or preserve", it is "record or lose track of",
which is a much easier call and lets the sweep finish.

Verify rather than assume, since it is one call per PR, then put the recovery
command in the issue:

```bash
git ls-remote origin 'refs/pull/<N>/head'    # should equal the branch tip
git fetch origin refs/pull/<N>/head
git checkout -b recover/<N> FETCH_HEAD
```

An issue naming what was unlanded, how much of it, and that command is strictly
more useful than a stale branch nobody will revisit --- and unlike the branch,
it appears in the tracker.
(2026-08-02, `Morrison-Lab/ai-config`: six closed-unmerged branches carried
work absent from `main`; every `refs/pull/N/head` resolved and matched its
branch tip exactly, so all six were deleted after the two substantial ones were
filed as #1062 and #1063.)

### 4. Present the plan (dry run)

Before taking any action, present a table to the user:

```
## Branch Cleanup Plan

| Branch | Last commit | Status | Action |
|--------|-------------|--------|--------|
| `old-feature` | 2025-03-15 | Dead (merged) | 🗑️ Delete |
| `wip-refactor` | 2025-11-20 | Stale (45 days, no MR) | 🔄 Rebase + open MR |
| `fix/42-typo` | 2026-06-15 | Active (open MR !80) | ⏭️ Skip |
| `experiment` | 2026-06-12 | New (<7 days) | ⏭️ Skip |

Proceed? (or pick specific branches to act on)
```

Wait for user confirmation before proceeding. If user says "just go" or
"do it", proceed with all proposed actions.

### 5. Delete dead branches

```bash
git push origin --delete <branch>   # DELETE_REF
```

Also clean up local tracking branches:
```bash
git branch -d <local-tracking-branch>  # if it exists locally
```

### 6. Rebase stale branches

For each stale branch:

```bash
git checkout -B <branch> origin/<branch>   # -B (not -b) force-resets if the branch already exists locally
git rebase origin/main
```

If rebase has conflicts:
- Attempt to resolve automatically (see the `resolve-conflicts` skill —
  consolidate both sides, don't blind-pick)
- If conflicts are non-trivial, skip this branch and report it
- Don't force-push a broken rebase

If rebase succeeds:
```bash
git push --force-with-lease origin <branch>   # PUSH
```

### 7. Open MRs for orphaned stale branches

For stale branches that have no open MR after rebasing:

```bash
# GitLab — assign to the current glab user (override ASSIGNEE to assign someone else)
ASSIGNEE="$(glab api user 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['username'])")"
glab mr create --source-branch=<branch> --target-branch=main \
  --title "<inferred title from branch name>" \
  --description "Orphaned branch rebased onto main. Review or close if no longer needed." \
  ${ASSIGNEE:+--assignee "$ASSIGNEE"}

# GitHub
gh pr create --head=<branch> --base=main \
  --title "<inferred title>" \
  --body "Orphaned branch rebased onto main. Review or close if no longer needed."   # CREATE_PR
```

### 8. Prune local branches

The remote pass doesn't touch branches that only exist in your checkout. Sweep
those too. First refresh remote-tracking state so "merged" and "gone" are
accurate:

```bash
git fetch --prune origin                       # marks deleted upstreams as [gone]
git branch --show-current                      # never delete the branch you're on
```

**The `--prune` is a prerequisite, not a refresh --- without it step b finds
nothing and reports success.** `[gone]` is produced *by* pruning, not by the
branch being deleted upstream: until a prune runs, `%(upstream:track)` is
empty for exactly the branches b exists to find, so its `grep` matches zero
rows and the sweep says there is nothing to clean.
The "nothing found" and "never ran" paths print the same thing,
so never take a zero-row result as clean
unless this fetch actually ran in this sweep.

Recommend the standing setting once, since it makes every other tool's view
correct too --- but keep the explicit `--prune` above regardless, so the sweep
does not depend on the user's config:

```bash
git config --global fetch.prune true          # or per-remote:
git config --global remote.origin.prune true
```

That setting only prunes `refs/remotes/origin/*`.
It never deletes a local branch, so it replaces none of the steps below.

Classify each **local** branch (excluding `main`/`master`/protected and the
current branch):

#### a. Merged into main → delete

```bash
git branch --merged origin/main --format='%(refname:short)' \
  | grep -vxF -e main -e master -e "$(git branch --show-current)"
# --format gives plain names. Plain `git branch` prefixes the current branch
# with `*` and a branch checked out in a linked worktree with `+`, so a
# column-anchored grep on the plain listing mangled such a name into
# `+ feature/foo` and the delete below failed on it (ai-config#1882; the
# clean-worktrees skill's step 3c records the same hazard). With no `*` to
# filter, the current branch is excluded by name instead. `grep -vxF`
# matches whole lines literally, so only `main`, `master`, and the current
# branch are excluded, and a branch like `maintain-docs` or
# `feature-main-menu` is NOT silently filtered out. A branch checked out in
# a linked worktree still appears; `git branch -d` refuses it, and the note
# below says how to read that refusal.
# Compare against origin/main (just fetched), NOT local `main` — your local main
# may be behind, which would hide branches that are actually merged.
git branch -d <branch>          # -d refuses if NOT actually merged — a safety net
```

`-d` (never `-D`) is deliberate, and its refusal has two readings.
`error: the branch 'X' is not fully merged` means unmerged commits, so treat the
branch as **stale**, not dead (see b).
`error: cannot delete branch 'X' used by worktree at ...` means the branch is
checked out in a linked worktree, so leave it alone, give it the status
`checked out in a worktree` in the step 4 plan table, and count it under
"Skipped" in the step 9 report; `clean-worktrees` is the skill that retires
the worktree first.

#### b. Upstream gone but the PR merged → delete

A branch whose remote was deleted shows `[gone]`:

```bash
git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads \
  | grep '\[gone\]'
```

For each, confirm the PR/MR actually merged before deleting (never assume):

```bash
# GitHub
gh pr list --head <branch> --state merged --json number,mergedAt | cat   # LIST_PRS

# GitLab
glab mr list --source-branch=<branch> --state merged 2>&1 | cat
```

- PR merged → `git branch -D <branch>` is acceptable here (the work landed via
  squash/rebase merge, so `-d` may not see it as merged). Confirm the merge
  first.
- No merged PR and unique commits exist → **stale local work**: don't delete;
  offer to push it and open an MR (step 7 mechanics).

**Read the PR, not local ancestry, to decide whether the work landed.** In a
repo that squash-merges --- `ucdavis/bcs` and `Morrison-Lab/ai-config` both do
--- a branch whose work is already on `main` still reports a non-zero
ahead-count, is not an ancestor of `main`, is absent from
`git branch --merged`, and is refused by `git branch -d`.
All four say "unmerged" about a branch that merged,
because the squash commit is a different commit.
So treat a `-d` refusal as *unproven*,
never as evidence the branch holds unique local work ---
that is what the merged-PR lookup above is for,
and why `-D` is the right tool once it comes back positive.

The converse still holds and is what keeps this safe: no merged PR **and**
unique commits means the work may exist nowhere else,
so it is never deleted without confirmation.
When the PR lookup is inconclusive,
check content rather than ancestry, since content survives a squash:

```bash
git show origin/main:<path> | grep <something-the-branch-added>   # did it land?
```

#### c. Never pushed, has unique commits → keep, but flag

```bash
git for-each-ref --format='%(refname:short) %(upstream)' refs/heads \
  | awk '$2=="" {print $1}'      # local branches with no upstream at all
```

Report these as "local-only, unpushed" and ask before doing anything — they may
be in-progress work that hasn't been pushed yet. Don't delete without
confirmation.

Apply the same dry-run discipline to local deletions as step 4 does for remote
branches — **no silent local deletions**. If you're doing a full local+remote
sweep, fold these local rows into the step-4 plan and present them together; if
you're running the local pass on its own, present a standalone local plan here
and wait for confirmation before deleting anything.

A standing [`daytb`](../daytb/SKILL.md) grant lifts this confirm step for the safe cases --- deleting a merged local branch is one of the local-git housekeeping actions that grant explicitly covers.
The skill's own safety preconditions are unchanged, and anything carrying commits reachable from no remote still asks.

### 9. Report

Print a summary covering **both** local and remote:

```
## Branch Cleanup Complete — <timestamp>

### Deleted — remote (dead)
- `old-feature` (last commit 2025-03-15, merged into main)

### Deleted — local (merged / upstream gone)
- `add-wrap-up-skill` (PR #26 merged; local straggler)
- `ums-session-learnings` (merged into main)

### Rebased + MR opened (stale)
- `wip-refactor` → [!85](url) (rebased, 3 commits ahead)

### Skipped (active/new)
- `fix/42-typo` — open MR !80
- `experiment` — created 2 days ago

### Flagged — local-only, unpushed (left alone)
- `scratch-idea` — 4 unpushed commits, no MR; your call

### Failed (conflicts)
- `ancient-branch` — rebase conflicts, needs manual resolution
```

## Safety rules

- **A merged PR settles that the work landed --- stop measuring there.**
  The content checks above exist for branches whose fate is *unknown*.
  Once `gh pr list --state merged` names a PR for the branch, residual
  differences against `main` are the branch's pre-review draft versus the
  post-review text that actually merged, and mean nothing about safety.
  Measuring anyway invents doubt about the one case that is already certain:
  in a 2026-08-02 sweep, 47 of 50 local branches had merged PRs and several
  scored under 90% on a line-presence check purely because review had reworded
  them.
- **A GitHub branch is never the only copy of a PR's work.**
  `refs/pull/N/head` is retained permanently and resolves after the head
  branch is deleted, so "delete the branch" and "lose the work" are different
  events on GitHub.
  This does not weaken the local-only rule below --- a branch that was **never
  pushed** has no PR ref behind it, and that is exactly the case that needs
  confirmation.
- **Never delete `main`, `master`, `develop`, or any protected branch.**
- **Never force-push to a branch with an open MR** without rebasing cleanly.
- **Always present the plan first** — no silent deletions.
- **Check for active work** before touching any branch.
- **Preserve local branches** the user is currently on (`git branch --show-current`).
- **Don't delete branches newer than 7 days** — they might be in-progress work
  that just hasn't gotten an MR yet.
- **Prefer `git branch -d` over `-D`** for local deletions — `-d` refuses unless
  the branch is merged, which catches "I thought this landed but it didn't."
  Only use `-D` after confirming the PR merged (squash/rebase merges can leave a
  local branch that `-d` won't recognize as merged).
- **Don't read a successful `-d` as proof the work reached `main`.**
  Per `git-branch(1)`, the branch must be fully merged "in its upstream branch,
  or in HEAD if no upstream was set".
  So a branch still tracking a live `origin/<name>` passes on the *upstream*
  check alone, printing `warning: deleting branch 'X' that has been merged to
  'refs/remotes/origin/X', but not yet merged to HEAD.`
  Only a `[gone]` upstream falls back to the HEAD comparison.
  Both outcomes are routine in one sweep (18 `-d` / 11 `-D` across 29 branches
  in one 2026-07-29 run), so whether `-d` sufficed or `-D` was required is not
  a classification signal --- step 3 is.
- **Never delete a local-only unpushed branch without confirmation** — if it has
  unique commits and no remote, that work exists nowhere else.

## Relationship to other skills

- **`sync-pr-branch`** — used internally when rebasing stale branches
- **`claim-pr`** — checked to avoid touching claimed branches
- **`ardi`** — user may want to ARDI the newly opened MRs afterward
- **`clean-worktrees` / `cw`** — the worktree counterpart. This skill sweeps
  *branches*; that one sweeps the *worktrees* a branch is checked out into. Run
  both so neither a dead worktree nor an orphaned branch lingers.

- **`clean-git`** --- the combined sweep.
  Runs `clean-worktrees` first, then this skill,
  because a branch held by a worktree cannot be deleted.

## Anti-patterns

- ❌ Deleting branches without checking for open MRs/issues first
- ❌ Force-pushing a broken rebase
- ❌ Touching branches that someone is actively working on
- ❌ Deleting branches without user confirmation
- ❌ Rebasing branches that have open MRs (use merge instead, or skip)
