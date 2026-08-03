---
name: "pr-on-claim"
description: "Codex wrapper for the ai-config Claude skill `pr-on-claim`. Open a draft PR immediately after claiming an issue \u2014 branch, empty commit, draft PR, claim comment \u2014 before writing any code. Use when asked to 'pr-on-claim', 'open a draft PR for this issue', or after claiming an issue you are about to implement. Use when Codex is asked to use `pr-on-claim`, `/pr-on-claim`, or the corresponding ai-config/Claude skill workflow."
---

# pr-on-claim (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/pr-on-claim/SKILL.md](../../skills/pr-on-claim/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/pr-on-claim/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/pr-on-claim`, resolve the symlink target for this wrapper directory first, then read `../../skills/pr-on-claim/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
