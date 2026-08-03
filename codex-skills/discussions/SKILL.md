---
name: "discussions"
description: "Codex wrapper for the ai-config Claude skill `discussions`. Read and respond to GitHub Discussions forum topics -- list a repo's discussions, read a topic and its comments, draft and post a reply, and mark an answer on Q&A discussions. Reads are available over REST (`gh api repos/{owner}/{repo}/discussions/...`), so a topic is readable even where GraphQL is blocked; writes are GraphQL-only (no `gh discussion` subcommand, no GitHub MCP tool), so posting runs `gh api graphql`. Use when asked to 'read the discussions', 'respond to this discussion', 'answer the discussion topic', 'reply to the forum', 'triage the discussion board', or 'check GitHub Discussions'. Use when Codex is asked to use `discussions`, `/discussions`, or the corresponding ai-config/Claude skill workflow."
---

# discussions (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/discussions/SKILL.md](../../skills/discussions/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/discussions/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/discussions`, resolve the symlink target for this wrapper directory first, then read `../../skills/discussions/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
