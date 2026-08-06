---
name: "daytb"
description: "Codex wrapper for the ai-config Claude skill `daytb`. Decide the question in front of you yourself instead of asking, then report what you chose. A per-decision grant of judgment latitude, scoped to the task at hand rather than the session -- the user stays present and reachable. Use when asked to 'daytb', 'do as you think best', 'do as you see fit', 'do whatever you think is best', 'your call', 'you decide', 'up to you', 'I trust your judgment here', or when a reply hands a pending decision back without answering it. Use when Codex is asked to use `daytb`, `/daytb`, or the corresponding ai-config/Claude skill workflow."
---

# daytb (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/daytb/SKILL.md](../../skills/daytb/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/daytb/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/daytb`, resolve the symlink target for this wrapper directory first, then read `../../skills/daytb/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
