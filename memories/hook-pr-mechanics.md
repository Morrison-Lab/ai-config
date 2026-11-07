# Shipping a hook PR: conflicts, review sha, and reply-hook rules

Measured 2026-11-07 while shipping ai-config#5089, #5091, #5092 and #5094 from one project thread (all merged).

## Two hook PRs conflict additively in three files

Two hook PRs open at once conflict in `README.md`, `hooks/hooks.json` and `plugins/ai-config-hooks/hooks/hooks.json`.
Each side added a README row and a matcher block, so nothing is in dispute.
Keep both rows and both blocks, then regenerate the mirror with `python3 scripts/gen-hooks-plugin.py` and confirm with `--check` and `scripts/check-hook-catalog.py`.

- **Do:** resolve hunk by hunk, keep both additions, regenerate the plugin mirror, and run the catalog check.
- **Don't:** take one side of `hooks/hooks.json` whole, or hand-edit the mirror.

## The review's `commit_sha` is not the PR head

The Claude review's JSON block reported `commit_sha` 7a4b5de for head 7863c93, and 43c24bc for head 5a4bf48.
Each is the review workflow's merge-with-base commit.
The comment's "Reviewed commit" line and the PR's check runs name the real head.

- **Do:** match the head by the "Reviewed commit" line and the PR's `head.sha`, and say in the handoff that the JSON sha differs.
- **Don't:** treat a differing JSON `commit_sha` as a stale review, or as a Clean verdict on another head.

## Reply hooks refuse on the first try

`mcp__hearthbot__post_message` is denied for a bare `#N`, for naming the coordinator or a session without a link, and for a "still open" claim with no live PR read that turn.
`send_later` needs both `message` and `delay_minutes`.

- **Do:** write every PR as `[owner/repo#N](url)`, link the coordinator session, and read the PR in the same turn before saying it is open.
- **Don't:** draft a status message from the previous turn's state.
