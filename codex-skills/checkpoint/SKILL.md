---
name: "checkpoint"
description: "Codex wrapper for the ai-config Claude skill `checkpoint`. Save a deliberate, mid-task stop-point snapshot \u2014 plan state, decisions made so far, file:line pointers, and next actions \u2014 without ending or pausing the session. Use when asked to 'checkpoint', 'save a checkpoint', 'snapshot where we are', or proactively right before a risky/hard-to-reverse step, after finishing a major phase of a long task, or before a long-running operation you might not be present to see finish. Use when Codex is asked to use `checkpoint`, `/checkpoint`, or the corresponding ai-config/Claude skill workflow."
---

# checkpoint (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/checkpoint/SKILL.md](../../skills/checkpoint/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/checkpoint/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/checkpoint`, resolve the symlink target for this wrapper directory first, then read `../../skills/checkpoint/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
