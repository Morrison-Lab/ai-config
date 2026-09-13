# stack-prs

Create (or maintain) a PR that is **stacked** on another open, unmerged PR: its branch starts from the base PR’s tip instead of `main`, and its own PR’s `base` points at the base PR’s branch instead of `main`. This is the general-purpose entry point for stacking — other skills (`ardia`, `gii`/`gia`, `stack-dont-pause`) each stack as a side effect of their own loop; this one does it directly when you already know you want to branch off another PR.

## When this fires

- “stack this on \#N”, “stack-prs”, “branch off that PR”, “make this depend on PR \#N”.
- The decision question itself — “should I stack this?”, “does this need to stack on \#N?” — routes here too: the gate below is the answer.
- New work may need another open PR’s code, or might conflict with it if branched from `main` in parallel — the gate below determines which.

It does **not** fire when the work is independent of every open PR — branch from `main` as usual. Don’t stack just because two PRs happen to be open at the same time.

## When to stack vs. branch from `main` — the decision gate

Branching from `main` is the default; stacking needs **positive, verified evidence**. A stack adds a real ordering constraint (the base PR must merge first, or the stack must be re-pointed around it) and a per-push sync burden (step 3 below), so run this gate before step 1, every time — including when the instruction was “stack this on \#N”: confirm the dependency is real rather than assumed. Stack only when at least one of the two tests passes.

### Test A — dependency: solving this issue depends on solving the other

Either kind of evidence counts, but check it — don’t infer it from titles:

- **The issues declare it.** The new work’s issue is marked blocked-by / “depends on” the base PR’s issue, or the two are ordered sub-issues of one parent. Read the issue and its linked PRs (`gh issue view <N>` — VIEW_ISSUE; `ISSUE_LINKED_PRS` for the timeline).

- **The code requires it.** A function, file, or config key the new work must call or edit is added by the base PR and absent from `main`. Confirm both halves:

  ``` bash
  gh pr diff <base-N> | grep -n "^+.*<needed-symbol-or-path>"   # DIFF_PR — the base PR adds it...
  git fetch origin main -q                                  # FETCH
  git grep -n "<needed-symbol-or-path>" origin/main         # ...and main does NOT already have it
  ```

  If the second grep finds it on `origin/main`, the dependency is on already-merged code — branch from `main`.

### Test B — overlap: both PRs will heavily modify the same passages

File-list overlap alone is **not** enough — two PRs editing disjoint regions of the same file usually merge cleanly, and [`sync-with-main`](../../shared/workflow/sync-with-main.md) absorbs that drift. Check overlap at the passage level:

``` bash
gh pr diff <base-N> --name-only        # DIFF_PR — the base PR's changed files
gh pr diff <base-N>                    # then read its hunks in any file you'll also touch
```

Stack when the planned work would rewrite the same function, block, or section the base PR’s hunks change — or append at the same insertion point (e.g. the end of a growing numbered list, the append-collision case `sync-with-main` documents). Branch from `main` when the shared file’s edits land in different regions.

### Neither test passes → branch from `main`

Merely concurrent PRs stay independent; stacking should not be reached for out of caution. See [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md) for the same decision made inline inside a sweep loop.

## Procedure

### 1. Create the dependent branch off the base PR’s tip

``` bash
git fetch origin <base-branch>                              # FETCH
git checkout -b <dependent-branch> "origin/<base-branch>"    # CREATE_BRANCH
```

Use the base PR’s `headRefName` (`gh pr view <base-N> --json headRefName -q .headRefName`, or `mcp__github__pull_request_read` method `get` in a remote session) as `<base-branch>` — never guess the branch name from the PR title.

### 2. Open the dependent PR with `base` set to the base branch

``` bash
gh pr create --base <base-branch> --title "<title>" --body "> [!IMPORTANT]
> Merge #<base-N> first --- this PR is stacked on its branch.

Stacked on #<base-N>.

<description>"   # CREATE_PR
```

