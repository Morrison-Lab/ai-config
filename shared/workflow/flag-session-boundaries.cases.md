# Case Records: Flag Session Boundaries

Case records and worked examples for [`flag-session-boundaries.md`](flag-session-boundaries.md).

## Leftover harness branches in scoped repositories

The harness assigns its branch name in *every* scoped repo and leaves each one checked out on it, including repos the session never opens.
So the sweep finds the branch sitting in places nothing in the conversation points at.

Two consequences follow:
1. Fast-forwarding `main` quietly does nothing in those repos because `main` is not checked out, leaving untouched repos stale.
2. `git branch -D` refuses with `cannot delete branch 'X' used by worktree at '<path>'`. That error names a worktree, which reads as a second checkout holding live parallel work, but is almost always just that repo's ordinary checkout sitting on the branch.

Settle liveness from the branch's commits (`origin/main..<branch>` having zero commits plus absence from remote), switch that repo to `main`, and delete the dead branch.
