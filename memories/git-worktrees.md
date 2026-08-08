# Git worktrees

Worktree-specific git behavior, split out of [`git.md`](git.md) under the
1200-line memory-file gate (the ai-config#694 pattern).
General git mechanics, remote/push behavior, and diff-range selection stay
there.

## Git --- `worktree add` does not cd into the new worktree
- `git worktree add <path> <ref>` creates the worktree at `<path>` but leaves the
  shell in the **original** checkout.
  Subsequent bare git commands (`git checkout`,
  `git merge`, etc.) run against the original checkout, not the new worktree.
- Always follow `git worktree add <path> …` with `cd <path>` before any further
  git work inside that worktree.
- When creating a worktree to fix a **conflict caused by a squash-merge on main**,
  `git fetch origin main <branch>` (both refs) **before** `git worktree add` so
  the squash commit is present when you merge.
  Fetching only the PR branch leaves
  origin/main stale and the merge won't pick up the commit that caused the conflict.

## Git --- removing a worktree that contains a submodule
- `git worktree remove <path>` **fails** on a worktree that has an initialized
  submodule: `fatal: working trees containing submodules cannot be moved or
  removed`.
  Many repos with a vendored `.ai-config` submodule hit this after a
  feature branch merges.
- Fix: `git worktree remove --force <path>` removes it cleanly.
  (Plain `--force`
  is enough; the submodule warning is the only blocker.)
  If the dir somehow lingers,
  `rm -rf <path> && git worktree prune` finishes the cleanup.
- The branch can't be deleted while the worktree still references it
  (`error: cannot delete branch '…' used by worktree at '…'`), so remove the
  worktree **first**, then `git branch -D <branch>`.

## Git (Windows) --- `worktree remove` on your own cwd partially fails, leaving an orphaned unregistered directory that silently falls through to the parent repo
- `git worktree remove <path>` on a `<path>` that is the **current process's cwd**
  fails on Windows with `error: failed to delete '<path>': Permission denied` --- Windows won't let you delete a directory a running process has open as its
  working directory.
  That failure is not clean/atomic: git had already
  unregistered the worktree (removed it from `git worktree list` and deleted
  the checked-out files) before the final `rmdir` step failed, so the
  directory is left **empty and unregistered** rather than restored to its
  prior working state.
- **The dangerous part:** an empty, unregistered directory nested under the
  main repo (e.g. `.claude/worktrees/<name>/`) is not an error state as far as
  git commands are concerned --- `git status`/`git log`/`git pull` etc. run from
  inside it just walk up to the parent directory, find `../../.git` there, and
  silently operate on the **main repo's checkout and branch** instead of
  erroring.
  Nothing points out that you're no longer in an isolated worktree;
  a `git pull --ff-only` there quietly fast-forwards the main checkout instead
  of failing.
- **Detect it** with `git rev-parse --show-toplevel` (or `--git-dir`) --- if the
  path it prints is the **parent** repo rather than the worktree path itself,
  you've hit this.
  `git worktree list` run from the parent repo also won't
  list the directory.
  (Same failure signature as a worktree that was simply
  never registered in the first place, e.g. because a harness only prepared
  the directory but never actually ran `git worktree add` --- check this first
  before assuming any work was corrupted.)
- **Fix** by re-registering in place: `git -C <parent-repo> worktree add
  <same-path> [-b <branch>] <base-ref>` --- safe to run even though the
  directory already exists, as long as it's empty (which it will be, since
  the failed removal already deleted its contents).
- Avoid triggering this at all: don't call `git worktree remove` on a path
  that's your own cwd.
  `cd` out to the parent repo (or a sibling worktree)
  first, *then* remove.

## Git --- `checkout -B` in a linked worktree silently bypasses the already-checked-out guard
- Plain `git checkout main` in a linked worktree correctly refuses when `main`
  is checked out in the primary (or any other) worktree: `fatal: 'main' is
  already used by worktree at …`.
  `git checkout -B main origin/main` does
  **not** refuse --- the reset-and-checkout form re-points the shared branch ref
  and checks it out in the current worktree anyway, leaving **two** worktrees
  both claiming `[main]` in `git worktree list`.
- The damage lands one command later: a `git pull` in the second worktree moves
  the shared ref out from under the first worktree's working tree --- HEAD
  advances while that worktree's index and files stay at the old commit, so
  `git status` there shows index-vs-HEAD as phantom **staged** diffs, with no
  error anywhere.
  In the primary worktree this reads as the just-merged PR's
  changes staged in reverse, as if about to commit a full revert of it.
- The scripted fallback is how it happens in practice:
  `git checkout -q main 2>/dev/null || git checkout -qB main origin/main` --- the plain form refuses (silenced by `-q`/`2>/dev/null`), the fallback
  "succeeds".
- **Recovery:** move the offending worktree onto a new branch
  (`git switch -c <next-branch>` --- frees the ref), then in the other worktree
  restore **only** the phantom-diff files
  (`git restore --staged --worktree <files>`) --- not a blanket `reset --hard`,
  which clobbers unrelated local state (e.g. a dirty submodule pointer).
