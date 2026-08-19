# Case records: flag-session-boundaries

Worked-example case records for the rules in
[`flag-session-boundaries.md`](flag-session-boundaries.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Leftover harness branches in scoped repositories

The harness assigns its branch name in *every* scoped repo and leaves each one checked out on it, including repos the session never opens.
So the sweep finds the branch sitting in places nothing in the conversation points at, and two things follow from that.

Point 3 of [`keep-checkouts-fresh`](keep-checkouts-fresh.md)'s "The working repo's main checkout" step quietly does nothing in those repos.
It fast-forwards `main` only when `main` is the checked-out branch, and here it never is, so a repo you never opened stays as stale as the container left it.

And `git branch -D` refuses, with `cannot delete branch 'X' used by worktree at '<path>'`.
That message names a worktree, which reads as a second checkout holding live parallel work --- the one condition that would genuinely make deleting the branch unsafe.
It is almost always just that repo's ordinary checkout sitting on the branch.
So the cautious reading is the wrong one here, and acting on it leaves a dead branch in place for the next session to re-discover and re-adjudicate.

Settle liveness from the branch's own commits rather than from the error text, and settle it before deleting anything.
Zero commits in `origin/main..<branch>`, plus absence from the remote, together mean there is nothing to lose.
Resist adding an ancestry check beside the first of those.
An empty `origin/main..<branch>` range is the same fact as `git merge-base --is-ancestor <branch> origin/main` succeeding, so running both confirms one thing twice rather than two things once.
Once liveness is settled, switch that repo to `main` --- which is what the refusal is really asking for --- and then delete.
