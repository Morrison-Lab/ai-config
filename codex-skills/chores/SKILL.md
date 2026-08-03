---
name: "chores"
description: "Codex wrapper for the ai-config Claude skill `chores`. Triage and wrap up dependency-bump / `chore(...)` PRs (Dependabot, Renovate, submodule and GitHub-Actions bumps): list the open bump PRs, classify each by bump size, confirm CI is fully green, auto-merge safe patch/minor bumps, and pull the changelog to flag risky major bumps for your call. Accepts an optional target repo. Use when asked to 'handle chores', 'chores', 'do the chores', 'wrap up the chore PRs', 'process the dependabot PRs', 'merge the dependency bumps', 'deal with the bump PRs', or 'handle the dependency updates'. Use when Codex is asked to use `chores`, `/chores`, or the corresponding ai-config/Claude skill workflow."
---

# chores (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/chores/SKILL.md](../../skills/chores/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/chores/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/chores`, resolve the symlink target for this wrapper directory first, then read `../../skills/chores/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
