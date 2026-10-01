# Put PRs in ready mode when they are ready for review

A Pull Request that is ready for review must be in ready mode, not left in draft.

A draft PR suppresses reviewer attention, notifications, and forge review automation.
Leaving a completed PR in draft leaves it invisible to reviewers who filter for ready work,
delays feedback, and wastes the delivery effort.
Convert it to ready mode explicitly using `gh pr ready <pr-number>` or forge UI.

## Exceptions

Two deliberate exceptions:

1. Up-front empty PRs opened on issue claim (the [`pr-on-claim`](pr-on-claim.md) pattern),
   un-drafted once the implementation has landed on the branch head and the repo's checks pass.
2. Deliberate draft-gating of a dependent PR, which is review-ready by
   construction and held in draft only to block the wrong merge order until its
   prerequisite merges.

Marking a PR ready grants no merge authority.
The strict merge policy still applies.

- **Do:** open a completed-work PR ready for review, or mark a draft ready once
  it is ready for review and its checks pass.
- **Do:** un-draft an up-front empty PR once its implementation has landed on
  the branch head and the checks pass.
- **Don't:** leave a PR that is ready for review in draft, except a
  deliberately draft-gated dependent PR held until its prerequisite merges.
- **Don't:** treat a tool's draft-by-default as the intended state once the
  work is ready for review.
