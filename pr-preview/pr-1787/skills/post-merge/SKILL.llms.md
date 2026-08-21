# post-merge — wrap up a merged PR (verify, tidy, then UMS)

The per-PR bookend to a piece of work. Once a PR/MR merges: confirm it landed, clean up the local branch, make sure nothing was left dangling, and — the point of the skill — **run UMS to learn from how the PR went** while the review lifecycle is still fresh in context.

## When this fires

- A PR/MR you were working on just merged.
- “post-merge”, “wrap up the merged PR”, “clean up after the merge”, “the PR merged — now what?”
- **“merge it” / “merge this” route to `merge-it`, not here** — that skill performs the merge first, then chains into this one. Only handle those phrases here when the PR is already merged (no merge left to do).
- Distinct from **`wrap-up`** (session-level, may span several PRs/issues) — `post-merge` is the single-PR version, run each time a PR lands.

## Procedure

### 1. Verify the merge — never assume

``` bash
gh pr view <N> --json number,title,state,mergedAt,mergeCommit,headRefName   # VIEW_PR
# GitLab
glab mr view <N>
```

Confirm `state == MERGED` and `mergedAt` is set. If it isn’t actually merged, **stop and report** — don’t tidy a branch whose work hasn’t landed. (The standing **never assume; always verify** rule applied to closing out a PR.)

### 1.25. Check for reviews that landed just before the merge

A review can post after your last processed round and before the human merges. Those findings are real even though they are absent from the merge commit. After confirming `mergedAt`, identify the last review this session explicitly dispositioned, then read every formal review and PR comment after that timestamp and before `mergedAt`. Do not use an imprecise “near the merge time” window. The lower bound is the last dispositioned review, and `mergedAt` is only the upper bound.

**When this session never dispositioned a review on this PR** — entering through the “the PR merged – now what?” route, or picking up a PR another session drove — there is no last-dispositioned-review timestamp to anchor on. Don’t skip the scan for lack of a lower bound. Scan the complete review and comment history through `mergedAt` instead, with no lower bound at all, since anything on the PR is late from this session’s point of view.

``` bash
gh api repos/<owner>/<repo>/pulls/<N>/reviews --paginate    # formal review bodies
gh api repos/<owner>/<repo>/pulls/<N>/comments --paginate   # inline review comments
gh api repos/<owner>/<repo>/issues/<N>/comments --paginate  # top-level PR comments
```

A formal review’s top-level body is not enough. For each late review, read the inline comments too, because an empty-body review can carry every finding inline. This is the same two-surface shape `ardi` already requires when reading formal reviews; do not reimplement it as a body-only scan here.

**Read the inline comments unfiltered, though — do not narrow them to one `pull_request_review_id`.** That filter is the natural way to pair each late review with its own findings, and it is the correct way to drill into a review a human pointed at. It is unsound as a completeness check, because the round and the review object are not the same unit: a reviewer can emit two review objects seconds apart carrying one finding each, so filtering by either id returns a strict subset that reads exactly like a complete answer.

Take the timestamp window from the enumeration above, and take *outstanding* from the **thread list**, which is per-thread rather than per-review and so cannot be split across review objects:

``` bash
gh api graphql -f query='{ repository(owner:"<owner>", name:"<repo>") {
  pullRequest(number:<N>) { reviewThreads(first:100) {
    totalCount
    nodes { id isResolved path line comments(first:1){nodes{databaseId}} } } } } }'
```

Page at `first:100` and select `totalCount`: a `totalCount` above the node count means the cap was hit, so the thread list is itself truncated — treat that as not-yet-clean, the guard `skills/pr-status/SKILL.md` and `skills/pr-status-all/SKILL.md` already use. `memories/github.md` carries the full statement and the case record.

**A finding can also arrive as a plain top-level PR comment rather than a formal review** — a bot posting a summary via `gh pr comment` (or the equivalent API call) rather than through the reviews endpoint, or a human commenting directly on the PR conversation. `pulls/<N>/reviews` and `pulls/<N>/comments` are both scoped to formal reviews and their inline threads; neither surface returns a plain PR conversation comment. Those live on the **issue comments** endpoint — a pull request is also an issue in GitHub’s data model — so the scan needs all three surfaces, not two, to cover every place a late finding can land.

If a late review contains findings:

1.  Confirm the merge commit does not contain the fix.
2.  File or use a follow-up issue or PR, and carry the findings there with a link back to the merged PR.
3.  Do not count the merged PR’s review loop as clean for those findings; the new PR owns them.

- **Do:** check every review and PR comment posted after the last dispositioned review and before `mergedAt`.
- **Do:** fetch late formal reviews’ inline comments, not only their top-level bodies.
- **Do:** fetch the issue-comments endpoint too, not just the two review surfaces — a late finding can arrive as a plain top-level PR comment.
- **Do:** carry late findings forward to a new tracked fix when the merge beat the ARD round.
- **Don’t:** use a vague “near merge time” window that can skip a late finding posted well before a delayed merge.
- **Don’t:** treat the merge as proof the final review round was clean.
- **Don’t:** drop a finding because it arrived too late for the merged branch.
- **Don’t:** skip this scan because no last-dispositioned-review timestamp exists — scan the whole history through `mergedAt` instead.
- **Don’t:** stop at the two formal-review surfaces — a bot or human can post a late finding as a plain issue comment that neither one returns.

