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

The plugin also ships `cursor-rules/` as user-global rules
(`.cursor-plugin/plugin.json` `"rules": "cursor-rules"`).
A live plugin is a skip for `~/.cursor/rules` too, not a second install.
A Claude skill catalog does not ship those rules, so it is not a skip
there.
Leftover `ok` symlinks under `~/.cursor/rules` whose target is this
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

A Cursor Cloud `Task` JSON `tool_result` (harness logs may show `task_v2`)
carries identity fields (including `cloudAgentBcId`) and no review body,
even when the child ran in the foreground.
That JSON is not the report to post as a fallback comment.
The harness may still paste a child assistant message into the parent
transcript.
Quote that paste only when it already carries Summary / Findings / Verdict.
Otherwise fetch the child transcript.
Do not treat a thinking paraphrase or an empty paste as the report.

The Cursor adapter skips `no-push-without-self-review.py` because JSONL
omits `tool_result` (see `SKIP_WITHOUT_TOOL_RESULT` in
[`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py)),
so this lesson is about the posted PR comment, not about satisfying the
pre-push guard.

- **Do:** quote a harness paste of the child's report when that paste
  already carries Summary / Findings / Verdict; otherwise call
  cursor-cloud `batch-fetch-details` with `bcIds: [<cloudAgentBcId>]` and
  `includeTranscripts: true`, then quote the last assistant `text` that
  carries those same sections --- not the last assistant message (which
  may be thinking or `tool_calls` with empty `text`), and not the whole
  file.
  `cloudAgentBcId` is a field on the Task JSON `tool_result`; `bcIds` is
  the tool parameter.
- **Don't:** treat the parent thinking "the reviewer approved" as the
  report, post the identity-only JSON `tool_result` as the review, quote
  a harness paste of thinking or empty `text`, quote the whole
  `transcript.json`, or paraphrase a missing body as Ready for merge.

(Measured 2026-08-25.
The wrap is
[ai-config#2234 comment 5415839535](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839535).
The identity-only JSON is the parent `Task` `tool_result` for child
`bc-61fbadd0-7970-5b2d-8775-4924a28e09a1`.
That comment does not contain the JSON.)

## Jules allowlist skips `cursor[bot]` / `author_association: NONE`

[`.github/workflows/jules-review.yml`](../.github/workflows/jules-review.yml)
requires `author_association` in OWNER/MEMBER/COLLABORATOR.
Comments from a Cursor Cloud run post as `cursor[bot]` / `NONE`, so
an `@jules review` comment from that identity is skipped.

This is the same class as
[`self-review-fallback.cases.md`](../shared/workflow/self-review-fallback.cases.md)
"A session that could reach none of four working reviewers"
([#1417](https://github.com/Morrison-Lab/ai-config/pull/1417) /
[#1433](https://github.com/Morrison-Lab/ai-config/issues/1433), 2026-08-12:
`claude[bot]` / `CONTRIBUTOR`).
2nd occurrence, 2026-08-25, #2234; the association this time is `NONE`.
3rd occurrence, 2026-08-26, #2290; still `cursor[bot]` / `NONE`.

- **Do:** have a human OWNER/MEMBER/COLLABORATOR post `@jules review`
  (the workflow trigger is a trusted comment containing that mention).
- **Don't:** re-post the same request from a session whose comments post
  as `cursor[bot]` / `NONE` --- the gate that skipped it skips the retry.

(Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234);
3rd occurrence measured 2026-08-26 on
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290).)

## Cursor Cloud `gh` writes can 403 while the PR-comment tool still posts

Measured 2026-08-26 on a Cursor Cloud run driving
[#2290](https://github.com/Morrison-Lab/ai-config/pull/2290):
`gh issue comment` and a Copilot review-request POST returned
`403 Resource not accessible by integration`.
`gh api user` returned the same 403.
`gh issue create` and `gh pr view` succeeded in the same session.
PR conversation comments posted through Cursor's `ManagePullRequest`
`post_comment` action (example:
[comment 5423368708](https://github.com/Morrison-Lab/ai-config/pull/2290#issuecomment-5423368708)).

This is a session-token measurement, not a standing GitHub outage.
Re-attempt `gh` writes before reporting them blocked, per
[`github-mcp-tools.md`](github-mcp-tools.md)'s 403-as-measurement note.

- **Do:** fall back to Cursor's `ManagePullRequest` `post_comment` when
  `gh pr comment` 403s in a Cursor Cloud session, and disclose agent
  authorship in the body.
- **Don't:** treat a 403 on one write surface as covering every `gh`
  write --- `gh issue create` worked in the same run that could not
  comment.

