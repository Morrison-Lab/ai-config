# Clean Git

Sweep a repo’s dead **worktrees** and dead **branches** in one pass, in the order that actually works, behind a single dry-run plan and a single confirmation.

This skill owns **sequencing and presentation only**. Every classification decision belongs to the two skills it drives:

- [`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) — which worktrees are dead.
- [`clean-branches`](../../skills/clean-branches/SKILL.llms.md) — which branches are dead, stale, or active.

Read both before running this. Do not restate or re-derive their tables here; a divergence between this file and either of them is a bug in this file.

## When this fires

- “clean git”, “clean up the repo”, “sweep worktrees and branches”
- “clean everything”, “tidy up git”, “prune it all”
- After a batch of PRs merge and both `.claude/worktrees/` and the branch list have grown.

Use the individual skills instead when only one half is wanted.

## Why the order is the whole point

Worktrees first, then branches. Not a preference — a constraint.

A branch checked out in a worktree cannot be deleted. `git branch -d` and `git branch -D` both refuse with `cannot delete branch 'X' used by worktree`. So a branch-first sweep leaves every worktree-held branch undeletable, and does it behind a message this corpus has already had to warn about: [`flag-session-boundaries`](../../shared/workflow/flag-session-boundaries.md) records “**Don’t:** read `used by worktree` as evidence that a separate live worktree exists”, because the usual cause is that repo’s own ordinary checkout sitting on the branch.

Both skills already state this order in their own cross-references. Nothing enforced it except the user typing two commands in sequence. That is the gap this skill closes.

## The overlap this skill has to resolve

[`clean-worktrees` step 5](../../skills/clean-worktrees/SKILL.llms.md) **already deletes each dead worktree’s branch inline**, with a documented `-d` then `-D` fallback. So the two passes genuinely overlap, and a naive merged plan double-counts: the branch pass, computed up front, lists branches the worktree pass is about to delete on its own.

The orchestrator resolves this by **subtraction**, not by suppression:

1.  Compute the worktree plan.
2.  Derive `INLINE` — the set of branches attached to worktrees classified dead, which the worktree pass will delete itself.
3.  Compute the branch plan.
4.  Subtract `INLINE` from the branch plan’s **local** delete list only, and report the subtracted count rather than dropping it silently.

`clean-worktrees` step 5 deletes with `git branch -d`, which is a **local** delete and never touches a remote ref. So subtracting `INLINE` from the remote list would report a stale `origin/<branch>` as handled while nothing in either pass deletes it. The remote list passes through untouched.

A branch in `INLINE` that the branch pass had classified **active** is a contradiction between the two skills, not a subtraction. Stop and surface it.

## Procedure

### 1. Classify, both passes

Run [`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) steps 1 through 3. Run [`clean-branches`](../../skills/clean-branches/SKILL.llms.md) steps 1 through 3 and step 8’s local enumeration.

**Neither pass touches a live worktree, branch, or remote before the gate — with one exception, and it is worth naming rather than rounding off.** `clean-worktrees` step 2 runs `git worktree prune -v` for real, not `--dry-run`, so a mutation has already happened by the time the plan is presented.

It is safe by construction rather than by convention: `git worktree prune` only drops administrative records for worktrees whose directory is **already gone from disk**, so there is no state it can destroy and nothing a confirmation could protect. Say so in the plan anyway, per step 2’s `Pruned stubs` line. A silent mutation under a heading promising none is how a reader stops believing the rest of the guarantees.

The invariant the gate actually protects is therefore narrower than “no mutation”, and stating it precisely is what makes it worth anything: **nothing that can lose work happens before confirmation.**

Derive the `INLINE` set. The command below is **not** `INLINE` — it is the raw worktree-to-branch mapping, every worktree included:

``` bash
git worktree list --porcelain \
  | awk '/^worktree /{p=$2} /^branch /{sub("refs/heads/","",$2); print $2"\t"p}' \
  > "$TMP/wt-branches.tsv"
```

