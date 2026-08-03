---
name: "check-dependency-updates"
description: "Codex wrapper for the ai-config Claude skill `check-dependency-updates`. Audit a repo for stale dependencies and surface available upgrades \u2014 pinned GitHub Actions tags/SHAs, renv.lock package versions, pre-commit revs, Quarto/tool versions in CI, submodules. Reports what could be updated and what each update buys, then drives the chosen bumps through the normal issue \u2192 branch \u2192 PR \u2192 ARDI flow. Use when asked to 'check dependency updates', 'cdu', 'audit dependency freshness', 'are my dependencies stale', 'check for outdated dependencies', 'should I bump the workflow SHAs', 'update the renv lockfile', or 'are there newer versions of my pinned actions'. Use when Codex is asked to use `check-dependency-updates`, `/check-dependency-updates`, or the corresponding ai-config/Claude skill workflow."
---

# check-dependency-updates (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/check-dependency-updates/SKILL.md](../../skills/check-dependency-updates/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/check-dependency-updates/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/check-dependency-updates`, resolve the symlink target for this wrapper directory first, then read `../../skills/check-dependency-updates/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
