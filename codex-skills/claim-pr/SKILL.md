---
name: "claim-pr"
description: "Codex wrapper for the ai-config Claude skill `claim-pr`. Post a 'paws off' claim comment on a PR/MR or issue before starting a work session on it, and resolve/unclaim when done, so other humans and the @claude CI bot don't start a colliding parallel session. Use before fetching a branch, editing, or running review cycles on a PR/issue \u2014 and after the work is paused, merged, or closed. Use when Codex is asked to use `claim-pr`, `/claim-pr`, or the corresponding ai-config/Claude skill workflow."
---

# claim-pr (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/claim-pr/SKILL.md](../../skills/claim-pr/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/claim-pr/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/claim-pr`, resolve the symlink target for this wrapper directory first, then read `../../skills/claim-pr/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
