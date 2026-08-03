---
name: "configure-gitattributes"
description: "Codex wrapper for the ai-config Claude skill `configure-gitattributes`. Configure or audit a repo's .gitattributes for common cases: union-merge for changelog/news files that almost always want both sides kept, line-ending normalization for shell scripts, marking generated trees so they don't count as source in diffs/language stats, and vendored/binary handling. Use when asked to 'configure gitattributes', 'set up .gitattributes', 'fix line endings', 'stop CHANGELOG merge conflicts', 'mark this as generated', or after a recurring merge-conflict pattern on a specific file suggests a merge-driver fix. Use when Codex is asked to use `configure-gitattributes`, `/configure-gitattributes`, or the corresponding ai-config/Claude skill workflow."
---

# configure-gitattributes (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/configure-gitattributes/SKILL.md](../../skills/configure-gitattributes/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/configure-gitattributes/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/configure-gitattributes`, resolve the symlink target for this wrapper directory first, then read `../../skills/configure-gitattributes/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
