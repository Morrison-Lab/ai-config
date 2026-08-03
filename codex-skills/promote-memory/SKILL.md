---
name: "promote-memory"
description: "Codex wrapper for the ai-config Claude skill `promote-memory`. Review staged learning candidates (from learn-staging.md) against explicit criteria \u2014 generality, staleness, redundancy, evidence, format \u2014 and promote the durable ones into committed memory (CLAUDE.md / memories/), discarding or holding the rest. The promotion-gate half of the learn/promote-memory pair. Use when asked to 'promote memory', 'review staged learnings', 'clear out learn-staging', or periodically (e.g. as part of ums) to work through an accumulating staging file. Use when Codex is asked to use `promote-memory`, `/promote-memory`, or the corresponding ai-config/Claude skill workflow."
---

# promote-memory (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/promote-memory/SKILL.md](../../skills/promote-memory/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/promote-memory/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/promote-memory`, resolve the symlink target for this wrapper directory first, then read `../../skills/promote-memory/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
