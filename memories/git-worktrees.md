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

## The same-branch collision can surface at TEARDOWN, and `git worktree list` cannot show it

Two sections above already own this phenomenon --- the `checkout -B` bypass and
the shared-ref move --- so read those for the mechanism and the recovery rather
than re-deriving either here.
Both place their prevention **before** the work: one says never to return to
`main` inside a linked worktree, the other says to run
`git worktree list | grep <branch>` before creating one.
This entry is the case where neither ran, the collision was already in place,
and the first thing to notice it was `git branch -d` during post-merge tidy-up.

**`git worktree list` reports each worktree's HEAD, so it cannot show a diverged
index.**
Two worktrees attached to one branch both resolve HEAD to that branch, so both
print the **same SHA** however far one worktree's index has moved from it.
`--porcelain` adds no index field either; it merely labels the same value
`HEAD`.
So the duplicated **branch name** is the only part of that output which reveals
the collision, and nothing in it reveals the staged divergence --- which is why
this can sit unnoticed until something tries to delete the branch.

**Read a `used by worktree` refusal twice when the branch is one you just
merged.**
`CLAUDE.md`'s wrap-up bullets say not to read `used by worktree` as evidence
that a separate live worktree exists, since "it is almost always just that
repo's ordinary checkout sitting on the branch".
That is right for the sweep it governs --- leftover harness branches in scoped
repos the session never opened --- and this is the other case.
A branch you drove to merge in **this** session, refusing deletion by naming a
path that is not your checkout, is the one place that "almost always" is worth
spending two commands on:

```bash
git worktree list                       # more than one row for this branch?
git -C <that-path> status --short       # does the other worktree hold an index?
```

**Git's own guard is the second of those, and `--force` is what skips it.**
`git worktree remove <path>` refuses on a dirty tree
(`fatal: '<path>' contains modified or untracked files, use --force to delete
it`), which is exactly the check that surfaces a staged divergence.
[`post-merge`](../skills/post-merge/SKILL.md) and
[`clean-worktrees`](../skills/clean-worktrees/SKILL.md) both already say not to
reach for `--force` blindly, so the procedural remedy exists; what this case
adds is that the refusal one step earlier, from `git branch -d`, is itself a
reason to look.

**When the staged diff reverses already-merged work, settle discarding by
content on `origin/main`.**
The recovery advice in the sections above preserves and restores selectively,
which is right when the worktree's own commits may be unique.
A staged reversal of a fix that has already merged is the case where discarding
is provably safe, and the deciding read is the content rather than any ancestry
or SHA comparison, per
[`fail-fast`](../shared/principles/fail-fast.md)'s "whether a change landed is
decided by looking for the change":

```bash
git show origin/main:<path> | grep -n "<a string only that change introduced>"
```

- **Do:** treat a `used by worktree` refusal on a just-merged branch as a
  prompt to count the rows in `git worktree list` and run `git status --short`
  in the other worktree.
- **Do:** confirm the fix is on `origin/main` by content before discarding a
  staged reversal of it.
- **Don't:** read matching SHAs in `git worktree list` as evidence the two
  worktrees agree --- that column is HEAD, and it says nothing about either
  index.
- **Don't:** reach for `git worktree remove --force` before reading the
  non-forced refusal, which is the only step that surfaces a staged divergence
  on its own --- `git status --short` reports it more precisely, and only if
  you think to run it.