In a remote/web session without `gh`, use `mcp__github__create_pull_request` with `base: "<base-branch>"`. Note the dependency explicitly in the body (`Stacked on #<base-N>`) so anyone scanning the PR list sees the relationship at a glance (`ardia`’s own stacking detection uses `baseRefName`, not the body text — see below).

A stack is the archetypal merge-order constraint, which is why the body leads with the `> [!IMPORTANT]` alert `CLAUDE.md`’s “Surface merge-order constraints” section prescribes: the plain `Stacked on #<base-N>` line reads as ordinary prose on a crowded PR page, and the alert does not. Report the order in chat under that section’s boxed `### 🔀 MERGE ORDER` marker too. Skip its third surface, draft-gating — `base` already points at the base branch, so GitHub cannot merge this PR into `main` out of order in the first place. The alert and the marker serve the human’s reading order; they aren’t enforcing a constraint the stack itself already enforces.

If the dependent work is being opened up front per [`pr-on-claim`](../../shared/workflow/pr-on-claim.md), open it as a draft from an empty commit exactly as that skill describes, just with `--base <base-branch>` instead of `main`.

### 3. Keep the dependent branch in sync as the base branch moves

Whenever the base PR gets new commits (a review fix, a rebase, `main` merged into it), merge that movement into the dependent branch before the next push or review trigger — the same standing rule [`sync-with-main`](../../shared/workflow/sync-with-main.md) applies to `main`, here applied to the base branch instead:

``` bash
git fetch origin <base-branch>     # FETCH
git merge "origin/<base-branch>"   # MERGE_BRANCH
```

Resolve any conflicts (see [`resolve-conflicts`](../../skills/resolve-conflicts/SKILL.llms.md)), run the repo’s pre-commit checks, then push. Do this before every push and before every fresh review request, exactly as `sync-pr-branch` does for `main`.

### 4. When the base PR merges, re-point the dependent PR at `main`

Once the base branch’s commits land on `main` (the base PR merges), the dependent PR no longer needs to target the base branch — retarget it so it merges normally and the stacking note stops being misleading:

``` bash
git fetch origin main            # FETCH
git merge origin/main            # MERGE_BRANCH -- see the ancestry test below before trusting this
gh pr edit <dependent-N> --base main   # EDIT_PR
```

In a remote/web session, use `mcp__github__update_pull_request` with `base: "main"`. GitHub’s documentation promises it retargets the PR **on its own** when the base branch is deleted on merge, and when that happens it changes nothing below, because retargeting only moves a pointer and never rewrites the branch.

**Do not rely on it.** In practice `gh pr merge <base-N> --delete-branch` can **close** the dependent PR instead of retargeting it, which [`memories/git-branches.md`](../../memories/git-branches.md) records from a separate incident a month earlier. So run `gh pr list --base <base-branch>` before merging, and omit `--delete-branch` whenever it returns anything. Delete the branch by hand once the dependent PR has visibly retargeted.

**Run that query before every merge, not only a `--delete-branch` one, and do not count on omitting the flag.** A plain squash merge orphans a dependent with no branch deletion involved: the dependent keeps its old merge base and re-shows the merged content as a conflict. And a repo configured to delete merged head branches does so whatever flag you passed, so omitting it changes nothing there. [`batch-merge-and-resolve`](../../shared/workflow/batch-merge-and-resolve.md)’s “A stacked PR is the one conflict that intersection cannot attribute” section carries the measurement and the attribution rule.

If it closes anyway, the head branch survives, and restoring the base is a better recovery than opening a replacement PR — it keeps the PR number, its comment thread, and its review verdicts:

``` bash
git push origin <merged-sha>:refs/heads/<deleted-base>   # restore the base
gh pr reopen <dependent-N>                               # only works now
gh pr edit <dependent-N> --base main                     # retarget
git push origin --delete <deleted-base>                  # re-delete
```

