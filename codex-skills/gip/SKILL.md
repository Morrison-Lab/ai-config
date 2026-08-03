---
name: "gip"
description: "Codex wrapper for the ai-config Claude skill `gip`. Grab Issues in Parallel: grab several provably-independent open issues and work them concurrently \u2014 one worktree-isolated subagent per issue, each implementing its issue, opening an MR/PR, and ARDI-ing it to clean. The parallel counterpart to the deliberately-serial `gii`. Use when asked to 'gip', 'grab issues in parallel', 'work several issues at once', 'parallelize the backlog', 'do these issues concurrently', or 'fan out the issue queue'. Use when Codex is asked to use `gip`, `/gip`, or the corresponding ai-config/Claude skill workflow."
---

# gip (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/gip/SKILL.md](../../skills/gip/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/gip/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/gip`, resolve the symlink target for this wrapper directory first, then read `../../skills/gip/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
