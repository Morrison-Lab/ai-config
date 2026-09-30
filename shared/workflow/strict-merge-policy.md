# Strict Merge Control Policy

Merging a Pull Request or Merge Request is strictly controlled across all agents and harnesses.

## Rules

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
- **Never merge over open review findings or treat a reviewer skip notice as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see [`fully-clean.md`](fully-clean.md)).
  A clean automated review from every available provider evaluating the current HEAD commit is strictly required for merging with `mwc`.
  A reviewer skip notice (e.g. for quota exhaustion or workflow edits) or a fallback self-review does NOT satisfy `mwc` or grant autonomous merge authority.
  All findings across the PR history must be Addressed, Rebutted, or Deferred before merge.
  A disagreement among reviews is not fully clean: any reviewer's standing not-clean --- nits included --- vetoes merge even with `mwc` active.
  ARD every item from every review, then request fresh reviews.
- **Never describe a PR as merge-ready without a clean review verdict on the latest commit.**
  GitHub's `mergeable` field is conflict existence (`MERGEABLE` / `CONFLICTING` / `UNKNOWN`).
  `mergeStateStatus: CLEAN` is conflict-free (GitHub `mergeable`) plus passing commit status, not a review verdict.
  Only `DIRTY` / `CONFLICTING` means conflicts.
  A PR whose latest commit has no authentic clean review is not merge-ready.
  Report it as blocked on review, not as merge-ready.
- **Revert premature or defective merges immediately.**
  If a PR is merged incorrectly, prematurely, or without clean external review approval,
  open a revert PR on `main` immediately and continue on the original PR branch per [`revert-premature-merge.md`](revert-premature-merge.md).
- **When you revert a merge, reopen its issue.**
  GitHub does not automatically reopen the issue a reverted PR closed;
  explicitly and immediately reopen the corresponding issue(s) (`gh issue reopen <issue-number>`) per [`revert-merge.md`](revert-merge.md).

## Infrastructure PRs standing `mwc` grant

Infrastructure PRs carry a standing `mwc` grant in every repo the user can push to.
A PR whose diff is only infrastructure --- CI workflows, tooling and scripts, configuration,
and recorded instructions and notes for AI and human developers
(`CLAUDE.md`, `AGENTS.md`, `.github/`, `.claude/`, memories, skills, contributor docs, `tools/`) ---
may be merged without asking once it is fully clean.
Every other rule in this section still binds, including the clean automated review on the current head,
so a quota-skipped review still holds the merge.
The test is effect rather than file type: infrastructure is whatever does not directly change the repo's consumer's experience.
Every PR in `Morrison-Lab/gha` or `Morrison-Lab/ai-config` counts as infrastructure, as both are infrastructure repos.
Where `hooks/no-unauthorized-merge.py` is active, clear it with `ALLOW_MERGE=1` on that one merge command, and state in the reply why the PR qualified.
Do not enable session-wide `/mwc` for it.

- **Do:** merge a fully clean infrastructure PR without asking, and say in the same reply that you did and why it qualified.
- **Don't:** extend the grant to a PR that mixes infrastructure with content, or merge one whose review was skipped.

See [`AGENTS.cases.md`](../../AGENTS.cases.md), "Strict Merge Control Policy" for the authentic user directives.
