---
name: "delegate-to-codex"
description: "Codex wrapper for the ai-config Claude skill `delegate-to-codex`. Delegate heavy read/draft/verify work to the `codex` CLI (a separately-billed ChatGPT-plan subagent) before spending Claude quota \u2014 build the prompts, run codex read-only, orchestrate multi-item work via a background runner + DONE-marker poll with a `--output-schema`, detect 5-hour usage-limit exhaustion, and fall back to Claude only for what codex can't finish. Use when asked to 'delegate to codex', 'use codex', 'run this on codex', 'dtc', 'codex-first', 'do this with codex', 'offload to codex', or before a heavy fan-out read/analysis/verify pass that would otherwise burn Claude/Workflow tokens. Use when Codex is asked to use `delegate-to-codex`, `/delegate-to-codex`, or the corresponding ai-config/Claude skill workflow."
---

# delegate-to-codex (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/delegate-to-codex/SKILL.md](../../skills/delegate-to-codex/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/delegate-to-codex/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/delegate-to-codex`, resolve the symlink target for this wrapper directory first, then read `../../skills/delegate-to-codex/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
