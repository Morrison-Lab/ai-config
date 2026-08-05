---
name: "config-ai"
description: "Codex wrapper for the ai-config Claude skill `config-ai`. Extend AI capabilities via the ai-config and/or gha repos -- given a stated capability ('teach Claude to X', 'add an AI capability for Y'), determine on the fly which implementation form fits (skill, subagent, memory/preference, harness hook, shared prompt fragment, or a gha reusable GitHub Actions capability / bot-workflow tweak) and dispatch to the specific builder skill -- or gha's composite-action + workflow_call convention -- that builds it. Falls back to filing a fully-specified issue on the target repo (or, if even that's unreachable, on the current repo for later transfer) when the session can't push there. Use when asked to 'config-ai', 'ca', 'cai', 'extend AI capabilities', 'add an AI capability', 'teach Claude to do X', 'give Claude the ability to X', or when a request names a desired behavior but not a mechanism. Use when Codex is asked to use `config-ai`, `/config-ai`, or the corresponding ai-config/Claude skill workflow."
---

# config-ai (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/config-ai/SKILL.md](../../skills/config-ai/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/config-ai/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/config-ai`, resolve the symlink target for this wrapper directory first, then read `../../skills/config-ai/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
