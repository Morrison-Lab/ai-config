---
name: "agent-builder"
description: "Codex wrapper for the ai-config Claude skill `agent-builder`. Build a new fan-out subagent under `.claude/agents/<name>.md` for a skill that needs one \u2014 FIRST check whether an existing agent (dependency-auditor, hallucination-detector, community-demand-scout) should be reused or extended instead, or an open PR is already building one to redirect to, and only then scaffold a new agent definition with a tight `tools:` list, a role-scoped system prompt, and an explicit boundary statement, paired with exactly one skill that spawns it. Read-only/no-mutate (scout) is the default archetype, but bounded-worker (Edit/Write for one scoped implementation task), critic, and paranoid-reviewer archetypes are also covered \u2014 see 'Worker-role archetypes' below. Use when asked to 'build an agent', 'create a subagent', 'make a new agent', 'add an agent', 'agent-builder', or when a heavy skill's fan-out step needs a dedicated worker persona instead of an inline Agent() prompt. Use when Codex is asked to use `agent-builder`, `/agent-builder`, or the corresponding ai-config/Claude skill workflow."
---

# agent-builder (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/agent-builder/SKILL.md](../../skills/agent-builder/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/agent-builder/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/agent-builder`, resolve the symlink target for this wrapper directory first, then read `../../skills/agent-builder/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
