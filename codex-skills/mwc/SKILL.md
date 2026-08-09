---
name: "mwc"
description: "Codex wrapper for the ai-config Claude skill `mwc`. Grant standing session-scoped permission to merge fully-clean PRs autonomously, without asking per PR, for the rest of the current session; also records the one standing per-repository grant (PRs targeting Morrison-Lab/ai-config), which needs no session step. Use when the user says 'merge when confident', 'mwc', 'merge at will', 'maw', 'you can merge PRs when you're confident', or otherwise grants a forward-looking, session-wide or repo-wide merge exception. Use when Codex is asked to use `mwc`, `/mwc`, or the corresponding ai-config/Claude skill workflow."
---

# mwc (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/mwc/SKILL.md](../../skills/mwc/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/mwc/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/mwc`, resolve the symlink target for this wrapper directory first, then read `../../skills/mwc/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