(Morrison-Lab/ai-config#1029: Copilot round 7 posted at 2026-08-02T06:29:10Z, and the PR merged at 06:30:55Z as `1e0b5fdf`. The suppressed findings were real, absent from the merged code, and had to be carried forward to \#1034.)

**A review can also arrive *after* `mergedAt`, which the bound above excludes by construction.** Everything above treats the merge as the scan’s upper bound, and for a review already sitting on the PR that is right. It also encodes an assumption that nothing further can land, and a reviewer dispatched before the merge does not stop working when the merge happens. `post-merge` runs promptly after the merge, which is what makes this a gap rather than a curiosity: the scan fires while a late review has not posted yet, so a single run returns a clean result that expires.

So re-read the three surfaces once more before closing the PR out, with no upper bound at all, and treat a `submitted_at` later than `mergedAt` as an ordinary finding rather than as an anomaly.

That re-read catches a review already sitting on the PR; it cannot catch one still in flight. A single synchronous read narrows the window but does not close it — the review that posted ten minutes after the merge in the case below would still be unposted at the moment `post-merge` runs. The durable catch is staying subscribed to the merged PR’s review activity, so the review notification wakes the session when the late verdict actually posts, or re-arming a delayed check with a defined completion condition.

Two things change when the review lands after the merge rather than before it.

The merged PR is **no longer a place to land code fixes**. That is a third reason for moving work elsewhere, distinct from the two the corpus already carries: ARD’s Defer moves a finding because fixing it would widen the PR’s scope, and [`address-every-comment`](../../shared/workflow/address-every-comment.md)’s `main`-sync case moves one because the line is not yours. Here the finding is in scope and is yours, and only the branch it belonged to is gone.

And the vehicle is a **follow-up PR against `main`**, narrower than the “issue or PR” item 2 above leaves open. The findings usually still apply to `main`, since `main` now holds the merged code they were written about — but confirm that against current `main` first, since an overlapping merge can have changed or removed that code before the follow-up runs. Where they do still apply, the fixes are already known, so an issue would record work that could simply be done.

**Post the back-pointer on the merged PR, not only the forward link.** Item 2 asks the follow-up to link back to the merged PR, which serves a reader who already knows the follow-up exists. That is the reader who needs it least. The follow-up is reachable only by someone who has already found it, whereas the merged PR is what a changelog entry, a `git blame`, or the review notification itself points at. That reader finds a review with unaddressed findings sitting under a merged banner, and has no way to tell whether anyone handled them. Comment on the merged PR naming the follow-up and each finding’s disposition, so the record reads correctly from whichever end it is entered.

`CLAUDE.md`’s push-races-the-merge case already asks for a comment of this shape, saying which of a merged PR’s findings did not ship in it. Its trigger is a `* [new branch]` push tell rather than a review posting, so neither case fires on the other.

- **Do:** re-read the three surfaces with no upper bound before closing out, and treat a review submitted after `mergedAt` as ordinary.
- **Do:** stay subscribed to the merged PR, or re-arm a delayed check with a completion condition, to catch a review that posts after `post-merge` runs — a single synchronous re-read cannot close that window.
- **Do:** open a follow-up PR against `main` when the findings are in scope and the fixes are known, rather than filing an issue.
- **Do:** comment on the merged PR naming the follow-up and each finding’s disposition.
- **Don’t:** read the scan’s clean result as durable when it ran promptly after the merge, before a late review could post.
- **Don’t:** treat a post-merge finding as a Defer, since nothing about its scope changed, only the branch’s availability.
- **Don’t:** rely on the follow-up’s link back as the whole record, since a reader who lands on the merged PR never sees it.

(Morrison-Lab/ai-config#1079 merged at 2026-08-03T03:36:11Z, and Copilot’s review posted at 03:46:25Z, ten minutes after the merge rather than two minutes before it as in \#1029 above. It carried three inline findings plus two more inside a `Suppressed comments (2)` block, and all five were correct. They were addressed against `main` in \#1082, opened for that purpose and merged at 04:15:05Z, and a comment on \#1079 at 03:52:47Z names \#1082 and each finding’s disposition.)

### 1.5. Cascade conflict scan

**In an ultracode/coordinator session, delegate this whole step to a subagent** rather than running the scan-and-resolve loop in the main thread — it’s exactly the kind of investigation-plus-fix work the coordinator should hand off (see `memories/preferences.md`’s coordinator-mode bullet). Brief the subagent with the merged PR’s number/branch and the steps below; have it report back which PRs it found conflicting, what it did about each, and any it skipped (already claimed, conflict it couldn’t understand). Do the scan inline only for a solo (non-orchestrated) session.

**If any OTHER agents already own a claimed branch (an active, resumable `Agent`-tool session, not a one-shot `Workflow`-internal `agent()` call), message each one directly right after the merge, instead of relying solely on a separate scan to find and fix their conflict after the fact:** “main just advanced (PR \#N merged) — fetch and merge origin/main into your branch now, resolve any conflict yourself (you have the context on your own change), then continue.” This is faster and higher-context than a scanning subagent guessing at the resolution from outside: the branch’s own owning agent already knows why its code looks the way it does.

**This depends on the coordinator finding out about a merge in the first place — so brief every delegated agent, up front, to report back the instant its OWN tracked PR merges, not just when its ARDI work is done.** A PR sitting “ready for merge” isn’t the end of that agent’s watch: keep polling until the merge actually happens — by a human, since the agent itself must not self-merge — then notify the coordinator immediately. This is what lets the coordinator fan out the “merge main now” nudge above to every OTHER live agent right when it matters, instead of the coordinator having to separately poll every open PR’s merge state itself to notice. Fold this into the standard delegation brief (see `gia`/`gii`’s per-issue agent prompts) alongside the no-self-merge instruction, rather than treating it as a one-off ask.

Reserve the scan-and-fix subagent above for branches with NO active owning agent (e.g. a completed `Workflow` run’s one-shot agent that already returned).

A squash-merge on `main` can knock previously-mergeable open PRs into conflict. Scan right after the merge is confirmed:

``` bash
gh pr list --state open \
  --json number,title,headRefName,mergeable,mergeStateStatus,comments   # LIST_PRS
```

For each PR where `mergeable == "CONFLICTING"` **or `"UNKNOWN"`** (GitHub can take minutes to finish computing mergeability after a push — a genuinely conflicting PR can sit in `UNKNOWN` and get missed if you filter for `CONFLICTING` alone):

1.  **Verify before claiming — don’t trust the flag alone.** See `resolve-conflicts`, “Verify before you act”: `git merge-tree --write-tree origin/main origin/<branch>` gives ground truth without a worktree (git ≥ 2.38). Skip if it comes back clean.

2.  **Attribute before claiming — a conflict this sweep found is not necessarily one your merge caused.** On a repo with an old PR backlog most surviving conflicts are ordinary drift (`DESCRIPTION`, a word list, a directory deleted months ago) and were conflicting before you arrived. Claiming them means resolving other people’s branches for no reason. Derive the merge’s own deleted and renamed paths and intersect them with each conflict’s paths:

    ``` bash
    merge=$(git rev-parse HEAD)   # the merge commit you just confirmed
    git diff --name-status -M "$merge^1" "$merge" | grep -E '^(D|R)'
    ```

    A conflicting path in neither set is drift — skip it. **One exception, and it is the conflict this merge most certainly caused:** a PR **stacked** on the branch you just merged conflicts on the paths that merge modified and added, never on the ones it deleted or renamed, so the intersection is empty and this step would skip it. Check `gh pr list --base <merged-branch>` before merging, treat any PR it returns as caused by you whatever the intersection says, and reach for [`cascade`](../../skills/cascade/SKILL.llms.md) rather than resolving the conflicts line by line. The `git diff` form is used because it is correct for **both** merge styles, which `git show` is not. A squash merge is an ordinary single-parent commit, so `git show --name-status "$merge"` diffs it normally and would do. A **true** merge commit has two parents, and `git show` defaults to a combined diff that omits every path changed in only one parent — on a clean merge that is all of them, so it prints no file list at all and silently yields an empty attribution set. Reaching for `git show` therefore works or fails depending on how the repo merges, which is not a property of the commit in front of you; naming `^1` explicitly removes the question. See [`batch-merge-and-resolve`](../../shared/workflow/batch-merge-and-resolve.md), “A conflict your sweep found is not a conflict your merge caused” and “A stacked PR is the one conflict that intersection cannot attribute”.

3.  **Check claim status.** Read the most recent comment. If it says “Working on this — paws off” (or equivalent) and the claim is still live — a push or comment within the last 2 hours — skip it — another session owns it. An expired claim (over 2 idle hours) no longer blocks; take over with a fresh claim comment of your own, per [`claim-pr`](../../shared/workflow/claim-pr.md)’s expiration rule.

4.  **Claim it.**

    ``` bash
    gh pr comment <N> --body "Working on this — paws off until I'm done."   # COMMENT_PR
    ```

5.  **Create an isolated worktree**, fetch the latest `main` (the squash-merge commit that caused the conflict), and merge:

    ``` bash
    git fetch origin main <branch>   # FETCH — fetch both: we need the new main tip
    git worktree add .claude/worktrees/pr-<N> origin/<branch>
    cd .claude/worktrees/pr-<N>
    git checkout -b <branch>         # or --track origin/<branch> if the name is free
    git merge origin/main            # MERGE_BRANCH — picks up the new squash-merge commit
    ```

6.  **Resolve conflicts** using the `resolve-conflicts` skill (consolidate both sides’ intent; do not blindly pick one side wholesale).

7.  **Run the repo’s pre-commit checks, `git fetch` the branch again, then push.** The claim comment isn’t an atomic lock — a repo’s own automated bot (e.g. an `@claude` CI agent triggered independently by the same merge event) can pick up and resolve the identical cascade conflict in parallel even when no claim comment was posted. If the fetch shows the remote has moved with an **equivalent** fix already pushed, adopt it (verify with `git merge-tree --write-tree origin/main origin/<branch>` \[git ≥ 2.38\] — no remaining conflict — plus a content diff against what you were about to push) instead of force-pushing a duplicate merge commit. Only push your own resolution if the remote is still where you left it.

    ``` bash
    git fetch origin <branch>   # FETCH
    # If origin/<branch> already carries an equivalent fix, stop here — don't push.
    git diff HEAD origin/<branch>   # empty/equivalent means the bot beat you to it
    git push origin <branch>   # PUSH — only if the remote hasn't moved
    cd -
    git worktree remove .claude/worktrees/pr-<N>
    ```

8.  **Unclaim** with a brief resolution summary:

    ``` bash
    gh pr comment <N> --body "Conflict resolved — branch is now mergeable. <one-line summary of what conflicted and how it was resolved>"   # COMMENT_PR
    ```

Resolve PRs one at a time — not because worktrees race each other (each worktree is an independent checkout), but because the same human or bot may be actively working a PR between your claim and your push. One-at-a-time keeps the blast radius small. Skip any PR whose conflict is in a file you can’t understand without more context — comment asking for clarification instead.

**Match the response to standing, not only to cause.** Step 2 says whether a conflict is yours; it does not say the branch is. A conflict you genuinely caused, on a branch you do not own — a colleague’s in-flight work, and most sharply a release branch carrying an out-of-band process — is an explanatory comment naming the deletion or rename and where the content went, rather than a push to their branch. `sync-with-main` does prescribe re-applying the change on the sibling branch and pushing it, and that fits a workflow or CI file in a repo you drive. It is not the default for someone else’s release branch.

### 2. Tidy the local branch

``` bash
if [ "$(git branch --show-current)" != "main" ]; then
  git checkout main
fi
git fetch origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  git pull --ff-only origin main
fi
if git show-ref --verify --quiet "refs/heads/<merged-branch>"; then
  git branch -d <merged-branch>     # -d, NOT -D
fi
```

Use `git branch -d` (not `-D`): `-d` refuses to delete a branch with commits that aren’t merged. If it refuses, the branch has unmerged work — investigate before forcing anything.

**Both outcomes are normal after a squash merge — a `-d` that succeeds is not evidence the commits reached `main`.** The natural reading of the paragraph above is that `-d` succeeding means `main` contains the work, so a squash-merged branch must always need `-D`. It does not. `git-branch(1)` defines the check against the **upstream**, not `main`: the branch must be “fully merged in its upstream branch, or in HEAD if no upstream was set with `--track` or `--set-upstream-to`.” A branch still tracking a live `origin/<name>` is trivially fully merged into its own upstream, so `-d` succeeds and says so:

    warning: deleting branch 'fix/thing' that has been merged to
             'refs/remotes/origin/fix/thing', but not yet merged to HEAD.

Which branch of that behavior you land on depends on whether the remote ref still exists, and that varies by repo setting and merge flag. A repo that auto-deletes head branches on merge (or `gh pr merge --delete-branch`) leaves `[gone]` upstreams that fall back to the HEAD check and refuse. In one sweep of 29 branches, 18 deleted with `-d` and 11 needed `-D`; neither count meant anything about whether the work had landed.

Two consequences. Don’t treat a refusal as a surprise worth debugging — read step 1’s merge confirmation and the `-D` guidance below instead. And don’t treat a **success** as confirmation, either: when it prints that warning, `-d` checked the remote ref, not `main`.

These guards avoid a common no-op/error sequence after `gh pr merge --delete-branch`: that command may already switch this checkout to `main`, fast-forward it, and delete the local merged branch.

If the PR was built in a **git worktree** (agent isolation or `session-lock`), remove the worktree as part of the tidy — a worktree pins its branch, so `git branch -d` *refuses* while the worktree still holds it (“branch is checked out at ”). Remove it first, then delete the branch:

``` bash
git worktree list                 # find the merged branch's worktree path
git worktree remove <path>        # refuses on a dirty tree — don't blindly --force
git branch -d <merged-branch>     # now succeeds
```

**Worktree containing a submodule:** `git worktree remove <path>` refuses with `fatal: working trees containing submodules cannot be moved or removed` even when the tree is perfectly clean (`git status --short` empty) — this is a different refusal than the dirty-tree one above, triggered by the mere presence of a submodule, not by uncommitted state. Confirm clean with `git status --short` first (as always), then `git worktree remove --force <path>` is the correct move here, not a sign of misclassification.

**Running from within the worktree:** if post-merge fires while the shell is inside the worktree being tidied, `git worktree remove <path>` fails (“cannot remove the currently checked out worktree”) and `git checkout main` is blocked (worktrees are locked to their branch). Use the repo root instead:

``` bash
REPO="$(git rev-parse --git-common-dir)/.."             # main checkout root
git -C "$REPO" worktree remove "$(git rev-parse --show-toplevel)"   # worktree root
git -C "$REPO" branch -d <merged-branch>
```

**Stale is not diverged, and the two need opposite responses — check which one you have before applying the bullet below.** A blocked `git checkout main` reads as the diverged case, since the symptom is the same and diverged is the case this skill warns about. Stale is far commoner: local `main` is merely behind `origin/main` and **0 ahead**, carrying nobody’s work. Two counts separate the cases exactly, and the rule is three-way rather than two:

``` bash
git fetch origin main
echo "behind: $(git rev-list --count main..origin/main)  ahead: $(git rev-list --count origin/main..main)"
```

| `ahead` | `behind` | what it is      | what to do                                 |
|---------|----------|-----------------|--------------------------------------------|
| any     | 0        | nothing to pull | leave `main` alone; just delete the branch |
| 0       | \> 0     | **stale**       | fast-forward by refspec, below             |
| \> 0    | \> 0     | **diverged**    | the bullet below                           |

Both counts matter, so do not key the decision on `ahead` alone. `git pull --ff-only` fails only in the last row: with `behind: 0` it reports `Already up to date.` and exits 0 even when `ahead` is non-zero, so routing that row to the diverged bullet mislabels it (harmlessly — there is nothing to pull either way). The row that actually misleads is the middle one, where treating stale as diverged leaves `main` behind for no reason.

What blocks the switch in that case is usually an **unrelated dirty file** (a `renv.lock` an `renv::snapshot()` rewrote, a lockfile, a local config) whose content differs between the *stale* `main` and your branch’s HEAD, so git refuses to carry the local edit across. That file is frequently identical between HEAD and `origin/main`, so fast-forwarding first dissolves the conflict — and a branch that is not checked out can be fast-forwarded by refspec, touching no working tree:

``` bash
git fetch origin main:main    # fast-forwards the ref; refuses if not a fast-forward
git checkout main             # now carries the dirty file across untouched
```

The refspec form is safe by construction, refusing a non-fast-forward rather than clobbering, so it cannot destroy a genuinely diverged local `main`. Preserve the dirty file rather than stashing or discarding it — it is unrelated to this PR, and may be another session’s or the user’s.

- **Do:** read both counts before deciding, and fast-forward by refspec when `ahead` is 0 and `behind` is not.
- **Don’t:** treat a blocked checkout as evidence of divergence, or leave `main` stale because the bullet below said to skip the pull.
- **Don’t:** key the decision on `ahead` alone — `behind: 0` is not divergence, whatever `ahead` reads.

(`ucdavis/bcs#536`, 2026-08-02: `git checkout main` aborted on a modified `renv.lock`, which looked like the diverged case. Local `main` was 54 behind and 0 ahead, and the file was byte-identical between HEAD and `origin/main` — it differed only from the 54-commit-stale `main`. `git fetch origin main:main` fast-forwarded the ref and the switch then succeeded with the local edit intact; skipping the pull as the bullet below prescribes would have left `main` 54 commits behind.)

**Before `-D`, compare the LOCAL branch against the MERGED head — step 1 confirmed the PR merged, which is not the same claim.** The `-D` guidance below rests on step 1: the PR is merged, so forcing is safe. That reasoning covers the commit the PR *merged*, and `-D` deletes whatever the **local ref** points at, which can be a different commit.

The gap opens without anyone doing anything unusual. A `main`-merge pushed to the branch after the PR merged, a bot commit, or your own unpushed work all leave the local ref ahead of the merged head, and the `-d` refusal a squash repo produces is identical either way — so the refusal carries no information about which case you are in, and the natural next step is the `-D` the text below authorizes.

One comparison settles it, and it costs nothing:

``` bash
merged=$(gh pr view <N> --json headRefOid --jq .headRefOid)   # VIEW_PR
git fetch origin "refs/pull/<N>/head" -q                      # FETCH
git log --oneline "$merged".."<branch>"    # empty => the ref is the merged head
```

**That fetch is load-bearing, not tidiness, because the merged head is routinely absent from the local object store at exactly this moment, and comparing against `origin/main` succeeds and lies.** Two distinct failure modes occur when skipping this fetch:

1.  **The error direction (behind merged head):** `gh pr merge --delete-branch` removes the remote branch, and the merge commit on `main` is a *squash* in this repo, so neither `origin/main` nor any remaining ref reaches the PR’s own head. `git log` then answers with

        fatal: Invalid revision range <sha>..<branch>

    which is the shape [`fail-fast`](../../shared/principles/fail-fast.md) warns about: the check did not run, and it says so on stderr while printing no commits — so a caller reading only stdout sees the same empty output a clean comparison produces. `refs/pull/<N>/head` survives the branch deletion and is what makes the SHA resolvable again.

2.  **The succeed-and-lie direction (`origin/main..<branch>` comparison):** Comparing against `origin/main..<branch>` instead of `refs/pull/<N>/head` exits **0** and prints plausible commit output. Because a squash-merge creates a new commit on `main` with a different SHA and parentage, the branch’s original commits are not ancestors of `main` even though their diff is fully merged. `git log --oneline origin/main..<branch>` lists every commit from the merged PR, falsely suggesting unmerged work remains on the branch. Comparing against `refs/pull/<N>/head` (via `git log "$merged".."<branch>"`) settles it cleanly:

    ``` bash
    git fetch origin "refs/pull/<N>/head" -q &&
    git log --oneline "$merged".."<branch>"   # empty => all local work reached the PR
    ```

So read the exit status rather than the output, and always anchor the comparison to the PR’s fetched head ref rather than `origin/main`. A non-zero exit means the comparison failed to happen, which is not evidence the branch is safe to delete; re-fetch and re-run before touching `-D`.

A non-empty list is not automatically a problem — a merge commit whose every input is already on `main` is safe to discard — but it is a question, and it has to be answered before the delete rather than after. Read the subjects: anything authored, rather than a merge or a revert of already-landed work, means the branch carries something the PR did not.

- **Do:** compare the local ref against the PR’s fetched head (`refs/pull/<N>/head`) before `-D`, and read the extra commits’ subjects when they differ.
- **Do:** name the branch’s SHA in the report when it differed from the merged head, so the discrepancy is visible rather than absorbed.
- **Don’t:** read step 1’s merge confirmation as covering the local ref — it is a claim about the PR’s head, and `-D` acts on yours.
- **Don’t:** use `origin/main..<branch>` as a liveness test in a squash-merging repo — it exits 0 and falsely reports merged commits as unmerged work.
- **Don’t:** infer from a `-d` refusal which case you are in; a squash repo refuses for every branch regardless.
- **Don’t:** read an `Invalid revision range` error as an empty answer — it prints no commits, exactly as a clean comparison does, and means the merged head is simply not in the local object store.

(`Morrison-Lab/ai-config#1595`, 2026-08-17: running `git log --oneline origin/main..<branch>` immediately after squash-merging printed two commits that had already merged under squash commit `86cc8233`. Fetching `refs/pull/1595/head` confirmed `FETCH_HEAD..<branch>` was empty.)

(`Morrison-Lab/ai-config#1566`, 2026-08-17: the PR merged at head `0a297637`, and the local branch stood at `ad3b7640`, which `git branch -D` duly printed while deleting it. `git log 0a297637..ad3b7640` lists nine commits — a `main` merge plus eight commits from `main`, including the four merge commits for this session’s own PRs. Nothing authored, so nothing was lost; the point is that the check ran afterwards, prompted by reading the delete output, rather than before.)

(The fetch requirement was measured on the very next merge, `#1586`, which shipped the block above. Running it as written, immediately after `gh pr merge --squash --delete-branch`, produced `fatal: Invalid revision range d8e17de2...ums/verify-local-branch-before-force-delete` and exit 128 — the merged head was unreachable because the remote branch was gone and `main` carried only the squash. `git fetch origin refs/pull/1586/head` resolved it, and the re-run printed nothing, which is what actually licensed the `-D`. The local ref was *behind* the merged head rather than ahead, so the original block’s failure mode was not in play; the recipe still could not answer.)

**Diverged main checkout (`ahead` and `behind` both non-zero):** `git pull --ff-only` fails when the main checkout has local commits from a concurrent session that hasn’t been pushed. Don’t force-merge or reset their work — skip the pull and delete the branch only. The branch deletion is what matters; another session will pull main when it’s ready. If `git branch -d` refuses because local `main` doesn’t yet include the merge (diverged HEAD, remote branch already deleted), use `git branch -D` — step 1 already confirmed the PR is merged, so the force-delete is safe here.

For a repo-wide sweep of *all* dead worktrees (not just this PR’s), run `clean-worktrees` (`cw`).

If other local branches were **stacked** on this one, offer to rebase them onto the new `main` rather than deleting silently (see `cb` / `clean-branches`).

### 3. Confirm deferred items are tracked

If the PR’s review loop deferred or acknowledged anything, make sure each has a follow-up issue (preferences: *never leave deferred items untracked*). List them, linked. File any that slipped through.

### 3.5. Check whether delivery is gated on a further human action

In most repos the merge *is* the delivery, and this step is a no-op. In a repo whose artifact reaches consumers only through a separate, human-gated release step, the merge is the midpoint, and the gap between the two is a window in which the repo’s own documentation is wrong.

`Morrison-Lab/gha` is the case to recognize. A capability ships with `examples/<name>.yml` and `website/reference/<name>.qmd` stubs pinning `@v2`, but `@v2` moves only when someone dispatches `slide-major-tag.yml` — so a consumer who copies a stub literally between merge and slide gets `workflow-not-found`, per that repo’s own README. The same holds for any tag-, registry-, or release-gated artifact: a version bump merged but unpublished, a submodule pin not yet bumped in its consumer.

Two things make this the step that gets skipped rather than deferred. Nothing turns red — CI passed, the PR is green and merged, and the failure lands on a consumer who is not in the room. And the slide is destructive (it force-moves a tag), so it needs explicit human authorization and cannot simply be folded into the tidy, which is exactly why it evaporates instead: a step you are not allowed to perform is easy to stop tracking.

Decide it mechanically rather than from memory of what the PR touched — two lookups settle it, so this is an [`algorithmatize-checks`](../../shared/workflow/algorithmatize-checks.md) case:

``` bash
git fetch origin --tags
git rev-parse 'v2^{}' origin/main   # equal means current; different means a slide is owed
```

Keep the `^{}`. It peels a tag to the commit it names, and without it an **annotated** tag resolves to its own tag-object SHA instead — which never equals a commit SHA, so the check would report a slide owed on every run and become noise rather than an instrument. A lightweight tag resolves the same either way, so the peeled form is correct for both and there is no case where dropping it helps. (`slide-tag` reads a tag with `git log --oneline -1 <tag>`, which peels for the same reason.)

Then raise it as a `⚠️ FLAG` in step 5’s report, naming the tag and what is unreachable until it moves. An offer is not a flag: say plainly that the slide is owed and that it needs the human, the same way [`report-mistakes-proactively`](../../shared/workflow/report-mistakes-proactively.md) rules out offering to file an issue instead of filing it.

- **Do:** compare the release ref against `main` after the merge, and flag the gap with the specific tag and the affected consumer-facing paths.
- **Do:** run the comparison on every merge rather than first judging whether the repo looks release-gated — it costs two commands and prints nothing to act on when the SHAs match, so the comparison *is* the classifier.
- **Don’t:** run the release step yourself when it force-moves a ref or publishes — that is the human-gated action `ardi` reserves for explicit authorization.
- **Don’t:** report a merged PR wrapped up while the artifact it documents is still unreachable at the version its own docs name.

(gha#357, 2026-07-30: three new reusable workflows merged as `159dbf4` while `v2` still pointed at `c50e847`, so every `@v2` line in the new capabilities’ own stubs named a workflow that did not exist yet. Found only by an ad-hoc `rev-parse` at the end of the tidy, after steps 1 through 3 had already reported clean.)

### 3.75. Register a merged hook, since the gate that forbade it earlier names no later moment

If the merged PR touched `hooks/`, the merge did not arm anything. It placed a file and merged a manifest entry. On the non-plugin install path a hook fires only once `~/.claude/settings.json` binds it, and that binding is per-machine local state no merge can write.

This step exists because README’s activation gate creates a **deferred step with no owner**. “Never activate a new hook before its PR merges” is read by the author, before the PR is opened, and its matching action has to happen after the merge, on every consumer machine. Merging happens on GitHub, where nothing local prompts anything, so the owed registration is never refused and never scheduled — it simply never happens.

It shares its shape with step 3.5 above and differs in the half that decides what to do. Both are owed after a merge, and neither turns anything red. But 3.5’s action force-moves a shared ref, so it is reserved for the human, whereas this one writes one machine’s own settings file and is yours to perform now. Do not carry 3.5’s “don’t run it yourself” bullet over to this step; here that would leave the guard inert, which is the failure rather than the caution.

One lookup and two calls settle it, run in the ai-config checkout after step 3 has already put it on `main` and pulled:

``` bash
git show --name-only --format= HEAD -- hooks/   # did this merge bring in a hook?
python3 scripts/install-hooks.py                # report: registered / missing / stale
python3 scripts/install-hooks.py --fix          # the call that actually registers
```

**`--fix` is the load-bearing flag.** A bare `install-hooks.py` only reports, and says so itself (`Re-run with --fix to register the missing hooks.`), so a step that stops there leaves the guard exactly as inert as before — which is this step’s own failure mode, performed while looking like compliance.

The instrument is worth running on **any** ai-config merge rather than only one that touched `hooks/` — it costs one command, prints `All hooks registered.` when there is nothing to do, and catches every hook that merged while someone else was driving. The first lookup is informational and reads `HEAD` because a squash merge puts the merged content in one commit; it decides nothing, so do not skip the instrument when it comes back empty.

Then follow [`keep-checkouts-fresh`](../../shared/workflow/keep-checkouts-fresh.md) point 2, the `~/.claude` consumer copies, which already owns the mechanics: run `check-install.py --fix` first so the script is on disk before anything binds to it, check `enabledPlugins` before `--fix` since the plugin path already loads every hook and a second registration makes each one fire twice, compare the printed `examined N` against the current `hooks/hooks.json` before believing a clean report, and say that hooks connect at session start so a mid-session `--fix` arms nothing until a restart.

**A hook cannot be the instrument for this one**, which is worth stating so nobody builds it. A guard that detects unregistered hooks is itself a hook, so on the non-plugin path it is unregistered in exactly the case it exists to catch, and on the plugin path — where it would run — registration is not needed at all. The detector is silent precisely when the condition holds, which is [`fail-fast`](../../shared/principles/fail-fast.md)’s pass-path-equals-failure-path shape. That is why this is a step in a skill rather than an entry in `hooks/`.

- **Do:** run `install-hooks.py` as part of every ai-config post-merge sweep, and report the `registered`/`missing`/`stale` counts rather than a verdict.
- **Do:** register a hook whose PR just merged, since the gate’s prohibition expired at the merge and nothing else will do it.
- **Don’t:** read a merged hook as an active one — merging places a file, and only a binding makes it fire.
- **Don’t:** build a hook to detect this; it is unregistered exactly when the condition is true.

(Morrison-Lab/ai-config#1786, 2026-08-20: one machine reported `registered=15 missing=16 stale=0` against a 31-hook manifest. Among the sixteen inert guards was `flag-add-a-outside-pathspec.py`, and in the same session `git add -A ':!inst/extdata'` swept `SAS/program/` into a pushed `ucdavis/bcs` commit carrying a cleartext SAS credential and real `StudyID_c` values — the verbatim mistake that hook was written to prevent, and whose docstring describes that exact command. `--fix` registered the missing sixteen, and a fed-payload test then confirmed the guard fires on the command and names `SAS/` in its output. Every rule needed to prevent this was already written and had been for weeks; what was missing was a moment at which anyone would run the command.)

### 4. Run UMS — learn from the PR’s lifecycle

Run the full `ums` procedure (invoke the `ums` skill by name), focused on what **this PR** taught:

- **Recurring review findings** — anything the reviewer flagged across rounds → encode the fix so the next PR avoids it from the start.
- **Corrections / guidance the user gave mid-PR** → preference + skill update (per “update BOTH skills AND preferences”).
- **Tool / CI quirks** hit during the loop → the matching topical memory file under `memories/`, or `debugging.md`; see `memories/MEMORY.md` for the current set.
- **A multi-step pattern that emerged** → run `spot-skill-opportunities` to judge whether it’s genuinely recurring, then hand off to `skill-builder`.

This is the “learn from mistakes and guidance along the way” step — a merge is the natural checkpoint to bank those lessons before the context is gone. If nothing durable emerged, say so explicitly rather than manufacturing edits. (UMS commits its own changes via a branch + PR.)

**Guard against recursion: skip this step when the merged PR was itself a UMS/learnings PR — one whose diff is entirely memory/skill edits capturing a previous PR’s lessons — and no new lessons emerged from its own review loop.** Re-running UMS there is redundant — the lessons are already encoded in the PR that just merged — and spawns an endless UMS-on-UMS chain (each UMS PR merges → triggers post-merge → triggers another UMS PR). Still do steps 1–3 and 5; just don’t manufacture a fresh UMS PR. (If the UMS PR’s *own* review surfaced a genuinely new, separate lesson, capture that — but not a restatement of what the PR already banked. Concretely: a reviewer approving with no comments means nothing new, so skip; a reviewer flagging a missing anti-pattern that isn’t already in the UMS diff is a new lesson worth a follow-up.)

**The second clause is the operative one, and it is the one that goes unevaluated.** The first clause holds for every learnings PR, which is the only kind of PR this guard ever fires on, so it is satisfied before you have read the rest of the sentence. Evaluate the second clause explicitly, by an actual pass over the merged PR’s own review rounds, and emit the guard’s outcome as a sentence either way. “Skipped under the recursion guard; the review loop raised nothing that is not already in the diff” is a report. Silence is the failure, because it is indistinguishable from step 4 never having been reached. See [`skill-checklists`](../../shared/workflow/skill-checklists.md)’s “An item a guard exempts is neither run nor skipped”.

### 5. Report

**Pause point: before reporting the merge wrapped up.** Do-Confirm; per [`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md).

The merge actually landed (step 1’s verification, not the notification).

The local branch is tidied and `main` is fast-forwarded.

Every deferred item has a filed follow-up issue.

If the merge brought in a hook, step 3.75 ran `install-hooks.py --fix` and the counts are reported. The bare invocation only reports, so “I ran install-hooks” is not evidence that anything was registered.

**Killer item: step 4’s UMS pass actually executed**, or was deliberately skipped under the recursion guard and that is stated. Marked because reporting this skill complete asserts that its final step ran, and the recorded failure is a `post-merge` run reported done whose UMS step never happened — which discards the learnings rather than delaying them. Naming what UMS changed (or that nothing durable emerged) is the evidence; “ran UMS” on its own is not.

Then a linked summary: the merged PR, the auto-closed issue, any deferred follow-up issues, what UMS updated, and a Pacific-time timestamp (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces PT on a machine set to any other zone).

**Session stopping point signal:** When this post-merge wrap-up completes the session’s work **and no PR this session opened or pushed to remains unmerged** (typically after the UMS follow-up PR itself merges — note step 4 normally opens one), finish the report with an explicit stopping-point statement (e.g. *“This session is at a good stopping point.”*) per `wrap-up`’s closing checklist. If a UMS follow-up PR or another task remains open, state explicitly that the session is not at a clean stopping point and name what is open.

## Relationship to other skills

- **`wrap-up`** — session-level bookend; also embeds UMS. `post-merge` is the per-PR version: run it each time a PR lands; run `wrap-up` once at session end. They share the verify-then-UMS shape.
- **`ums`** — step 4 invokes it.
- **`spot-skill-opportunities`** — step 4’s “multi-step pattern that emerged” bullet routes here to judge recurrence before handing off to `skill-builder`.
- **`slide-tag`** – what step 3.5’s flag asks the human to authorize; it does the force-move, this skill only detects that one is owed.
- **`cb` / `clean-branches`** — for stacked or stale sibling branches.
- **`clean-worktrees` / `cw`** — if the PR was built in a git worktree, remove it during the tidy (step 2); a leftover worktree pins its branch and blocks `git branch -d`.
- **`st` / `gi`** — the front of the lifecycle that `post-merge` closes.

## Anti-patterns

- ❌ Deleting the branch before confirming the merge actually landed.
- ❌ Reaching for `git branch -D` (force) without checking why `-d` refused.
- ❌ Running `-D` without comparing the local ref against the PR’s merged head — step 1 confirms the PR merged, and `-D` deletes whatever your local branch points at, which can be a different commit.
- ❌ Force-pulling or resetting a diverged main checkout — the divergence may be another session’s in-progress work. Skip the pull; don’t clobber it.
- ❌ Skipping UMS on a normal PR — the just-merged PR is exactly when the lessons are freshest.
- ❌ Recursing UMS on a UMS PR — running UMS again when the just-merged PR was itself the learnings PR, restating lessons it already banked (see step 4’s guard). The chain has to terminate somewhere.
- ❌ Leaving deferred/acknowledged items without follow-up issues.
- ❌ Reporting a hook PR wrapped up without step 3.75’s `--fix` run – the hook is merged, documented, and inert, which is the deferred-step-with-no-owner shape this skill’s own step 3.75 exists to close, arriving one level up in the checklist meant to catch it.
- ❌ Calling a merge wrapped up in a release-gated repo without comparing the release ref against `main` (step 3.5) – the merged docs pin a version consumers cannot resolve until a human slides the tag.
- ❌ Reporting “all cleaned up” while a stacked sibling branch dangles unmentioned.
- ❌ Treating the whole cascade-scan hit list as work caused by this merge, without intersecting it against the merge’s own deleted and renamed paths (step 1.5’s own step 2) — on an old backlog that claims other people’s stale PRs for no reason.
- ❌ Pushing a resolution to a branch you don’t own when a comment would do — sharpest on a release branch, where a push can disrupt an out-of-band process.

Back to top
