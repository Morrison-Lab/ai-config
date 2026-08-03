---
name: "find-overlap"
description: "Codex wrapper for the ai-config Claude skill `find-overlap`. Read-only detector of overlapping or redundant content across a corpus \u2014 skills, memories, docs, prose, or any file set. Clusters comparable units by similarity, classifies each cluster as intentional-alias / adjacent-but-distinct / genuine-duplicate, and reports each with similarity evidence and a recommended disposition (merge / cross-link / leave-distinct) routed to the right action skill. Detects and reports only \u2014 never edits, merges, or deletes. Use when asked to 'find overlap', 'find overlapping skills', 'find overlapping content', 'find duplicates', 'find redundant content', 'audit for duplication', 'dedupe audit', \"what's redundant here\", or 'where do these overlap'. Invoke explicitly with /find-overlap. Use when Codex is asked to use `find-overlap`, `/find-overlap`, or the corresponding ai-config/Claude skill workflow."
---

# find-overlap (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/find-overlap/SKILL.md](../../skills/find-overlap/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/find-overlap/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/find-overlap`, resolve the symlink target for this wrapper directory first, then read `../../skills/find-overlap/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
