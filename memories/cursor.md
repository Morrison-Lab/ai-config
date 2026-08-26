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

## Cursor Cloud `Task` dispatches `adversarial-reviewer`

Measured 2026-08-25 PDT: a Cursor Cloud session can dispatch the
`adversarial-reviewer` persona through `Task`
(`subagent_type: adversarial-reviewer`).
Morrison-Lab/ai-config ships that persona under both `.claude/agents/`
and `.opencode/agents/`.
Which path Cursor Cloud reads was not isolated.

The dispatch this corpus requires is foreground
(`run_in_background` false).
Measured 2026-08-25 PDT on a Cursor Cloud Grok conductor in this repo:
that conductor's `Task` schema listed `run_in_background`
and did not list `isolation`.
`flag-unassigned-worktree.py` warns on every such dispatch
because the Cursor adapter maps `Task` to `Agent`
when `subagent_type` is not explore/plan/shell
([`.cursor/hooks/adapt-claude-hooks.py`](../.cursor/hooks/adapt-claude-hooks.py)),
and that hook's `READ_ONLY` set is Explore/Plan.
Deciding the child needs no worktree is fine;
the schema has no `isolation` field to mark that decision.
Tracked as [#2276](https://github.com/Morrison-Lab/ai-config/issues/2276).

Record `git rev-parse HEAD` before the dispatch.
After the child returns, compare that sha to `git rev-parse HEAD`
and to the child's `Reviewed-Commit` line.
`git status --short` is a dirty-tree check, not a HEAD check.
Cursor's adapter skips `no-push-without-self-review.py`
(`SKIP_WITHOUT_TOOL_RESULT`),
so a failed or skipped dispatch is not caught before the push.
The push-enforcement check is the parent's reading of the `Task`
result and the posted PR comment.

When the conductor is not Claude, pass a listed Claude slug on `model`
(that 2026-08-25 PDT conductor listed `claude-opus-5-thinking-high`
on its `Task` model list).
The `Task` schema documents that omitting `model` inherits the parent.
That inherit path was not separately observed on a live omit.
A separate context buys independence of intent even if `model` is omitted
([`adversarial-self-review`](../shared/workflow/adversarial-self-review.md)).
Passing a listed Claude slug when the conductor is not Claude also buys
independence of vendor from the author, which inherit does not.
That is the [#2270](https://github.com/Morrison-Lab/ai-config/issues/2270)
instruction, not the floor.
Independence from a Claude primary is the second-reviewer pairing,
not this dispatch
([`self-review-fallback`](../shared/workflow/self-review-fallback.md)).

Measured 2026-08-25 PDT: the persona's `tools:` frontmatter is
instruction-level on Cursor Cloud, not a harness filter.
The `.claude/agents/` copy carries a `tools:` field;
the `.opencode/` copy uses `permission: edit: deny` instead.
The Cursor Grok dispatch measured that day on
[#2265](https://github.com/Morrison-Lab/ai-config/pull/2265) and
[#2266](https://github.com/Morrison-Lab/ai-config/pull/2266)
still received Write schemas.
State read-only in the brief.
GitHub `claude-review` skipping for a missing
`CLAUDE_CODE_OAUTH_TOKEN` or quota does not mean Claude is
unreachable on that conductor's `Task` tool.

[#2270](https://github.com/Morrison-Lab/ai-config/issues/2270)
is the instruction to use this route.

- **Do:** dispatch `Task` `adversarial-reviewer` in the foreground
  (`run_in_background` false) for every self-review in a Cursor
  session that can resolve the persona, including when GitHub
  `claude-review` skipped a run.
- **Do:** when the conductor is not Claude and a Claude model is
  listed for `Task`, pass that Claude model on `model`.
- **Do:** brief the child not to edit.
  Record `HEAD` before the dispatch, and after it returns compare
  that sha to `git rev-parse HEAD` and to `Reviewed-Commit`.
- **Don't:** treat a skipped GitHub `claude-review` as "no
  Claude reviewer is reachable in this session".
- **Don't:** omit `model` on that dispatch when Claude is
  listed and the conductor is not Claude.
- **Don't:** prefix `ALLOW_UNREVIEWED_PUSH=1` on the grounds
  that the subagent route was unavailable, after a `Task`
  dispatch just ran.
- **Don't:** treat a clean `git status` as proof the child did
  not commit.

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
That comment does not contain the JSON.
The same author wrap recurred 2026-08-25 PDT on
[#2265](https://github.com/Morrison-Lab/ai-config/pull/2265) and
[#2266](https://github.com/Morrison-Lab/ai-config/pull/2266).)

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

- **Do:** have a human OWNER/MEMBER/COLLABORATOR post `@jules review`
  (the workflow trigger is a trusted comment containing that mention).
- **Don't:** re-post the same request from a session whose comments post
  as `cursor[bot]` / `NONE` --- the gate that skipped it skips the retry.

(Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234).)

