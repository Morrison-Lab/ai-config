---
name: "clean-worktrees"
description: "Codex wrapper for the ai-config Claude skill `clean-worktrees`. Clean Worktrees: sweep dead git worktrees in the current repo \u2014 prune admin stubs for already-deleted dirs, then remove linked worktrees whose branch merged into main (or is gone) and whose tree is clean. Never touches the main or current worktree, a dirty tree, a locked worktree, or one with a live session-lock session. Presents a dry-run plan first. Use when asked to 'clean worktrees', 'cw', 'prune worktrees', 'clean dead worktrees', 'remove stale worktrees', or 'tidy up worktrees'. Use when Codex is asked to use `clean-worktrees`, `/clean-worktrees`, or the corresponding ai-config/Claude skill workflow."
---

# clean-worktrees (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/clean-worktrees/SKILL.md](../../skills/clean-worktrees/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/clean-worktrees/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/clean-worktrees`, resolve the symlink target for this wrapper directory first, then read `../../skills/clean-worktrees/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
