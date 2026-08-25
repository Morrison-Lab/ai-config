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

User-level `~/.cursor/hooks.json` is not available to cloud agents.
`sessionStart` injection is desktop-only.
Cloud agents get `UserPromptSubmit` context on the first `postToolUse`
of a generation; a tool-less cloud turn drops that context rather than
delaying it, because `beforeSubmitPrompt` cannot inject.
Desktop Cursor with third-party Claude hooks enabled also loads
`~/.claude/settings.json`; do not pair that with this project adapter
(both sources run; measured against Cursor's third-party hook docs on
2026-08-25).

