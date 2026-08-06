---
name: "do-as-you-think-best"
description: "Codex wrapper for the ai-config Claude skill `do-as-you-think-best`. Alias for `daytb`. Decide the question in front of you yourself instead of asking, then report what you chose -- scoped to the task at hand, not the session. Use when asked to 'do as you think best', 'do as you see fit', 'your call', 'you decide', or 'up to you'. Use when Codex is asked to use `do-as-you-think-best`, `/do-as-you-think-best`, or the corresponding ai-config/Claude skill workflow."
---

# do-as-you-think-best (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/do-as-you-think-best/SKILL.md](../../skills/do-as-you-think-best/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/do-as-you-think-best/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/do-as-you-think-best`, resolve the symlink target for this wrapper directory first, then read `../../skills/do-as-you-think-best/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
