# Wrap up a merged PR with UMS

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#wrap-up-a-merged-pr-with-ums) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

When a PR/MR you were working on **merges**, run the `post-merge` skill: verify the merge actually landed, tidy the local branch (checkout `main`, pull, `git branch -d`), confirm any deferred items have follow-up issues, then run **UMS** to capture what the PR's review lifecycle taught --- recurring review findings, corrections, and guidance given along the way.
A merge is the natural checkpoint to bank lessons before the context is lost.

This is not the *first* checkpoint, though, and it should rarely be the one carrying the whole backlog.
Per [`CLAUDE.md`'s "Run UMS proactively"](../../CLAUDE.md#run-ums-proactively-as-learnings-accumulate), the pass already ran when the review verdict came back clean, so `post-merge`'s UMS covers what the merge itself taught -- a conflict resolved on the way in, a check that only fires on `main`, a squash that reshaped the history.
Run it regardless: a short pass that finds nothing new is the expected outcome when the verdict-time pass did its job, not a reason to skip the step.

"merge it" / "merge this" / "merge the PR" as bare directives (no slash) trigger the `merge-it` skill: when the PR isn't merged yet, it merges the ready PR (squash by default) **then** chains straight into `post-merge` (tidy + UMS); when the PR is already merged it goes directly to `post-merge`.
Either way the post-merge wrap-up --- including the UMS follow-up PR --- runs **automatically, without asking**.
If the phrase is clearly part of ordinary prose rather than a standalone directive, treat it as such.
