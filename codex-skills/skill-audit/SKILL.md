---
name: "skill-audit"
description: "Codex wrapper for the ai-config Claude skill `skill-audit`. Report which skills in this repo's skills/ directory actually fire (and how often) versus which are installed but never invoked, and recommend pruning candidates. Reads local Claude Code session transcripts as the usage signal (no built-in invocation-telemetry API exists), buckets every skill into actively-used / dormant / dead, and reports a pruning table without deleting anything itself. Use when asked to 'audit skill usage', 'skill-audit', 'which skills are dead weight', 'what skills have I never used', 'find unused skills', 'prune skills by usage', 'skill usage report', or 'which skills should I delete'. Use when Codex is asked to use `skill-audit`, `/skill-audit`, or the corresponding ai-config/Claude skill workflow."
---

# skill-audit (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/skill-audit/SKILL.md](../../skills/skill-audit/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/skill-audit/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/skill-audit`, resolve the symlink target for this wrapper directory first, then read `../../skills/skill-audit/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
