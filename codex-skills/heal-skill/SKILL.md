---
name: "heal-skill"
description: "Codex wrapper for the ai-config Claude skill `heal-skill`. Repair a skill that just misfired \u2014 fired when it shouldn't have, failed to fire when it should have, or led the session astray. Diagnose the root cause from where the session got confused, propose a minimal fix to the skill's trigger/description/body, and apply it with the user's approval. Use when the user says \"that skill confused you\", \"heal that skill\", \"fix the skill that misfired\", \"that shouldn't have triggered\", or right after a skill visibly went wrong. Invoke explicitly with /heal-skill. Use when Codex is asked to use `heal-skill`, `/heal-skill`, or the corresponding ai-config/Claude skill workflow."
---

# heal-skill (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/heal-skill/SKILL.md](../../skills/heal-skill/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/heal-skill/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/heal-skill`, resolve the symlink target for this wrapper directory first, then read `../../skills/heal-skill/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
