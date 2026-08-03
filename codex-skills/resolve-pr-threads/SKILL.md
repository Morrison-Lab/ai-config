---
name: "resolve-pr-threads"
description: "Codex wrapper for the ai-config Claude skill `resolve-pr-threads`. Sweep a PR/MR's inline review threads and resolve only the ones that are already genuinely settled (Addressed-and-pushed, Defer-with-issue-linked, Acknowledged, or a Rebut the reviewer didn't re-raise), leaving anything else open for a full `ard` pass. Use when asked to 'resolve pr threads', 'clean up the threads', 'resolve stale threads', or before re-requesting review so old threads don't carry over. Does not disposition new findings \u2014 that's `ard`'s job. Use when Codex is asked to use `resolve-pr-threads`, `/resolve-pr-threads`, or the corresponding ai-config/Claude skill workflow."
---

# resolve-pr-threads (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/resolve-pr-threads/SKILL.md](../../skills/resolve-pr-threads/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/resolve-pr-threads/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/resolve-pr-threads`, resolve the symlink target for this wrapper directory first, then read `../../skills/resolve-pr-threads/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