- **The same suppression bites outside worktrees, on ref manipulation
  generally: never `2>/dev/null` a git command that moves a branch ref.**
  `git branch -f main origin/main` is the right way to realign `main` when
  it is *not* checked out (per `CLAUDE.md`'s "Keep ai-config and repo
  checkouts fresh"), but git refuses it outright when `main` **is** the
  current branch ("cannot force update the branch checked out at ...").
  That refusal is the signal; a `2>/dev/null` on it, or burying it mid-chain
  in a `;`-separated compound whose later commands still succeed, throws the
  signal away and leaves you on a stale base with everything reporting
  success.
  The staleness then surfaces somewhere unrelated and much later:
  a diff-scoped CI check reporting a phantom hit in a file you never
  touched, because the base ref, not the file, was wrong.
  Run ref-moving commands unsuppressed and read their output;
  when `main` is checked out,
  use `git pull --ff-only` (or `git checkout --detach` first) instead of
  `git branch -f`.
  (ai-config#691: `git branch -f main origin/main` was
  refused this way while `main` was checked out -- the error suppressed, the
  ref left untouched -- leaving the branch two commits
  behind; caught only when `scripts/check-new-line-breaks.py` flagged a line
  in `memories/tools.md` that the working tree did not contain.)
- **Prevention:** in a session/linked worktree, never "return to main" after a
  merge --- branch the next task directly off the remote
  (`git switch -c <branch> origin/main`) and leave `main` itself to the
  primary checkout.
  To advance the local `main` ref without checking it out
  (CLAUDE.md § "Keep ai-config and repo checkouts fresh" recommends this when
  a single checkout sits on a feature branch), `git branch -f main
  origin/main` is the safe form to *attempt* --- not because the guard never
  fires, but because it **fails closed**: when any worktree holds `main` it
  hard-refuses (`fatal: cannot force update the branch 'main' checked out
  at …`, verified empirically) instead of silently double-checking-out the
  way `checkout -B` does; in that multi-worktree case, leave updating `main`
  to the worktree that holds it.
  (Hit on `Lacaedemon/sparta`, 2026-07-16: a
  post-merge tidy ran the fallback form inside a session worktree; the
  primary showed nine phantom staged reversals of the just-merged PR until
  restored.)

## Git --- if a target branch is already checked out in another worktree, push by refspec instead of switching
- Attempting to `checkout` a branch already active elsewhere fails with
  `fatal: '<branch>' is already used by worktree at ...`.
- When you need to land your current commit on that branch (for example, to
  update an existing PR branch), avoid switching branches: push your current
  HEAD directly to the target remote branch with
  `git push "<remote>" HEAD:"<target-branch>"`.
  Note that this pushes **all commits
  reachable from HEAD**, not just your latest one; before pushing, verify the
  outgoing range is safe --- the target branch should be an ancestor of HEAD
  (`git merge-base --is-ancestor "<target-branch-tip>" HEAD`), and there should be
  no unrelated commits between them --- to avoid advancing the PR branch beyond
  what you intended.
  Don't hard-code `origin` without
  checking: in a fork/multi-remote setup, `origin` may be your own fork while
  the existing PR's head branch lives on a different remote (e.g.
  `upstream`), so pushing to `origin` silently creates/advances a same-named
  branch there instead of updating the intended PR.
  Confirm which remote
  actually owns the PR's head (`git remote -v`, or match the PR's
  `head.repo` from `gh pr view "<N>" --json headRepositoryOwner,headRepository`)
  before picking the refspec's remote.
- This avoids clobber-prone workarounds (`checkout -B`) and avoids opening a
  new sibling PR by mistake.

## Two worktrees on the same branch name silently move a shared ref, not a conflict error