`INLINE` is the subset whose **worktree** [`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) step 3 classified **Dead**. Every other step number on this page belongs to *this* skill, so that one is labelled with its file and the rest are not.

Write those Dead paths out, then intersect:

``` bash
# One Dead worktree path per line, from clean-worktrees step 3's classification.
printf '%s\n' "${DEAD_WORKTREE_PATHS[@]}" | sort -u > "$TMP/dead-worktrees.txt"

# INLINE: the branch column, kept only where the worktree column is Dead.
awk -F'\t' 'NR==FNR { dead[$0]; next } $2 in dead { print $1 }' \
  "$TMP/dead-worktrees.txt" "$TMP/wt-branches.tsv" \
  | sort -u > "$TMP/inline.txt"
```

Give it the negative control every filter needs: `wc -l` both files, and confirm `inline.txt` is shorter than `wt-branches.tsv` whenever any live worktree exists. An `INLINE` the same length as the raw mapping means the filter did not run, which is the failure the next paragraph describes.

Using the raw mapping as `INLINE` breaks the sweep immediately rather than subtly, which is worth stating because it looks like a shortcut that would merely over-subtract. Every live worktree appears in it, including the main checkout and the one you are standing in. Their branches are `Active` to the branch pass by construction, so the contradiction rule below fires on the first one and halts a sweep that had nothing wrong with it.

### 2. Present one combined plan — wait for confirmation

    ## Git Cleanup Plan --- <timestamp>

    ### Pruned stubs (already done --- records for directories already gone)
    ### Worktrees to remove (branch deleted inline)
    ### Worktrees flagged --- dirty / unpushed (left alone)
    ### Branches to delete --- remote
    ### Branches to delete --- local
    ### Branches to rebase + open MR (stale)
    ### Skipped --- active / new / current
    ### Subtracted from the branch pass LOCAL list (deleted inline by the worktree pass): <N>

One confirmation covers the whole plan. Do not proceed on silence.

### 3. Execute — worktrees, then branches

Run `clean-worktrees` steps 5 and 6. Then run `clean-branches` steps 5 through 8.

Re-derive the branch list between the two. The worktree pass has just changed it, and step 1’s plan is a prediction rather than a fact. A branch that was in `INLINE` and is still present after the worktree pass has **two** possible causes, and they call for opposite responses:

``` bash
git worktree list --porcelain | grep -Fq "worktree $path" && echo STILL-THERE || echo REMOVED
```

- **The worktree is gone.** Then removal succeeded and `git branch -d` simply refused. That is routine rather than exceptional: `clean-worktrees` step 5 documents the refusal at length for squash-merged branches, and measured an 18/11 `-d`/`-D` split across a 29-branch sweep. Leave it to the branch pass, which is equipped to confirm the merge and escalate to `-D`.
- **The worktree is still there.** Then removal genuinely failed, and the safety rule below applies.

Distinguishing them matters because the safety rule stops the branch pass on a worktree failure. Reading every surviving branch as a failure would abort the whole sweep on the commonest outcome there is.

### 4. Report

Emit both skills’ report sections under one heading, with the subtraction count carried through from step 2 so the branch pass’s smaller numbers are legible rather than surprising.

## Safety rules

Both skills’ safety rules apply unchanged and in full. This skill adds no exceptions to either, and it weakens neither.

Three that the combined form makes easier to get wrong:

- **One confirmation is not blanket authority.** It covers the plan as presented. Anything the re-derivation in step 3 turns up that was not in that plan needs its own confirmation.
- **A failure in the worktree pass stops the branch pass.** The branch pass’s plan was computed assuming the worktree pass succeeded. Do not carry on into a sweep whose premise just failed.
- **Never `--force` a dirty worktree to keep the combined run tidy.** A half-finished sweep is the correct outcome there.

## Relationship to other skills

- **[`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) / `cw`** — the first pass. Run it alone when only worktrees are in question.
- **[`clean-branches`](../../skills/clean-branches/SKILL.llms.md) / `cb`** — the second pass. Run it alone in a repo with no worktrees.
- **[`wrap-up`](../../skills/wrap-up/SKILL.llms.md)** — its state sweep surfaces leftover worktrees and branches. This is the skill it hands off to.
- **[`post-merge`](../../skills/post-merge/SKILL.llms.md)** — per-PR tidy-up. This is the repo-wide bulk form.
- **[`session-lock`](../../skills/session-lock/SKILL.llms.md)** — creates the worktrees swept here. Its registry is what keeps a live session’s worktree off the plan.

Do not confuse this with **`clear-all`**, which is an alias for [`gia`](../../skills/gia/SKILL.llms.md) and does something entirely unrelated — opening PRs for every issue and driving them to clean. The two names are one letter apart on purpose-avoidance grounds: this skill is deliberately **not** called `clean-all`.

## Anti-patterns

- Running the branch pass first, then reading `used by worktree` as a live parallel session.
- Presenting two separate confirmations and calling that a combined sweep.
- Dropping the inline-deleted branches from the plan silently, so the branch count looks wrong.
- Re-stating either skill’s classification table here, which guarantees the copies drift.
- Continuing into the branch pass after a worktree removal failed.

Back to top
