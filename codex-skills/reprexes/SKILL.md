---
name: "reprexes"
description: "Codex wrapper for the ai-config Claude skill `reprexes`. Isolate a technical problem into a minimal reproducible example (\"reprex\") and iterate fixes on that instead of inside the full application. Use when debugging a bug whose cause isn't obvious after a first look, when a failure only surfaces deep in a large pipeline / app / render, when the full-context test loop is slow, or before filing an upstream issue. Invoke explicitly with /reprexes. Use when Codex is asked to use `reprexes`, `/reprexes`, or the corresponding ai-config/Claude skill workflow."
---

# reprexes (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/reprexes/SKILL.md](../../skills/reprexes/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/reprexes/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/reprexes`, resolve the symlink target for this wrapper directory first, then read `../../skills/reprexes/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
