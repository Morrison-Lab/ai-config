---
name: "pr-status-all"
description: "Codex wrapper for the ai-config Claude skill `pr-status-all`. Print a table summarizing the true status of every open PR in the repo --- for each one, read the LATEST review comment (not a cached verdict) and parse it for remaining findings, alongside CI state and whether the branch is behind main. Gathers the per-PR signals concurrently (one subagent per PR). Use when asked \"summarize all open PRs\", \"status table of my PRs\", \"what's the state of every PR\", \"give me a PR dashboard\", or any whole-queue status overview. For a single PR use `pr-status`; to actually drive PRs to clean use `ardia`. Use when Codex is asked to use `pr-status-all`, `/pr-status-all`, or the corresponding ai-config/Claude skill workflow."
---

# pr-status-all (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/pr-status-all/SKILL.md](../../skills/pr-status-all/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/pr-status-all/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/pr-status-all`, resolve the symlink target for this wrapper directory first, then read `../../skills/pr-status-all/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
