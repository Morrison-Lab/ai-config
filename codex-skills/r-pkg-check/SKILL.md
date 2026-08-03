---
name: "r-pkg-check"
description: "Codex wrapper for the ai-config Claude skill `r-pkg-check`. Run devtools::check() / R CMD check on an R package before a release, triage the NOTEs/WARNINGs/ERRORs it reports, and re-run to confirm clean. Use when asked to 'r-pkg-check', 'run R CMD check', 'run devtools::check', 'check this R package before release', or before submitting to CRAN. Use when Codex is asked to use `r-pkg-check`, `/r-pkg-check`, or the corresponding ai-config/Claude skill workflow."
---

# r-pkg-check (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/r-pkg-check/SKILL.md](../../skills/r-pkg-check/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/r-pkg-check/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/r-pkg-check`, resolve the symlink target for this wrapper directory first, then read `../../skills/r-pkg-check/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
