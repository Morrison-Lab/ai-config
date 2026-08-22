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

`INLINE` can also collide with the 8c bucket, and that one is a **precedence** question rather than a contradiction: a branch with no configured upstream can sit in a Dead worktree, so it is both “deleted inline by the worktree pass” and “local-only, kept”. **8c wins.** Drop it from `INLINE`, leave it in the flagged bucket, and say so in the plan — the two buckets disagree about whether the work exists anywhere else, and the conservative reading is the one that keeps it.

## Procedure

### 1. Classify, both passes

Everything in this step shares a scratch directory, so create it **first**. Several commands write into `$TMP`, and an undefined `$TMP` sends each redirect to the filesystem root:

``` bash
TMP=$(mktemp -d)
```

Run [`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) steps 1 through 3. Run [`clean-branches`](../../skills/clean-branches/SKILL.llms.md) steps 1 through 3.

For the local half, run step 8’s **classification** only. `clean-branches` step 8 has no separately-runnable enumeration sub-step: each of 8a, 8b, and 8c bundles its listing command and its `git branch -d`/`-D` into one fenced block. So name the read half explicitly rather than delegating to a sub-step that does not exist:

``` bash
# Branches checked out in ANY worktree cannot be deleted. clean-branches 8a
# gets this free from the `*` prefix its column-anchored grep filters, but
# `--format` prints no `*`/`+` marker at all, so switching to it to dodge the
# `+` mangling ALSO drops that protection. Derive the set explicitly instead.
git worktree list --porcelain -z | tr '\0' '\n' \
  | awk '/^branch /{b=substr($0,8); sub("refs/heads/","",b); print b}' \
  | sort -u > "$TMP/checked-out.txt"

# 8a --- merged into main. `--format` is clean-worktrees step 3c's documented
# remedy, applied here because THIS skill guarantees worktrees exist: plain
# `git branch --merged` prefixes a worktree-checked-out branch with `+`, which
# mangles the name and defeats a column-anchored grep.
git branch --merged origin/main --format='%(refname:short)' \
  | grep -vxF -e main -e master \
  | grep -vxFf "$TMP/checked-out.txt"

# 8b --- upstream gone. clean-branches' own command, verbatim.
git for-each-ref --format='%(refname:short) %(upstream:track)' refs/heads \
  | grep '\[gone\]'

# 8c --- NO CONFIGURED UPSTREAM. That is what this command detects, and it is
# wider than clean-branches' "never pushed, has unique commits" label: it also
# returns branches whose upstream was unset, branches already merged, and
# main/current unless excluded. Filter before presenting.
git for-each-ref --format='%(refname:short) %(upstream)' refs/heads \
  | awk '$2=="" {print $1}' \
  | grep -vxE 'main|master' \
  | while read -r b; do
      [ "$(git rev-list --count "origin/main..$b")" -gt 0 ] && echo "$b"
    done
```

**Do not run the `git branch -d` or `-D` lines that share those blocks.** Those deletions belong to this skill’s step 3, after the gate. `clean-branches` is safe on its own here only because of a prose instruction after all three sub-steps (“no silent local deletions … wait for confirmation”), not because the blocks are deletion-free — so an orchestrator that cites the block without that prose inherits none of the protection.

**Neither pass touches a live worktree, branch, or remote before the gate — with one exception, and it is worth naming rather than rounding off.** `clean-worktrees` step 2 runs `git worktree prune -v` for real, not `--dry-run`, so a mutation has already happened by the time the plan is presented.

That prune is safe by construction rather than by convention: `git worktree prune` only drops administrative records for worktrees whose directory is **already gone from disk**, so there is no state it can destroy and nothing a confirmation could protect. Say so in the plan anyway, per step 2’s `Pruned stubs` line. A silent mutation under a heading promising none is how a reader stops believing the rest of the guarantees.

**A second pre-gate mutation, and this one is not safe by construction.** Both delegates refresh remote-tracking state in their classify steps — [`clean-worktrees`](../../skills/clean-worktrees/SKILL.llms.md) step 3 and [`clean-branches`](../../skills/clean-branches/SKILL.llms.md) step 2 each run `git fetch --prune origin`. `--prune` deletes remote-tracking refs whose upstream branch is gone, and such a ref can be the last thing in this clone pointing at those commits.

So “nothing that can lose work happens before confirmation” is **false as an unconditional claim**, and narrowing it further would keep the same defect in smaller print. Snapshot the refs first instead, which makes the statement true rather than merely careful:

``` bash
git for-each-ref --format='%(objectname) %(refname)' refs/remotes/origin \
  > "$TMP/pre-prune-refs.txt"
```

Report the snapshot’s path in the plan. Anything the prune removed is recoverable from it for as long as the objects survive gc, and a reader who knows the file exists can check before confirming.

With that snapshot taken, the invariant the gate protects is: **nothing that can lose work happens before confirmation, and the one pre-gate mutation that could is recorded first.**

Derive the `INLINE` set. This first command produces the raw worktree-to-branch mapping, every worktree included — which is **not** `INLINE`:

``` bash
# -z plus NUL-safe parsing: a worktree path may contain spaces, and `$2`
# truncates it, silently dropping that branch from INLINE.
git worktree list --porcelain -z \
  | tr '\0' '\n' \
  | awk '/^worktree /{p=substr($0,10)}
         /^branch /{b=substr($0,8); sub("refs/heads/","",b); print b"\t"p}' \
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

Give it the negative control every filter needs: `wc -l` both files, and confirm `inline.txt` is shorter than `wt-branches.tsv` whenever any live worktree exists. An `INLINE` the same length as the raw mapping means the filter did not run: every live worktree’s branch is still in it, including the main checkout’s, so the contradiction rule fires spuriously on all of them.

Using the raw mapping as `INLINE` breaks the sweep immediately rather than subtly, which is worth stating because it looks like a shortcut that would merely over-subtract. Every live worktree appears in it, including the main checkout and the one you are standing in. Their branches are `Active` to the branch pass by construction, so the contradiction rule stated earlier fires on the first one and halts a sweep that had nothing wrong with it.

### 2. Present one combined plan — wait for confirmation

    ## Git Cleanup Plan --- <timestamp>

    ### Pruned stubs (already done --- records for directories already gone)
    ### Worktrees to remove (branch deleted inline)
    ### Worktrees flagged --- dirty / unpushed (left alone)
    ### Branches to delete --- remote
    ### Branches to delete --- local
    ### Branches to rebase + open MR (stale)
    ### Skipped --- active / new / current
    ### Branches flagged --- no upstream, unique commits (kept, never deleted)
    ### Survived both passes --- needs a human
    ### Pre-prune ref snapshot: <path>
    ### Subtracted from the branch pass LOCAL list (deleted inline by the worktree pass): <N>

One confirmation covers the whole plan. Do not proceed on silence.

### 3. Execute — worktrees, then branches

Run `clean-worktrees` steps 5 and 6. Then run `clean-branches` steps 5 through 8.

Re-derive the branch list between the two. The worktree pass has just changed it, and step 1’s plan is a prediction rather than a fact. A branch that was in `INLINE` and is still present after the worktree pass has **two** possible causes, and they call for opposite responses:

``` bash
# -x is load-bearing: without it, a removed `.../wt/feature` still matches a
# surviving `worktree .../wt/feature-2` and reports a false STILL-THERE.
git worktree list --porcelain | grep -Fqx "worktree $path" \
  && echo STILL-THERE || echo REMOVED
```

- **The worktree is gone.** Then removal succeeded and `git branch -d` simply refused. That is routine rather than exceptional: `clean-worktrees` step 5 documents the refusal at length for squash-merged branches, and measured an 18/11 `-d`/`-D` split across a 29-branch sweep. Hand it to the branch pass **only if it falls in 8b**, whose `[gone]` branches get merged-PR confirmation and may escalate to `-D`. 8a retries `git branch -d` and says “never `-D`” explicitly, so it has no escalation path. A branch merged into `origin/main` but not into `HEAD`, with no configured upstream and no merged PR, therefore survives **both** passes. Report it as `Survived both passes --- needs a human`, since silently leaving it is what makes a sweep look complete when it is not.
- **The worktree is still there.** Then removal genuinely failed, which stops the branch pass.

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
