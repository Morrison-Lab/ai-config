---
name: "cascade"
description: "Codex wrapper for the ai-config Claude skill `cascade`. Cascade merges DOWN a PR stack \u2014 merge each open PR's base branch into it (main into unstacked PRs, each stacked PR's base branch into the PR on top of it), resolving squash-stack conflicts and verifying each merge is content-neutral. Does NOT merge any PR into main. Use on \"cascade\", \"/cascade\", \"cascade the stack\", \"propagate main down the stack\", or after one or more PRs in a stack merge and the rest need their bases folded in. Use when Codex is asked to use `cascade`, `/cascade`, or the corresponding ai-config/Claude skill workflow."
---

# cascade (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/cascade/SKILL.md](../../skills/cascade/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/cascade/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/cascade`, resolve the symlink target for this wrapper directory first, then read `../../skills/cascade/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
