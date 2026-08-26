The Claude Code on the web harness injects a "Git Development Branch Requirements" section that assigns a session-unique branch name (e.g. `claude/abc123`) as the default for each repo.
**That branch is a fallback for brand-new work with no existing PR.**

When a task involves an existing PR or branch, work on that PR's branch instead:

1. Find the branch name: call `mcp__github__pull_request_read` (`method: get`) or (in CLI sessions) `gh pr view <N> --json headRefName -q .headRefName`.
2. Check it out or create a worktree from `origin/<branch>`.
3. Push back to that branch and update the existing PR --- do not open a new one.

Use the harness-specified branch only when starting work with no existing PR and no existing branch to continue.

**Treat a PR-preview URL as an explicit PR target.**
If the user points to a page under a path like
`.../pr-preview/pr-436/...`,
interpret that as "work on PR #436" by default:
check out that PR's branch,
push updates to it,
and update that same PR.
Do not open a separate PR unless the user explicitly asks for one.

**Exception --- the session can only push to its own branch.**
Some web/remote sessions are scoped so the agent proxy allows pushing *only* to the harness-assigned branch;
a push to any other branch (the existing PR's branch included) is rejected with `HTTP 403`.
When that happens you cannot follow step 3.
Don't retry the 403 --- it's a policy denial, not a transient error.

**Prefer stacking the fix, not superseding the PR.**
When the work is an incremental fix to an existing, still-open PR (a review finding, a small addition) rather than a full rebuild, push the fix to the assigned branch and open it as a PR **stacked on** the original --- `base` set to the original PR's own branch, per the [`stack-prs`](../../skills/stack-prs/SKILL.md) skill --- rather than superseding it.
Comment on the original PR pointing to the stacked one, and note the dependency ("stacked on this branch --- either merge #N into this branch first, or merge this PR and #N will retarget to `main`").
This keeps the diff to just the incremental change instead of re-litigating the whole original PR's content, and it composes correctly regardless of how the maintainer merges it: they can merge the stacked PR straight into the original's branch (folding the fix in before the original PR itself merges) or merge the original first and let the stacked PR retarget to `main` per that skill's step 4.
Reserve the supersede path (below) for when stacking doesn't fit --- the original branch/PR is abandoned, or the fix amounts to a full rebuild rather than an incremental addition.

**A plain `git merge --ff-only` plus push is a second way to fold a stacked PR
into its base, alongside GitHub's own merge button --- and GitHub notices
either way.**
When the stacked PR's branch is a strict superset of its base
(confirm with `git merge-base --is-ancestor <base-tip> <stacked-tip>`),
merging the stacked branch into the base branch locally with `--ff-only` and
pushing moves only a ref, with no new commit created.
GitHub still detects that the stacked PR's head commit is now reachable from
its base, and closes that PR as **merged** on its own, deleting its head
branch if the repo auto-deletes on merge.
This is the same outcome the paragraph above describes for GitHub's merge
button, reached by a different door.

**This is still a merge, bound by the Strict Merge Control Policy below** ---
the same explicit-permission requirement that gates clicking the merge button
applies here too, since the effect on the stacked PR is identical.
Never run this to close a PR on your own initiative.
It also only applies when the base genuinely is another open PR's branch, not
`main` --- the adjacent fact above, that a squash-merged base PR makes GitHub
auto-retarget the stacked PR to `main`, means "its base" can silently become
`main` once the original PR merges.
Fast-forwarding straight into `main` this way would push unreviewed commits
to the default branch, bypassing PR review and required checks entirely.

Verify the superset relationship before relying on this, and prefer
`--ff-only` specifically --- it refuses outright, rather than silently
creating a new, unreviewed merge commit on the base branch, if the two
branches have actually diverged.
Confirm the auto-close afterward with `gh pr view <stacked-N> --json
state,mergeCommit`; a `state: MERGED` with `mergeCommit.oid` equal to the
commit you just pushed confirms the fast-forward was picked up.
(`UCD-SERG/serocalculator#547` -> `#545`, 2026-08-08: `git merge
origin/claude/pr-545-fix-h4gclq --ff-only` in `#545`'s worktree, followed by a
push, left both branches at commit `6a6f83c0d`; GitHub closed `#547` as merged
and deleted its head branch within the same push --- done with the user's
explicit go-ahead on the underlying architectural decision.)

**Supersede fallback, when stacking doesn't apply:** push the fix to the assigned branch, open a **new** PR off `main` that supersedes the original (say "Supersedes #N" in the body and rebuild as a single clean commit so no sensitive history leaks through), comment on the original PR pointing to the replacement, and close the original once the new PR merges.

**Rebuilding the single clean commit: diff against `main`, don't cherry-pick from the write-protected branch.**
`main` usually doesn't yet contain the original PR's changes, so cherry-picking just your incremental fix commit conflicts --- it was written against the PR branch's state, not `main`'s.
Instead, diff the whole file set and apply it fresh:
```bash
git diff origin/main <old-branch> -- <changed-files> > /tmp/rebuild.diff
git checkout -B <assigned-branch> origin/main
git apply /tmp/rebuild.diff
git add <changed-files> && git commit -m "..." && git push -u origin <assigned-branch>
```
(Seen on ai-config#372 → #380: the assigned branch could push, `sync-freshness-rule` could not.)

**Check whether the branch's own PR merged before adding more commits to it.**
If a PR on this branch merged via **squash** (common in repos that enforce it), the branch's old commits are no longer ancestors of `main`'s new tip --- `git merge-base --is-ancestor <old-commit> origin/main` returns false.
Committing follow-up work on top of that stale branch and pushing looks fine locally, but the resulting PR's diff shows the *entire prior PR's changes again* against `main`, confusing reviewers and re-litigating already-merged content.
Before adding commits to a branch you didn't just create, fetch `origin/main` and check ancestry first.
If the branch's own PR already merged, don't build on top of it --- start clean: `git checkout -b <branch> origin/main`, then `git cherry-pick` only the genuinely new commit(s).
If you've already pushed a bloated diff, the same fix applies retroactively: rebuild the branch from `origin/main` plus a cherry-pick of the new work, then `git push --force-with-lease`. (Seen on gha#161 → gha#162 and ai-config#344 → ai-config#354, both squash-merged.)

**A stacked PR reaches that bloated state with no push of yours at all, and it announces itself as a merge conflict.**
The preventable half of this sits on the other party, in
[`batch-merge-and-resolve`](batch-merge-and-resolve.md)'s "A stacked PR is the
one conflict that intersection cannot attribute" section --- run
`gh pr list --base <branch>` before merging *anything*, since a plain squash
orphans a dependent with no deletion or rename for an attribution sweep to
find.
This section is what the dependent's own session does once that did not
happen.
The rule above is written around an action you take: you add commits to a stale branch, so the check fires when you are about to commit.
A PR stacked on another PR's branch needs nothing from you.
When the base PR squash-merges, GitHub **auto-retargets** the stacked PR to `main`.
The same orphaning then happens retroactively, to a branch that has been sitting untouched.

What makes it worth its own entry is the symptom.
The bloat presents as `mergeable_state: dirty` --- a conflict --- which invites conflict resolution.
Resolving those conflicts would mean re-litigating already-merged content line by line.
The diff and commit count are the tell that it is not a real conflict:

| | before the base merged | after |
| --- | --- | --- |
| `mergeable_state` | `clean` | `dirty` |
| diff | `+82/-0` | `+122/-0` |
| commits | 2 | 9 |

So when a stacked PR goes dirty, check ancestry before touching the conflicts.
`git merge-base --is-ancestor <base-PR-commit> origin/main` returning false means the base squash-merged, and the fix is the rebuild above rather than a merge.
Confirm the base PR's content is genuinely on `main` first, since that is what makes discarding those commits safe.
Normalize whitespace and backticks when you check (`git show origin/main:<path>`), because this corpus breaks lines mid-phrase.

**A live variant of the same check: the human can merge the branch's PR out from under an in-flight push, not just leave a stale branch to discover later.**
Pushing a commit right as its own PR merges lands in a race in repos that auto-delete head branches on merge: GitHub deletes the head branch, and the in-flight push silently recreates it under the same name --- but now as a brand-new, orphaned branch with no PR, built on top of commits that (for a real merge commit, unlike the squash case above) *are* ancestors of `main`'s new tip.
`git status`/`git push` report success --- but the push is not quite silent, and its one tell is worth knowing, because it fires at the moment of the race rather than hours later.
A push onto a branch that still exists prints a SHA range (`f7bf71f..899e5de <branch> -> <branch>`);
a push that *recreates* a deleted branch prints `* [new branch] <branch> -> <branch>` instead.
Seeing `* [new branch]` for a branch you have already been pushing to means the remote branch was deleted underneath you, which on a PR branch means the PR merged.
Read the push output rather than only its exit status, and run the ancestry check immediately when that line appears.
Recovery is the same ancestry check as above (`git merge-base --is-ancestor <branch-tip> origin/main`), then cherry-pick the orphaned commit onto a fresh branch off the new `origin/main`;
note that this check's *answer* depends on the repo's merge strategy and so is not itself the signal --- it comes back true where the PR merged as a real merge commit (the serocalculator case in [`CLAUDE.cases.md`](../../CLAUDE.cases.md)) and false in a squash-merge repo, where `main` carries a new single commit your branch never saw.
Either answer leaves the recovery the same, and in the squash case the orphaned commit is genuinely absent from `main`, so check whether its content actually landed (`git show origin/main:<path> | grep`) rather than inferring it from the merge notification;
delete the stray local and (if push-permitted) remote branch.
If the orphaned commit is genuinely new work --- not a fix that belongs in the now-merged PR --- treat this as the natural start of a new, stacked issue + PR rather than trying to reopen or append to the merged one.

**That tell's precondition is a repo setting, so check the setting rather than
assuming it in either direction --- and a branch that still resolves after your
own late push cannot tell you what the setting is.**
The paragraph above names its precondition, "in repos that auto-delete head
branches on merge", and never says how to find out whether it holds.
Here it holds.
`Morrison-Lab/ai-config` does delete merged head branches, so the tell was
available and the push that followed the merge did print it.
What failed was not the signal.

The evidence that looks like it settles the question is the one that cannot.
After a late push to an already-merged PR's branch, `git ls-remote` resolves
that branch under both hypotheses: the branch was never deleted, or it was
deleted at merge and your own push recreated it.
Both end with the branch present at the pushed commit, so a resolving ref is a
true observation that answers neither hypothesis, and reading it as "this repo
keeps merged head branches" reads a settled fact out of evidence that does not
discriminate.

Two checks do discriminate, and both are cheap.
Other merged PRs' head branches, which no late push has touched, either resolve
or do not.
And the PR's own timeline records the deletion in as many words, since GitHub
logs an auto-delete the same way it logs a manual one.

What is genuinely narrower here than in the paragraph above is the **trigger**,
not the tell.
There the push is concurrent with the merge, so the race is the thing you are
already watching for.
Here minutes had passed and the PR's state had not been re-read since the
review, so nothing prompted a look at the push output at all.
The "Check whether the branch's own PR merged before adding more commits to it"
rule earlier in this section has the same gap: "a branch you didn't just
create" reads as inapplicable on a branch you have been driving continuously
all session, which is exactly the branch this happens on.

Do not reach for that rule's ancestry check as the alternative, though.
This repo squash-merges, and `git merge-base --is-ancestor <branch-tip>
origin/main` returns non-ancestor for an **open** PR's branch too, whose
commits do not reach `main` until the squash.
Measured both ways: the orphaned commit below and this entry's own branch while
its PR was open each came back non-ancestor.
So the check cannot separate "still open" from "just merged", which is the
paragraph above's own warning that its answer depends on the merge strategy and
so is not itself the signal.
Re-reading the PR's `merged` field and `head.sha` is what discriminates.

What the failure costs is a claim rather than a commit.
The fix lands on a real remote branch attached to nothing, so the inline thread
gets resolved against a commit that never reached `main`, and the round's
status reads "finding Addressed, thread resolved" when that is true of a branch
and false of the PR.
This is the shape [`ardi`](ardi.md)'s "a fix is not 'pushed'
until it is on the PR's head commit" bullet describes, one step further out:
there the fix never left the working tree, here it reached a remote branch that
was no longer attached to a PR.

- **Do:** re-read the PR's `merged` field and `head.sha` immediately before
  pushing a fix to a branch whose PR you have not re-read this round.
- **Do:** read `git push`'s own output on that push, and treat `* [new branch]`
  on a branch you have been pushing to as the PR having merged.
- **Do:** treat a `--dry-run` that prints `* [new branch]` for a branch this
  session already published as the same tell; query the PR's `state` and do
  not proceed to the live push if it is MERGED or CLOSED.
- **Do:** settle whether a repo deletes merged head branches from other merged
  PRs' branches, or from the PR's timeline, before concluding that a tell was
  unavailable.
- **Don't:** read a branch that still resolves after your own late push as
  evidence it was never deleted; the push recreated it.
- **Don't:** substitute the ancestry check for re-reading the PR's state in a
  squash-merge repo, where it returns non-ancestor for an open PR too.
- **Don't:** report a finding as Addressed on the strength of a pushed commit
  without checking which ref that commit is reachable from.

**Everything above is scoped to a PR that MERGED, and the closed-not-merged
case fires none of its tells --- while a branch-level push-landed check passes
cleanly and feels like having complied with the rule.**
A PR can leave your control without merging: an owner veto, a supersede, a
scope decision.
A closed PR still accepts pushes to its head branch.
It simply stops tracking that branch, so its `head.sha` freezes at whatever it
was at closure while the branch moves on normally.

Note what that does to the remedy the section above prescribes.
Its Do-bullet names the `merged` field, and on a closed-unmerged PR `merged`
reads `false` --- which is exactly what an **open** PR reports, so the named
field cannot discriminate the two states at all.
`mergeable_state` is worse than useless here, since it can still read `clean`
on a closed PR.
The `* [new branch]` tell cannot fire either, because it requires the head
branch to have been **deleted**, and nothing was: the branch is fine, and only
the PR is closed.
The ancestry check is already ruled out above for a squash-merge repo.

So read `state`, not `merged`.
`state` is the field that separates `open` from `closed`, and `closed_at`
timestamps it.

**The substitute check is what makes this survive a careful session, and it is
the one the corpus itself marks as a killer item.**
Comparing `git rev-parse HEAD` against `git rev-parse origin/<branch>` answers
whether the **branch** moved.
It cannot answer whether the **PR** is still open, and those two questions come
apart exactly here --- the branch accepts the push, the two SHAs agree, and the
check reports success truthfully about a question nobody needed answered.
Running it therefore reads as compliance with the PR-state rule it is standing
in for, which is why nothing prompts the second read.
[`ardi`](ardi.md)'s pre-push checklist carries that comparison as its killer
item, so the substitution has the corpus's own emphasis behind it.

What it costs is a claim rather than a commit, one step further out than the
merged case above.
The commit is real and the branch is real; the PR is not tracking either, so a
comment or body edit citing that commit describes a head the PR does not have.
Every artifact of the round then reads as work continuing with approval, when
approval had been withdrawn an hour earlier.

- **Do:** read the PR's `state` before pushing to a branch whose PR you have
  not re-read this round, and treat `closed` as ending the round whether or not
  it merged.
- **Do:** run the branch-level SHA comparison **and** the PR-state read, as two
  checks answering two questions, rather than letting the first stand for both.
- **Do:** compare the PR's `head.sha` against your local `HEAD` when a PR looks
  quiet, since a frozen `head.sha` is the tell a closed PR leaves behind.
- **Don't:** read `merged: false` as meaning the PR is open --- a closed PR
  reports it identically.
- **Don't:** expect `* [new branch]` or a `mergeable_state` change to announce
  a closure; nothing is deleted and the state can still read `clean`.
- **Don't:** count the killer-item SHA comparison as having checked the PR ---
  it is a true answer to a different question, which is what makes it feel
  sufficient.

(`Morrison-Lab/ai-config#1500`, 2026-08-16/17: the PR asked in its own body to
be vetoed rather than absorbed, and it was.
The veto comment landed at `23:05:08Z` and the PR closed at `23:05:12Z`.
A session then committed `ade5f0a` at `00:06:40Z`, pushed it to
`ums/pr-1259-learnings`, posted a round-2 comment at `00:08:05Z`, and edited the
PR body --- 61 minutes after closure, none of it noticed.
The push was verified by comparing `HEAD` against `origin/ums/pr-1259-learnings`,
which agreed.
`pull_request_read` on #1500 reports `head.sha` `645ed496`, `state` `closed`,
`merged` `false`, and `mergeable_state` `clean`, while
`git ls-remote origin ums/pr-1259-learnings` reports `ade5f0a3`, two commits
ahead.
The body's own "Corrections to this body" entry cites figures re-derived at
`ade5f0a`, a head that PR has never tracked.)

**The harness-assigned branch name itself can already exist locally, pointing at unrelated stale content from an earlier session in the same container.**
A fresh container doesn't guarantee a fresh local branch state --- `git checkout -b <harness-branch> origin/<existing-PR-branch>` can fail with "a branch named `<harness-branch>` already exists" if a prior session in this container created one under that same name and left it pointing at old work.
Don't assume it's safe to reuse or that it reflects the actual PR: check `git merge-base --is-ancestor <local-tip> origin/main` first --- if the local tip is already an ancestor of `main` (i.e. it was old, already-merged content, not in-flight work), it's safe to discard by force-checking out the real PR branch under that same name with `git checkout -B <harness-branch> origin/<existing-PR-branch>` (uppercase `-B` resets the branch in place instead of erroring).

**A PR whose head branch lives in a different repo entirely (not just a scope-restricted push) always needs the supersede path --- there's no fix-in-place option to prefer over it.**
A cross-fork "sync upstream into main" PR --- opened by comparing `<upstream-owner>/<repo>:main` against `<fork-owner>/<repo>:main` --- has its head ref owned by the upstream repo, not the fork.
When that PR shows a real conflict (`mergeable_state: dirty`), the fork has no push access to the head branch at all, regardless of what the harness's own push-scope policy allows elsewhere in the session --- so the stacking preference above doesn't apply here;
go straight to superseding.
Fetch both remotes, merge upstream's branch into a fork-local branch off the fork's own `main`, resolve conflicts there, open a same-repo PR ("Supersedes #N" in the body), and close the original once the replacement merges.
