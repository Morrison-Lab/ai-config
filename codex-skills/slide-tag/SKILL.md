---
name: "slide-tag"
description: "Codex wrapper for the ai-config Claude skill `slide-tag`. Force-move a floating Git tag (e.g., v2) to a new commit \u2014 typically current main HEAD. Handles fetch, safety checks, delete+recreate pattern. Use when asked to 'slide <tag>', 'move tag to main', 'update the v2 tag', or 'bump the floating tag'. Use when Codex is asked to use `slide-tag`, `/slide-tag`, or the corresponding ai-config/Claude skill workflow."
---

# slide-tag (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/slide-tag/SKILL.md](../../skills/slide-tag/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/slide-tag/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/slide-tag`, resolve the symlink target for this wrapper directory first, then read `../../skills/slide-tag/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
