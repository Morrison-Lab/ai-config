Take a fresh reading of the remote branch **immediately** before every `git push`, and reconcile what it shows rather than overwriting it.
Not at the start of the round, not when you last synced, not when you opened the PR --- immediately before, every time.

## Ownership is what suppresses the check

The branch you cut, whose PR you opened, and whose review round you are driving is the branch you are *least* likely to check before pushing to.
That is the whole difficulty, and it is not carelessness: you know what is on the branch because you put it there, so a check reads as ceremony rather than as a question with an unknown answer.

The belief is routinely wrong, and [`claim-pr`](claim-pr.md) already records all three ways.
The `@claude` agent pushes to your branch on PR activity, typically to merge `main` in.
A second CLI session under the same account can claim the same PR and drive it.
And a human can push to it at any time.
None of those announce themselves in your conversation. (Reconfirmed on `ai-config#2668`, 2026-08-30: a posted claim comment did not stop the first case from recurring --- see [`claim-pr`](claim-pr.md)'s "Third occurrence" note.)

Note which direction the parallelism runs, because it inverts the usual intuition: the more agents are working a repo, the likelier a collision and the less any single session can observe one coming.
So the check matters most exactly when the evidence for needing it is least visible, which is why judgment does not reach it and an instrument has to.

That is the same shape [`pr-on-claim`](pr-on-claim.md)'s open-PR check has, and it fails the same way: the skipped step is a *query about other people* rather than anything in your own sequence, so nothing about the moment feels like an omission.

## A fetch is a measurement, and it expires

[`claim-pr`](claim-pr.md) carries three procedures for a push that came back rejected --- the identical-merge case, the same-parents-different-tree case, and the "already done" comment from a parallel session.
Every one of them runs **after** the collision.

The immediacy rule is what makes them rarely needed.
A `git fetch` from earlier in the session is a reading of the remote *at that moment*, and it stopped being evidence the instant somebody else pushed.
This is the same expiry [`CLAUDE.md`](../../CLAUDE.md)'s timestamp rule states for the clock, and it goes wrong the same way: having genuinely checked earlier is what licenses not checking now, because the memory of having consulted the remote obscures that the reading has lapsed.

`git ls-remote` is the reading to take, not `git fetch`:

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git ls-remote --heads origin "$BRANCH"
```

It is read-only --- it updates no remote-tracking ref and writes nothing into the object store --- so it cannot itself change the state it reports on, and it cannot silently satisfy a lease (see below).

Classify what it returns:

| Reading | Meaning |
| --- | --- |
| no ref | nothing to collide with |
| tip equals local `HEAD` | already pushed |
| tip is an ancestor of the pushed ref | fast-forward; safe |
| tip is **not** an ancestor of the pushed ref | somebody else is driving this branch |

**The local side of that comparison is the ref you are *pushing*, which is `HEAD` only when the refspec says so.**
`git push origin feature-x` run while `main` is checked out pushes local `feature-x`, so comparing against `HEAD` compares against the wrong branch.
It fails in the dangerous direction: a remote commit that happens to be an ancestor of `main` reads as a fast-forward while local `feature-x` genuinely diverges, so the check goes quiet in exactly the case it exists for.
Resolve the source from the refspec (`src` in `src:dst`, the bare name otherwise, `HEAD` when there is no refspec) and compare against that.

Only the last one needs anything, and it needs a reconcile rather than an overwrite.
Whether you already hold the remote tip's object is the sharpest part of the reading, and it points the opposite way to intuition: an object you *cannot* resolve locally is the worse signal, not the milder one, because the remote moved after your last fetch and you cannot see what is there.

## `--force-with-lease` is not the safe form on its own

This corpus reaches for `--force-with-lease` as *the* safe force-push at nine sites, derived rather than recalled:

```bash
git grep -l "force-with-lease" origin/main -- '*.md'
```

On 2026-08-22 that returned [`memories/git-worktrees.md`](../../memories/git-worktrees.md), [`memories/git.md`](../../memories/git.md), [`memories/preferences.md`](../../memories/preferences.md), [`keep-checkouts-fresh`](keep-checkouts-fresh.md), [`use-existing-pr-branch`](use-existing-pr-branch.md), and the `clean-branches`, `mma`, `rescue-closed`, and `stack-prs` skills.
It is much safer than bare `--force` and it is not sufficient, because the lease is defeatable and none of those nine says so.

The mechanism: the lease compares the remote tip against **your remote-tracking ref**, not against anything you have actually looked at.
So any background `git fetch` refreshes that ref and the lease then passes over the very commits it existed to protect --- a scheduled poller, another tool working the same checkout, a `--recurse-submodules` fetch, an IDE's auto-fetch.
The push succeeds, reports nothing unusual, and the commits are gone from the remote.

`--force-if-includes` is the missing half, added in Git 2.30.0, whose release notes describe it as ensuring "that what is being force-pushed was created after examining the commit at the tip of the remote ref that is about to be force-replaced".
Mechanically it checks the remote-tracking tip against the local branch's **reflog** rather than against its ancestry, so a fetch you never saw no longer satisfies the lease.
`git push --help` names the hazard directly: the refs it guards against are ones "that may have been implicitly updated in the background".
It is an *ancillary* option, so passing it without a bare `--force-with-lease` does nothing for you.
The two always travel together.
Use both, always:

```bash
git push --force-with-lease --force-if-includes
```

**The `stale info` failure is not a reason to force, and reaching for one there is the specific reflex [`memories/git-branches.md`](../../memories/git-branches.md) exists to stop.**
After a squash-merge with auto-delete removes the branch your ref still names, `--force-with-lease` fails with `stale info`, which reads alarmingly like a race with another session.
It is not one, and that file says so in as many words: the lease is unsatisfiable rather than violated, "`--force` is unnecessary, and there is nothing to race".
One read settles it --- `git ls-remote --heads origin <branch>` --- and empty output means the next push *creates* the branch.
That create is safe only when no MERGED PR already owned this head.
A squash-merge with auto-delete also leaves `ls-remote` empty.
A `--dry-run` of `git push -u origin <branch>` then prints `* [new branch]`
and often `Would set upstream of ...`, which is the recreate tell
[`use-existing-pr-branch`](use-existing-pr-branch.md) names for a live push.
Query `gh pr list --state all --head <branch>` before pushing
(see [`check-open-prs-before-duplicating`](check-open-prs-before-duplicating.md)).
If a listed PR is MERGED, do not recreate the deleted head;
open a follow-up off `origin/<default-branch>`
and cherry-pick orphaned commits onto that fresh branch
(see [`use-existing-pr-branch`](use-existing-pr-branch.md)).
A CLOSED-unmerged PR does not auto-delete its head;
that case fires none of the recreate tells.
An OPEN PR whose head is missing still wants a plain push.
If there was no such PR, a **plain push** is the fix, or `git fetch --prune`
and a retry when you want the remote-tracking ref corrected too.
That is consistent with the point above: where the remote ref does not exist
and no merged PR owned it, there is nothing for any force to overwrite.

2nd occurrence of the recreate-from-empty-ls-remote failure, 2026-08-26 PDT,
Cursor Cloud, [ai-config#2272](https://github.com/Morrison-Lab/ai-config/pull/2272):
the Address dry-run printed `* [new branch]` and `Would set upstream of ...`
after the squash-merge auto-deleted the head.
`gh pr view` showed MERGED.
A live push would have recreated the deleted branch.
Prior record: [`use-existing-pr-branch`](use-existing-pr-branch.md)'s
live-push tell.
Morrison-Lab/ai-config#857 -> #872 is the *correct* same-name follow-up
from new `main`, not a prior occurrence of this failure.

So `ALLOW_FORCE_PUSH=1` is a deliberate escape valve for a case this rule did not foresee, not a shortcut for a known one.
If you reach for it, say in the same breath what the lease refused and why forcing is right --- and if the answer is `stale info`, it is not.

## The instrument

`hooks/no-clobbering-push.py` is this rule's mechanism, per [`algorithmatize-checks`](algorithmatize-checks.md) --- because a rule that has to be *recognized as applicable* at the moment of typing is exactly the gap [`skills/push`](../../skills/push/SKILL.md) cannot close on its own.
That skill states the pre-push checks well and only runs when it is invoked, so a bare `git push` in the middle of an ARDI round never passes through it.

The hook binds `PreToolUse` on `Bash` and splits the two questions by which of them is decidable:

- It **refuses** a bare `--force` / `-f`, because that is decidable from the command text alone and the remedy costs one word.
  `--force-with-lease --force-if-includes` is never the worse command --- where the remote ref does not exist the lease succeeds trivially --- so the refusal is always satisfiable, and being wrong about it costs a retype rather than a lost commit.
- It **warns** on everything else, from the live `ls-remote` reading above, and stays silent on a fast-forward.
  Whether a divergence matters is a judgment it cannot make: a rebase you did on purpose and a parallel session's commits look identical from here.
  Per [`README`](../../README.md)'s "A hook that misfires is worse than a missing one", that path only ever adds context.

## When the check fires, reconcile

Fetch and read before deciding anything:

```bash
git fetch origin "$BRANCH"
git log --oneline "HEAD..origin/$BRANCH"
```

Then follow [`claim-pr`](claim-pr.md)'s tree-and-parents comparison, which distinguishes the two cases a rejected push can mean: an identical merge another session already pushed, where the answer is `git reset --hard origin/<branch>`, and a **differently resolved** one, where a reset silently discards whatever your version got right and the answer is to merge the two commits.
Never force-push over the difference to find out which it was.

## The diff is the review surface, so read it

The remote check above covers collisions.
A second staleness lives entirely on your side: edits composed against a
working tree that has since moved.
Read a file, then pull or switch branches, then apply an edit whose anchor
text came from the earlier read, and the edit can still report success
while writing against text HEAD no longer carries --- matchers forgive
near-misses, so a stale anchor does not always fail loudly.
What lands in the push is churn you did not intend, and prose composed
from the stale read asserts things about the tree that the pushed diff
contradicts.

Two cheap looks close it.
Re-read any file you are about to edit whenever a checkout, pull, or reset
has happened since your last read of it.
And before anything leaves the machine, read the actual patch and confirm
every hunk is one you intended:

```bash
git diff origin/<default-branch>...HEAD
```

A `--stat` summary is not that look: it names files and counts lines, so
it surfaces a stray *file* but not a wrong edit inside an expected one ---
and the wrong-edit-inside-an-expected-file case is exactly the staleness
this section is about.

The patch is also the only surface a reviewer sees, so a changelog claim
about what this PR fixes has to be derivable from it.
A fix the patch cannot show was landed by somebody else's PR, and claiming
it here misattributes the work.

(Measured 2026-08-24 in Morrison-Lab/gha#599: an edit made from a read
taken before `git pull` applied without a loud failure, carried an
unscoped rewrite of another workflow file into the push, and produced a
changelog fragment crediting this PR with a fix that had merged the day
before --- the reviewer caught the misattribution in round 2 and round 3
confirmed it fixed.)

## Once pushed, add a new commit rather than amending

Amending an already-pushed commit (`git commit --amend`) rewrites the commit object and mints a new SHA.
The original commit is orphaned once force-pushed over, even when using safe `--force-with-lease --force-if-includes`.
The audit trail breaks silently: automated reviewer bots, adversarial reviewer agents, and human reviewers cite specific commit SHAs in their review verdicts and comments.
Detaching the commit SHA leaves those verdicts pointing to an unreachable history.
Once a commit is pushed, add a new commit instead of amending.
The extra commit is squashed cleanly at PR merge, so history tidiness is preserved without breaking the review audit trail.

## Once pushed, actively monitor CI and review to completion

Pushing a commit to a PR/MR branch is the start of the round, not the end of the turn.
Do not abandon monitoring after pushing or assume automated pipelines and reviewer runs will complete without active polling.
Immediately maintain an active polling loop or scheduled wake mechanism.
Actively query current-head CI/pipeline status (`gh pr checks` / `glab ci list` or `glab mr view`) and review verdicts (`gh pr view` / `glab mr view`) until that round reaches a terminal state.
Re-arm the poll while work remains.

- **Do:** take a fresh `git ls-remote` reading immediately before every push, including on a branch you created and believe you alone are driving.
- **Do:** push with `--force-with-lease --force-if-includes` whenever a force is genuinely wanted, and state a reason whenever you reach for `ALLOW_FORCE_PUSH=1`.
- **Do:** add a new commit rather than amending once a commit has been pushed to the remote.
- **Do:** immediately start or re-arm active CI and review polling after pushing to a PR/MR, driving the round until it reaches a terminal state.
- **Do:** reconcile a divergence by fetching and reading it, and treat an object you cannot resolve locally as the stronger signal rather than the weaker.
- **Don't:** treat an earlier fetch, sync, or green CI run as the check --- each was a reading of a moment that has passed.
- **Don't:** read "I opened this branch and its PR" as evidence you are its only driver.
  That belief is what the check exists to test.
- **Don't:** run `git commit --amend` on a commit that has already been pushed and reviewed, orphaning the SHA cited in review verdicts.
- **Don't:** abandon monitoring after pushing, or assume automated pipelines and reviewer runs will complete without active polling.
- **Don't:** reach for bare `git push --force`, and don't read `--force-with-lease` alone as safe --- a background fetch defeats it silently.
- **Don't:** pair `--force` *with* the lease and expect protection.
  Git's documentation for `-f, --force` says the flag "disables that check, the other safety checks in PUSH RULES below, and the checks in `--force-with-lease`" --- so the two together are a plain force push.
  (That is upstream `master`'s wording.
  The man page shipped with git 2.50.1 words it differently and says the same thing.)
- **Don't:** answer a `stale info` refusal with a force, or read the message as self-explanatory.
  It reports only that your remote-tracking ref no longer matches the remote, never why.
  `git ls-remote --heads origin <branch>` settles existence and nothing further.
  A non-empty result still needs the tip comparison above before you pick a remedy.
- **Do:** when `ls-remote` is empty, query
  `gh pr list --state all --head <branch>` before treating the next push as a first publish.
  MERGED means do not recreate.
- **Don't:** read empty `ls-remote` or a dry-run `* [new branch]` line as proof this is a new feature branch.
- **Do:** re-read a file before editing it whenever a checkout, pull, or
  reset has happened since your last read of it.
- **Don't:** claim a fix in changelog or prose text that the pushed patch
  itself cannot show.

(Directive from the user, 2026-08-21:
"cai: add protections against clobbering commits from other agents on a branch
you think you own; always check immediately before pushing".
Tracked as ai-config#1883.
`grep -rn 'force-if-includes'` over the whole repo returned 0 hits when the directive arrived, against the nine files enumerated above reaching for `--force-with-lease` as the safe form.)
