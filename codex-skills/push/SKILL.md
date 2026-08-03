---
name: "push"
description: "Codex wrapper for the ai-config Claude skill `push`. Pre-push safety gate: before `git push`, check the PR/branch for signals that say don't touch it \u2014 another session's 'paws off' claim, a branch HEAD that advanced past your last commit, hold/block labels (do-not-merge, WIP, hold, blocked), `@claude` runs in flight, or a push straight to a protected branch. If any fire, STOP and ask the user for guidance instead of pushing; if clean, push with the standard retry backoff. Use when asked to 'push', 'push this', 'push my changes', or before any push to a shared PR branch. Use when Codex is asked to use `push`, `/push`, or the corresponding ai-config/Claude skill workflow."
---

# push (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/push/SKILL.md](../../skills/push/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/push/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/push`, resolve the symlink target for this wrapper directory first, then read `../../skills/push/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
