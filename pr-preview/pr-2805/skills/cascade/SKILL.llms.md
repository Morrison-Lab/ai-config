# cascade

Merge stacked PRs’ **base branches into the PRs stacked on top of them** — including `main` into unstacked PRs — so every open branch in a stack stays synced with what’s beneath it.

**This is a downward propagation only.** “Cascade” never means merging the PRs themselves into `main`; merging PRs is a separate, human-gated action (`merge-it`). (A bare “Cascade” was misread exactly that way on the `d-morrison/rme` \#1035–#1042 stack, 2026-07-17 — this skill exists to pin the meaning.)

## Procedure

1.  **Map the stack.** List open PRs and their base branches (`gh pr list --json number,headRefName,baseRefName`, or `mcp__github__list_pull_requests` in remote sessions). A PR based on `main` is unstacked; a PR based on another PR’s head branch is stacked on it. Order the work from the base outward: `main` → first-level branches → branches stacked on those, and so on.

2.  **For each branch, in that order.** Set up one isolated worktree for the whole cascade (so the repo’s primary checkout is never disturbed), then switch it from branch to branch as you work down the stack:

    ``` bash
    # once, from the repo's primary checkout:
    git worktree add --detach <dir> && cd <dir>

    # then, per branch:
    git fetch origin <branch> <base> -q
    git checkout -B <branch> origin/<branch>
    git merge origin/<base>
    ```

    (`checkout -B` inside the worktree resets to the remote tip even when a stale local branch of that name exists; a branch already checked out in another worktree can’t be checked out here — reuse that worktree for it instead.)

3.  **Resolve squash-stack conflicts to the branch side.** When the base advanced by squash-merging PRs whose commits the branch already carries (the normal stacked-PR lifecycle), the three-way merge sees the same content twice under different SHAs and conflicts on every co-touched file. The branch side already contains the base’s content, so:

    ``` bash
    while IFS= read -r -d '' f; do git checkout --ours "$f"; done \
      < <(git diff --name-only --diff-filter=U -z)
    git add -A
    ```

4.  **Verify the merge is content-neutral before trusting it.** The merged tree should be byte-identical to the pre-merge branch tree:

    ``` bash
    git diff --cached HEAD --stat   # staged resolution vs pre-merge tip: expect empty
    # or, after an auto-committed merge:
    git diff 'HEAD~1' HEAD --stat   # vs first parent: expect empty
    ```

    An **empty** diff means the reviewed, render-verified tree is unchanged — finalize the merge, noting the verification in the message (the auto-committed case is already final):

    ``` bash
    git commit -m "Merge <base> into <branch> (content-neutral sync)"
    ```

    Then skip re-running the repo’s pre-commit render/lint/test gates. A **non-empty** diff means the base carried changes the branch lacks (someone else’s PR merged, a hotfix on `main`): stop treating it as mechanical — review the delta and run the repo’s full pre-commit checks before pushing.

5.  **Push, minding CI and the remote branch.** Each push triggers a fresh review/build round on that PR, and review/preview workflows commonly run under `concurrency: cancel-in-progress` — so batch each branch’s cascade into one push, and don’t push a branch again while its round is in flight (see `sync-with-main`’s and gha’s cancellation-race notes). Step 2’s `checkout -B <branch> origin/<branch>` starts from the just-fetched remote tip, so unlike `sync-pr-branch`’s local-branch flow there’s usually nothing to reconcile — but `origin/<branch>` can still move in the window before the push (an `@claude` bot commit, another session). If the push is rejected as non-fast-forward, `git fetch origin <branch>` and `git merge origin/<branch>`, then push again — never force-push.

6.  **Repeat down the stack** — after a first-level branch is synced and pushed, the branches stacked on it merge *it* (not `main`) in the same way.

## Relationship to other skills

- **`sync-pr-branch` / `merge-main`** — the single-branch case (one PR vs `main` and its own remote); `cascade` is the whole-stack generalization, and defers to that skill’s pre-commit-check guidance whenever a merge is not content-neutral.
- **`stack-prs`** — creates stacked PRs; `cascade` maintains them as their bases move.
- **`resolve-conflicts`** — general conflict-resolution mechanics; step 3 here is the squash-stack special case where “take the branch side” is provably correct (verified by step 4’s empty-diff check, not assumed).
- **`merge-it`** — merging a PR into `main` stays human-gated there; `cascade` never does it.

## Anti-patterns

- ❌ Reading “cascade” as “merge the stack’s PRs into `main`” — the direction is down the stack, not into it.
- ❌ Taking `--ours` on conflicts without step 4’s empty-diff verification — a non-empty result means the base had content the branch lacks, and blind `--ours` would silently revert it on the next merge.
- ❌ Cascading a branch before its own base has been cascaded — order matters; work from `main` outward.
- ❌ Re-rendering/re-testing after a verified content-neutral merge — the tree is byte-identical to the already-verified state; the checks would re-prove what the empty diff already proved.

Back to top
