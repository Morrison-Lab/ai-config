# resolve-conflicts — consolidate the best of both branches

A merge conflict means **both** branches edited the same region — and each side changed it for a reason. The right resolution almost always keeps the *intent* of **both** sides. The default failure mode is to grab one side wholesale (`--ours` / `--theirs`) and silently throw the other branch’s work on the floor. Don’t. **Consolidate, don’t choose.**

## When this fires

- Any git operation stops on a conflict: `git merge`, `git rebase`, `git cherry-pick`, `git stash pop`, `git pull` (merge *or* rebase), `git revert`. The tell is `CONFLICT (content): Merge conflict in …` and `Unmerged paths:` in `git status`.
- “resolve the conflicts”, “fix the merge conflicts”, “I have a merge conflict”, “consolidate the best of both branches”, “help me merge these branches”, “the branch won’t merge cleanly”.
- **Delegated from another skill**: `sync-pr-branch` step 5 (“resolve any conflicts fully”), `clean-branches`’ rebase-onto-main step, or a stacked `gii` MR. When one of those stops on a conflict, run this.

## Verify before you act — don’t trust `mergeable` alone

Before claiming and fixing a PR flagged by a cascade conflict scan (`post-merge` step 1.5, `ardi`’s opportunistic sweeps, `wrap-up` step 1), get ground truth locally instead of acting on the API field directly:

``` bash
git fetch origin main <branch> -q   # FETCH
git merge-tree --write-tree origin/main origin/<branch>   # git >=2.38; no worktree/checkout needed
echo "exit: $?"   # 0 = clean merge (no action needed); 1 = real conflict exists
```

Two failure modes this catches:

