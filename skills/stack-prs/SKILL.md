---
name: stack-prs
description: "Stack a PR on another open PR only when verifiably necessary — first run the decision gate (does solving this issue depend on solving the other? will both PRs heavily modify the same code passages?), and branch from `main` when neither holds. When stacking is warranted: branch off the base PR's tip, open the dependent PR with its `base` set to that PR's branch, and keep it in sync as the base branch moves (or re-point it to `main` once the base merges). Use when asked to 'stack this PR on #N', 'branch off that PR', 'stack-prs', 'should I stack this?', 'does this need to stack on #N?', or whenever new work may depend on an open, unmerged PR's code."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# stack-prs

Create (or maintain) a PR that is **stacked** on another open, unmerged PR:
its branch starts from the base PR's tip instead of `main`, and its own PR's
`base` points at the base PR's branch instead of `main`. This is the
general-purpose entry point for stacking — other skills (`ardia`, `gii`/`gia`,
`stack-dont-pause`) each stack as a side effect of their own loop; this one
does it directly when you already know you want to branch off another PR.

## When this fires

- "stack this on #N", "stack-prs", "branch off that PR", "make this depend on
  PR #N".
- The decision question itself — "should I stack this?", "does this need to
  stack on #N?" — routes here too: the gate below is the answer.
- New work may need another open PR's code, or might conflict with it
  if branched from `main` in parallel — the gate below determines which.

It does **not** fire when the work is independent of every open PR — branch
from `main` as usual. Don't stack just because two PRs happen to be open at
the same time.

## When to stack vs. branch from `main` — the decision gate

Branching from `main` is the default; stacking needs **positive, verified
evidence**. A stack adds a real ordering constraint (the base PR must merge
first, or the stack must be re-pointed around it) and a per-push sync burden
(step 3 below), so run this gate before step 1, every time — including when
the instruction was "stack this on #N": confirm the dependency is real
rather than assumed. Stack only when at least one of the two tests passes.

### Test A — dependency: solving this issue depends on solving the other

Either kind of evidence counts, but check it — don't infer it from titles:

- **The issues declare it.** The new work's issue is marked blocked-by /
  "depends on" the base PR's issue, or the two are ordered sub-issues of one
  parent. Read the issue and its linked PRs
  (`gh issue view <N>` — VIEW_ISSUE; `ISSUE_LINKED_PRS` for the timeline).
- **The code requires it.** A function, file, or config key the new work
  must call or edit is added by the base PR and absent from `main`. Confirm
  both halves:

  ```bash
  gh pr diff <base-N> | grep -n "^+.*<needed-symbol-or-path>"   # DIFF_PR — the base PR adds it...
  git fetch origin main -q                                  # FETCH
  git grep -n "<needed-symbol-or-path>" origin/main         # ...and main does NOT already have it
  ```

  If the second grep finds it on `origin/main`, the dependency is on
  already-merged code — branch from `main`.

### Test B — overlap: both PRs will heavily modify the same passages

File-list overlap alone is **not** enough — two PRs editing disjoint regions
of the same file usually merge cleanly, and
[`sync-with-main`](../../shared/workflow/sync-with-main.md) absorbs that
drift. Check overlap at the passage level:

```bash
gh pr diff <base-N> --name-only        # DIFF_PR — the base PR's changed files
gh pr diff <base-N>                    # then read its hunks in any file you'll also touch
```

Stack when the planned work would rewrite the same function, block, or
section the base PR's hunks change — or append at the same insertion point
(e.g. the end of a growing numbered list, the append-collision case
`sync-with-main` documents). Branch from `main` when the shared file's edits
land in different regions.

### Neither test passes → branch from `main`

