---
name: "learn"
description: "Codex wrapper for the ai-config Claude skill `learn`. Log a candidate learning to a lightweight, local staging file \u2014 without deciding yet whether it's durable enough for committed memory. The low-friction counterpart to record-learnings/memorize: jot it down now, let promote-memory vet it later. Use when asked to 'log a learning', 'stage this as a learning', 'note this for later', or proactively for a discovery that might matter but you're not yet sure it's general/durable enough to commit directly. Use when Codex is asked to use `learn`, `/learn`, or the corresponding ai-config/Claude skill workflow."
---

# learn (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/learn/SKILL.md](../../skills/learn/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/learn/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/learn`, resolve the symlink target for this wrapper directory first, then read `../../skills/learn/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
