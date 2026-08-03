---
name: "mma"
description: "Codex wrapper for the ai-config Claude skill `mma`. Merge main into all open PR branches in the current repo. For every open PR, fetch, merge origin/main (and origin/<branch>) in, resolve conflicts, run the repo's pre-commit checks, and push \u2014 reusing sync-pr-branch's per-branch procedure, looped across the whole open-PR queue. Use on \"merge main into all pr branches\", \"sync every open PR with main\", \"mma\", or when several PRs have all drifted behind main at once (e.g. after a run of merges) and need resyncing in one pass. Use when Codex is asked to use `mma`, `/mma`, or the corresponding ai-config/Claude skill workflow."
---

# mma (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/mma/SKILL.md](../../skills/mma/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/mma/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/mma`, resolve the symlink target for this wrapper directory first, then read `../../skills/mma/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
