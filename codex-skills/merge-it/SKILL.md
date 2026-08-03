---
name: "merge-it"
description: "Codex wrapper for the ai-config Claude skill `merge-it`. Merge a ready pull request, then automatically wrap up \u2014 verify the merge landed, tidy the branch, and run UMS \u2014 without asking. Use when the user says 'merge it', 'merge this', 'merge the PR', or 'go ahead and merge'. Performs the actual merge when the PR isn't merged yet (squash by default), then chains into the post-merge skill. If the PR is already merged, it skips straight to post-merge. Use when Codex is asked to use `merge-it`, `/merge-it`, or the corresponding ai-config/Claude skill workflow."
---

# merge-it (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/merge-it/SKILL.md](../../skills/merge-it/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/merge-it/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/merge-it`, resolve the symlink target for this wrapper directory first, then read `../../skills/merge-it/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
