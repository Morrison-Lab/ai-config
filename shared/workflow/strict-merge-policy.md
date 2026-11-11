# Strict Merge Control Policy

Merging a Pull Request or Merge Request is strictly controlled across all agents and harnesses.

## Rules

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
  No session or standing grant substitutes ([`irreversible-actions-need-authorization`](irreversible-actions-need-authorization.md)).
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

## Waiver of the cross-model review

When no non-Claude model and harness can run (the network policy blocks the host, the backend is down, the CLI or credential is absent after enumerating every route), try each route once, then waive the cross-model review.
The waiver grants no merge authority: the merge still needs `mwc` or an explicit instruction, a clean Claude review plus green CI, and a PR note that the review was waived, which reviewer was attempted, and the error.
A reviewer that ran and returned not-clean is not unavailable and still vetoes the merge.
The waiver removes only the cross-model requirement;
authorization, [`fully-clean`](fully-clean.md), and the clean-on-head rules still bind.
Full procedure: [`adversarial-self-review`](adversarial-self-review.md#waiver-when-no-cross-model-reviewer-can-run) (Ezra, 2026-10-16).

## Retired: standing `mwc` grants

This file used to grant a standing `mwc` to infrastructure-only PRs and to every PR in `Morrison-Lab/ai-config`, `Morrison-Lab/gha` and `d-morrison/macros`.
[`irreversible-actions-need-authorization`](irreversible-actions-need-authorization.md) retired both grants (Ezra, 2026-11-11, ai-config#5326).
`hooks/no-unauthorized-merge.py` and `hooks/no-mwc-ask-for-infra-pr.py` still implement them until that issue's follow-up lands, so neither hook's verdict authorizes a merge.

- **Do:** drive an infrastructure PR to fully clean, then ask the user to merge it, naming the PR.
- **Don't:** merge it because the merge hook allows it, or skip the question because the ask hook denies a reply that mentions `mwc`;
  ask by naming the PR instead.

See [`AGENTS.cases.md`](../../AGENTS.cases.md), "Strict Merge Control Policy" for the authentic user directives.