The order is forced: `gh pr reopen` fails while the base is missing, and `gh pr edit --base` fails on a closed PR (`Cannot change the base branch of a closed pull request`). Expect `reviewDecision: REVIEW_REQUIRED` afterward — retargeting resets the review state even though the head commit never moved. (UCD-SERG/serocalculator \#633/#635, 2026-08-07. PR \#635 closed two seconds after \#633 merged, and that timing is what establishes the cause.)

Keep an issue or PR reference off the start of a line when you break these sentences: markdownlint reads a leading `#` as a malformed ATX heading and fails `validate` with MD018.

After retargeting, GitHub recomputes the diff against `main`. It should now show only the dependent PR’s own changes, since the base PR’s commits are already on `main`. **Check that it does, with an ancestry test rather than by eye** — the two ways it can go wrong have different causes and different fixes, and only one of them is the merge’s fault:

`git merge-base --is-ancestor` prints nothing and answers through its exit status alone, so report the three outcomes rather than running it bare:

``` bash
git fetch origin main                                             # FETCH
git merge-base --is-ancestor "origin/<base-branch>" origin/main   # ANCESTRY
case $? in
  0) echo "ancestor -- real merge commit" ;;
  1) echo "not an ancestor -- squash or rebase merge" ;;
  *) echo "cannot tell -- origin/<base-branch> is gone; treat as squash" ;;
esac
git diff --stat origin/main...HEAD                                # DIFF
```

Keep the third arm rather than collapsing it into the second with `&& ... || ...`. The command exits 2 or higher when `origin/<base-branch>` does not resolve, which happens once the base branch is deleted on merge and something has run `git fetch --prune` since — and a two-branch form maps that error onto “not an ancestor”, so a broken check and a real squash print the same thing. That is the [`fail-fast`](../../shared/principles/fail-fast.md) shape: a check whose failure path is indistinguishable from one of its answers. The *action* is the same either way, since both lead to the rebuild below, but only the three-arm form tells you which one you are in.

- **Ancestor, diff still bloated** — the base PR merged as a real merge commit and the `git merge` above was a no-op or missed something. Re-run it.
- **Not an ancestor** — the base PR was **squash-merged**, so its commits are not on `main` at all; `main` carries one new commit with the same content under a different hash. The dependent PR’s diff therefore re-shows the base PR’s already-merged work, and **merging `main` cannot fix it**: the merge commit keeps those original commits in the branch’s history, which is exactly what the diff is reporting.
- **Cannot tell** — the remote-tracking ref is gone, so the test has nothing to compare. Treat it as the squash case and rebuild; that is correct under a real merge too, just unnecessary.

The squash case is the one to know, because nothing warns you. `CLAUDE.md` carries this ancestry check already, but under a trigger that does not fire here — it fires *before adding commits to a branch you did not just create*, whereas a stacked PR is created and pushed while the base is still open, and self-bloats later when the base lands. No action of yours sits between the two. So a stack in a squash-merging repo needs this check on the base PR’s **merge**, not on your next push.

Rebuild rather than merge, keeping only the dependent PR’s own commits:

``` bash
git checkout -B <dependent-branch> origin/main                        # RESET_BRANCH
git cherry-pick <commit-1> [<commit-2> ...]                           # CHERRY_PICK
git push --force-with-lease origin <dependent-branch>                 # PUSH
```

Spell the commits out as separate arguments rather than as `<commit>...`. A trailing `...` reads as git’s own three-dot range syntax, which resolves against `HEAD` and selects something quite different from “these commits”. For a contiguous run, name the range explicitly instead: `git cherry-pick <oldest>^..<newest>`.

Get that list from the branch as it stood **before** the reset, not from memory — `git log --oneline --no-merges "origin/<base-branch>..<dependent-branch>"` while both refs still exist, or the PR’s own commit list.

`--no-merges` is required rather than tidy. Every step-3 sync left a merge commit on the dependent branch, reachable from it and not from the base, so the range contains commits `cherry-pick` refuses outright: *commit is a merge but no `-m` option was given*. The same applies to the PR’s commit list, which shows those merges too — so filter by hand when reading it, rather than assuming GitHub has already dropped them.

Confirm the diff dropped to the dependent PR’s own changes, and re-run the repo’s pre-push checks at the new head rather than carrying over the earlier run’s results — the branch is a different commit now, so the old output describes something else. Say on the PR that you rebuilt and why, since a force-push with no explanation reads as history being rewritten for no reason.

Update the PR body to drop the `Stacked on #<base-N>` note — and the `> [!IMPORTANT]` merge-order alert from step 2 — once this step is done; both describe a constraint that no longer exists, and a stale alert trains readers to ignore the next real one.

### 5. If the base PR is abandoned or closed unmerged

Re-target the dependent branch onto `main` directly and drop the base PR’s unmerged commits from the dependent branch’s history — don’t leave a PR silently based on a branch that will never land:

``` bash
git fetch origin main    # FETCH
git rebase --onto origin/main "origin/<base-branch>" <dependent-branch>
gh pr edit <dependent-N> --base main   # EDIT_PR
```

This rewrites the dependent branch’s history — **get explicit approval from the user before running it**, and before force-pushing the result (`git push --force-with-lease origin <dependent-branch>` — `PUSH`), since it discards the abandoned base PR’s commits from a published branch.

## Relationship to other skills

- **`ardia`** — detects stacked PRs via `baseRefName` and sequences them (base before derived) as part of sweeping the whole open-PR queue. This skill is the direct, single-PR counterpart: use it when you already know you want to stack, rather than letting a sweep discover the relationship.
- **`stack-dont-pause`** (`shared/workflow/stack-dont-pause.md`) — the rule that a clean-but-unmerged PR is not a reason to pause a sweep; stack new, dependent work on it instead of waiting. This skill is the mechanics that rule points to.
- **`sync-pr-branch`** / **`merge-main`** — the analogous “keep in sync” procedure for a branch and `main`. Step 3 here is that same procedure applied to a moving base branch instead of `main`.
- **`resolve-conflicts`** (`rc`) — used in step 3 when the base branch’s movement conflicts with the dependent branch.
- **`pr-on-claim`** — step 2’s draft-PR-up-front pattern, adapted to target the base branch instead of `main`.
- **`gii`** / **`gia`** — stack issues’ PRs on a prior unmerged issue’s branch as part of their serial loop ([\#123](https://github.com/Morrison-Lab/ai-config/issues/123)); this skill is the reusable primitive they could each call instead of reimplementing the mechanics.

## Anti-patterns

- ❌ Guessing the base PR’s branch name from its title instead of reading `headRefName` — a mismatch silently branches from the wrong ref.
- ❌ Stacking two PRs that are merely concurrent but not actually dependent — branch from `main` instead; stacking adds a real ordering constraint.
- ❌ Skipping the decision gate because the instruction already said “stack this” — the gate confirms the dependency is real; an assumed dependency that fails both tests should be surfaced back, not silently stacked.
- ❌ Treating file-list overlap alone as proof of a conflict (Test B) — disjoint regions of the same file merge cleanly from `main`; only same-passage edits (or a shared insertion point) justify the stack.
- ❌ Claiming a code dependency without checking `origin/main` — a symbol the base PR touches may already be merged, making the dependency moot.
- ❌ Letting the dependent branch drift after the base branch gets new commits — sync it before every push, not just once at creation.
- ❌ Leaving the dependent PR targeting the base branch after the base PR merges — retarget to `main` (step 4) so the diff and merge behave normally.
- ❌ Treating the retarget as the whole of step 4 — run the ancestry test after it, since under a squash-merge the diff stays bloated while retargeting moves a pointer without touching the branch.
- ❌ Merging `main` again to shrink a diff that is bloated because the base PR was squash-merged, when the merge preserves the very commits the diff is reporting — rebuild from `main` and cherry-pick instead.
- ❌ Force-pushing or rebasing a published dependent branch without telling the user, even when the base PR was abandoned (step 5).

Back to top
