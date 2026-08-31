# Git branches

Branch and remote-branch lifecycle: pushing, renaming, deleting, retargeting,
recovering, and pruning.
Split out of [`git.md`](git.md) (ai-config#694 pattern) at the 1200-line
gate.

## Git --- `gh pr merge --delete-branch` can orphan a stacked PR instead of retargeting it
- GitHub's docs promise automatic retargeting: "If you delete a head branch
  after its pull request has been merged, GitHub checks for any open pull
  requests in the same repository that specify the deleted branch as their
  base branch.
  GitHub automatically updates any such pull requests, changing
  their base branch to the merged pull request's base branch."
- In practice (Lacaedemon/sparta, 2026-07-01), `gh pr merge <N> --squash
  --delete-branch` did NOT retarget a stacked PR onto the new base --- it
  auto-**closed** the stacked PR instead.
  Root cause unconfirmed (possibly a
  timing/API-path difference between `gh`'s post-merge branch deletion and the
  web UI's "Delete branch" button the docs describe) --- but the failure mode is
  reproducible enough to plan around regardless of cause.
- **Before running `gh pr merge <N> --delete-branch`**, check whether another
  open PR uses that branch as its base: `gh pr list --base <branch-name>`.
  If one does, omit `--delete-branch` (merge without it, or delete manually
  afterward once you've confirmed the stacked PR retargeted cleanly).
- **Both halves of that mitigation are narrower than they read: the trigger is
  wrong, and the remedy does not work in a repo that auto-deletes.**
  The check
  is gated on `--delete-branch`, so a plain squash merge fires none of it and
  orphans the dependent anyway --- the merge base stays put, and the dependent
  re-shows the merged content as a conflict.
  And omitting the flag buys nothing
  where the repo deletes merged head branches on its own, since the branch goes
  away whatever you passed (measured on `Morrison-Lab/ai-config`, 2026-08-16:
  five of five recently merged head branches were absent from `git ls-remote
  --heads origin`, the sixth surviving only because an open PR still used it).
  So run the base query before **any** merge.
  [`shared/workflow/batch-merge-and-resolve.md`](../shared/workflow/batch-merge-and-resolve.md)'s
  "A stacked PR is the one conflict that intersection cannot attribute" section
  carries the derivation and the attribution rule.
- **Recovery when it happens anyway:** the *head* branch of the closed PR
  usually still exists (only the deleted *base* branch is gone) ---
  `gh pr reopen` fails once the base is gone, so instead open a **new** PR
  from that same head branch targeting `main` (or whatever the new
  grandparent base is), note in the body that it supersedes the closed PR
  number with identical commits, and comment on the closed PR linking the
  replacement.
- **When run from a worktree/checkout that's currently on the branch being
  merged, `gh pr merge --delete-branch` also switches that checkout to the
  default branch and fast-forwards it, and deletes the now-merged local
  branch** --- a normal, convenient side effect, not a bug.
  Don't follow it
  with the usual post-merge `git checkout main && git pull && git branch -d
  <branch>` sequence on autopilot: the checkout is already on `main` and
  up to date, and `git branch -d <branch>` errors `branch '<branch>' not
  found` since `gh` already deleted it. Check `git branch --show-current`
  first before running any of those.

## Git --- renaming an open PR's *head* branch can close the PR (no reopen)

`gh api -X POST repos/{owner}/{repo}/branches/{branch}/rename` (or the web UI
"Rename branch") on a branch that is the **head** of an open PR **can close**
that PR.
GitHub's documented behavior is to auto-update a PR's head ref when its
branch is renamed and keep the PR open, but this has been observed to fail: the
PR closed and could not be reopened --- `gh pr reopen` returns `GraphQL: Could not
open the pull request. (reopenPullRequest)`.
Whether that's an edge case
(timing, an older API, an Enterprise instance) or the head ref not surviving the
rename, treat a head-branch rename as something that **may** close the PR.

Branch-rename **does** reliably retarget PRs whose **base** is the renamed
branch; the head-branch case is the risky one.

**How to apply:** don't rename a branch backing an open PR just to fix a
misleading name.
Live with the name (explain it in the PR body), or accept
you'll open a replacement PR --- rename, immediately open a new PR from the new
branch, say "Supersedes #N", and comment on the closed PR pointing forward.
(Hit on `ucdavis/bcs` 2026-07-09: renaming `fix/msm-competing-risks-324` to a
name that no longer asserted a refuted diagnosis closed PR #326, replaced
by #328.)

## Stacked PRs across a squash-merge: rebuild via cherry-pick, and verify force-pushes actually landed

Two git/GitHub behaviors that compose on stacked PRs (learned on
Lacaedemon/sparta #883→#884, 2026-07-15):

- When the base PR of a stack merges (with branch auto-delete), GitHub
  auto-retargets the stacked PR to the new base --- no manual retarget needed,
  and a manual `gh api ... -f base=main` after the fact 422s (something to
  the effect of "already exists") precisely because it already happened.
  But if the base was **squash-merged**, the stacked branch still carries
  the base's original commits, which are no longer ancestors of main ---
  `git merge origin/main` conflicts on the very content that already landed.
  Rebuild instead:
  `git checkout -B <branch> origin/main && git cherry-pick <own-commits...>
  && git push --force-with-lease`.
- **A rejected `git push --force-with-lease` is easy to miss in a compound
  command** --- after `checkout -B`, the remote-tracking ref can be stale, the
  push's rejection prints to stderr but scrolls past in long output, and the
  PR keeps serving the old head (showing merge conflicts that look
  unexplainable).
  Verify a force-push actually landed by re-reading the PR
  head (`gh pr view N --json headRefOid`) and comparing to the local SHA ---
  then `git fetch` + retry the push if it didn't.
  Don't diagnose PR state
  until the head matches.
- **`stale info` after `checkout -B` usually means the remote branch was
  DELETED, not moved -- and then a plain push is the correct fix, not a bigger
  hammer.**
  The bullet above says the remote-tracking ref can be stale; this is the
  specific cause that recurs on this repo's normal flow, since a squash-merge
  with auto-delete-on-merge removes the branch while your ref still names its
  old tip.
  `--force-with-lease` then fails for a reason that reads alarmingly like a
  race with another session:

  ```
  ! [rejected]  HEAD -> claude/... (stale info)
  ```

  The lease is unsatisfiable rather than violated, because the ref it names no
  longer exists.
  So the reflex it invites -- reach for `--force`, or assume someone else
  pushed -- is wrong in both directions: `--force` is unnecessary, and there is
  nothing to race.
  Settle which case it is before pushing anything:

  ```sh
  git ls-remote --heads origin <branch>   # empty output = deleted
  ```

  Empty means the next push *creates* the branch, so it can destroy nothing and
  needs no lease at all.
  `git fetch --prune` followed by a retry works for the same reason, and is
  worth preferring when you want the remote-tracking ref corrected too.
  Non-empty means a real concurrent session pushed to the remote branch; settle
  claims and inspect commits before forcing.

  - **Do:** run `git ls-remote --heads origin <branch>` when a lease push
    reports `stale info`, and plain-push (or `git fetch --prune` + push) when it comes back empty.
  - **Don't:** escalate to `--force`, or suspect a parallel session, before
    checking whether the branch still exists.

  (Morrison-Lab/ai-config#857 -> #872, 2026-07-30: #857 squash-merged and its
  head branch was auto-deleted.
  Restarting the same harness-assigned branch name from the new `main` and
  pushing the follow-up work produced `stale info`; `ls-remote` returned
  nothing, and the plain push reported `* [new branch]`.)

## `git push origin <name>` pushes the LOCAL BRANCH of that name, not HEAD

`git push origin <refspec>` takes a *ref*, not a label for "what I am working
on".
So in a checkout that has both the PR's branch checked out and a leftover
local branch named after something else --- the harness-assigned
`claude/...` name, say --- running `git push -u origin claude/...` pushes
**that other branch**, wherever it happens to point, and leaves the current
work unpushed.

The failure is quiet in the direction that matters.
The push succeeds, `git log` still shows the commits, and the only complaint
is from whatever check later notices the PR did not move.
The `-u` compounds it by repointing the *other* branch's upstream, so a
subsequent bare `git push` is now aimed somewhere new.

The tell is `* [new branch]` in the push output, and this is a **second
cause** for that line, distinct from the one in `CLAUDE.md`'s "Use the
existing PR branch" section.
There it means the remote branch was deleted underneath you, which on a PR
branch means the PR merged.
Here it means the ref you named had no remote counterpart because it was
never the branch you were working on.
Both warrant stopping, and they are told apart by which name is on the line:
if it is not the branch you have been pushing all along, you pushed the
wrong ref.

Recovery is cheap when caught immediately --- push the real branch, then
clean up the stray remote ref (`git merge-base --is-ancestor <stray-tip>
origin/main` first, to confirm it carries nothing unmerged; note that
deletion no-ops under the remote push proxy, per the section below).

- **Do:** push with no refspec (`git push`) once upstream is set, or name the
  branch you confirmed with `git branch --show-current`.
- **Do:** read the push output for `* [new branch]` versus a `SHA..SHA`
  range, and stop on the former.
- **Don't:** paste a branch name from the harness's instructions into
  `git push` without checking it is the branch you are on.
- **Don't:** read a zero exit status as evidence the right commits went out.

(Morrison-Lab/gha#357, 2026-07-29: `git push -u origin
claude/gha-pr-357-review-of6k4h` while on `add-gemini-and-ai-review-workflows`
created a stray remote branch at an already-merged commit and pushed none of
the round's four commits.
Caught by the `* [new branch]` line, since the PR branch had been pushed
several times already.)

## Remote-session push proxy: branch DELETION silently no-ops

The Claude Code web/remote push proxy accepts branch pushes but silently
refuses branch deletions: `git push origin --delete <branch>` (and the
`:refs/heads/<branch>` refspec form) reports `Everything up-to-date` (or
`fatal: the remote end hung up unexpectedly` followed by up-to-date) while
`git ls-remote` confirms the remote branch still exists.
There is no error
that says "deletion not allowed" --- the success-looking output is the trap.
Verify with `git ls-remote --heads origin <branch>` after any deletion
attempt, and when it survives, hand the deletion to the user (GitHub UI
Branches page) instead of retrying. (ucdavis/rampp, 2026-07-17: deleting the
orphaned `claude/split-survival` stack branch per its tracking issue no-op'd
twice; delegated to the repository owner in the issue-close comment.)

## Cleaning up a branch deleted on `origin` is two mechanisms, and only one is a config

"Prune branches once they are deleted on `origin`" sounds like one setting.
It is two, they live in different places, and only the first is a git config.

**Half 1 --- the remote-tracking ref.**
`fetch.prune=true` (or the per-remote `remote.origin.prune=true`) drops
`refs/remotes/origin/<name>` once that branch is gone upstream, on an
**unscoped** fetch.
A scoped one (`git fetch origin main --prune`) prunes nothing outside its own
refspec, config or no config, so it leaves the ref resolving --- see
[`keep-checkouts-fresh`](../shared/workflow/keep-checkouts-fresh.md).
It never touches a local branch.
Verified on git 2.34.1 (2026-07-29), deleting `feat` from a second clone:

```
=== after fetch.prune=true ===
remote-tracking refs:   origin/master       <- origin/feat pruned
LOCAL branches:         feat  * master      <- feat untouched
```

**Half 2 --- the local branch whose upstream is now `[gone]`.**
Git has no config for this at all, so no setting will ever do it.
It is a procedure, owned by
[`clean-branches`](../skills/clean-branches/SKILL.md) step 8b: find the
`[gone]` branches, confirm the PR actually merged, then delete.
Keep it confirmation-gated --- it is the half that can destroy work.

### Without half 1, half 2 reports a false clean rather than an error

The `[gone]` marker is produced **by pruning**, not by the branch being deleted
upstream.
Until a prune runs, `%(upstream:track)` is empty for exactly the branches the
sweep exists to find, so a `grep '\[gone\]'` matches nothing and the sweep
reports there is nothing to clean:

```
=== plain fetch, no prune ===
feat | origin/feat | track=
=== after fetch.prune=true ===
feat | origin/feat | track=[gone]
```

That is the shape [`fail-fast`](../shared/principles/fail-fast.md) warns about:
the "nothing found" path and the "never ran" path print the same thing.
So a sweep has to *establish* that a prune happened rather than assume it.
Running `git fetch --prune` inside the step is what keeps the config a
convenience rather than a silent prerequisite.

### In a squash-merge repo, local ancestry cannot be the safety signal

The safety rule is "never delete a branch carrying unique local commits", and
the obvious instruments for it all give the wrong answer where the repo
squash-merges.
Verified against a branch whose work had demonstrably landed on `main`:

```
ahead: 1   behind: 1
is feat an ancestor of master?      NO
git branch --merged origin/master   ->  * master        (feat absent)
git branch -d feat                  ->  error: The branch 'feat' is not fully merged.
```

Every one of those says "unmerged" about a branch that merged.
Once the upstream ref itself has been pruned there is no upstream left to
compare against, so `-d` falls back to `HEAD` and refuses.
Read that refusal as *unproven*, not as *unique local work* --- which is why
step 8b confirms the merge through the PR and only then reaches for `-D`.

So the authoritative landed-signal is the PR's own merge state, and the
content check that survives a squash (`git show origin/main:<path>`), not
local ancestry.
`ucdavis/bcs` and `Morrison-Lab/ai-config` both squash-merge.

- **Do:** set `fetch.prune` for the remote-tracking half, and treat the
  local-branch half as a reviewed sweep rather than something a config does.
- **Do:** decide "did this land?" from the PR, in any repo that squash-merges.
- **Don't:** read a `[gone]` sweep that found nothing as a clean result until
  you know a prune actually ran.
- **Don't:** treat `git branch -d` refusing, a non-zero ahead-count, or absence
  from `git branch --merged` as evidence a branch still holds unpushed work.

## GitHub keeps `refs/pull/N/head` forever, so deleting a closed PR's branch loses nothing

Deleting the head branch of a **closed, unmerged** PR feels lossy, since the
commits are on no branch afterwards and `main` never absorbed them.
It is not.
GitHub retains the PR's own head ref permanently, and it still resolves after
the branch is gone.

Check before deleting, and recover afterwards:

```bash
git ls-remote origin 'refs/pull/669/head'          # still resolves post-deletion
git fetch origin refs/pull/669/head
git checkout -b recover/669 FETCH_HEAD
```

Verify rather than assume, since it is one call: `git ls-remote`'s SHA should
equal the branch tip you are about to delete.
Measured across six closed PRs on `Morrison-Lab/ai-config`
(#305, #306, #430, #553, #610, #669):
every `refs/pull/N/head` resolved and matched its branch tip exactly.

Two consequences worth carrying:

- A closed PR's branch is safe to delete, so the real deliverable is a tracking
  issue recording *what* was unlanded and the recovery command -- not keeping
  the ref.
- These refs are **not** fetched by the default refspec
  (`+refs/heads/*:refs/remotes/origin/*`), so they cost nothing until asked for.

- **Do:** cite the `refs/pull/N/head` recovery command in the issue that
  records the unlanded work.
- **Don't:** hold a dead branch open as the backup copy -- GitHub already is
  one.

## An orphaned `refs/remotes/<ns>/*` namespace inflates every branch count

A one-off `git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'` writes refs
that **no configured refspec matches**.
Nothing updates them, `--prune` never touches them (it prunes only what a
refspec covers), and they persist indefinitely.

They are counted by `git branch -r`, so a repo can report hundreds of "remote
branches" that are neither remote nor branches.

```bash
git config --get-all remote.origin.fetch      # what is actually tracked
git for-each-ref --format='%(refname)' | grep -v '^refs/remotes/origin/'   # what is not
git for-each-ref --format='delete %(refname)' refs/remotes/pr/ | git update-ref --stdin
```

Before sweeping branches, separate the tracked namespace from stray ones ---
otherwise the sweep's scope is wrong from the first command.

(2026-08-02: `git branch -r` reported 741 on `Morrison-Lab/ai-config`, of which
709 were orphaned `refs/remotes/pr/*` from an earlier PR-head fetch and only 31
were real branches.
Deleting them took the repo from ~800 refs to 49.)

## Uncommitted leftovers on a merged branch can be a REJECTED direction, not unfinished work

Finding staged or unstaged edits on a branch whose PR already merged reads as
"work someone did not finish", and the reflex is to complete and land it.
Check the opposite hypothesis first, because the working tree records only that
an edit was *made*, never that it was *kept*.

Two shapes seen together on one branch:

- **A stale base.**
  The edits were written against an older `main`, so applying
  them now silently reverts whatever landed in between.
- **A rejected direction.**
  The edits contradict what the merged PR concluded,
  because they predate its final review round.

The second is the dangerous one: it looks like unfinished work and is actually
a bug someone already fixed correctly.

So before completing leftover work, check the branch's PR state, then verify
the edit's own claim independently rather than inferring intent from its
presence.

- **Do:** run the leftover edit's central claim as an experiment before landing
  it.
- **Do:** diff each leftover file against current `main`, not against the
  branch tip, to separate genuinely new content from stale-base reverts.
- **Don't:** treat an uncommitted edit as an unfinished intention -- it may be
  a draft the review already overruled.

(2026-08-02, after `Morrison-Lab/ai-config#900` merged: three staged files
proposed *unquoting* git's `branch -d` warning literal.
Reproducing the command showed git prints the quoted form with a trailing
period, which is what `main` already had -- so the leftovers would have
reintroduced the exact defect that PR's final round fixed.
A fourth, unstaged file held genuinely new content plus a stale-base reversion
of a taxonomy that had landed meanwhile; only the new half was carried forward,
as #1054.)

## Git --- deleting a remote branch returns HTTP 403 in a remote/web session

`git push origin --delete <branch>` (and its `:refs/heads/<branch>` spelling)
is refused by the agent proxy from a Claude Code remote/web session:
`error: RPC failed; HTTP 403`, then `fatal: the remote end hung up`.
It is a policy answer rather than a transient one, so the retry-with-backoff
path does not apply --- retrying reproduces the identical 403.

The failure also prints a trailing `Everything up-to-date`, which reads as
success once the error line scrolls away.

- **Do:** delete a remote branch through the forge API or UI here, and confirm
  with `git ls-remote origin refs/heads/<branch>`.
- **Do:** leave the branch and say so when neither is available; its closed PR
  is the record of why it exists.
- **Don't:** retry the delete with backoff.
- **Don't:** read `Everything up-to-date` as the delete having succeeded.

(Measured 2026-08-22;
[ai-config#1999](https://github.com/Morrison-Lab/ai-config/issues/1999).)

## A stale remote-tracking ref after a squash merge makes a re-cut branch look unpushed

Squash-merging a PR with auto-delete removes the remote branch, but your local `refs/remotes/origin/<branch>` survives, still pointing at the **pre-squash** head.
Re-cut the same branch name from the updated `main` and any check comparing it to that ref reports commits to push, because `main`'s squash commit is not an ancestor of the branch history the ref remembers.

Measured 2026-08-28 after [ai-config#2539](https://github.com/Morrison-Lab/ai-config/pull/2539) merged: a `Stop` hook reported *"2 unpushed commit(s) on branch claude/gii-x6fd58"* over a branch sitting exactly at `origin/main` with a clean tree.

```bash
git log --oneline origin/main..HEAD | wc -l   # 0 -- nothing to push
git ls-remote origin refs/heads/<branch>      # empty -- deleted on merge
git rev-parse --short origin/<branch>         # still resolves: the stale ref
git fetch origin --prune                      # the fix
```

Pushing is the wrong response and is the one the warning invites.
[`check-before-pushing`](../shared/workflow/check-before-pushing.md) already names the adjacent case --- MERGED means auto-delete, do not recreate --- and this is how you arrive at it without meaning to: the branch is a fresh cut for *new* work, so it does not feel like recreating anything.

Note which direction the instrument failed in.
Most of this corpus's cases are a check reporting clean when it could not fail;
this one reports a problem that does not exist, from the same cause --- a measurement taken against a snapshot that has expired.

- **Do:** run `git fetch --prune` after a merge that auto-deletes the branch, and before trusting anything that compares against a remote-tracking ref.
- **Do:** settle "is there anything to push" from `origin/main..HEAD` and `git ls-remote`, not from the tracking ref.
- **Don't:** push to clear the warning --- the remote branch is gone, and recreating it is what `check-before-pushing` forbids.
