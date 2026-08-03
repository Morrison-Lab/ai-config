---
name: "resolve-conflicts"
description: "Codex wrapper for the ai-config Claude skill `resolve-conflicts`. Resolve git merge/rebase/cherry-pick conflicts by consolidating the best of BOTH branches \u2014 understand why each side changed the hunk, then reconstruct a resolution that preserves both intents instead of blindly picking `--ours`/`--theirs`. Remove the markers, run the repo's pre-commit checks, stage, and finish the operation. Use when a merge / rebase / cherry-pick / stash pop / revert / pull reports conflicts, or when asked to 'resolve conflicts', 'resolve the merge conflicts', 'fix the conflicts', 'I have a merge conflict', 'consolidate the best of both branches', or 'help me merge these branches'. Delegated to from `sync-pr-branch` step 5, `clean-branches`, and `gii`. (For multiple AI *sessions* clobbering one local checkout, that's `deconflict-sessions` / `session-lock`, not this.) Use when Codex is asked to use `resolve-conflicts`, `/resolve-conflicts`, or the corresponding ai-config/Claude skill workflow."
---

# resolve-conflicts (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/resolve-conflicts/SKILL.md](../../skills/resolve-conflicts/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/resolve-conflicts/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/resolve-conflicts`, resolve the symlink target for this wrapper directory first, then read `../../skills/resolve-conflicts/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
