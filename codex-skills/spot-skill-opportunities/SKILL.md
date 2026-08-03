---
name: "spot-skill-opportunities"
description: "Codex wrapper for the ai-config Claude skill `spot-skill-opportunities`. Proactively notice, in the moment and not just at a session-end checkpoint, when a repeatable multi-step workflow, decision framework, tool-integration pattern, or dedicated fan-out worker persona is emerging during ANY task \u2014 then surface it as a candidate skill (or agent) and hand off to skill-builder or agent-builder, rather than quietly repeating the same hand-rolled steps next time. This is the recognition step; skill-builder and agent-builder are the construction steps. Use continuously, whenever you catch yourself repeating a multi-step dance done earlier in this session or a prior one, improvising a workaround for something that will recur, or the user says 'again', 'like last time', 'we did this before', or 'always do X'. Also fires as a standing checklist item inside record-learnings, ums, wrap-up, and post-merge. Use when Codex is asked to use `spot-skill-opportunities`, `/spot-skill-opportunities`, or the corresponding ai-config/Claude skill workflow."
---

# spot-skill-opportunities (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/spot-skill-opportunities/SKILL.md](../../skills/spot-skill-opportunities/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/spot-skill-opportunities/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/spot-skill-opportunities`, resolve the symlink target for this wrapper directory first, then read `../../skills/spot-skill-opportunities/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
