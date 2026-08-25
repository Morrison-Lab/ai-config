# Cursor

Cursor-specific agent and plugin behavior, split out of
[`tools.md`](tools.md) so that file stays under the 1200-line memory-file
gate (ai-config#694 / #2003).
General local-tool notes stay in `tools.md`.
GitHub PR review via Bugbot is in [`cursor-bugbot.md`](cursor-bugbot.md),
not this file.

## Cursor agent cannot write `.cursorignore` from the sandbox

The Write/StrReplace tools, and a sandboxed Shell, refuse a file named
`.cursorignore` with `operation not permitted`, including a tempfile of that
name under `/tmp`.
The filename is the trigger, not the destination.

- **Do:** write `.cursorignore` with Shell `required_permissions: ["all"]`.
- **Don't:** retry Write or StrReplace after that denial, or conclude the
  path is unwritable.

(Measured 2026-08-18 on Morrison-Lab/ai-config#1642.)

## Cursor hides `.cursorignore` paths from the agent, including worktrees

Cursor's Read/Grep/Glob/Write tools cannot see paths that match
`.cursorignore`.
This repo's `.cursorignore` lists `.claude/worktrees/`, so a
`session-lock` worktree placed there is invisible to Cursor even though
`git worktree list` and the filesystem still show it.

- **Do:** put a Cursor session's worktree outside `.claude/worktrees/`
  (a sibling directory, or another path Cursor can see).
- **Do:** check `git worktree list` before treating an empty Glob/Read of
  `.claude/worktrees/<name>` as "the worktree was never created".
- **Don't:** abandon isolation and edit the primary checkout just because
  Cursor cannot see the worktree; move the worktree to a visible path
  instead.

(Measured 2026-08-23 on Morrison-Lab/ai-config#1928: the first worktree at
`.claude/worktrees/cursor-first-class` was removed after `.cursorignore`
hid it, and work continued on the main checkout.)

## Cursor plugin, `~/.cursor/skills`, and `~/.claude/skills` are alternatives

A live Cursor plugin (`~/.cursor/plugins/local/ai-config` or
`~/.cursor/plugins/cache/<org>/ai-config`) **or** `~/.claude/skills`
already serving this repo is a skip, not a second install.
Do not `rglob` `~/.cursor/plugins/marketplaces`: a catalog clone plus this
repo's Antigravity `plugins/ai-config` is a false positive.
Leftover `ok` symlinks under `~/.cursor/skills` whose target is this
checkout or a sibling worktree are **stacked**, not healthy.

Full `bootstrap.sh` installs `~/.claude/skills` first, so the
`~/.cursor/skills` link path almost never runs.
Do not "fix" tests to expect `~/.cursor/skills/ardi` after a full
bootstrap.

Do not point the Cursor plugin `hooks` field at Claude `hooks/hooks.json`;
that is Morrison-Lab/ai-config#1934, out of #1927 by design.

Cursor Cloud loads project hooks from [`.cursor/hooks.json`](../.cursor/hooks.json)
(native `version: 1` schema), not the Claude catalog.
[`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py)
translates Cursor events into the payload the existing `hooks/` scripts
already consume.
The event mapping is [docs/cursor-hook-mapping.md](../docs/cursor-hook-mapping.md).
Cursor JSONL omitted `tool_result` as of 2026-04-13 (Cursor staff);
three fail-closed Stop/PreToolUse scripts are skipped until that changes
([#2241](https://github.com/Morrison-Lab/ai-config/issues/2241)).
Warn-only Claude Stop `systemMessage` maps to Cursor `followup_message`
because `stop` has no warn-only field.
`postToolUse.additional_context` is emitted; Cloud consumption is
unmeasured as of 2026-08-25 (desktop through 3.7.x discarded it).
Stop scanners still read JSONL, not that field
([#2245](https://github.com/Morrison-Lab/ai-config/issues/2245)).

User-level `~/.cursor/hooks.json` is not available to cloud agents.
`sessionStart` injection is desktop-only.
Cloud agents emit `UserPromptSubmit` context on the first `postToolUse`
of a generation; whether the model sees it is unmeasured on Cloud.
A tool-less cloud turn drops that context rather than delaying it,
because `beforeSubmitPrompt` cannot inject.
Desktop Cursor with third-party Claude hooks enabled also loads
`~/.claude/settings.json`; do not pair that with this project adapter
(both sources run; measured against Cursor's third-party hook docs on
2026-08-25).

## Cursor Cloud Task `tool_result` is identity-only

A Cursor Cloud `task_v2` return is `{agentId, isBackground, cloudAgentBcId}`
only --- no review text, even when the child ran in the foreground.
The parent `tool_result` therefore cannot satisfy
[`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)'s
rule that a verdict is admitted from the reviewer's `tool_result`.

Fetch the child transcript via cursor-cloud `batch-fetch-details`
(`includeTranscripts: true`) using that `cloudAgentBcId` before posting a
fallback review.

- **Do:** fetch the child transcript from `cloudAgentBcId` before posting
  the fallback comment, and quote that report.
- **Don't:** treat the parent thinking "the reviewer approved" as the report,
  or paraphrase a missing `tool_result` as Ready for merge.

(Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839535);
child `bc-61fbadd0`.)

## Jules allowlist skips `cursor[bot]` / `author_association: NONE`

[`.github/workflows/jules-review.yml`](../.github/workflows/jules-review.yml)
requires `author_association` in OWNER/MEMBER/COLLABORATOR.
This Cloud session's comments post as `cursor[bot]` / `NONE`, so
an `@jules review` comment from this session is skipped.

This is the same class as
[`self-review-fallback.cases.md`](../shared/workflow/self-review-fallback.cases.md)
"A session that could reach none of four working reviewers"
([#1417](https://github.com/Morrison-Lab/ai-config/pull/1417) /
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433), 2026-08-12:
`claude[bot]` / `CONTRIBUTOR`).
2nd occurrence, 2026-08-25, #2234; the association this time is `NONE`.

- **Do:** have a human OWNER/MEMBER/COLLABORATOR post the request
  (the workflow trigger is a trusted comment containing that bot mention).
- **Don't:** re-post the same request from this Cloud session --- the gate
  that skipped it skips the retry.

(Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234).)

