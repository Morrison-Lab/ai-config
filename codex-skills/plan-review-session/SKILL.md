---
name: "plan-review-session"
description: "Codex wrapper for the ai-config Claude skill `plan-review-session`. Turn a catalog of common student errors into review-session teaching material \u2014 typically a new chapter in a Quarto course book (mistake callout + worked solution per error) \u2014 and open a PR. Use after grade-work, or when asked to \"plan a review session\", \"make a review chapter from these mistakes\", or \"build review material for the midterm\". Use when Codex is asked to use `plan-review-session`, `/plan-review-session`, or the corresponding ai-config/Claude skill workflow."
---

# plan-review-session (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/plan-review-session/SKILL.md](../../skills/plan-review-session/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/plan-review-session/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/plan-review-session`, resolve the symlink target for this wrapper directory first, then read `../../skills/plan-review-session/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
