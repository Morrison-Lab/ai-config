---
name: "permission-check"
description: "Codex wrapper for the ai-config Claude skill `permission-check`. Read-only self-diagnostic for 'why is Claude Code prompting me for this' (or 'why isn't it'). Walks the permission config layers in resolution order (managed policy, CLI args, project-local, project-shared, user) and reports which layer's rule actually wins for a given tool/action pattern. Never edits config \u2014 see update-config for that. Use when asked to 'permission check', 'why does this keep prompting', 'why is this auto-allowed', 'check my permissions', 'diagnose permission prompt', or 'what rule controls this tool call'. Use when Codex is asked to use `permission-check`, `/permission-check`, or the corresponding ai-config/Claude skill workflow."
---

# permission-check (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/permission-check/SKILL.md](../../skills/permission-check/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/permission-check/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/permission-check`, resolve the symlink target for this wrapper directory first, then read `../../skills/permission-check/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
