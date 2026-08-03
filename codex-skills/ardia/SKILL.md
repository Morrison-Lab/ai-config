---
name: "ardia"
description: "Codex wrapper for the ai-config Claude skill `ardia`. ARD + Iterate-All: apply ARDI (ARD + iterate) to every open PR/MR in the repo. Optionally survey and prepare independent PRs in parallel, then drive each one to a clean review verdict in turn. Use when asked to 'ardia', 'iterate all', 'iterate all PRs', 'iterate every open PR', 'carry every open PR to clean', 'review-loop all my PRs', 'drive all MRs to clean', or to run the ARD-iterate loop across the whole open-PR queue rather than a single PR. Use when Codex is asked to use `ardia`, `/ardia`, or the corresponding ai-config/Claude skill workflow."
---

# ardia (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/ardia/SKILL.md](../../skills/ardia/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/ardia/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/ardia`, resolve the symlink target for this wrapper directory first, then read `../../skills/ardia/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
