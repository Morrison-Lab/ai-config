---
name: "post-merge"
description: "Codex wrapper for the ai-config Claude skill `post-merge`. Wrap up a just-merged PR/MR: verify the merge actually landed (never assume), tidy the local branch (switch to main, pull, delete the merged branch), confirm any deferred follow-up issues are tracked, flag a release step the merge left owed (a floating tag a human must still slide), then run UMS to capture what the PR's review lifecycle taught -- mistakes corrected and guidance given along the way. Use right after a PR merges, or when asked to 'post-merge', 'wrap up the merged PR', or 'clean up after the merge'. For the directive to actually perform the merge ('merge it' / 'merge this'), use the merge-it skill, which merges then chains into this one. Use when Codex is asked to use `post-merge`, `/post-merge`, or the corresponding ai-config/Claude skill workflow."
---

# post-merge (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/post-merge/SKILL.md](../../skills/post-merge/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/post-merge/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/post-merge`, resolve the symlink target for this wrapper directory first, then read `../../skills/post-merge/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