- **`mergeable == "UNKNOWN"` is not “no conflict.”** GitHub returns `UNKNOWN` right after a push or a sibling PR’s merge, while it’s still computing — sometimes for minutes. A cascade scan that filters only `mergeable == "CONFLICTING"` silently skips a PR stuck in `UNKNOWN` even when it’s genuinely conflicting. Treat `UNKNOWN` the same as `CONFLICTING`: a candidate to verify, not a PR to skip.
- **`mergeable == "CONFLICTING"` (or a `dirty` mergeable_state) can itself be stale.** GitHub computes it against whatever `main` snapshot it last saw — if a sibling PR merged since, the flag may still say conflicting even though a fresh merge against current `main` is clean. Acting on a stale flag risks wasted resolution effort. (Seen on ai-config#372: flagged `dirty`, but `git merge-tree` against current `main` came back clean — no manual resolution was needed, just a `git merge` + push.)

If `git merge-tree` exits clean, there’s nothing to resolve — skip the PR (or, if you want the branch to reflect the now-current `main`, do a plain `git merge origin/main && git push`, no conflict markers involved). Only proceed to the consolidation procedure below when it reports a real conflict.

**Check `git --version` before trusting the exit code — on git \<2.38 this command fails a different way that a naive check misreads.** `--write-tree` mode doesn’t exist before 2.38; on an older install the command errors with `fatal: unknown rev --write-tree` (a non-zero exit, same as a real conflict) or, if scripted with a text-based check instead of the exit code, an error message that a naive `grep -qi conflict` fails to match — silently misclassifying every single PR in a batch scan as clean (a false negative that defeats the whole scan; hit across a 5-PR cascade scan on ai-config, 2026-07-03). Confirm `git --version` is 2.38+ before relying on this command’s exit code at all. On an older git, use the legacy 3-arg form instead (same read-only guarantee, no worktree/checkout):

``` bash
base=$(git merge-base origin/main origin/<branch>)
git merge-tree "$base" origin/main origin/<branch>   # git <2.38 (any version)
# conflict markers ("<<<<<<<") in the output = real conflict; empty/clean = no conflict
```

## Core principle: consolidate the best of both branches

Each conflict hunk has three inputs — the common **base**, **our** side, and **their** side. Picking a winner is right only when one side’s change is genuinely the *same* edit, or strictly subsumes the other. Otherwise the merge should contain a **synthesis** that honors both:

- Two different features touching neighbouring lines → keep **both** edits.
- A refactor on one side + a bugfix on the other → apply the bugfix *to the refactored code*.
- A rename on one side + an edit to the old name on the other → carry the edit onto the new name.
- **`CONFLICT (add/add)` on the same newly-added file** (common with sibling PRs) → compare `:2:` vs `:3:` first; keep the side that carries the newer baseline (often `main` after a sibling PR merged), then manually re-apply any newer deltas from the other side (review fixes, wording corrections, version pins) before staging.

If you can’t see why a side changed the hunk, you’re not ready to resolve it — go read the history first (step 2).

## Procedure

1.  **Survey the battlefield.** Know which operation you’re in (the semantics of “ours”/“theirs” depend on it — see the warning below) and list the conflicted files:

    ``` bash
    git status                                   # header names the operation
    git diff --name-only --diff-filter=U         # just the unmerged paths
    ```

2.  **Understand BOTH sides before editing a single hunk.** For each conflicted file, look at the three-way picture and *why* each side diverged:

    ``` bash
    git log --merge --oneline -- <file>   # commits from both sides (during a MERGE)
    git show :1:<file>                    # BASE (common ancestor)
    git show :2:<file>                    # OURS  (HEAD / current side)
    git show :3:<file>                    # THEIRS (incoming side)
    ```

    The `:1:`/`:2:`/`:3:` index stages work in any conflicted operation. `git log --merge` is merge-only; for the others, inspect the incoming side directly via the operation’s ref — `git show MERGE_HEAD` (merge), `REBASE_HEAD` (rebase), `CHERRY_PICK_HEAD` (cherry-pick), `REVERT_HEAD` (revert), or the kept `stash@{0}` entry for a stash pop (`git stash show -p stash@{0}`). Ask: what problem was each side solving? Different features? One refactor + one fix? A move/rename vs an in-place edit? The answer dictates the merge.

3.  **Consolidate.** Edit the working file into a version that keeps the valuable change from **both** sides, then delete every conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`). Take one side wholesale only when you’ve confirmed the other side has nothing worth keeping — and note that you did.

    **Also check whether the merged result duplicates content that already exists elsewhere in the file — a separate problem from the textual conflict itself.** This can arise two ways: a single incoming PR may internally copy a sentence into a new section (the merge is clean, but the result now says the same thing twice), or both branches may independently add equivalent sentences in different sections (a cross-branch variant with the same symptom). In both cases `git merge`/`merge-tree` reports zero conflicts even though the result contains duplication — sometimes with a pronoun or reference that only made sense in its original location. Grep the merged file for the distinctive phrase from each side’s addition before finishing; if it already appears elsewhere, keep one copy (usually the version with the clearer standalone referent) and drop the redundant one. (ai-config#446: the merge itself was clean, but the incoming PR’s own diff had separately duplicated a CLAUDE.md sentence verbatim into a different section, where “this policy” lost its antecedent — the intra-PR variant, caught by the `@claude` review bot as a distinct finding from the conflict resolution.)

4.  **Prove no markers (or whitespace damage) slipped through:**

    ``` bash
    git diff --check                      # flags leftover markers + whitespace errors
    grep -rnE '^(<<<<<<< |======= *$|>>>>>>> )' . --exclude-dir=.git   # precise markers, portable -E
    ```

5.  **Run the repo’s pre-commit checks before committing the resolution.** A merge where each side compiled *separately* can still break *combined*. Build / lint / test / spellcheck per the current repo (use its `render` / `lint` / `spell` / `test` skills if it ships them). Don’t commit a resolution that fails checks.

6.  **Stage the resolved files, then finish the operation** — never `--abort` or `--skip` away a conflict you were asked to resolve. The finish command matches the operation `git status` names, **not** the command you typed (a `git pull` is a merge *or* a rebase underneath — check which):

    ``` bash
    git add <file> …
    git commit                 # merge (message prefilled from MERGE_MSG)
    git rebase --continue      # rebase (incl. `git pull --rebase`)
    git cherry-pick --continue # cherry-pick
    git revert --continue      # revert (message prefilled)
    # stash pop: no commit/continue — `git add` the resolution, then `git stash drop`.
    #   A conflicted pop does NOT auto-drop the stash, and dropping it is
    #   independent of committing: the resolved changes stay as working-tree edits.
    ```

## ⚠️ “ours” and “theirs” flip between merge and rebase

- In a **merge** (`git merge X` on branch `B`): `ours`/`:2:` = `B` (where you are), `theirs`/`:3:` = `X` (being merged in).
- In a **rebase** (`git rebase X` on branch `B`): rebase replays *your* commits onto `X`, so `ours`/`:2:` = **`X`, the branch you’re landing on**, and `theirs`/`:3:` = **your own commit being replayed**. The opposite of a merge.

Confirm which physical branch is “ours” before you reach for `--ours` / `--theirs` — getting this backwards silently keeps the wrong side. (This is *why* the skill defaults to consolidating both rather than picking a side.)

## Relationship to other skills

- **`sync-pr-branch`** (aliases `sync` / `merge-main` / `resync-branch`) — its step 5 says “resolve any conflicts fully”; **this** is that step’s how-to. Run it when that sync stops on a conflict, then return to finish the sync.
- **`clean-branches`** — when rebasing a stale branch onto `main` hits a non-trivial conflict, resolve it here instead of skipping the branch.
- **`gii` / `split-concerns`** — stacked or parallel MRs are the usual source of conflicts; this is how you clear them once they collide.
- **`check-history`** — run *before* implementing to avoid creating avoidable conflicts/regressions in the first place; this skill cleans up the ones that still happen.
- **`deconflict-sessions` / `session-lock`** — **not** this skill. Those are about two AI *sessions* clobbering one local checkout (a locking concern), not git *content* conflicts. Different sense of “conflict.”

## Anti-patterns

- ❌ Blind `git checkout --ours/--theirs <file>` (or `git merge -X ours/theirs`) without confirming the dropped side had nothing worth keeping — the classic silent-data-loss move.
- ❌ Resolving a hunk before understanding *why* each side changed it.
- ❌ Mixing up “ours”/“theirs” in a rebase (they’re reversed vs a merge).
- ❌ Committing with conflict markers still in a file — always `git diff --check`.
- ❌ Committing the resolution without running the repo’s build/lint/test checks.
- ❌ `git rebase --skip` / `git merge --abort` to dodge a conflict you were asked to resolve.
- ❌ Force-pushing a half-resolved merge/rebase.

Back to top
