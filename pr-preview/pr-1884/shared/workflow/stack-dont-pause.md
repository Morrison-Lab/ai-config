The clear-all family --- `ardia`, `gia`, `gii`, `gip`, and the `clear-all`
alias --- clears a whole queue of PRs and issues in one run. Merging stays
human-gated (see `ardi.md`: the loop reports a PR ready, it never self-merges).
But that gate stops the *merge*, not the *sweep*.

**Not having self-merge freedom is never a reason to pause between items.**
Driving a PR to fully clean ends that PR's ARDI loop, not the whole run. Once a
PR is clean, move straight to the next item --- don't stall waiting for a human
to merge it first. Waiting for a merge you're not allowed to perform would halt
the queue indefinitely, which is exactly what these skills exist to avoid.

Keep the loop moving by **stacking**. When the next item isn't naturally
independent of a completed-but-unmerged PR --- it needs that PR's code, or it
would modify the same passages that PR changes (not merely the same files ---
see `stack-prs`'s decision gate) --- branch it off that PR's tip instead of
`main`, so it stacks on top. Note the dependency in the new PR's description
(`Stacked on #N --- merge that first`) and track the merge order for the final
report. Branch off `main` only when the next item is genuinely independent of
every open PR. See the [`stack-prs`](../../skills/stack-prs/SKILL.md) skill for
the mechanics --- branching off the base PR's tip, setting the new PR's `base`,
keeping it in sync as the base branch moves, and re-targeting to `main` once
the base merges.

So the between-item decision is always *keep going*; the only open question is
the base branch:

- **Independent of every open PR** (or the PR it depended on has already
  merged) --- branch from `origin/main`.
- **Depends on a clean-but-unmerged PR** --- branch from that PR's tip, and
  stack.

A genuinely blocked or ambiguous item is **not** a stop either --- surface it
and bypass it, working the rest of the queue around it. It halts the loop only
when every remaining item (PR or issue) depends on it, so no independent work is
left to move on to.

So the loop stops only when the queue runs dry (or collapses to items all
blocked on one stuck item), or a skill's own checkpoint fires (e.g. GII's
5-issue pause) --- never because an item is blocked while independent work
remains, and never merely because a finished PR is still waiting on a human
merge.