Git *should* refuse `git checkout -B <branch>` (or checking that branch out)
when another worktree already has it checked out --- but in practice, creating
a second worktree for a branch name a leftover worktree from earlier in the
same session still holds (e.g. via `git worktree add <path> origin/<branch>`
then `git checkout -B <branch>` inside it) can succeed without error and
silently repoint the shared branch ref out from under the first worktree.
That worktree's `git status` then shows a wall of spurious modified/deleted
files --- not real data loss, just its checked-out files diffing against the
ref's new (moved) tip while its own index/working tree still reflect the old
one.
Confirm via that worktree's own reflog (`git -C <path> reflog show
HEAD`) that its real last commit is still there and reachable --- check with
`git merge-base --is-ancestor <that-commit> <new-ref-tip>` --- before concluding
anything, but treat any push made under this collision as suspect until
verified, since it may have been built from a different, wrong base than
intended.
**Prevention:** always `git worktree list | grep <branch>` before
creating a new worktree for a PR branch, especially one worked earlier in the
same session (a `wave-N-*`-style dispatch worktree is exactly the kind that
lingers).
If one already exists, reuse it (`git fetch` +
`git reset --hard origin/<branch>`) instead of adding a second one on the same
name --- or use a distinct local branch name if reuse isn't feasible.
(`Lacaedemon/sparta` PR #626, 2026-07-03 --- recovered with no data loss, but
required a `--force-with-lease` push to fix and explicit user sign-off given
the ref-mutation risk.)

**On Windows, `~/.claude`'s real-copy consumer directories can drift far more
than a quick glance suggests --- check the whole corpus, not just `CLAUDE.md`.**
CLAUDE.md's own "Keep ai-config and repo checkouts fresh" step 2 already says a
`git pull` on the ai-config checkout doesn't propagate to
`~/.claude/{skills,shared,commands,memories}` on Windows (real copies, not
symlinks).
In practice the drift found there can be large even in an actively-used setup: one check found `CLAUDE.md` itself missing ~10 sections, `skills/` with 56 of ~90 files differing (plus 6 new skills never copied over), `shared/` with 5 differing/missing fragments, and `memories/` with 3 of 4 files differing --- accumulated silently because the per-session refresh habit checks `CLAUDE.md` (loaded every turn, so staleness there is visible) but not the other three directories (loaded on-demand, so staleness there is invisible until a skill/memory is actually needed and reads wrong).
Before trusting a sync is complete, `diff -rq` (or `cp -r` unconditionally, after checking for genuine un-upstreamed local edits per the existing before-overwriting caution) all four directories, not just the one that happens to render in every prompt.
(`Lacaedemon/sparta`, 2026-07-04.)

## `isolation: "worktree"` gives a worktree of the SESSION's repo, not of the repo a brief names

Every section above concerns worktrees you create yourself.
This one concerns the worktree the Claude Code harness creates for a subagent,
which is a real `git worktree` at `<primary-repo>/.claude/worktrees/agent-<id>`
and lands somewhere the dispatching session does not choose.

The `Agent` tool's description of `isolation` says only that `"worktree"` gives
the agent its own git worktree, auto-cleaned if unchanged.
It does not say *which* repository, and the answer is the session's primary one
rather than anything the brief mentions.

So `isolation` does nothing for a **cross-repo** dispatch.
Sending an agent from a session rooted in repo A to do work in repo B, with
`isolation: "worktree"` set, hands it a worktree of **A** --- and a brief telling
it to "work in the worktree you were given" is then unfollowable as written.

Measured 2026-08-07 from a session whose primary working directory was
`/Users/ezramorrison/Documents/GitHub/psw`.
An `Agent` launched with `isolation: "worktree"`, whose brief named no repository
at all, reported:

```
pwd                       -> /Users/ezramorrison/Documents/GitHub/psw/.claude/worktrees/agent-a1beebe72c1787629
git remote get-url origin -> https://github.com/d-morrison/psw.git
```

**Checking afterwards proves nothing, which is why this stayed a hypothesis for
a while.**
Auto-clean is real and fast, so a `git worktree list` run once the agent has
finished shows only the main checkout whatever happened --- an unchanged worktree
and a worktree that never existed leave the identical trace.
That is the [`fail-fast`](../shared/principles/fail-fast.md) shape where a
check's failure path and its pass path print the same thing.

The surviving signal is the **mtime** of `<primary-repo>/.claude/worktrees`.
Across two probes it moved 14:38 -> 14:41:08 -> 14:41:47 in the psw checkout,
while the ai-config checkout's stayed at 11:39.
Reading the agent's own `pwd` is better still, and is what settled it here.

The remedy is to name the target clone in the brief and have the agent build its
own worktree there:

```bash
default=$(git -C /path/to/target-clone symbolic-ref --short refs/remotes/origin/HEAD)
git -C /path/to/target-clone worktree add -b <branch> /private/tmp/wt-<slug> "$default"
```

`refs/remotes/origin/HEAD` is unset in some clones, and
`git remote set-head origin -a` populates it (verified idempotent: it prints
`'origin/HEAD' is unchanged` when already correct).

Resolve the default branch rather than writing `origin/main`, per the
"Resolve `<default-branch>` from the repo rather than assuming `main`" rule in
[`preferences.md`](preferences.md), which measures the hard-coded form dying
with `fatal: invalid reference: origin/main` against a repo whose default is
`develop`.
That rule prefers `--detach` for a worktree the *dispatcher* creates and hands
over, to avoid a `.git/config` lock race under concurrent creation.
Here the agent creates its own and needs a branch to commit to, so `-b` is
right --- but use `--detach` if you ever fan several of these out at once.

- **Do:** name the target clone by path when dispatching an agent into a repo
  other than the session's own, and tell it to create its own worktree there off
  that repo's resolved `origin/<default-branch>`.
- **Do:** settle where an agent actually landed from the agent's own `pwd`, not
  from a `git worktree list` run after it exits.
- **Don't:** write "the worktree you were given" into a cross-repo brief ---
  `isolation` cannot have given it one of the target repo.
- **Don't:** read an empty `git worktree list` in the primary repo as evidence
  that no worktree was created there; auto-clean removes an unchanged one.

(Morrison-Lab/ai-config#1268, from the UMS pass on
[#1259](https://github.com/Morrison-Lab/ai-config/pull/1259).
The receiving agent caught the contradiction and recovered on its own, which is
the discretionary premise check
[`challenge-the-assignment`](../shared/workflow/challenge-the-assignment.md) says
not to leave as the only detector.)
