# Monitor every pushed PR head to completion

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#monitor-every-pushed-pr-head-to-completion) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Whenever ending a turn while waiting for CI completion or AI reviews after pushing to a PR in any repository, launch a `schedule` timer (e.g. 120s) to actively monitor that exact head commit.
If no review has arrived when the timer expires, verify whether review workflow runs are still in progress in CI (`gh run list` / `gh pr view --json statusCheckRollup`). If the reviewer failed, was canceled, skipped with no replacement, or produced a stub review with no stated verdict, invoke self-review fallback per `shared/workflow/self-review-fallback.md`; otherwise fix any dispatch or workflow failures discovered along the way and schedule another timer to maintain continuous monitoring until a review lands, self-review fallback triggers, or CI completes.
Keep polling and address actionable failures or findings until all workflows and check runs are complete and passing (success or skipped), the current-head review is clean, and no review threads remain unresolved.
Once that commit is fully clean and green, stop the **intensive head poll** for it; don't restart that poll for the same commit unless something regresses.
A later push creates a new head commit and starts a new monitoring cycle automatically.

A push can start `validate` and no review run at all.
So confirm a review run exists for the head (`actions/runs?head_sha=<sha>`) rather than waiting for one, as on [ai-config#3251](https://github.com/Morrison-Lab/ai-config/pull/3251), where none started (2026-09-04).
Start a missing one the way [`automated-review-before-human`](automated-review-before-human.md) step 1 says for the repo.

**Ending the head poll does not end the PR watch.**
The two run at different frequencies and answer different questions, and only the first one is finished when a head goes green:

- The **head poll** asks "is this commit done?" and terminates when it is.
- The **PR watch** ([`CLAUDE.md`'s "Subscribe to PR updates automatically"](../../CLAUDE.md#subscribe-to-pr-updates-automatically)) asks "is this PR still mergeable and still clean?" and runs until the PR merges or closes.

That distinction is load-bearing because a clean head can regress with **no push of yours at all**.
The base branch advancing is enough: the PR goes `CONFLICTING`, or `main` catches up to an R package's `DESCRIPTION` version, or a sibling PR merges a colliding append --- each turning a green, review-clean head red while nothing about that commit changed.
`shared/workflow/fully-clean.md` says the same thing about verdicts: a clean CI run and a clean review are a snapshot, not a standing guarantee.

So keep checking mergeability and check state at the lower PR-watch frequency after the head poll ends, and **restart the intensive poll if state regresses** --- a new conflict, a check flipping red, a fresh review comment.
Re-derive it from a live query rather than trusting the earlier verdict.

**Every poller shares one GitHub REST budget, so run one checker poller at a time.**
All agents and tools on the account draw on the same 5,000 core requests an hour, and several `Monitor` pollers each re-running `check-pr-fully-clean.py` for different PRs exhausted it on 2026-11-06 ([ai-config#5045](https://github.com/Morrison-Lab/ai-config/issues/5045)).
Poll one PR's checker at a time, and read a head's annotations with `scripts/batch-read-annotations.py`, which pauses between runs and stops above a budget floor, rather than with one call per run.
