---
name: "prompt-me"
description: "Codex wrapper for the ai-config Claude skill `prompt-me`. Surface the single most pressing open question still waiting on user input \u2014 or, with a numeric argument, that many of the most pressing ones \u2014 instead of leaving it buried under unrelated work in the transcript. Use when asked to 'prompt me', 'pm', 'prompt me 3', 'pm 3', 'what are you waiting on me for', 'what do you need from me', 'remind me what you asked', or '/prompt-me [N]'. For every open question at once, use `prompt-me-all` / `pma` instead. Use when Codex is asked to use `prompt-me`, `/prompt-me`, or the corresponding ai-config/Claude skill workflow."
---

# prompt-me (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/prompt-me/SKILL.md](../../skills/prompt-me/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/prompt-me/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/prompt-me`, resolve the symlink target for this wrapper directory first, then read `../../skills/prompt-me/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