(`Morrison-Lab/ai-config`, 2026-08-10, tidying after PR #1365 merged as squash
commit `491906bf`.
`git branch -d learn/dispatch-cancel-and-commit-identifiers` refused, naming
`/tmp/wt-ums-1363-1364`.
`git worktree list` showed that path and `/home/user/ai-config` both on that
branch and both at `2714db61`.
The primary's `git status --short` was empty; the linked worktree's was not,
reporting `M  shared/workflow/pr-on-claim.md` and `M  skills/ardi/SKILL.md`,
both staged, and `git diff --cached` there showed the **pre-`2714db61`**
content of both --- so committing it would have reverted the `--ref` fix that
had just merged.
Those two files are a subset of the four `491906bf` touched.
Discarding was confirmed safe by content, for **both** files rather than one
--- the section's own principle is that membership in a merged commit's file
list is not the deciding read:
`git show 2714db61:shared/workflow/pr-on-claim.md` (now in
`shared/workflow/pr-on-claim.rationale.md`) carries
`gh workflow run <review-workflow>.yml -R <owner>/<repo> --ref <PR-branch> -f
pr_number=<N>` in its review-dispatch section, and
`git show 2714db61:skills/ardi/SKILL.md` carries the same string in its
review-dispatch section.
Resolved with `git worktree remove --force` plus `git branch -D`.
How the two worktrees came to share the branch was **not** established, so
nothing here asserts a mechanism for it.
The output claims above were re-measured on git 2.43.0 against a synthetic
two-worktree repo: with one worktree holding a staged reversal, both rows of
`git worktree list` printed the same SHA, `--porcelain` printed that value as
`HEAD` for each with no index field, the non-forced `git worktree remove`
refused with the `contains modified or untracked files` message, and
`git branch -d` refused with
`error: cannot delete branch 'feat' used by worktree at '<path>'`.)

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

## In a session rooted in a worktree, `cd <repo-root>` lands in the MAIN checkout

The section at the top of this file covers `git worktree add` leaving the shell
in the original checkout.
This is the inverse, and it fires in a session that is *already* rooted in a
worktree --- the shape the Claude Code harness sets up when it opens one.

The worktree lives *under* the repo root (`<repo>/.claude/worktrees/<name>`),
so the repo root is a real, valid, plausible-looking path that is **not** the
worktree --- and it is the path every instinct reaches for when a command needs
to name the repo.

**The trap does not depend on how the shell's working directory behaves between
calls, and it fires either way.**
If the directory persists, one wrong `cd` sends every later command to the main
checkout.
If it resets, each command re-opens with a `cd` and each one is wrong
separately.
So read the reconciliation below as explaining how *often* the mistake recurs,
never as the mechanism that causes it.

Which behaviour you get is genuinely unsettled, and
[`claude-code.md`](claude-code.md)'s "Bash tool cwd persists across calls"
section disagrees with what this session measured.
That section says a **main** session's cwd persists, citing the Bash tool's own
description, and that only an Agent/subagent thread resets it.
This was a main session, and the harness reset the cwd to the worktree root
after every call, printing `Shell cwd was reset to <worktree>` each time ---
in the same session whose Bash tool description read "Working directory
persists between calls".
So the tool's own description and its behaviour disagreed, and the behaviour is
what governed.

That observation does not establish *why*, and one session cannot separate the
two candidates: a worktree-rooted session may reset where an ordinary one
persists, or the persists claim may simply be stale.
A third session, 2026-08-12, saw **both behaviours at once**, which rules out
the first candidate as stated.
It was an ordinary main session in a plain multi-repo checkout, no worktree
anywhere.
Several calls printed `Shell cwd was reset to /home/user`, and a
`cd /home/user/gha` in one call nonetheless carried into the next: a Python
edit script with no `cd` of its own, invoked immediately after, resolved a
relative path against `/home/user/gha` rather than the repo the session had
been editing.
So within one session the directory both reset and persisted, and neither
"worktree sessions reset" nor "the persists claim is stale" accounts for that
on its own.
Treat the behaviour as unpredictable per call rather than fixed per session,
which is the reading all three measurements support.

**The consequence in a multi-repo session is an edit landing in the wrong
repository, and it is silent.**
Both sibling checkouts held a file at the same relative path
(`.github/workflows/claude-code-review.yml`), so the script opened a real
file, of the right shape, in the wrong tree.
Nothing about the call announces it -- the working directory is not echoed,
and a repo-relative path is exactly what looks correct in a diff.

Two habits make it fail closed rather than silently, and the second is the one
that actually caught it:

- Address files by **absolute path** in any session holding more than one
  checkout, and prefer `git -C <path>` over `cd`, per
  [`preferences.md`](preferences.md).
- Make an edit script **assert its anchor before writing**.
  A replacement keyed on exact surrounding text cannot match a different
  repo's file, so the script aborts with no write rather than mangling
  something.
  Put every assert ahead of the single write at the end, so a failure leaves
  the tree untouched.

That is a specific case of [`fail-fast`](../shared/principles/fail-fast.md):
the anchor is the check, and the ordering is what keeps its failure path from
doing damage.

