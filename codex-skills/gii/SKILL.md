---
name: "gii"
description: "Codex wrapper for the ai-config Claude skill `gii`. Grab Issues Iteratively: loop over the repo's open issues \u2014 grab the top one, implement it, open an MR/PR, ARDI it to clean, then recurse to the next issue. Stacks MRs when later issues depend on earlier (unmerged) branches. Use when asked to 'gii', 'gis', 'grab issues', 'work through the backlog', 'keep going', or 'do all the issues'. Use when Codex is asked to use `gii`, `/gii`, or the corresponding ai-config/Claude skill workflow."
---

# gii (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/gii/SKILL.md](../../skills/gii/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/gii/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/gii`, resolve the symlink target for this wrapper directory first, then read `../../skills/gii/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
