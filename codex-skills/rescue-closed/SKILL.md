---
name: "rescue-closed"
description: "Codex wrapper for the ai-config Claude skill `rescue-closed`. Search the graveyard of closed issues and closed-but-unmerged PRs to surface the ones worth returning to \u2014 abandoned, stale-bot-closed, closed-as-not-planned, or superseded-but-never-landed \u2014 then triage, reopen, or re-file the keepers with current context. Use when asked to 'rescue closed issues', 'revive a closed PR', 'reopen abandoned work', 'what closed issues/PRs should we revisit', 'comb the graveyard', 'resurrect stale issues', 'salvage abandoned PRs', or 'rescue-closed'. Use when Codex is asked to use `rescue-closed`, `/rescue-closed`, or the corresponding ai-config/Claude skill workflow."
---

# rescue-closed (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/rescue-closed/SKILL.md](../../skills/rescue-closed/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/rescue-closed/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/rescue-closed`, resolve the symlink target for this wrapper directory first, then read `../../skills/rescue-closed/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
