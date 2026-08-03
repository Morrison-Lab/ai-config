---
name: "consolidate-memory"
description: "Codex wrapper for the ai-config Claude skill `consolidate-memory`. Merge two or more genuinely-redundant memory entries in the `memories/` corpus into a single canonical entry \u2014 union the facts, keep one copy in the right scope, and repoint any `[[links]]` \u2014 so the corpus shrinks without losing a fact or a cross-reference. Delegates detection to `find-overlap` (scope = `memories/`), proposes a plan for approval, then ships it via branch + PR. The memory-corpus counterpart of `consolidate-skills`. Use when asked to \"consolidate memory\", \"consolidate memories\", \"merge duplicate memories\", \"dedupe memories\", or \"collapse redundant memory entries\". Invoke explicitly with /consolidate-memory. Use when Codex is asked to use `consolidate-memory`, `/consolidate-memory`, or the corresponding ai-config/Claude skill workflow."
---

# consolidate-memory (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/consolidate-memory/SKILL.md](../../skills/consolidate-memory/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/consolidate-memory/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/consolidate-memory`, resolve the symlink target for this wrapper directory first, then read `../../skills/consolidate-memory/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
