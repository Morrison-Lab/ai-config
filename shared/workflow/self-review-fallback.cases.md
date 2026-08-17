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
