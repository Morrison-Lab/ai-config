# Case records: batch-merge-and-resolve

Worked-example case records for the rules in
[`batch-merge-and-resolve.md`](batch-merge-and-resolve.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "The batch pass" --- a squash-merge queue that serial chasing could not converge

(Morrison-Lab/ai-config, 2026-07-30/31.
`main` took 7 squash-merges in the hour ending `00:51:57 PT`; over the last 10
first-parent commits the span was 87.1 min and the mean interval 9.7 min.
`git log --merges` reported none of them, the repo being squash-merged.
An agent merged `main` into #946 at `00:42:25 PT`; #943 landed at `00:50:28 PT`
and re-dirtied it 8 minutes later, so the review round never closed.
Five open PRs touched `CLAUDE.md` at that point: #943, #946, #951, #959,
and #961 --- of which #943 and #951 have since merged.
A pairwise sweep of the 8 heads then open found **2 of 8** conflicting with
`main` and **9 of 28** pairs conflicting with each other.
The pair #953 and #961 was one of the 9: each was clean against `main`
and conflicted with the other on `.github/workflows/validate.yml`.
The negative control caught two false all-clears before any zero was trusted:
`--write-tree` exiting 129 on git 2.34.1, and `grep '^<<<<<<<'` returning 0
against a real conflict whose markers were diff-indented.
Both had reported all 28 pairs clean.)
