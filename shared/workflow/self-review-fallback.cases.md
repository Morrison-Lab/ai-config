# Case records: self-review-fallback

Worked-example case records for the rules in
[`self-review-fallback.md`](self-review-fallback.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Where the cross-vendor directive came from

(Directive source: a public write-up of a multi-agent review workflow, 2026-08:
"Models are from different vendors, and you get better results due to them
having different approaches and different blind spots.
Friction (disagreement) is your friend here."
The corpus already had the mechanisms --- Copilot alongside `claude-review`,
plus [`agy-review-workflow`](../../skills/agy-review-workflow/SKILL.md) and
[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) --- and no
statement of why to pair across vendors or how to weight their agreement.)

## A session that could reach none of four working reviewers

(`Morrison-Lab/ai-config#1417`, 2026-08-12, filed as
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433).
A remote session could summon none of four configured reviewers, and each
gate was read rather than inferred.

`claude-review.yml` is `workflow_dispatch`-only, and
`POST .../actions/workflows/claude-review.yml/dispatches` returned
`403 Resource not accessible by integration` --- the session token carries no
`actions: write`.

`claude-bot.yml` carries no job-level `if:` of its own and delegates to
`Morrison-Lab/gha/.github/workflows/claude.yml@v1`, whose job `if:` requires
`author_association` in `["OWNER","MEMBER","COLLABORATOR"]`.
`jules-review.yml` and `antigravity-review.yml` carry the same allowlist
inline.
Reading the callers alone would have found three unconditional-looking
trigger blocks and settled nothing.

The common cause was one identity fact: API **reads** authenticated as the
repo owner, while comment **writes** landed as `claude[bot]` with
`author_association: CONTRIBUTOR`.
All three comment-triggered runs therefore reported `skipped`, not `failure`.

Copilot was the one reviewer that was genuinely down --- requested
successfully, then refused with "unable to review ... reached their quota
limit" --- which is the case this fragment's fallback already covered, and
not the case the entry above is about.

What settled that the others were up rather than broken: `claude-review`
completed successfully on `ums/is-stale-branch-coverage` and
`ums/mechanism-claim-comments` the same day.
So the PR was reported blocked on an external verdict rather than ready, and
was not merged, even though `Morrison-Lab/ai-config` carries a standing `mwc`
grant --- that grant's scope limit is a **fully clean** PR, and a PR one human
action short of a reachable reviewer is not one.)

## The stub-retry skipped on a sentinel denial count

(Morrison-Lab/ai-config, 2026-08-20: two PRs, [#1724](https://github.com/Morrison-Lab/ai-config/pull/1724)
and [#1741](https://github.com/Morrison-Lab/ai-config/pull/1741), produced an
identical `review / claude-review` job signature --- jobs `96364511234` and
`96365603526`, the latter in run `32349569604`.

Read off `actions/jobs/<id>`, both jobs concluded `failure` with the same three
steps deciding it:

| step | conclusion |
| --- | --- |
| `Fail the check if the review did not complete (attempt 1)` | `success` |
| `Retry Claude Code Review after a stub result or action short-circuit` | `skipped` |
| `Resolve final review outcome` | `failure` |

Every other step in both jobs was `success` or `skipped`, which is
[`fully-clean`](fully-clean.md)'s "a job's conclusion is set by whichever step
failed" in its plainest form.

The job log carries the cause in three consecutive lines:

```
permission_denials_count could not be parsed from execution result
  (got 'MISSING'); defaulting to sentinel 999999 (gha#370).
permission_denials_count=999999 (stub-retry max_denials=5)
permission_denials_count=999999 exceeds the stub-retry threshold (5) ---
  this looks like gha#198's pattern, not gha#185's; not marking as retryable.
```

The execution result's own summary earlier in the same log reads
`"permission_denials_count": 0`, so the real count was well inside the
threshold and the run was refused a retry purely on the parser's failure value.
`Morrison-Lab/gha#370` is closed, and the sentinel behaviour it introduced is
what fires here.

The check then reported `Claude review states no verdict (no '### Verdict'
heading or 'Verdict:' line anywhere in its output)` --- the stub signature the
parent fragment already describes --- while the retry meant to recover it never
ran.)

**Third occurrence, 2026-08-20, on the PR documenting the first two.**
[#1757](https://github.com/Morrison-Lab/ai-config/pull/1757)'s own
`review / claude-review` job (`96501751353`, run `32392491819`) reproduced the
signature exactly: `Retry Claude Code Review after a stub result or action
short-circuit` concluded `skipped`, `Resolve final review outcome` concluded
`failure`, and `review / require-review` went red behind it.
Three instances inside one day puts this past
[`deterministic-tools`](../principles/deterministic-tools.md)'s third-occurrence
bar, so the retry-eligibility gate is a candidate for a fix in `gha` rather than
for a sharper sentence here --- the sentinel defaults toward refusing a retry,
which is the opposite of the direction a fail-safe should take when the cost of
a wrong retry is one extra review and the cost of a wrong refusal is an
unreviewed PR.
