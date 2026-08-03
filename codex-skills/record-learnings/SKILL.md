---
name: "record-learnings"
description: "Codex wrapper for the ai-config Claude skill `record-learnings`. Persist discoveries, debugging insights, and working patterns to memory and shared instruction files as you work. Ensures knowledge survives across sessions and is accessible to other AI agents via the shared ai-config repo. Use continuously \u2014 after solving a tricky bug, discovering a codebase convention, or learning a tool quirk. Use when Codex is asked to use `record-learnings`, `/record-learnings`, or the corresponding ai-config/Claude skill workflow."
---

# record-learnings (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/record-learnings/SKILL.md](../../skills/record-learnings/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/record-learnings/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/record-learnings`, resolve the symlink target for this wrapper directory first, then read `../../skills/record-learnings/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
