---
name: post-merge
description: "Wrap up a just-merged PR/MR: verify the merge actually landed (never assume), tidy the local branch (switch to main, pull, delete the merged branch), confirm any deferred follow-up issues are tracked, flag a release step the merge left owed (a floating tag a human must still slide), then run UMS to capture what the PR's review lifecycle taught -- mistakes corrected and guidance given along the way. Use right after a PR merges, or when asked to 'post-merge', 'wrap up the merged PR', or 'clean up after the merge'. For the directive to actually perform the merge ('merge it' / 'merge this'), use the merge-it skill, which merges then chains into this one."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# post-merge — wrap up a merged PR (verify, tidy, then UMS)

The per-PR bookend to a piece of work. Once a PR/MR merges: confirm it landed,
clean up the local branch, make sure nothing was left dangling, and — the
point of the skill — **run UMS to learn from how the PR went** while the
review lifecycle is still fresh in context.

## When this fires

- A PR/MR you were working on just merged.
- "post-merge", "wrap up the merged PR", "clean up after the merge", "the PR
  merged — now what?"
- **"merge it" / "merge this" route to `merge-it`, not here** — that skill
  performs the merge first, then chains into this one. Only handle those phrases
  here when the PR is already merged (no merge left to do).
- Distinct from **`wrap-up`** (session-level, may span several PRs/issues) —
  `post-merge` is the single-PR version, run each time a PR lands.

## Procedure

### 1. Verify the merge — never assume

```bash
gh pr view <N> --json number,title,state,mergedAt,mergeCommit,headRefName   # VIEW_PR
# GitLab
glab mr view <N>
```

Confirm `state == MERGED` and `mergedAt` is set. If it isn't actually merged,
**stop and report** — don't tidy a branch whose work hasn't landed. (The
standing **never assume; always verify** rule applied to closing out a PR.)

### 1.25. Check for reviews that landed just before the merge

A review can post after your last processed round and before the human merges.
Those findings are real even though they are absent from the merge commit.
After confirming `mergedAt`,
identify the last review this session explicitly dispositioned,
then read every formal review and PR comment after that timestamp
and before `mergedAt`.
Do not use an imprecise "near the merge time" window.
The lower bound is the last dispositioned review,
and `mergedAt` is only the upper bound.

**When this session never dispositioned a review on this PR** --- entering
through the "the PR merged -- now what?" route, or picking up a PR another
session drove --- there is no last-dispositioned-review timestamp to anchor
on.
Don't skip the scan for lack of a lower bound.
Scan the complete review and comment history through `mergedAt` instead,
with no lower bound at all,
since anything on the PR is late from this session's point of view.

```bash
gh api repos/<owner>/<repo>/pulls/<N>/reviews --paginate    # formal review bodies
gh api repos/<owner>/<repo>/pulls/<N>/comments --paginate   # inline review comments
gh api repos/<owner>/<repo>/issues/<N>/comments --paginate  # top-level PR comments
```

A formal review's top-level body is not enough.
For each late review,
filter the inline comments by `pull_request_review_id`,
because an empty-body review can carry every finding inline.
This is the same two-surface shape `ardi` already requires when reading
formal reviews;
do not reimplement it as a body-only scan here.

**A finding can also arrive as a plain top-level PR comment rather than a
formal review** --- a bot posting a summary via `gh pr comment` (or the
equivalent API call) rather than through the reviews endpoint, or a human
commenting directly on the PR conversation.
`pulls/<N>/reviews` and `pulls/<N>/comments` are both scoped to formal
reviews and their inline threads; neither surface returns a plain PR
conversation comment.
Those live on the **issue comments** endpoint --- a pull request is also an
issue in GitHub's data model --- so the scan needs all three surfaces, not
two, to cover every place a late finding can land.

If a late review contains findings:

1. Confirm the merge commit does not contain the fix.
2. File or use a follow-up issue or PR, and carry the findings there with a link back to the merged PR.
3. Do not count the merged PR's review loop as clean for those findings; the new PR owns them.

