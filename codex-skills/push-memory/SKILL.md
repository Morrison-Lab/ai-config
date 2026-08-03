---
name: "push-memory"
description: "Codex wrapper for the ai-config Claude skill `push-memory`. Push a general-purpose memory into the ai-config repo when you're working primarily in ANOTHER repo \u2014 a `CLAUDE.md` standing rule or a `memories/*.md` reference fact \u2014 delivered on its own branch + PR (or via the GitHub file API) without disturbing the repo you're in. Use when the user says 'push this to ai-config', 'remember this globally from here', 'add this to ai-config's memory / CLAUDE.md', 'record this in ai-config even though we're in <other repo>', or '/push-memory'. For the normal case where ai-config IS your working repo, use `memorize` instead. Use when Codex is asked to use `push-memory`, `/push-memory`, or the corresponding ai-config/Claude skill workflow."
---

# push-memory (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/push-memory/SKILL.md](../../skills/push-memory/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/push-memory/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/push-memory`, resolve the symlink target for this wrapper directory first, then read `../../skills/push-memory/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
