---
name: "wait-for-results"
description: "Codex wrapper for the ai-config Claude skill `wait-for-results`. Wait for long-running jobs to finish (SLURM arrays, builds, CI, background tasks, remote agents), then run the agreed follow-up step. Immediately runs the `handoff` skill first so session state is saved before the wait \u2014 if the session ends or context resets mid-wait, the next session can resume cleanly. Use when asked to 'wait for results', 'wait for the jobs', 'poll until done then combine/run X', or after launching a long job you intend to act on when it completes. Use when Codex is asked to use `wait-for-results`, `/wait-for-results`, or the corresponding ai-config/Claude skill workflow."
---

# wait-for-results (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/wait-for-results/SKILL.md](../../skills/wait-for-results/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/wait-for-results/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/wait-for-results`, resolve the symlink target for this wrapper directory first, then read `../../skills/wait-for-results/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
