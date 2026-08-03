---
name: "gia"
description: "Codex wrapper for the ai-config Claude skill `gia`. Grab Issues + iterate-All: clear the repo's entire work queue in two phases \u2014 first run ARDIA (drive every open PR/MR to a clean review verdict), then run GII (grab each open issue, implement it, open an MR/PR, ARDI to clean, recurse). Use when asked to 'gia', 'ardia+gii', 'adria+gii', 'gii+ardia', 'gii+adria', 'clear the whole queue', 'clean all PRs then do all the issues', 'burn down everything', 'tidy the repo end to end', or 'empty the backlog'. Use when Codex is asked to use `gia`, `/gia`, or the corresponding ai-config/Claude skill workflow."
---

# gia (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/gia/SKILL.md](../../skills/gia/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/gia/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/gia`, resolve the symlink target for this wrapper directory first, then read `../../skills/gia/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
