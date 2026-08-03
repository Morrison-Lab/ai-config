---
name: "check-history"
description: "Codex wrapper for the ai-config Claude skill `check-history`. Review the MR/PR history (merged and closed) before starting work on an issue, to ensure proposed changes don't undo past progress or re-introduce previously fixed problems. Use automatically before beginning implementation on any issue or MR \u2014 especially when modifying shared infrastructure, CI templates, or code that has been refactored before. Use when Codex is asked to use `check-history`, `/check-history`, or the corresponding ai-config/Claude skill workflow."
---

# check-history (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/check-history/SKILL.md](../../skills/check-history/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/check-history/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/check-history`, resolve the symlink target for this wrapper directory first, then read `../../skills/check-history/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
