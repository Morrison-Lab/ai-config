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

`hooks/no-bare-stash-pop.py` denies a bare pop or apply in a repository with more than one worktree.
`ALLOW_BARE_STASH_POP=1` clears one command.

## Untracked scratch swept in by `git add -A`

An add-everything (`git add -A`, `git add --all`, `git add .`) stages whatever untracked files sit in the work tree, including ones another session or your own tooling left there.
A worktree-isolated agent's checkout under `.claude/worktrees/` holds its own `.git`, so it is staged as a gitlink that no clone can resolve ([ai-config#3884](https://github.com/Morrison-Lab/ai-config/issues/3884)).
The message file of `git add -A && git commit -F msg.txt` is staged before the commit reads it, so the commit ships its own message ([ai-config#3558](https://github.com/Morrison-Lab/ai-config/issues/3558)).

- **Do:** write a commit message file outside the work tree, in the session scratchpad or `/tmp`, and pass that path to `-F`.
- **Do:** ignore `.claude/worktrees/` in every repository where agents run with worktree isolation, and name the paths you mean to add.
- **Don't:** run `git add -A` in a tree you have not just read with `git status --short`.

`hooks/no-add-sweeping-scratch.py` refuses an add that would stage an embedded repository, and a commit whose `-F` file is staged or would be swept in by an earlier add-everything on the same line.
`ALLOW_SCRATCH_ADD=1` clears one command.

## The main checkout's branch

A repository's main worktree is the checkout other sessions, subagents and background jobs open by default, so its branch and index are shared even when everyone else works in a linked worktree.
A `git checkout -B <branch>` run from the wrong directory left the main checkout on a fixer's branch with a stale index ([ai-config#4233](https://github.com/Morrison-Lab/ai-config/issues/4233)), and a switch under a running subagent put a commit on the wrong branch ([ai-config#3204](https://github.com/Morrison-Lab/ai-config/issues/3204)).

- **Do:** give each branch its own worktree (`git worktree add <dir> <branch>`) and run its git commands there, with `git -C <dir>` or after `cd <dir>`.
- **Do:** leave a checkout on its branch while a background job or subagent you started is still reading it.
- **Don't:** run `git switch` or a branch-changing `git checkout` in the main worktree of a repository that has linked worktrees.

`hooks/no-switch-in-main-checkout.py` denies `git switch` and a branch-changing `git checkout` (a commit, `-`, `-b`, `-B`, `--orphan`, `--detach`) in the main worktree while more than one worktree exists.
Restoring paths (`--`, `-p`, a name that is not a commit) passes.
`ALLOW_MAIN_CHECKOUT_SWITCH=1` clears one command.
