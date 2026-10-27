# Run the fully-clean checker where GraphQL works

The merge rule is `scripts/check-pr-fully-clean.py` exiting 0 on the current head.
A hand check of `mergeable_state`, check runs and a review verdict does not count in its place
(Ezra's coordinator, 2026-10-27).

The checker needs GraphQL.
A cloud session whose proxy returns 403 for GraphQL cannot run it.
In that case:

- Start a Remote Control session on a machine where GraphQL works (standing permission: cf463-02)
  and run `python3 scripts/check-pr-fully-clean.py <N> -R <owner>/<repo>` there.
- Merge only after exit 0 on the head you are merging.
- Do not merge on a hand check because the cloud session cannot reach the checker.
  If Remote Control is unavailable, report the PR as waiting on the checker.

Standing `mwc` grants (gha, macros, ai-config) remove the per-PR word, not the checker.
