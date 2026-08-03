---
name: "prompt-me-all"
description: "Codex wrapper for the ai-config Claude skill `prompt-me-all`. Restate every open question still waiting on user input \u2014 anything asked earlier in the conversation that hasn't been answered yet \u2014 as a single, clearly numbered list, instead of leaving it scattered across the transcript. Use when asked to 'prompt me all', 'promptmeall', 'pma', or '/prompt-me-all'. For just the single most pressing question (or a requested top N), use `prompt-me` / `pm` instead. Use when Codex is asked to use `prompt-me-all`, `/prompt-me-all`, or the corresponding ai-config/Claude skill workflow."
---

# prompt-me-all (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/prompt-me-all/SKILL.md](../../skills/prompt-me-all/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/prompt-me-all/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/prompt-me-all`, resolve the symlink target for this wrapper directory first, then read `../../skills/prompt-me-all/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
