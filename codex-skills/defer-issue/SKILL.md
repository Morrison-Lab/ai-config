---
name: "defer-issue"
description: "Codex wrapper for the ai-config Claude skill `defer-issue`. File a follow-up issue (GitHub via `gh`, GitLab via `glab`) when the user defers work out of the current scope. Use when the user says \"defer this\", \"followup issue for X\", \"let's handle this in a separate PR\", or otherwise asks to push work to later. Use when Codex is asked to use `defer-issue`, `/defer-issue`, or the corresponding ai-config/Claude skill workflow."
---

# defer-issue (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/defer-issue/SKILL.md](../../skills/defer-issue/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/defer-issue/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/defer-issue`, resolve the symlink target for this wrapper directory first, then read `../../skills/defer-issue/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
