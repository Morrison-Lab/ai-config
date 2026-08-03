---
name: "link-skills"
description: "Codex wrapper for the ai-config Claude skill `link-skills`. Audit the skills corpus for cross-reference gaps \u2014 pairs of skills that should point to each other under `## Relationship to other skills` but don't. Surfaces asymmetric links (A names B but B omits A), thematic clusters whose members don't reference their siblings, and real skills missing a Relationship section; proposes minimal edits to add the links. Use when asked to 'link skills', 'link-skills', 'cross-link the skills', 'find cross-link opportunities', 'which skills should reference each other', 'audit skill cross-references', or 'find missing skill links'. Use when Codex is asked to use `link-skills`, `/link-skills`, or the corresponding ai-config/Claude skill workflow."
---

# link-skills (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/link-skills/SKILL.md](../../skills/link-skills/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/link-skills/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/link-skills`, resolve the symlink target for this wrapper directory first, then read `../../skills/link-skills/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
