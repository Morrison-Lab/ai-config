---
name: "reproducibility-audit"
description: "Codex wrapper for the ai-config Claude skill `reproducibility-audit`. Audit a project's reproducibility posture with a checklist scoped per project type (R package, Quarto book/site, general script repo): hidden/undocumented dependencies, hardcoded absolute paths, undocumented prerequisites, environment assumptions, and output traceability (can a result be traced back to the exact script/line that produced it). Reports gaps in a table and files a tracking issue for the ones worth fixing. Use when asked to 'reproducibility audit', 'audit reproducibility', 'check reproducibility', 'is this project reproducible', 'find hidden dependencies', 'find hardcoded paths', 'check environment assumptions', 'can this be reproduced from scratch', 'audit for a replication package', or 'check output traceability'. Use when Codex is asked to use `reproducibility-audit`, `/reproducibility-audit`, or the corresponding ai-config/Claude skill workflow."
---

# reproducibility-audit (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/reproducibility-audit/SKILL.md](../../skills/reproducibility-audit/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/reproducibility-audit/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/reproducibility-audit`, resolve the symlink target for this wrapper directory first, then read `../../skills/reproducibility-audit/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
