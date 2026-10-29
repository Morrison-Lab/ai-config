# Every PR is as small and focused as it can be

Ezra, 2026-10-23: "don't allow massive sweep PRs like [pds#244](https://github.com/Morrison-Lab/pds/pull/244) anymore;
do them in minimal batches", and "every PR should be as small and focused as it can be while completely solving its stated task" ([ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698)).

## The rule

- A PR solves its stated task completely and nothing else.
- A PR changes at most 10 files and 300 lines (added plus deleted).
  Generated, lock, `_freeze/`, image and data paths are not counted.
- A sweep across many files goes out as minimal batches, and only when Ezra explicitly asked for it ([`no-sweeps-by-default`](no-sweeps-by-default.md)).
  Each batch is one concern, with its own issue and its own PR.
  Open the first batch, then the next, rather than one PR for all of them.
- Stacked PRs are fine: each layer is small, and each names the layer it needs.
- Content and infrastructure stay in separate PRs, as before.

## The mechanisms

- `hooks/no-oversized-pr-push.py` denies a `git push` of a branch over the cap, before CI is spent.
  Clear it with an `ALLOW_LARGE_PR=1` prefix for a stacked branch whose base is not the default branch, or when the maintainer asked for one mechanical PR, and state why in the reply.
- gha's `check-pr-size` ([gha#1188](https://github.com/Morrison-Lab/gha/issues/1188)) fails the same PR in CI.
  The `size-exempt` label lifts it.
- The caps are a decision, recorded here: 10 files and 300 lines, tight on purpose after Ezra changed "waves" to "minimal batches".
  Change them in the hook, in the gha defaults and here together.
