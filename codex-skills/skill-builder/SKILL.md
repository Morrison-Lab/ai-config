---
name: "skill-builder"
description: "Codex wrapper for the ai-config Claude skill `skill-builder`. Build a new skill for the ai-config repo the right way -- FIRST check whether an existing skill should be extended instead (search skills/, scripts/, and hooks/, scan every branch for in-flight similar work, AND check open PRs for in-progress drafts to redirect to instead of duplicating), and only then scaffold skills/<name>/SKILL.md with proper frontmatter, a discoverable trigger-rich description, a spelled-out/short alias as appropriate, cross-links, and (if it encodes a standing rule) matching preferences.md / CLAUDE.md updates -- shipped via branch + PR, reviewer requested, ARDI'd to clean. Use when asked to 'build a skill', 'create a skill', 'make a new skill', 'add a skill', 'add an alias for X', 'make X an alias for Y', 'should this be an alias for Y', or 'skill-builder' -- creating an alias stub routes here too, so the codex wrapper gets regenerated and the stub is self-reviewed. Use when Codex is asked to use `skill-builder`, `/skill-builder`, or the corresponding ai-config/Claude skill workflow."
---

# skill-builder (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/skill-builder/SKILL.md](../../skills/skill-builder/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/skill-builder/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/skill-builder`, resolve the symlink target for this wrapper directory first, then read `../../skills/skill-builder/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
