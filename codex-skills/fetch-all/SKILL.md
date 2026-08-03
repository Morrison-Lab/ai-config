---
name: "fetch-all"
description: "Codex wrapper for the ai-config Claude skill `fetch-all`. Fetch All: run `git fetch` from origin across EVERY git repo under a directory (default: the current dir's immediate children), reporting per-repo status \u2014 up-to-date, updated (with the ref changes), failed (with the error), or skipped (no origin). A read-only sweep: it fetches, it never merges, pulls, or touches your working tree. Use when asked to 'fetch all', 'fa', 'fetch from origin on all repos', 'fetch every repo', 'update all my repos', 'git fetch everywhere', or 'fetch all the repos under <dir>'. Use when Codex is asked to use `fetch-all`, `/fetch-all`, or the corresponding ai-config/Claude skill workflow."
---

# fetch-all (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/fetch-all/SKILL.md](../../skills/fetch-all/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/fetch-all/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/fetch-all`, resolve the symlink target for this wrapper directory first, then read `../../skills/fetch-all/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
