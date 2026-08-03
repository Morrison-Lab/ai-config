---
name: "brainstorm"
description: "Codex wrapper for the ai-config Claude skill `brainstorm`. Pre-implementation Socratic Q&A: run a short multi-round clarifying-question loop with the user before any code is written or issue is filed, then write the agreed approach to a plan file. Use when asked to 'brainstorm', 'brainstorm this', 'let's brainstorm', 'plan this out first', or when a request is vague enough that jumping straight to an issue or PR would lock in the wrong scope. Use when Codex is asked to use `brainstorm`, `/brainstorm`, or the corresponding ai-config/Claude skill workflow."
---

# brainstorm (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/brainstorm/SKILL.md](../../skills/brainstorm/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/brainstorm/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/brainstorm`, resolve the symlink target for this wrapper directory first, then read `../../skills/brainstorm/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
