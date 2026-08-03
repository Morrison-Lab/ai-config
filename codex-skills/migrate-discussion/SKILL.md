---
name: "migrate-discussion"
description: "Codex wrapper for the ai-config Claude skill `migrate-discussion`. Migrate an item between GitHub Discussions and Issues when it fits the other tracker better \u2014 a discussion that's really an actionable bug/task moves to Issues; an issue that's really an open-ended question, idea, or support request moves to Discussions. Prefers GitHub's native convert feature (preserves author, thread, and cross-links); falls back to a recreate-and-cross-link procedure via `gh` when the native path isn't available. Use when asked to 'convert this issue to a discussion', 'move this to a discussion', 'this discussion should be an issue', 'make an issue from this discussion', or 'migrate between discussions and issues'. Use when Codex is asked to use `migrate-discussion`, `/migrate-discussion`, or the corresponding ai-config/Claude skill workflow."
---

# migrate-discussion (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/migrate-discussion/SKILL.md](../../skills/migrate-discussion/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/migrate-discussion/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/migrate-discussion`, resolve the symlink target for this wrapper directory first, then read `../../skills/migrate-discussion/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
