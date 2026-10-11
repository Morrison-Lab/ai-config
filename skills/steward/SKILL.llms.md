# Steward: how to drive or watch a Morrison-Lab PR

This is the repo-level PR guidance that Claude’s PR-activity harness reads from `.claude/skills/steward/SKILL.md` on a PR’s head branch. Where it differs from the harness’s built-in rules on conventions or on how proactive to be, this file wins. It cannot override the harness’s “never” rules: never skip or disable a test, never rewrite history on someone else’s branch, never push an empty commit or close and reopen a PR to kick CI.

Each point below is a pointer to the lab rule that carries the detail; read the linked file before acting on that point.

## Posture

- **Driving a PR** (you opened it, or were asked to iterate or take it to clean): subscribe, run the ARDI loop to fully clean, and keep a check-in armed, without asking first. See [`watch-and-ardi`](../../shared/workflow/watch-and-ardi.md), [`ardi`](../../skills/ardi/SKILL.llms.md) and [`fully-clean`](../../shared/workflow/fully-clean.md).
- **Review-only request:** leave the findings and stop. No ARDI, no pushes, no merge.

## Review findings

- **Address every in-scope finding, optional ones included.** This overrides the harness’s rule that an optional or nit finding never starts a push: in these repos a plainly correct nit gets fixed now, in the next push or in a push of its own. See [`address-every-comment`](../../shared/workflow/address-every-comment.md).
- **Reply before pushing:** on each finding you fix, reply naming the not-yet-pushed commit and what it changes, as your last write before the push.
- **A verdict counts only on the current head.** A NOT_CLEAN verdict caused only by an outside dependency, such as a page another repo hasn’t deployed yet, still blocks `require-clean-verdict`. After the dependency lands, re-run the whole review workflow (“Re-run all jobs”) or push, so a fresh verdict posts. See [`review-verdict-pitfalls`](../../shared/workflow/review-verdict-pitfalls.md).

## CI

- **Re-running only the failed jobs cannot recover a failed `post-review`.** `post-review` downloads `claude-review-payload-<run>-<attempt>`, and a failed-jobs re-run bumps the attempt without re-running `claude-review`, so the artifact is missing. Re-run all jobs instead, or let the next push start a fresh review. See [`claude-review-dispatch`](../../memories/claude-review-dispatch.md).
- **Link checks fetch live URLs.** A link to another lab site fails until that site’s PR merges and its Pages deploy finishes. Say so once on the PR, name the blocking PR, and re-run the check after the deploy. To confirm a deploy, read the other repo’s `gh-pages` branch rather than fetching `*.github.io`, which some sandboxes block.
- **Batch fixes into one push.** See [`efficient-pr-babysitting`](../../shared/workflow/efficient-pr-babysitting.md).
- **A review that cannot run is not a verdict.** A malformed token secret or a usage limit is a repository or account problem: say so once on the PR, and don’t treat the PR as reviewed.

## Merging

- **Merge only with a grant.** Pushing to green is not permission to merge. `mwc` grants autonomous merging of fully clean PRs for the session; otherwise, merge only the PRs the user named. See [`mwc`](../../skills/mwc/SKILL.llms.md).
- **View the rendered document before calling a document PR ready.** When the PR changes a Word, PDF, slide, or manuscript render, open the render at the current head, look at every page, post the evidence, and get and post an independent referee read of that render before reporting it ready or merging it. Green CI is not enough. See [`review-rendered-documents`](../../shared/workflow/review-rendered-documents.md).
- **Surface merge order** when one PR depends on another, such as links to a page that a sibling PR adds. Merge the dependency first, wait for its deploy, then re-check the dependent PR.
- **Keep branches synced with `main`** by merging, never by rebasing someone else’s branch. See [`sync-with-main`](../../shared/workflow/sync-with-main.md).

## Comments

- Every comment you post ends with the agent attribution footer.
- Post one standing-down comment per blocker, not one per event.

Back to top
