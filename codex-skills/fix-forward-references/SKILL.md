---
name: "fix-forward-references"
description: "Codex wrapper for the ai-config Claude skill `fix-forward-references`. Detect and fix forward references in prose \u2014 a cross-reference or phrase (\"see below\", \"as discussed below\", \"in the following section\", \"we'll cover this later\") that points a reader ahead to content they haven't reached yet. Greps for the primary signal of a directional word (below/later/following/subsequently/further down/next/afterward), confirms each hit isn't an idiom or already-backward reference, then rearranges the document (moves the referenced content earlier) or rewords the reference to fix it. Use when asked to 'fix forward references', 'find forward references', 'check for forward references', 'remove forward references', 'fix-forward-references', 'ffr', 'this points ahead to something not written yet', or 'rearrange this so nothing references content below it'. Also runs proactively as part of any PR/MR review that touches narrative prose, alongside `definition-crossrefs.md`'s narrower formal-crossref-div check. Use when Codex is asked to use `fix-forward-references`, `/fix-forward-references`, or the corresponding ai-config/Claude skill workflow."
---

# fix-forward-references (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/fix-forward-references/SKILL.md](../../skills/fix-forward-references/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/fix-forward-references/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/fix-forward-references`, resolve the symlink target for this wrapper directory first, then read `../../skills/fix-forward-references/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
