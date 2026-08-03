---
name: "r-pkg-spellcheck"
description: "Codex wrapper for the ai-config Claude skill `r-pkg-spellcheck`. Run R-package spellcheck before pushing changes that touch user-facing text (NEWS.md, .Rd, .Rmd, roxygen comments, vignettes). Use before `git push` in any R-package repo, or when the user asks to spellcheck. Use when Codex is asked to use `r-pkg-spellcheck`, `/r-pkg-spellcheck`, or the corresponding ai-config/Claude skill workflow."
---

# r-pkg-spellcheck (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/r-pkg-spellcheck/SKILL.md](../../skills/r-pkg-spellcheck/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/r-pkg-spellcheck/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/r-pkg-spellcheck`, resolve the symlink target for this wrapper directory first, then read `../../skills/r-pkg-spellcheck/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
