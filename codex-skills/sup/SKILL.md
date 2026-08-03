---
name: "sup"
description: "Codex wrapper for the ai-config Claude skill `sup`. Send to Upstream: file an issue or open a PR on an upstream repo (a fork's parent, a dependency, or any external project). Use when you've found a bug, want to propose a fix, or need to request a feature in a project you don't own. Handles both 'just report it' (issue) and 'here's the fix' (PR) workflows. Use when asked to 'sup', 'send upstream', 'file upstream issue', 'upstream PR', 'contribute this fix back', or 'report this bug upstream'. Use when Codex is asked to use `sup`, `/sup`, or the corresponding ai-config/Claude skill workflow."
---

# sup (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/sup/SKILL.md](../../skills/sup/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/sup/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/sup`, resolve the symlink target for this wrapper directory first, then read `../../skills/sup/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
