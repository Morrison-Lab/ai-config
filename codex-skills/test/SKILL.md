---
name: "test"
description: "Codex wrapper for the ai-config Claude skill `test`. Test an MR's changes \u2014 run unit tests in the current repo if available, or trigger a downstream pipeline in a revdep test bed (e.g., test.hac). Use when asked to 'test this MR', 'run tests', 'verify downstream', or 'check this in test.hac'. Use when Codex is asked to use `test`, `/test`, or the corresponding ai-config/Claude skill workflow."
---

# test (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/test/SKILL.md](../../skills/test/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/test/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/test`, resolve the symlink target for this wrapper directory first, then read `../../skills/test/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
