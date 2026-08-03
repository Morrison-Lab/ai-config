---
name: "prefer-upstream"
description: "Codex wrapper for the ai-config Claude skill `prefer-upstream`. Before building custom implementations, check r-lib, tidyverse, and similar ecosystem organizations for off-the-shelf solutions. Prefer well-maintained upstream packages over hand-rolled code. Use when about to write utility functions, parsers, CI helpers, or anything that 'feels like someone must have solved this already.' Use when Codex is asked to use `prefer-upstream`, `/prefer-upstream`, or the corresponding ai-config/Claude skill workflow."
---

# prefer-upstream (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/prefer-upstream/SKILL.md](../../skills/prefer-upstream/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/prefer-upstream/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/prefer-upstream`, resolve the symlink target for this wrapper directory first, then read `../../skills/prefer-upstream/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
