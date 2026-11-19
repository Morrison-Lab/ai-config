# Leave git state other sessions share alone

Worktrees isolate a branch, its index and its working tree.
They do not isolate everything git keeps per repository, and parallel sessions in one repository share the rest ([ai-config#5315](https://github.com/Morrison-Lab/ai-config/issues/5315)).

## The stash stack

`refs/stash` is one stack for every worktree of a repository.
A bare `git stash pop` or `git stash apply` takes `stash@{0}`, which may be another session's work.
A clean pop applies it in your worktree and drops it, and the command exits 0 ([ai-config#1907](https://github.com/Morrison-Lab/ai-config/issues/1907), [#3584](https://github.com/Morrison-Lab/ai-config/issues/3584)).
`git stash` on a clean tree saves nothing and also exits 0, so a later pop in the same script restores someone else's entry ([`memories/git-stash.md`](../../memories/git-stash.md)).

- **Do:** answer a baseline question without the stack: `git worktree add --detach <dir> <ref>` or `git show <ref>:<path>`.
- **Do:** when you must stash, push with a unique message (`git stash push -u -m "<tag>"`), find your entry's SHA by that tag in `git stash list --format='%H %gs'` (no match means the push saved nothing), then `git stash apply <sha>`.
- **Do:** to drop it afterwards, find its current `stash@{N}` by its SHA in `git stash list --format='%H %gd'` just before `git stash drop`, since `N` shifts when another session pushes.
- **Don't:** run `git stash pop` or `git stash apply` without naming the entry, or name `stash@{0}` because you just pushed: another session may have pushed since.
