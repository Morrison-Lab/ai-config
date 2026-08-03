---
name: "away"
description: "Codex wrapper for the ai-config Claude skill `away`. Grant standing session-scoped permission to stop asking clarifying questions and operate unattended for the rest of the session \u2014 e.g. when the user is about to be unavailable for a while. Use best judgment to pick work you're confident about, defer or skip work that's genuinely ambiguous instead of blocking on it, and consult a stronger/more capable model for a second opinion when one is available instead of surfacing a question. Use when asked to 'away', 'I'll be away for a while', 'going offline', 'don't ask me anything', 'use your best judgment', 'operate autonomously', 'no questions mode', or similar standing 'stop blocking on me' grants. Use when Codex is asked to use `away`, `/away`, or the corresponding ai-config/Claude skill workflow."
---

# away (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/away/SKILL.md](../../skills/away/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/away/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/away`, resolve the symlink target for this wrapper directory first, then read `../../skills/away/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
