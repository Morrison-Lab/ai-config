---
name: "sync-pr-branch"
description: "Codex wrapper for the ai-config Claude skill `sync-pr-branch`. Sync an active PR branch with both `main` and its own remote -- fetch origin, verify its PR has not already merged, merge origin/main into the branch, merge origin/<current-branch> into local (reconciling commits pushed elsewhere, e.g. by the @claude bot or another machine), then resolve conflicts, run the repo's pre-commit checks, and push. Use before triggering a review or pushing fixes, on \"sync\", \"update the branch\", \"merge main in\", \"resync the branch\", \"reconcile local and remote\", \"the branch is behind main\", or whenever main or the remote branch has moved ahead. Use when Codex is asked to use `sync-pr-branch`, `/sync-pr-branch`, or the corresponding ai-config/Claude skill workflow."
---

# sync-pr-branch (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/sync-pr-branch/SKILL.md](../../skills/sync-pr-branch/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/sync-pr-branch/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/sync-pr-branch`, resolve the symlink target for this wrapper directory first, then read `../../skills/sync-pr-branch/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