Don't settle the disagreement by picking one.
Read the `Shell cwd was reset` line, which costs nothing and answers the
question **for the call that printed it**.
Do not read it as settling the session: the 2026-08-12 measurement above saw
that line on several calls and still had a `cd` carry into a later one, so its
presence earlier in a session is not evidence about the call in front of you.

So `cd /path/to/repo` is the most natural thing to type and the wrong thing to
type: it silently selects the main checkout, which is on a different branch.
Nothing errors, and every command afterwards is individually correct.

**The two failure modes look nothing alike, which is why fixing one does not
inoculate you against the other.**

- **Writes land on the wrong branch.**
  Editing by absolute path writes into the main checkout, and a following
  `git add -A && git commit` commits them onto whatever branch that checkout has
  --- typically `main`.
  The feature branch in the worktree stays empty, so a later `git push` from the
  worktree answers `Everything up-to-date` while carrying none of the work.
  That answer is the tell: an up-to-date push on a branch you have been editing
  all session means the edits are somewhere else.
- **Reads answer about the wrong commit.**
  `HEAD=$(git rev-parse HEAD)` in the main checkout returns `main`'s tip, so a
  verification sweep keyed on `$HEAD` reports on `main` rather than on the PR.
  This is the dangerous one: `main` is green, so the sweep returns "all complete,
  none failing" --- a false all-clear, delivered by a command that did exactly
  what it was told.
  The count is the tell, if you read it: 51 check runs at `main`'s tip against 32
  at the PR head, for a PR whose own checks were the subject.

Recovery from the write case is cheap, and no work is lost: the commit is a real
commit, so cherry-pick it onto the feature branch from the worktree, then
`git reset --hard origin/main` in the main checkout.
Do it before pushing, and nothing ever leaves the machine.

The remedy is to stop passing the repo root at all.
Use `git -C <explicit-path>` when a command must target a specific checkout, and
otherwise let the harness's own cwd stand rather than re-establishing it.
Where a `cd` is genuinely wanted, print `git branch --show-current` in the same
call and read it.

- **Do:** run `git -C <path>` against a named checkout instead of `cd`-ing to it.
- **Do:** treat `Everything up-to-date` on a branch you have been editing as
  evidence the edits went elsewhere, not as evidence they were already pushed.
- **Do:** compare a derived `$HEAD` against the PR's own `headRefOid` before
  keying any verification sweep on it.
- **Don't:** read the repo root as "the repo" in a worktree session --- it is one
  specific checkout, on one specific branch, and not the one you are working.
- **Don't:** trust a sweep that returned a clean answer without checking which
  commit it examined; querying the wrong SHA fails green.

(`Morrison-Lab/gha#440`, 2026-08-09: both modes in one session.
The implementation was written and committed onto `main` in the main checkout
while the branch sat at its empty claim commit, caught only when `git push`
answered `Everything up-to-date`.
Later, the fully-clean sweep ran against `5220802` --- `main`'s tip --- and
reported 51 check runs complete and none failing, for a PR whose head was
`d877f6d`.
Re-running it against the real head returned 32.)

## A repo script run from a worktree can measure the MAIN checkout, because it resolves paths relative to itself

The section above is about a `cd` that sends *you* to the wrong checkout.
This is the case where your working directory is right and the **script** goes
somewhere else, so every instinct that rule trains does not fire.

A repo script that locates the repository from its own location --- `__file__`,
`$(dirname "$0")`, or a walk upward from there --- reads the tree containing the
script, not the tree you are standing in.
So invoking the main checkout's copy from a worktree measures the main
checkout:

```bash
cd /path/to/worktree
python3 /path/to/main-checkout/scripts/check-context-closure.py   # measures the MAIN checkout
python3 ./scripts/check-context-closure.py                        # measures the worktree
```

Both commands succeed and both print a plausible figure.

**The output usually does say which tree it read, and discarding that line is
how the mistake actually happens.**
A well-behaved instrument prints its scope, and it prints it on a *different
line* from the figure you came for --- which is
[`fail-fast`](../shared/principles/fail-fast.md)'s "A zero-shaped summary can be
sound, and the scope line is what decides it", met one artifact over.
`check-context-closure.py` opens every run with its resolved base:

