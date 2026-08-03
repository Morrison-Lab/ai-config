---
name: "workaround-watcher"
description: "Codex wrapper for the ai-config Claude skill `workaround-watcher`. Scaffold a scheduled GitHub Actions workflow that watches an upstream issue/PR you're blocked on and, when it's fixed (closed-as-completed / merged), auto-opens a PR reverting your local workaround back to a committed \"target\" template. Use when you add a temporary workaround for an upstream bug and want to be reminded \u2014 with the revert pre-drafted \u2014 once it's resolved, instead of the workaround silently outliving its reason. Use when Codex is asked to use `workaround-watcher`, `/workaround-watcher`, or the corresponding ai-config/Claude skill workflow."
---

# workaround-watcher (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/workaround-watcher/SKILL.md](../../skills/workaround-watcher/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/workaround-watcher/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/workaround-watcher`, resolve the symlink target for this wrapper directory first, then read `../../skills/workaround-watcher/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
