---
name: "r-pkg-news"
description: "Codex wrapper for the ai-config Claude skill `r-pkg-news`. Draft a new NEWS.md entry for an R package from recent commits or a PR description, matching the package's existing entry style. Use when asked to 'r-pkg-news', 'update NEWS.md', 'write a NEWS entry', or 'add a changelog entry for this R package'. Use when Codex is asked to use `r-pkg-news`, `/r-pkg-news`, or the corresponding ai-config/Claude skill workflow."
---

# r-pkg-news (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/r-pkg-news/SKILL.md](../../skills/r-pkg-news/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/r-pkg-news/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/r-pkg-news`, resolve the symlink target for this wrapper directory first, then read `../../skills/r-pkg-news/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