```
/home/user/ai-config: 74 file(s), 1,151,207 bytes (~287,801 tokens at 4 B/token)
```

So the cheapest discriminator is not a heuristic at all.
It is reading the first line.

The habit that defeats it is piping a check through `tail` to keep the output
short.
The figure you want is usually near the end, the provenance is at the start, and
`| tail -2` keeps the first and drops the second --- so the truncation is
invisible, deliberate, and self-inflicted.
Read the whole output at least once per script, and reach for `tail` only after
you know what the header says.

**Where a script genuinely prints no root, fall back to comparing the figure
against `main`.**
A worktree carrying uncommitted or unpushed work should differ from `main` in
whatever is being measured, so an identical figure is the signal to re-run the
local copy rather than a reassuring coincidence.
Treat that as the fallback it is, not as the primary check.

Two consequences beyond getting one number wrong.
A guard consulted this way reports on the wrong tree, so it can pass a worktree
whose content would fail --- the fail-green direction, per
[`fail-fast`](../shared/principles/fail-fast.md)'s "A proxy that answers a
narrower question passes the same way".
And a brief that tells a subagent to run a check without saying *which copy*
hands it the same ambiguity, which is
[`challenge-the-assignment`](../shared/workflow/challenge-the-assignment.md)'s
authoring-side rule: do not assert anything about the recipient's environment
you cannot query.

- **Do:** run a repo script from the worktree's **own** copy, by a path inside
  that worktree.
- **Do:** read a check's first line before piping it through `tail`, since
  scope and provenance live in the header and the figure lives at the end.
- **Do:** name the copy to run when briefing an agent working in a worktree.
- **Don't:** assume `cd` into the worktree redirects a script invoked by an
  absolute path elsewhere --- the script never reads your cwd.
- **Don't:** invent a heuristic to recover information you truncated away; check
  whether the tool already reports it.

(`Morrison-Lab/ai-config#1347`, 2026-08-09: `check-context-closure.py` was run
from the PR's worktree by the main checkout's path and reported `CLAUDE.md` at
133,901 characters --- exactly the main checkout's figure.
The worktree's own copy reported 134,415.
The wrong number was caught only because it matched a figure measured earlier in
the same session.
By then it had already been written into a PR comment as verification.
The same trap was then hand-carried into a subagent brief to prevent a repeat,
which is what showed it belonged here rather than in one session's head.

Review round 1 on `#1358` then found the first draft of this entry overclaiming:
it asserted that nothing names the tree, and that the matching-number comparison
was therefore the only cheap discriminator.
Both are false for the very script cited here.
Every invocation in that session had been piped through `| tail -2` or
`| tail -1`, which keeps the closing `CLAUDE.md: N characters` line and drops the
opening `/home/user/ai-config: 74 file(s), ...` line that names the resolved
base.
So the blind spot was self-inflicted, and the heuristic was invented to recover
information that was being discarded on purpose --- which is a better lesson
than the one first written down, and is why the entry now leads with reading the
header rather than with comparing figures.)

## A nested worktree inflates a whole-tree instrument, because the worktree lives INSIDE the repo

"A repo script run from a worktree can measure the MAIN checkout" above is the
case where an instrument reads a **different** tree than the one you stand in.
This is the mirror: the instrument reads **your** tree, correctly, plus a second
copy of the corpus nested inside it.
`isolation: "worktree"` on an `Agent` call places that worktree at
`<repo>/.claude/worktrees/agent-<id>`, so while the agent is live the repository
physically contains another branch's checkout of every file.

Whether an instrument notices depends on how it enumerates files.
Measured on `main` at `41d82611`, with and without one worktree present:

| instrument | no worktree | one worktree present |
| --- | --- | --- |
| `npx markdownlint-cli2` | `Linting: 512 files` | `Linting: 1207 files` |
| `scripts/check-links.py` | 503 files | 503 files |
| `scripts/check-context-closure.py` | 80 fragments | 80 fragments |
| `scripts/check-hook-catalog.py` | 18 / 20 | 18 / 20 |

Removing the worktree returned markdownlint to 512.

What decides exposure is **how an instrument enumerates**, and the shapes are
worth knowing because they predict which of your own tools is affected without
re-measuring each one.

Exactly one shape is exposed, which is why only one row moved:

