When orchestrating an **ultracode** (`Workflow`-tool, multi-agent) session that
touches git, check for merge conflicts **every time a merge actually
occurs** --- not just once at the end. This is broader than the single-branch
case [`sync-with-main`](sync-with-main.md) covers: an ultracode session can
merge git state at several points --- reconciling `isolation: 'worktree'`
agent branches back into the target branch, integrating results from
concurrent `parallel()`/`pipeline()` stages that each committed changes, or
syncing a PR branch mid-workflow --- and each of those merges needs its own
check.

Worktree isolation prevents two agents from clobbering each other's *working
tree* while they run, but it does not prevent a real conflict once their
branches are merged back together: two agents can still touch the same file
(or edit two files whose logic must stay in sync) and produce a genuine
conflict at merge time. Don't assume isolation implies conflict-free --- verify
each merge as it happens.

**GitHub's mergeable indicator does not evaluate custom `.gitattributes`
merge drivers.** The PR page's conflict banner and the `mergeable_state` API
field reflect GitHub's own merge check, which does not invoke
`merge=<driver>` declarations (e.g. `merge=union` on a changelog file --- see
[`configure-gitattributes`](../../skills/configure-gitattributes/SKILL.md)).
A real `git merge` run locally, with `.gitattributes` checked out, can behave
differently from what GitHub reports: a file GitHub flags as conflicting can
auto-resolve cleanly under a union merge driver, and the reverse mismatch is
possible too since GitHub's check simply doesn't run the same logic. Don't
treat GitHub's flag as the ground truth for whether a merge is clean when a
repo defines custom merge drivers.

When correctness matters (deciding whether a worktree branch's result really
conflicts, whether a PR branch can fast-forward, whether two parallel agents'
output can combine), do the merge for real rather than trusting the
platform's indicator alone. Prefer the non-destructive `git merge-tree` form
--- it doesn't touch the working tree or current branch, so there's no
checkout or abort to get wrong:

```bash
git fetch origin <branch-a> <branch-b>
git merge-tree "$(git merge-base origin/<branch-a> origin/<branch-b>)" \
  origin/<branch-a> origin/<branch-b>
```

If you need the merge actually materialized (to inspect merged file
contents, not just conflict/no-conflict), check out `branch-a` explicitly
first --- `git merge --no-commit` merges into whatever is currently checked
out, not into whichever branch you happened to fetch:

```bash
git fetch origin <branch-a> <branch-b>
git checkout -b _check-merge origin/<branch-a>
git merge --no-commit --no-ff origin/<branch-b>
# inspect, then: git merge --abort
```
