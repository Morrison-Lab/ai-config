---
name: "st"
description: "Codex wrapper for the ai-config Claude skill `st`. Start Task (issue-first): kick off a new piece of work the right way \u2014 before writing any code or opening a PR, make sure a tracking issue exists (search the tracker; if none covers it, file one), then branch, implement, open a PR, and ARDI to clean. Use when starting new work that isn't already tied to an open issue, or when asked to 'st', 'start a task', 'start a new task', or 'new task'. Use when Codex is asked to use `st`, `/st`, or the corresponding ai-config/Claude skill workflow."
---

# st (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/st/SKILL.md](../../skills/st/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/st/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/st`, resolve the symlink target for this wrapper directory first, then read `../../skills/st/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
