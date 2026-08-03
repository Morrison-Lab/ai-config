---
name: "claude-agent-workflow"
description: "Codex wrapper for the ai-config Claude skill `claude-agent-workflow`. Add or modify the `anthropics/claude-code-action` agent workflow (`.github/workflows/claude.yml`). Preserves the load-bearing patterns \u2014 bot-actor `if:` filter, per-PR concurrency, EPI202_TOKEN/submodules access, R+Quarto+renv setup, stats-allowlist build, late-comment polling prompt, and the post-Claude review re-dispatch. Use when Codex is asked to use `claude-agent-workflow`, `/claude-agent-workflow`, or the corresponding ai-config/Claude skill workflow."
---

# claude-agent-workflow (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/claude-agent-workflow/SKILL.md](../../skills/claude-agent-workflow/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/claude-agent-workflow/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/claude-agent-workflow`, resolve the symlink target for this wrapper directory first, then read `../../skills/claude-agent-workflow/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