Merely concurrent PRs stay independent; stacking should not be reached for
out of caution. See
[`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md) for the same
decision made inline inside a sweep loop.

## Procedure

### 1. Create the dependent branch off the base PR's tip

```bash
git fetch origin <base-branch>                              # FETCH
git checkout -b <dependent-branch> "origin/<base-branch>"    # CREATE_BRANCH
```

Use the base PR's `headRefName` (`gh pr view <base-N> --json headRefName -q
.headRefName`, or `mcp__github__pull_request_read` method `get` in a remote
session) as `<base-branch>` — never guess the branch name from the PR title.

### 2. Open the dependent PR with `base` set to the base branch

```bash
gh pr create --base <base-branch> --title "<title>" --body "Stacked on #<base-N> --- merge that first.

<description>"   # CREATE_PR
```

In a remote/web session without `gh`, use `mcp__github__create_pull_request`
with `base: "<base-branch>"`. Note the dependency explicitly in the body
(`Stacked on #<base-N>`) so anyone scanning the PR list sees the relationship
at a glance (`ardia`'s own stacking detection uses `baseRefName`, not the body
text — see below).

A stack is the archetypal merge-order constraint, so raise it the way
`CLAUDE.md`'s "Surface merge-order constraints" section prescribes rather than
leaving it to the plain `Stacked on #<base-N>` line: lead the dependent PR's
body with a `> [!IMPORTANT]` alert naming the prerequisite, and report the
order in chat under the boxed `### 🔀 MERGE ORDER` marker. Skip that section's
third surface, draft-gating, here --- `base` already points at the base
branch, so GitHub cannot merge this PR into `main` out of order in the first
place. The alert and the marker exist for the human's reading order, not to
enforce a constraint the stack itself already enforces.

If the dependent work is being opened up front per
[`pr-on-claim`](../../shared/workflow/pr-on-claim.md), open it as a draft from
an empty commit exactly as that skill describes, just with `--base
<base-branch>` instead of `main`.

### 3. Keep the dependent branch in sync as the base branch moves

Whenever the base PR gets new commits (a review fix, a rebase, `main` merged
into it), merge that movement into the dependent branch before the next push
or review trigger — the same standing rule
[`sync-with-main`](../../shared/workflow/sync-with-main.md) applies to `main`,
here applied to the base branch instead:

```bash
git fetch origin <base-branch>     # FETCH
git merge "origin/<base-branch>"   # MERGE_BRANCH
```

Resolve any conflicts (see [`resolve-conflicts`](../resolve-conflicts/SKILL.md)),
run the repo's pre-commit checks, then push. Do this before every push and
before every fresh review request, exactly as `sync-pr-branch` does for `main`.

### 4. When the base PR merges, re-point the dependent PR at `main`

Once the base branch's commits land on `main` (the base PR merges), the
dependent PR no longer needs to target the base branch — retarget it so it
merges normally and the stacking note stops being misleading:

```bash
git fetch origin main            # FETCH
git merge origin/main            # MERGE_BRANCH — picks up the now-merged base commits via main
gh pr edit <dependent-N> --base main   # EDIT_PR
```

In a remote/web session, use `mcp__github__update_pull_request` with `base:
"main"`. After retargeting, GitHub recomputes the diff against `main` — it
should now show only the dependent PR's own changes, since the base PR's
commits are already on `main`. If it doesn't (the merge above was a no-op or
missed something), re-check before proceeding. Update the PR body to drop the
`Stacked on #<base-N>` note --- and the `> [!IMPORTANT]` merge-order alert
from step 2 --- once this step is done; both describe a constraint that no
longer exists, and a stale alert trains readers to ignore the next real one.

### 5. If the base PR is abandoned or closed unmerged

Re-target the dependent branch onto `main` directly and drop the base PR's
unmerged commits from the dependent branch's history — don't leave a PR
silently based on a branch that will never land:

```bash
git fetch origin main    # FETCH
git rebase --onto origin/main "origin/<base-branch>" <dependent-branch>
gh pr edit <dependent-N> --base main   # EDIT_PR
```

This rewrites the dependent branch's history — **get explicit approval from
the user before running it**, and before force-pushing the result
(`git push --force-with-lease origin <dependent-branch>` — `PUSH`), since it
discards the abandoned base PR's commits from a published branch.

## Relationship to other skills

- **`ardia`** — detects stacked PRs via `baseRefName` and sequences them (base
  before derived) as part of sweeping the whole open-PR queue. This skill is
  the direct, single-PR counterpart: use it when you already know you want to
  stack, rather than letting a sweep discover the relationship.
- **`stack-dont-pause`** (`shared/workflow/stack-dont-pause.md`) — the rule
  that a clean-but-unmerged PR is not a reason to pause a sweep; stack new,
  dependent work on it instead of waiting. This skill is the mechanics that
  rule points to.
- **`sync-pr-branch`** / **`merge-main`** — the analogous "keep in sync"
  procedure for a branch and `main`. Step 3 here is that same procedure
  applied to a moving base branch instead of `main`.
- **`resolve-conflicts`** (`rc`) — used in step 3 when the base branch's
  movement conflicts with the dependent branch.
- **`pr-on-claim`** — step 2's draft-PR-up-front pattern, adapted to target
  the base branch instead of `main`.
- **`gii`** / **`gia`** — stack issues' PRs on a prior unmerged issue's branch
  as part of their serial loop
  ([#123](https://github.com/d-morrison/ai-config/issues/123)); this skill is
  the reusable primitive they could each call instead of reimplementing the
  mechanics.

## Anti-patterns

- ❌ Guessing the base PR's branch name from its title instead of reading
  `headRefName` — a mismatch silently branches from the wrong ref.
- ❌ Stacking two PRs that are merely concurrent but not actually dependent —
  branch from `main` instead; stacking adds a real ordering constraint.
- ❌ Skipping the decision gate because the instruction already said "stack
  this" — the gate confirms the dependency is real; an assumed dependency
  that fails both tests should be surfaced back, not silently stacked.
- ❌ Treating file-list overlap alone as proof of a conflict (Test B) —
  disjoint regions of the same file merge cleanly from `main`; only
  same-passage edits (or a shared insertion point) justify the stack.
- ❌ Claiming a code dependency without checking `origin/main` — a symbol the
  base PR touches may already be merged, making the dependency moot.
- ❌ Letting the dependent branch drift after the base branch gets new commits
  — sync it before every push, not just once at creation.
- ❌ Leaving the dependent PR targeting the base branch after the base PR
  merges — retarget to `main` (step 4) so the diff and merge behave normally.
- ❌ Force-pushing or rebasing a published dependent branch without telling
  the user, even when the base PR was abandoned (step 5).
