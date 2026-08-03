---
name: "convert-repo-format"
description: "Codex wrapper for the ai-config Claude skill `convert-repo-format`. Convert a repo from one SERG project format to another \u2014 R package, Quarto website, Quarto book, or Quarto manuscript \u2014 using the lab's template repos (`rpt`, `qwt`, `qbt`, `qmt`) as the source of truth for the target's structure. Detect the current format, swap the project config, add/remove format-specific files and CI workflows, adapt `DESCRIPTION`, then verify against the target's checks. Use when asked to 'convert this repo to a <format>', 'crf', 'convert repo format', 'turn this book into a website', 'make this manuscript an R package', 'reformat this repo as a Quarto book', or 'change this repo's project type'. Use when Codex is asked to use `convert-repo-format`, `/convert-repo-format`, or the corresponding ai-config/Claude skill workflow."
---

# convert-repo-format (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/convert-repo-format/SKILL.md](../../skills/convert-repo-format/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/convert-repo-format/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/convert-repo-format`, resolve the symlink target for this wrapper directory first, then read `../../skills/convert-repo-format/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
