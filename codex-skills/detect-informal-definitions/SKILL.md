---
name: "detect-informal-definitions"
description: "Codex wrapper for the ai-config Claude skill `detect-informal-definitions`. Detect concepts introduced with definition-grade precision --- a named term, an equation, an `\\eqdef` --- that never got wrapped in the project's formal definition construct (a Quarto `#def-`/`#thm-`-style crossref div, or the equivalent glossary/docstring convention elsewhere), so it has no stable id and nothing downstream can cite it. Greps for a bolded term followed by defining language, or a naming sentence ending 'is:'/'are:' right before a display equation, then confirms each hit isn't a reused already-defined term, a tool-usage aside, or part of a deliberately informal list --- before proposing a formal div, a worked example, and updated citations. Use when asked to 'detect informal definitions', 'find informal definitions', 'check for missing definitions', 'is this concept formally defined', or 'detect-informal-definitions'. Also runs proactively in any PR/MR review that introduces new technical content. Use when Codex is asked to use `detect-informal-definitions`, `/detect-informal-definitions`, or the corresponding ai-config/Claude skill workflow."
---

# detect-informal-definitions (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/detect-informal-definitions/SKILL.md](../../skills/detect-informal-definitions/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/detect-informal-definitions/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/detect-informal-definitions`, resolve the symlink target for this wrapper directory first, then read `../../skills/detect-informal-definitions/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