- **Do:** check every review and PR comment posted after the last dispositioned review and before `mergedAt`.
- **Do:** fetch late formal reviews' inline comments, not only their top-level bodies.
- **Do:** fetch the issue-comments endpoint too, not just the two review surfaces --- a late finding can arrive as a plain top-level PR comment.
- **Do:** carry late findings forward to a new tracked fix when the merge beat the ARD round.
- **Don't:** use a vague "near merge time" window that can skip a late finding posted well before a delayed merge.
- **Don't:** treat the merge as proof the final review round was clean.
- **Don't:** drop a finding because it arrived too late for the merged branch.
- **Don't:** skip this scan because no last-dispositioned-review timestamp exists --- scan the whole history through `mergedAt` instead.
- **Don't:** stop at the two formal-review surfaces --- a bot or human can post a late finding as a plain issue comment that neither one returns.

(Morrison-Lab/ai-config#1029:
Copilot round 7 posted at 2026-08-02T06:29:10Z,
and the PR merged at 06:30:55Z as `1e0b5fdf`.
The suppressed findings were real,
absent from the merged code,
and had to be carried forward to #1034.)

### 1.5. Cascade conflict scan

**In an ultracode/coordinator session, delegate this whole step to a
subagent** rather than running the scan-and-resolve loop in the main thread
--- it's exactly the kind of investigation-plus-fix work the coordinator
should hand off (see `memories/preferences.md`'s coordinator-mode bullet).
Brief the subagent with the merged PR's number/branch and the steps below;
have it report back which PRs it found conflicting, what it did about each,
and any it skipped (already claimed, conflict it couldn't understand). Do the
scan inline only for a solo (non-orchestrated) session.

**If any OTHER agents already own a claimed branch (an active, resumable
`Agent`-tool session, not a one-shot `Workflow`-internal `agent()` call),
message each one directly right after the merge, instead of relying solely on
a separate scan to find and fix their conflict after the fact:** "main just
advanced (PR #N merged) --- fetch and merge origin/main into your branch now,
resolve any conflict yourself (you have the context on your own change), then
continue." This is faster and higher-context than a scanning subagent
guessing at the resolution from outside: the branch's own owning agent
already knows why its code looks the way it does.

**This depends on the coordinator finding out about a merge in the first
place --- so brief every delegated agent, up front, to report back the
instant its OWN tracked PR merges, not just when its ARDI work is done.**
A PR sitting "ready for merge" isn't the end of that agent's watch: keep
polling until the merge actually happens --- by a human, since the agent
itself must not self-merge --- then notify the coordinator immediately. This
is what lets the coordinator fan out the "merge main now" nudge above to
every OTHER live agent right when it matters, instead of the coordinator
having to separately poll every open PR's merge state itself to notice. Fold
this into the standard delegation brief (see `gia`/`gii`'s per-issue agent
prompts) alongside the no-self-merge instruction, rather than treating it as
a one-off ask.

Reserve the scan-and-fix
subagent above for branches with NO active owning agent (e.g. a completed
`Workflow` run's one-shot agent that already returned).

A squash-merge on `main` can knock previously-mergeable open PRs into conflict.
Scan right after the merge is confirmed:

```bash
gh pr list --state open \
  --json number,title,headRefName,mergeable,mergeStateStatus,comments   # LIST_PRS
```

For each PR where `mergeable == "CONFLICTING"` **or `"UNKNOWN"`** (GitHub can
take minutes to finish computing mergeability after a push — a genuinely
conflicting PR can sit in `UNKNOWN` and get missed if you filter for
`CONFLICTING` alone):

1. **Verify before claiming — don't trust the flag alone.** See
   `resolve-conflicts`, "Verify before you act": `git merge-tree --write-tree
   origin/main origin/<branch>` gives ground truth without a worktree
   (git ≥ 2.38). Skip if it comes back clean.
2. **Check claim status.** Read the most recent comment. If it says "Working on
   this — paws off" (or equivalent), skip it — another session owns it.
3. **Claim it.**
   ```bash
   gh pr comment <N> --body "Working on this — paws off until I'm done."   # COMMENT_PR
   ```
4. **Create an isolated worktree**, fetch the latest `main` (the squash-merge
   commit that caused the conflict), and merge:
   ```bash
   git fetch origin main <branch>   # FETCH — fetch both: we need the new main tip
   git worktree add .claude/worktrees/pr-<N> origin/<branch>
   cd .claude/worktrees/pr-<N>
   git checkout -b <branch>         # or --track origin/<branch> if the name is free
   git merge origin/main            # MERGE_BRANCH — picks up the new squash-merge commit
   ```
5. **Resolve conflicts** using the `resolve-conflicts` skill (consolidate both
   sides' intent; do not blindly pick one side wholesale).
6. **Run the repo's pre-commit checks, `git fetch` the branch again, then push.**
   The claim comment isn't an atomic lock — a repo's own automated bot (e.g. an
   `@claude` CI agent triggered independently by the same merge event) can pick up
   and resolve the identical cascade conflict in parallel even when no claim
   comment was posted. If the fetch shows the remote has moved with an
   **equivalent** fix already pushed, adopt it (verify with `git merge-tree
   --write-tree origin/main origin/<branch>` [git ≥ 2.38] — no remaining conflict — plus a
   content diff against what you were about to push) instead of force-pushing
   a duplicate merge commit. Only push your own resolution if the remote is
   still where you left it.
   ```bash
   git fetch origin <branch>   # FETCH
   # If origin/<branch> already carries an equivalent fix, stop here — don't push.
   git diff HEAD origin/<branch>   # empty/equivalent means the bot beat you to it
   git push origin <branch>   # PUSH — only if the remote hasn't moved
   cd -
   git worktree remove .claude/worktrees/pr-<N>
   ```
7. **Unclaim** with a brief resolution summary:
   ```bash
   gh pr comment <N> --body "Conflict resolved — branch is now mergeable. <one-line summary of what conflicted and how it was resolved>"   # COMMENT_PR
   ```

Resolve PRs one at a time — not because worktrees race each other (each
worktree is an independent checkout), but because the same human or bot may be
actively working a PR between your claim and your push. One-at-a-time keeps
the blast radius small. Skip any PR whose conflict is in a file you can't
understand without more context — comment asking for clarification instead.

### 2. Tidy the local branch

```bash
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

Use `git branch -d` (not `-D`): `-d` refuses to delete a branch with commits
that aren't merged. If it refuses, the branch has unmerged work — investigate
before forcing anything.

**Both outcomes are normal after a squash merge --- a `-d` that succeeds is not
evidence the commits reached `main`.**
The natural reading of the paragraph above is that `-d` succeeding means `main`
contains the work, so a squash-merged branch must always need `-D`.
It does not.
`git-branch(1)` defines the check against the **upstream**, not `main`:
the branch must be "fully merged in its upstream branch, or in HEAD if no
upstream was set with `--track` or `--set-upstream-to`."
A branch still tracking a live `origin/<name>` is trivially fully merged into
its own upstream, so `-d` succeeds and says so:

```
warning: deleting branch 'fix/thing' that has been merged to
         'refs/remotes/origin/fix/thing', but not yet merged to HEAD.
```

Which branch of that behavior you land on depends on whether the remote ref
still exists, and that varies by repo setting and merge flag.
A repo that auto-deletes head branches on merge (or `gh pr merge
--delete-branch`) leaves `[gone]` upstreams that fall back to the HEAD check
and refuse.
In one sweep of 29 branches, 18 deleted with `-d` and 11 needed `-D`;
neither count meant anything about whether the work had landed.

Two consequences.
Don't treat a refusal as a surprise worth debugging --- read step 1's merge
confirmation and the `-D` guidance below instead.
And don't treat a **success** as confirmation, either:
when it prints that warning, `-d` checked the remote ref, not `main`.

These guards avoid a common no-op/error sequence after
`gh pr merge --delete-branch`: that command may already switch this checkout
to `main`, fast-forward it, and delete the local merged branch.

If the PR was built in a **git worktree** (agent isolation or `session-lock`),
remove the worktree as part of the tidy — a worktree pins its branch, so
`git branch -d` *refuses* while the worktree still holds it ("branch is checked
out at <path>"). Remove it first, then delete the branch:

```bash
git worktree list                 # find the merged branch's worktree path
git worktree remove <path>        # refuses on a dirty tree — don't blindly --force
git branch -d <merged-branch>     # now succeeds
```

**Worktree containing a submodule:** `git worktree remove <path>` refuses with
`fatal: working trees containing submodules cannot be moved or removed` even
when the tree is perfectly clean (`git status --short` empty) — this is a
different refusal than the dirty-tree one above, triggered by the mere
presence of a submodule, not by uncommitted state. Confirm clean with
`git status --short` first (as always), then `git worktree remove --force
<path>` is the correct move here, not a sign of misclassification.

**Running from within the worktree:** if post-merge fires while the shell is
inside the worktree being tidied, `git worktree remove <path>` fails ("cannot
remove the currently checked out worktree") and `git checkout main` is blocked
(worktrees are locked to their branch). Use the repo root instead:

```bash
REPO="$(git rev-parse --git-common-dir)/.."             # main checkout root
git -C "$REPO" worktree remove "$(git rev-parse --show-toplevel)"   # worktree root
git -C "$REPO" branch -d <merged-branch>
```

**Stale is not diverged, and the two need opposite responses --- check which
one you have before applying the bullet below.**
A blocked `git checkout main` reads as the diverged case, since the symptom is
the same and diverged is the case this skill warns about.
Stale is far commoner: local `main` is merely behind `origin/main` and **0
ahead**, carrying nobody's work.
Two counts separate the cases exactly, and the rule is three-way rather than
two:

```bash
git fetch origin main
echo "behind: $(git rev-list --count main..origin/main)  ahead: $(git rev-list --count origin/main..main)"
```

| `ahead` | `behind` | what it is | what to do |
|---|---|---|---|
| any | 0 | nothing to pull | leave `main` alone; just delete the branch |
| 0 | > 0 | **stale** | fast-forward by refspec, below |
| > 0 | > 0 | **diverged** | the bullet below |

Both counts matter, so do not key the decision on `ahead` alone.
`git pull --ff-only` fails only in the last row: with `behind: 0` it reports
`Already up to date.` and exits 0 even when `ahead` is non-zero, so routing
that row to the diverged bullet mislabels it (harmlessly --- there is nothing
to pull either way).
The row that actually misleads is the middle one, where treating stale as
diverged leaves `main` behind for no reason.

What blocks the switch in that case is usually an **unrelated dirty file**
(a `renv.lock` an `renv::snapshot()` rewrote, a lockfile, a local config)
whose content differs between the *stale* `main` and your branch's HEAD, so
git refuses to carry the local edit across.
That file is frequently identical between HEAD and `origin/main`, so
fast-forwarding first dissolves the conflict --- and a branch that is not
checked out can be fast-forwarded by refspec, touching no working tree:

```bash
git fetch origin main:main    # fast-forwards the ref; refuses if not a fast-forward
git checkout main             # now carries the dirty file across untouched
```

The refspec form is safe by construction, refusing a non-fast-forward rather
than clobbering, so it cannot destroy a genuinely diverged local `main`.
Preserve the dirty file rather than stashing or discarding it --- it is
unrelated to this PR, and may be another session's or the user's.

- **Do:** read both counts before deciding, and fast-forward by refspec when
  `ahead` is 0 and `behind` is not.
- **Don't:** treat a blocked checkout as evidence of divergence, or leave
  `main` stale because the bullet below said to skip the pull.
- **Don't:** key the decision on `ahead` alone --- `behind: 0` is not
  divergence, whatever `ahead` reads.

(`ucdavis/bcs#536`, 2026-08-02: `git checkout main` aborted on a modified
`renv.lock`, which looked like the diverged case.
Local `main` was 54 behind and 0 ahead, and the file was byte-identical
between HEAD and `origin/main` --- it differed only from the 54-commit-stale
`main`.
`git fetch origin main:main` fast-forwarded the ref and the switch then
succeeded with the local edit intact; skipping the pull as the bullet below
prescribes would have left `main` 54 commits behind.)

**Diverged main checkout (`ahead` and `behind` both non-zero):**
`git pull --ff-only` fails when the main checkout
has local commits from a concurrent session that hasn't been pushed. Don't
force-merge or reset their work — skip the pull and delete the branch only.
The branch deletion is what matters; another session will pull main when it's
ready. If `git branch -d` refuses because local `main` doesn't yet include
the merge (diverged HEAD, remote branch already deleted), use `git branch -D` —
step 1 already confirmed the PR is merged, so the force-delete is safe here.

For a repo-wide sweep of *all* dead worktrees (not just this PR's), run
`clean-worktrees` (`cw`).

If other local branches were **stacked** on this one, offer to rebase them onto
the new `main` rather than deleting silently (see `cb` / `clean-branches`).

### 3. Confirm deferred items are tracked

If the PR's review loop deferred or acknowledged anything, make sure each has a
follow-up issue (preferences: *never leave deferred items untracked*). List
them, linked. File any that slipped through.

### 3.5. Check whether delivery is gated on a further human action

In most repos the merge *is* the delivery, and this step is a no-op.
In a repo whose artifact reaches consumers only through a separate,
human-gated release step, the merge is the midpoint, and the gap between the
two is a window in which the repo's own documentation is wrong.

`Morrison-Lab/gha` is the case to recognize.
A capability ships with `examples/<name>.yml` and
`website/reference/<name>.qmd` stubs pinning `@v2`, but `@v2` moves only when
someone dispatches `slide-major-tag.yml` --- so a consumer who copies a stub
literally between merge and slide gets `workflow-not-found`, per that repo's
own README.
The same holds for any tag-, registry-, or release-gated artifact: a version
bump merged but unpublished, a submodule pin not yet bumped in its consumer.

Two things make this the step that gets skipped rather than deferred.
Nothing turns red --- CI passed, the PR is green and merged, and the failure
lands on a consumer who is not in the room.
And the slide is destructive (it force-moves a tag), so it needs explicit
human authorization and cannot simply be folded into the tidy, which is
exactly why it evaporates instead: a step you are not allowed to perform is
easy to stop tracking.

Decide it mechanically rather than from memory of what the PR touched --- two
lookups settle it, so this is an
[`algorithmatize-checks`](../../shared/workflow/algorithmatize-checks.md)
case:

```bash
git fetch origin --tags
git rev-parse 'v2^{}' origin/main   # equal means current; different means a slide is owed
```

Keep the `^{}`.
It peels a tag to the commit it names, and without it an **annotated** tag
resolves to its own tag-object SHA instead --- which never equals a commit
SHA, so the check would report a slide owed on every run and become noise
rather than an instrument.
A lightweight tag resolves the same either way, so the peeled form is correct
for both and there is no case where dropping it helps.
(`slide-tag` reads a tag with `git log --oneline -1 <tag>`, which peels for
the same reason.)

Then raise it as a `⚠️ FLAG` in step 5's report, naming the tag and what is
unreachable until it moves.
An offer is not a flag: say plainly that the slide is owed and that it needs
the human, the same way
[`report-mistakes-proactively`](../../shared/workflow/report-mistakes-proactively.md)
rules out offering to file an issue instead of filing it.

- **Do:** compare the release ref against `main` after the merge, and flag the
  gap with the specific tag and the affected consumer-facing paths.
- **Do:** run the comparison on every merge rather than first judging whether
  the repo looks release-gated --- it costs two commands and prints nothing to
  act on when the SHAs match, so the comparison *is* the classifier.
- **Don't:** run the release step yourself when it force-moves a ref or
  publishes --- that is the human-gated action `ardi` reserves for explicit
  authorization.
- **Don't:** report a merged PR wrapped up while the artifact it documents is
  still unreachable at the version its own docs name.

(gha#357, 2026-07-30: three new reusable workflows merged as `159dbf4` while
`v2` still pointed at `c50e847`, so every `@v2` line in the new capabilities'
own stubs named a workflow that did not exist yet.
Found only by an ad-hoc `rev-parse` at the end of the tidy, after steps 1
through 3 had already reported clean.)

### 4. Run UMS — learn from the PR's lifecycle

Run the full `ums` procedure (invoke the `ums` skill by name), focused on what
**this PR** taught:

- **Recurring review findings** — anything the reviewer flagged across rounds
  → encode the fix so the next PR avoids it from the start.
- **Corrections / guidance the user gave mid-PR** → preference + skill update
  (per "update BOTH skills AND preferences").
- **Tool / CI quirks** hit during the loop → the matching topical memory file
  under `memories/`, or `debugging.md`; see `memories/MEMORY.md` for the
  current set.
- **A multi-step pattern that emerged** → run `spot-skill-opportunities` to
  judge whether it's genuinely recurring, then hand off to `skill-builder`.

This is the "learn from mistakes and guidance along the way" step — a merge is
the natural checkpoint to bank those lessons before the context is gone. If
nothing durable emerged, say so explicitly rather than manufacturing edits.
(UMS commits its own changes via a branch + PR.)

**Guard against recursion: skip this step when the merged PR was itself a
UMS/learnings PR — one whose diff is entirely memory/skill edits capturing a
previous PR's lessons — and no new lessons emerged from its own review loop.**
Re-running UMS there is redundant — the lessons are already encoded in the PR
that just merged — and spawns an endless UMS-on-UMS chain (each UMS PR merges →
triggers post-merge → triggers another UMS PR). Still do steps 1–3 and 5; just don't
manufacture a fresh UMS PR. (If the UMS PR's *own* review surfaced a genuinely
new, separate lesson, capture that — but not a restatement of what the PR
already banked. Concretely: a reviewer approving with no comments means nothing
new, so skip; a reviewer flagging a missing anti-pattern that isn't already in
the UMS diff is a new lesson worth a follow-up.)

### 5. Report

**Pause point: before reporting the merge wrapped up.**
Do-Confirm; per
[`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md).

- [ ] The merge actually landed (step 1's verification, not the notification).
- [ ] The local branch is tidied and `main` is fast-forwarded.
- [ ] Every deferred item has a filed follow-up issue.
- [ ] **Killer item: step 4's UMS pass actually executed**, or was
      deliberately skipped under the recursion guard and that is stated.
      Marked because reporting this skill complete asserts that its final step
      ran, and the recorded failure is a `post-merge` run reported done whose
      UMS step never happened --- which discards the learnings rather than
      delaying them.
      Naming what UMS changed (or that nothing durable emerged) is the
      evidence; "ran UMS" on its own is not.

Then a linked summary: the merged PR, the auto-closed issue, any deferred
follow-up issues, what UMS updated, and a Pacific-time timestamp
(`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces
PT on a machine set to any other zone).

## Relationship to other skills

- **`wrap-up`** — session-level bookend; also embeds UMS. `post-merge` is the
  per-PR version: run it each time a PR lands; run `wrap-up` once at session
  end. They share the verify-then-UMS shape.
- **`ums`** — step 4 invokes it.
- **`spot-skill-opportunities`** — step 4's "multi-step pattern that emerged"
  bullet routes here to judge recurrence before handing off to `skill-builder`.
- **`slide-tag`** -- what step 3.5's flag asks the human to authorize; it does
  the force-move, this skill only detects that one is owed.
- **`cb` / `clean-branches`** — for stacked or stale sibling branches.
- **`clean-worktrees` / `cw`** — if the PR was built in a git worktree, remove
  it during the tidy (step 2); a leftover worktree pins its branch and blocks
  `git branch -d`.
- **`st` / `gi`** — the front of the lifecycle that `post-merge` closes.

## Anti-patterns

- ❌ Deleting the branch before confirming the merge actually landed.
- ❌ Reaching for `git branch -D` (force) without checking why `-d` refused.
- ❌ Force-pulling or resetting a diverged main checkout — the divergence may be another session's in-progress work. Skip the pull; don't clobber it.
- ❌ Skipping UMS on a normal PR — the just-merged PR is exactly when the
  lessons are freshest.
- ❌ Recursing UMS on a UMS PR — running UMS again when the just-merged PR was
  itself the learnings PR, restating lessons it already banked (see step 4's
  guard). The chain has to terminate somewhere.
- ❌ Leaving deferred/acknowledged items without follow-up issues.
- ❌ Calling a merge wrapped up in a release-gated repo without comparing the
  release ref against `main` (step 3.5) -- the merged docs pin a version
  consumers cannot resolve until a human slides the tag.
- ❌ Reporting "all cleaned up" while a stacked sibling branch dangles unmentioned.
