---
name: "purge-hallucinations"
description: "Codex wrapper for the ai-config Claude skill `purge-hallucinations`. Audit a target for hallucinations \u2014 concrete, checkable references that don't actually resolve (a missing file path, an undefined R function/object, a non-existent `uses:` action ref or version, a dead URL, a `[[memory-link]]` with no target, a fabricated skill name, citation, package, flag, config key, or SDK method) \u2014 then interactively propose a fix for each one. Conservative: only flags references PROVEN absent; unverifiable \u2260 hallucination. Scope is any of the memory/instruction corpus (ai-config memories/, skills/, CLAUDE.md), the current repo's code & docs, or an explicit file / PR diff / pasted AI output. Use when asked to 'purge hallucinations', 'ph', 'check for hallucinations', 'verify the references', 'find made-up / fabricated references', 'fact-check this AI output', 'does everything in this file actually exist', 'audit my memories for stale references', or 'what did you make up'. Use when Codex is asked to use `purge-hallucinations`, `/purge-hallucinations`, or the corresponding ai-config/Claude skill workflow."
---

# purge-hallucinations (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/purge-hallucinations/SKILL.md](../../skills/purge-hallucinations/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/purge-hallucinations/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/purge-hallucinations`, resolve the symlink target for this wrapper directory first, then read `../../skills/purge-hallucinations/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
