# Revert a merge and reopen its issue

When you run `git revert` on a merge commit
that was merged prematurely or incorrectly,
the issue it originally closed is NOT automatically reopened by GitHub.

**Rule:** When you revert a merge,
you must explicitly and immediately reopen the corresponding issue(s)
that were closed by that PR.

- E.g., `gh issue reopen <issue-number>`

Never leave a user's original feature/bug issue closed
if the code fixing it was just reverted from `main`.
