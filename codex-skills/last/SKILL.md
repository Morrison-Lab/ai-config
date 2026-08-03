---
name: "last"
description: "Codex wrapper for the ai-config Claude skill `last`. Queue the instructions that follow `/last` after every other task \u2014 and keep them last even as new `/also` tasks arrive. Only another `/last` goes after a previous `/last`. Use when a task must run at the very end regardless of what else gets added (final render, commit-and-push, cleanup, wrap-up). Invoke explicitly with /last. Use when Codex is asked to use `last`, `/last`, or the corresponding ai-config/Claude skill workflow."
---

# last (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/last/SKILL.md](../../skills/last/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/last/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/last`, resolve the symlink target for this wrapper directory first, then read `../../skills/last/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
