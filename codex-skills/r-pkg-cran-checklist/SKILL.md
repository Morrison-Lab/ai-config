---
name: "r-pkg-cran-checklist"
description: "Codex wrapper for the ai-config Claude skill `r-pkg-cran-checklist`. Walk through the standard CRAN submission checklist for an R package \u2014 clean R CMD check --as-cran, DESCRIPTION/cran-comments.md, reverse-dependency checks, win-builder/rhub checks, version bump, and a NEWS.md entry. Use when asked to 'r-pkg-cran-checklist', 'prepare for CRAN submission', 'CRAN checklist', or 'is this package ready for CRAN'. Use when Codex is asked to use `r-pkg-cran-checklist`, `/r-pkg-cran-checklist`, or the corresponding ai-config/Claude skill workflow."
---

# r-pkg-cran-checklist (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/r-pkg-cran-checklist/SKILL.md](../../skills/r-pkg-cran-checklist/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/r-pkg-cran-checklist/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/r-pkg-cran-checklist`, resolve the symlink target for this wrapper directory first, then read `../../skills/r-pkg-cran-checklist/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
