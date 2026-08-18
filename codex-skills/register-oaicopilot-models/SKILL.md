---
name: "register-oaicopilot-models"
description: "Codex wrapper for the ai-config Claude skill `register-oaicopilot-models`. Register new models in the `oai-compatible-copilot` (OAICopilot) VS Code extension's `oaicopilot.models` setting, given a list or screenshot of available models (e.g. a Databricks Model Serving endpoint list). Diffs the requested models against what's already configured, infers each new entry's parameters (context length, max tokens, vision, apiMode, family) from the closest already-configured sibling of the same model family, and appends only the missing entries without disturbing existing ones. Use when asked to 'register these models', 'add these models to oaicopilot', 'register all these models in oaic configuration', 'add these to the model picker', or when handed a list/screenshot of served-model names to make available in GitHub Copilot Chat. Use when Codex is asked to use `register-oaicopilot-models`, `/register-oaicopilot-models`, or the corresponding ai-config/Claude skill workflow."
---

# register-oaicopilot-models (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/register-oaicopilot-models/SKILL.md](../../skills/register-oaicopilot-models/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/register-oaicopilot-models/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/register-oaicopilot-models`, resolve the symlink target for this wrapper directory first, then read `../../skills/register-oaicopilot-models/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
