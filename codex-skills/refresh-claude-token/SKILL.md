---
name: "refresh-claude-token"
description: "Codex wrapper for the ai-config Claude skill `refresh-claude-token`. Rotate CLAUDE_CODE_OAUTH_TOKEN across the repos that already carry it, without /install-github-app's App-install and workflow scaffolding. Wraps scripts/rotate-claude-token.py, hands the interactive minting step to the human, and closes the gap that script cannot: proving the new token authenticates, not merely that the secret changed. Use when asked to 'refresh the claude token', 'rotate the claude token', 'rct', 'update CLAUDE_CODE_OAUTH_TOKEN', 'the claude token expired', 'reviews are failing with a credential error', or 'is there a command that just updates the token'. Use when Codex is asked to use `refresh-claude-token`, `/refresh-claude-token`, or the corresponding ai-config/Claude skill workflow."
---

# refresh-claude-token (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/refresh-claude-token/SKILL.md](../../skills/refresh-claude-token/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/refresh-claude-token/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/refresh-claude-token`, resolve the symlink target for this wrapper directory first, then read `../../skills/refresh-claude-token/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