- **An unrestricted recursive glob from the repo root.**
  `.markdownlint-cli2.jsonc` globs `**/*.md`, and its `ignores` list named
  generated output and dependencies rather than a nested checkout.

The other three rows are immune, and each for a different reason:

- **A named-directory glob** never reaches it.
  `check-links.py`'s `SCAN_GLOBS` lists `skills/**/*.md`, `memories/**/*.md`,
  and their siblings, so `.claude/` sits outside its search space.
- **A closure walk from named entry points** never reaches it either.
  `check-context-closure.py`'s `walk_closure` follows references outward from
  its roots, so a nested checkout is reachable only if something in the closure
  cites it, and nothing does.
- **A fixed-file read** has nothing to enumerate at all.
  `check-hook-catalog.py` opens `hooks/hooks.json` and `README.md` by path;
  it globs nothing.

One further immune shape is worth naming even though no row above uses it,
since much of `scripts/` is built on it: **a `git ls-files` enumeration**
cannot see a nested worktree, because its files are untracked in the parent
index.
`scripts/check-memory-file-size.py` is the example.

The config fix is tracked as
[#1511](https://github.com/Morrison-Lab/ai-config/issues/1511) and proposed in
[#1513](https://github.com/Morrison-Lab/ai-config/pull/1513), and is not what
this entry is about.
That PR's own `ignores` comment carries the breakdown of the 1207 --- the
worktree's markdown, the files its `.claude/skills` symlink pulls in, and its
`codex-skills/` escaping the root-anchored ignore --- so read the count's
composition there rather than here.
The enumeration question outlives that fix, since any tool added later that
globs the repo root inherits the same exposure.

**Nothing in the output flags the change.**
`Summary: 0 issues in 0 files` is identical either way, so the inflation lives
entirely in the `Linting:` line --- and a reader who pipes to `tail` to shorten
the output keeps the summary and drops exactly that line.
That is the same self-inflicted blind spot recorded in "A repo script run from a
worktree can measure the MAIN checkout", arriving through a different fault.

Note the failure direction is the opposite of
[`fail-fast`](../shared/principles/fail-fast.md)'s "A zero-shaped
summary can be sound, and the scope line is what decides it".
There a sound figure is wrongly retracted; here an inflated one is published
unremarked, and the same line separates the two cases.

So **run `git worktree list` before publishing a whole-tree figure**.
More than one row means the scan may have covered another branch's copy of the
corpus, so the figure describes a tree nobody asked about.
`git archive HEAD | tar -x` into a scratch directory settles it outright ---
[`fail-fast`](../shared/principles/fail-fast.md) already prescribes that for a
drifted working tree, and an archive of `HEAD` carries no untracked nested
checkout either.

A second consequence is a hook rather than a figure.
A pre-commit hook running such a tool with `always_run: true` scans the nested
checkout too, so it can fail on a file from a branch you are not on, in a commit
that does not touch it.

- **Do:** run `git worktree list` before quoting a whole-tree count.
- **Do:** ask how an instrument enumerates --- `git ls-files`, named
  directories, or a root glob --- before assuming it is immune.
- **Don't:** read a stable `Summary:` line as evidence the scope was stable;
  the scope sits on the line above it.
- **Don't:** trust a whole-tree figure measured while a subagent was live,
  including one you published earlier in the same session.

## A quiet worktree is not evidence the session working it has stopped

Every earlier section in this file assumes the peer worktree is dead.
This one is about telling that apart from a peer worktree that only *looks*
dead, before you edit it, delete it, or reassign its branch.
The operative rule --- ask the agent, never infer --- is restated in
`CLAUDE.md`'s "Subagent worktrees are assigned" section; this section carries
the evidence and the case record behind it.

`git status --short` reporting nothing uncommitted, and `git log
origin/<branch>..HEAD` reporting nothing unpushed, both answer a question
about a **moment**: is anything sitting here right now that a snapshot would
show.
Neither answers "is anyone working here".
A session between edits, or paused mid-thought, produces the identical
snapshot to a session that finished and walked away, and nothing in either
command distinguishes the two.

`ListAgents` not naming a session is the same shape of gap, not a stronger
signal.
It reports what the harness currently tracks, and a session can be alive and
simply not be one the listing surfaces --- so absence there is not proof of
absence in fact, any more than a clean `git status` is.

**The `idle_notification` timestamp check is sound in form and only as good as
the timestamp you compare it against.**
Comparing a teammate's last `idle_notification` against your own most recent
message to it is the right check --- a notification timestamped before your
last message is stale, not evidence the teammate has gone quiet since.
But that check has an input you supply, and if the timestamp you are comparing
against is itself invented rather than read, the comparison inherits the
error: a fabricated "now" can make a live, recent notification look stale, and
the conclusion --- "this session has gone quiet" --- is then built on a number
nobody measured.
`Morrison-Lab/ai-config#1453` owns that defect and its fix (derive every
timestamp you reason about, don't extrapolate from one you derived earlier);
what matters here is the interaction, not the fix: a fabricated figure feeding
straight into a **liveness** decision is a sharper failure than feeding into
an ordinary status recap, because the decision it distorts is exactly the one
this section is about.

**One step earlier than the timestamp: the field's own semantics are not
established anywhere in this corpus, so a correct timestamp comparison still
does not settle liveness on its own.**
An `idle_notification` carries an `idleReason` such as `"available"`, and
reading that as "this session has stopped working" is an inference this
corpus has never verified.
`"available"` describes a session that is not currently blocked on a tool
call --- which is exactly what a session sitting on a backgrounded `gh run
watch` looks like from the outside, since the watch runs and reports without
occupying the foreground.
So the timestamp check above can be run correctly, against a real,
non-fabricated timestamp, and the result still says only when the notification
was sent --- never what sending it actually meant.
Read `idleReason` as an unglossed field rather than as a verdict, and treat a
liveness question it seems to answer as still open.

**Two more direct ways the same misreading arrives, both concluding "dead" on
evidence that only shows "quiet right now".**

- A worktree read clean via `git status --short`, with no unpushed commits and
  no `ListAgents` entry, was judged finished, and a second session began
  editing a file inside it.
  The Edit tool's own read-staleness guard refused: `File has been modified
  since read`.
  The worktree's owner had started editing between the read and the write.
  What actually prevented the clobber was that guard, not the judgment that
  produced the edit attempt --- worth naming plainly, since crediting your own
  care for a tool's backstop is how the next read of a clean worktree gets
  trusted a little more than it should.
- A worktree instead sat with real uncommitted work (38 insertions) for over
  nine hours, with no `ListAgents` entry for it, and was judged dead on that
  basis.
  It was alive, and replied within a minute once asked directly.

Both readings used the same evidence --- a snapshot plus an absent listing ---
and reached opposite, both wrong, conclusions.
That is the tell that the evidence does not discriminate: it produced "quiet
but alive" and "quiet and abandoned" from the identical two facts.

**A harness-reported failure is not a snapshot, and there the question is what
to salvage rather than whether the agent is alive.**
Everything above concerns evidence that cannot discriminate --- a quiet
worktree, an absent listing --- where the remedy is to ask.
A `task-notification` carrying `status: failed` is a different kind of signal.
It comes from the harness rather than from an inference of yours, so asking
buys nothing and costs an agent spin-up aimed at a process already gone.

The useful discovery is that a failed agent has often already pushed.
An agent that stalls during its verification or reporting phase can have
committed and pushed everything first, so the work sits safe on the remote
while the *report* about it is what was lost.
The report is also the only part that felt like the deliverable, which is why
the failure reads as total.
Reading it that way leads to redoing work that already landed, and a redo can
diverge from what was actually pushed.

Four reads settle what survived, before touching anything:

```bash
gh pr view <N> --json headRefOid --jq .headRefOid   # what the remote has
git -C <worktree> rev-parse HEAD                    # what the worktree has
git -C <worktree> status --short                    # uncommitted
git -C <worktree> log --oneline @{u}..HEAD          # committed, unpushed
```

A matching remote and local head, an empty status, and an empty unpushed range
together mean the work landed in full and only the reporting was lost.
Then finish the remainder yourself rather than resuming the agent, and verify
its changes against the tree rather than against its commit message --- the
verification step is precisely the one that did not run.

- **Do:** treat a harness `status: failed` as authoritative about the process,
  and check what was pushed rather than asking a dead agent.
- **Do:** re-verify a failed agent's work against the tree, since the checks it
  was about to run are the missing ones.
- **Don't:** redo work on the assumption a stalled agent lost it --- pushing
  early is the whole point, and it usually worked.
- **Don't:** apply the ask-don't-infer rule here.
  That rule governs evidence which cannot discriminate, and a harness failure
  signal discriminates.

(Morrison-Lab/ai-config#1696, 2026-08-19: an agent addressing six review
findings stalled on a 600s watchdog, its last line reading "Now the full check
suite before a single push".
It had already pushed --- remote head, worktree HEAD, and an empty unpushed
range all agreed --- so the six fixes were intact and only the check suite, the
disposition comment, and the re-review dispatch remained.
Those were finished directly, and the PR merged as `f5059a84` after a clean
second round.)

**Long-stalled uncommitted work in a container-local worktree is still a real
problem, and the fix is to ask, not to infer.**
Uncommitted state in a worktree survives nothing --- not a container
restart, not a reclaim, not the session that made it forgetting to push.
So a worktree sitting on real, unpushed edits for hours is genuinely worth
resolving rather than leaving alone indefinitely.
The tension is real: leaving it risks losing work if the container churns,
and touching it risks clobbering work in progress.
The resolution is not to infer an answer from indirect signals that cannot
support one --- it is to ask the session directly (`SendMessage` to its id, or
the equivalent for a peer Claude Code session) and act on the reply.
One message costs a round trip.
A clobbered edit costs another session's unpushed work outright, with no
recovery path once it is gone.

- **Do:** treat a clean, in-sync `git status` in another session's worktree as
  a statement about that instant, never as a statement about whether anyone is
  still working there.
- **Do:** treat `ListAgents` not naming a session as "not tracked here", not as
  "does not exist".
- **Do:** ask the session directly before editing or reclaiming a worktree
  that has sat with real uncommitted work for an extended stretch --- and
  before concluding it is dead just because it has sat quietly.
- **Don't:** derive an `idle_notification` staleness comparison from a
  timestamp you extrapolated rather than measured; see `#1453` for that half.
- **Don't:** read `idleReason` as a liveness verdict; a correct timestamp
  comparison still leaves the field's own meaning unestablished.
- **Don't:** credit your own judgment when a tool's built-in guard is what
  actually stopped a clobber --- name the guard, so the next read of a clean
  worktree gets checked rather than trusted.

(`Morrison-Lab/ai-config`, 2026-08-13, in the multi-teammate session that went
on to merge #1452 as `fcc09f00`: a dispatched teammate's `idle_notification`s
at `16:08:59Z` and `16:10:24Z` were judged stale against status recaps timestamped
roughly `16:13Z` and `16:20Z` --- timestamps that had themselves been
extrapolated rather than re-derived, per `#1453`.
Separately, that teammate's worktree read `git status --short` clean and
in-sync, with no `ListAgents` entry, and was judged finished; editing
`shared/workflow/fully-clean.md` inside it was refused by the Edit tool's
staleness guard mid-edit, because the teammate had started editing the same
file between the read and the write.
Later the same worktree sat with 38 uncommitted insertions for over nine
hours with no `ListAgents` entry, was judged dead, and replied within a
minute once asked --- it then reclaimed the PR itself.
A fourth instance came from a different source: the team-lead session's own
review message on the PR recording all this, which read the agent writing
this entry as idle roughly three minutes after it dispatched the review run
that produced round 1, on the strength of an `idleReason: "available"`
notification --- and named the notification's own semantics as unverified
only once the writer pointed out the watch had, in fact, been running the
whole time.
Recorded here as evidence about the field rather than about a worktree,
since nothing about it involved git state --- the mechanism is identical to
the first two instances, and the correction came from a message rather than
from a diff.)

## A subagent that has REPORTED COMPLETION can still be resumed, so its worktree is not yours to work in

The section above is entirely about concluding "dead" on evidence that shows
only "quiet" --- a clean `git status`, an absent `ListAgents` entry, an
`idleReason` nobody has glossed.
Its remedy is to ask the agent before touching its worktree.

This is the case where the agent has answered without being asked.
A dispatched subagent emits a completion notification, the orchestrator reads
it, and that is a far stronger signal than any of the above: it is the agent's
own report that it has stopped.
It is still not terminal.
The harness's own notification says so in as many words --- "the same task-id
may notify more than once", because the agent can be resumed and will then
notify again --- so a completion report bounds the past and promises nothing
about the future.

**The second-order effect is the expensive half, and it lands on the agent
rather than on you.**
Working in a completed agent's worktree puts your commits on its branch and in
its reflog.
When it resumes, it finds a commit it did not make, freshly pushed, on the PR
it claimed --- which is exactly the signature
[`claim-pr`](../shared/workflow/claim-pr.md)'s parallel-session check names,
and that check is sound.
So the agent applies a correct rule to a manufactured signal, concludes a live
session is racing it, stops pushing, and escalates a question to a user who is
not there.

Note which way this fails.
Nothing is corrupted and no work is lost, so there is no artifact to inspect
afterwards --- the cost is a stalled agent and a question nobody asked for,
which reads as the agent being cautious rather than as the orchestrator having
manufactured its evidence.

The fix is to keep the two working directories separate rather than to reason
harder about liveness.
Cut your own worktree off the branch and work there, and reclaim the agent's
only after deciding it will not be resumed.
Where you must work in its tree, say so **to the agent** before it resumes,
since a message is the one thing that can distinguish your commit from a
stranger's.

- **Do:** cut a separate worktree for your own commits on a dispatched agent's
  branch, rather than reusing the worktree it was given.
- **Do:** read a completion notification as "stopped for now", the same way
  the section above reads a quiet worktree.
- **Do:** tell the agent when one of its branch's commits is yours, so its
  parallel-session check has something to weigh.
- **Don't:** treat a completion report as licence to reclaim a worktree --- it
  is stronger evidence than silence and still not terminal.
- **Don't:** read the resulting "a parallel session is racing me" escalation
  as the agent malfunctioning; it is applying a correct rule to evidence you
  created.

(`Morrison-Lab/ai-config#1481`, 2026-08-15.
A sidecar UMS agent opened the PR and reported completion.
The orchestrator then addressed the review's one blocking finding from inside
that agent's own worktree, committing `4d8c6c7a` and pushing it.
The agent was resumed, found a commit it had not made --- correctly authored
`Claude <noreply@anthropic.com>`, already pushed, present in its own reflog ---
applied `claim-pr`'s parallel-session rule, declined to push, and asked which
of the two sessions should keep driving.
Its analysis was right at every step, including its verification that the
commit it had not made was the better fix; only its premise was false, and the
orchestrator had supplied it.)

## `git push -u origin HEAD` from a worktree publishes the worktree's own branch name

`pr-on-claim`'s mechanics block ends with `git push -u origin HEAD`, which is
correct where you are on the PR's branch and wrong from a scratch worktree.
`HEAD` resolves to the **local** branch name, and a worktree cut for a PR is
routinely named after the PR number (`wt-1787`) rather than after the PR's
branch --- so the push creates a new remote ref that looks like a real branch,
succeeds, and prints a `* [new branch]` line that reads as success.

The commit still has to be pushed again to the right ref afterwards, so the PR
is fine; what is left behind is a stray ref nobody will recognize.

**Deleting it may not be available to you**, which is what turns a slip into a
tracked issue.
From a remote session the delete push failed
(`send-pack: unexpected disconnect`) and the REST delete returned **403**, so
the ref stayed.

- **Do:** push an explicit refspec from a worktree ---
  `git push origin HEAD:<pr-branch>` --- rather than relying on `HEAD`'s local
  name.
- **Do:** file the cleanup when you cannot delete the stray ref yourself,
  rather than leaving it for whoever next lists branches.
- **Don't:** read `* [new branch]` as confirmation you pushed where you meant
  to; it is confirmation you pushed somewhere new.
- **Don't:** assume `-u` is harmless because the commit is correct --- the
  commit is not what goes astray.

(Morrison-Lab/ai-config#1826, 2026-08-21: a review fix for #1787 was pushed
from a worktree whose local branch was `wt-1787`, creating
`refs/heads/wt-1787` at `74995e3c`.
The same commit reached `feat/register-hooks-after-merge` seconds later via an
explicit refspec, so the PR was unaffected;
the stray ref could not be deleted from that session and was filed instead.)
