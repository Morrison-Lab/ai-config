---
name: clean-git
description: "Sweep dead worktrees then dead branches, in that order."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Clean Git

Sweep a repo's dead **worktrees** and dead **branches** in one pass,
in the order that actually works,
behind a single dry-run plan and a single confirmation.

This skill owns **sequencing and presentation only**.
Every classification decision belongs to the two skills it drives:

- [`clean-worktrees`](../clean-worktrees/SKILL.md) --- which worktrees are dead.
- [`clean-branches`](../clean-branches/SKILL.md) --- which branches are dead, stale, or active.

Read both before running this.
Do not restate or re-derive their tables here;
a divergence between this file and either of them is a bug in this file.

## When this fires

- "clean git", "clean up the repo", "sweep worktrees and branches"
- "clean everything", "tidy up git", "prune it all"
- After a batch of PRs merge and both `.claude/worktrees/` and the branch list have grown.

Use the individual skills instead when only one half is wanted.

## Why the order is the whole point

Worktrees first, then branches.
Not a preference --- a constraint.

A branch checked out in a worktree cannot be deleted.
`git branch -d` and `git branch -D` both refuse with
`cannot delete branch 'X' used by worktree`.
So a branch-first sweep leaves every worktree-held branch undeletable,
and does it behind a message this corpus has already had to warn about:
[`flag-session-boundaries`](../../shared/workflow/flag-session-boundaries.md)
records "**Don't:** read `used by worktree` as evidence that a separate live worktree exists",
because the usual cause is that repo's own ordinary checkout sitting on the branch.

Both skills already state this order in their own cross-references.
Nothing enforced it except the user typing two commands in sequence.
That is the gap this skill closes.

## The overlap this skill has to resolve

[`clean-worktrees` step 5](../clean-worktrees/SKILL.md) **already deletes each dead worktree's branch inline**,
with a documented `-d` then `-D` fallback.
So the two passes genuinely overlap,
and a naive merged plan double-counts:
the branch pass, computed up front, lists branches the worktree pass is about to delete on its own.

The orchestrator resolves this by **subtraction**, not by suppression:

1. Compute the worktree plan.
2. Derive `INLINE` --- the set of branches attached to worktrees classified dead,
   which the worktree pass will delete itself.
3. Compute the branch plan.
4. Subtract `INLINE` from the branch plan's delete list,
   and report the subtracted count rather than dropping it silently.

A branch in `INLINE` that the branch pass had classified **active** is a
contradiction between the two skills, not a subtraction.
Stop and surface it.

## Procedure

### 1. Classify, both passes, no mutation

Run [`clean-worktrees`](../clean-worktrees/SKILL.md) steps 1 through 3.
Run [`clean-branches`](../clean-branches/SKILL.md) steps 1 through 3 and step 8's local enumeration.
Neither pass removes, deletes, rebases, or pushes anything yet.

Derive the `INLINE` set from the worktree classification:

```bash
git worktree list --porcelain | awk '/^worktree /{p=$2} /^branch /{sub("refs/heads/","",$2); print $2"\t"p}'
```

### 2. Present one combined plan --- wait for confirmation

```
## Git Cleanup Plan --- <timestamp>

### Worktrees to remove (branch deleted inline)
### Worktrees flagged --- dirty / unpushed (left alone)
### Branches to delete --- remote
### Branches to delete --- local
### Branches to rebase + open MR (stale)
### Skipped --- active / new / current
### Subtracted from the branch pass (deleted inline by the worktree pass): <N>
```

One confirmation covers the whole plan.
Do not proceed on silence.

### 3. Execute --- worktrees, then branches

Run `clean-worktrees` steps 5 and 6.
Then run `clean-branches` steps 5 through 8.

Re-derive the branch list between the two.
The worktree pass has just changed it,
and step 1's plan is a prediction rather than a fact.
A branch that was in `INLINE` and is still present after the worktree pass
means that worktree removal failed --- report it, do not delete the branch here.

### 4. Report

Emit both skills' report sections under one heading,
with the subtraction count carried through from step 2
so the branch pass's smaller numbers are legible rather than surprising.

## Safety rules

Both skills' safety rules apply unchanged and in full.
This skill adds no exceptions to either,
and it weakens neither.

Three that the combined form makes easier to get wrong:

- **One confirmation is not blanket authority.**
  It covers the plan as presented.
  Anything the re-derivation in step 3 turns up that was not in that plan
  needs its own confirmation.
- **A failure in the worktree pass stops the branch pass.**
  The branch pass's plan was computed assuming the worktree pass succeeded.
  Do not carry on into a sweep whose premise just failed.
- **Never `--force` a dirty worktree to keep the combined run tidy.**
  A half-finished sweep is the correct outcome there.

## Relationship to other skills

- **[`clean-worktrees`](../clean-worktrees/SKILL.md) / `cw`** --- the first pass.
  Run it alone when only worktrees are in question.
- **[`clean-branches`](../clean-branches/SKILL.md) / `cb`** --- the second pass.
  Run it alone in a repo with no worktrees.
- **[`wrap-up`](../wrap-up/SKILL.md)** --- its state sweep surfaces leftover
  worktrees and branches.
  This is the skill it hands off to.
- **[`post-merge`](../post-merge/SKILL.md)** --- per-PR tidy-up.
  This is the repo-wide bulk form.
- **[`session-lock`](../session-lock/SKILL.md)** --- creates the worktrees swept
  here.
  Its registry is what keeps a live session's worktree off the plan.

Do not confuse this with **`clear-all`**, which is an alias for
[`gia`](../gia/SKILL.md) and does something entirely unrelated ---
opening PRs for every issue and driving them to clean.
The two names are one letter apart on purpose-avoidance grounds:
this skill is deliberately **not** called `clean-all`.

## Anti-patterns

- Running the branch pass first, then reading `used by worktree` as a live parallel session.
- Presenting two separate confirmations and calling that a combined sweep.
- Dropping the inline-deleted branches from the plan silently, so the branch count looks wrong.
- Re-stating either skill's classification table here, which guarantees the copies drift.
- Continuing into the branch pass after a worktree removal failed.
