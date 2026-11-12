# Every PR is as small and focused as it can be

Ezra, 2026-10-23: "don't allow massive sweep PRs like [pds#244](https://github.com/Morrison-Lab/pds/pull/244) anymore;
do them in minimal batches", and "every PR should be as small and focused as it can be while completely solving its stated task" ([ai-config#4698](https://github.com/Morrison-Lab/ai-config/issues/4698)).

## The rule

- A PR solves its stated task completely and nothing else.
- A PR changes at most 10 files and 300 lines (added plus deleted).
  Generated, lock, `_freeze/`, image and data paths are not counted.
  A committed generator output counts until the repo's `.gitattributes` marks it `linguist-generated`;
  then neither the push hook nor gha's `check-pr-size` counts it, and GitHub folds it in review
  ([ai-config#5288](https://github.com/Morrison-Lab/ai-config/issues/5288)).
  The lines of a newly added `_fig-*` subfile are not counted either, but the file still counts toward the 10
  ([ai-config#4928](https://github.com/Morrison-Lab/ai-config/issues/4928), Ezra "daytb", 2026-11-04):
  figure code in two languages made one decision into three PRs.
- A content-identical mechanical PR is exempt at any size: a pure move, rename, or split with no wording change
  ([ai-config#5128](https://github.com/Morrison-Lab/ai-config/issues/5128), Ezra "daytb", 2026-11-09).
  Its body must say "mechanical, content-identical".
  A reviewer checks that claim by diffing the moved text, so a PR that also rewords is not exempt.
  The cap still applies to a PR that mixes a move with an edit.
  Moved lines count as changed for `lint-changed-lines`, so a lint fix on them may be needed.
  A mechanical split lists in its body every such lint-driven edit to moved lines
  ([ai-config#5130](https://github.com/Morrison-Lab/ai-config/issues/5130), from [pds#364](https://github.com/Morrison-Lab/pds/pull/364)).
- A sweep across many files goes out as minimal batches, and only when Ezra explicitly asked for it ([`no-sweeps-by-default`](no-sweeps-by-default.md)).
  Each batch is one concern, with its own issue and its own PR.
  Open the first batch, then the next, rather than one PR for all of them.
- Stacked PRs are fine: each layer is small, and each names the layer it needs.
- Content and infrastructure stay in separate PRs, as before.

## Measure early, and split by patch

Learned while splitting the priority-label branch on 2026-11-11 ([ai-config#5359](https://github.com/Morrison-Lab/ai-config/issues/5359)).
That branch reached 22 files and 488 lines over six self-review rounds before its first push was refused,
so the split came after the review work.
No hook warns at commit time or on a file checkout from another commit yet;
that issue tracks both.

- **Do:** run `git diff --shortstat origin/main...HEAD` after the first commit and after each fix round,
  and split a second concern out as soon as the branch nears the cap.
  Review fixes add tests, and tests alone carried a later branch from under the cap to 311 lines.
- **Do:** carry a change onto a new base with `git diff <merge-base> <commit> -- <files> | git apply --index --3way`,
  then compare `git diff --cached --numstat` with the original branch's numstat for those files.
- **Do:** after a split, open each file a part cites at `origin/main` and confirm the cited rule is there.
  A citation checked against the unsplit branch can point at text that only an unmerged sibling PR adds
  ([ai-config#5369](https://github.com/Morrison-Lab/ai-config/pull/5369)).
- **Don't:** leave the size check to the push.
- **Don't:** run `git checkout <commit> -- <file>` to carry a change onto a newer base.
  It carries the whole old file, so it silently reverts what `main` changed since the branch point
  (`hooks/hooks.json` lost 12 lines that way, and nothing failed).

## The mechanisms

- `hooks/no-oversized-pr-push.py` denies a `git push` of a branch over the cap, before CI is spent.
  A pure rename (no line changed) does not count toward the file cap.
  Clear it with an `ALLOW_LARGE_PR=1` prefix for a stacked branch whose base is not the default branch, or for a mechanical, content-identical move or split, and state why in the reply.
- gha's `check-pr-size` ([gha#1188](https://github.com/Morrison-Lab/gha/issues/1188)) fails the same PR in CI.
  The `size-exempt` label lifts it; put it on a mechanical, content-identical PR.
- The caps are a decision, recorded here: 10 files and 300 lines, tight on purpose after Ezra changed "waves" to "minimal batches".
  The 300 was a starting value with no data behind it ([ai-config#4928](https://github.com/Morrison-Lab/ai-config/issues/4928)).
  Before keeping it, measure it against the PRs that hit it.
  Change the caps and the `_fig-*` exemption in the hook, in the gha defaults and here together.
