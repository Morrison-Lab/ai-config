---
name: "recover-followups"
description: "Codex wrapper for the ai-config Claude skill `recover-followups`. Retrieve untracked follow-up items from closed PRs and issues. Sweeps their bodies, comments, review threads, and ARD 'Deferred'/'Acknowledged' summaries for promised future work, then cross-references against open issues and surfaces (and offers to file) the ones never tracked. Use when asked to 'recover followups', 'rfu', 'find untracked followups', 'audit closed PRs for dropped follow-ups', 'what follow-ups slipped through', or 'did we lose any deferred work?'. Use when Codex is asked to use `recover-followups`, `/recover-followups`, or the corresponding ai-config/Claude skill workflow."
---

# recover-followups (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/recover-followups/SKILL.md](../../skills/recover-followups/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/recover-followups/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/recover-followups`, resolve the symlink target for this wrapper directory first, then read `../../skills/recover-followups/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
