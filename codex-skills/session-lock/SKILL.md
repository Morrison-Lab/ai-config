---
name: "session-lock"
description: "Codex wrapper for the ai-config Claude skill `session-lock`. Deconflict multiple AI agent sessions working the same local repo checkout. Maintains a machine-local registry (under .git/) of active sessions so parallel Claude Code / Copilot / other sessions can see each other, refuse to clobber the same working tree or branch, isolate into a git worktree, and recover after a crash. Use when starting a write session on a repo that other local sessions may also have open, when asked to 'deconflict sessions', 'avoid stepping on another session', 'lock the worktree', or before edits/commits in a shared checkout. The LOCAL counterpart to claim-pr (which deconflicts via GitHub/GitLab comments). Use when Codex is asked to use `session-lock`, `/session-lock`, or the corresponding ai-config/Claude skill workflow."
---

# session-lock (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/session-lock/SKILL.md](../../skills/session-lock/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/session-lock/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/session-lock`, resolve the symlink target for this wrapper directory first, then read `../../skills/session-lock/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
