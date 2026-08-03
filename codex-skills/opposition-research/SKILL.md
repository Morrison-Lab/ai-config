---
name: "opposition-research"
description: "Codex wrapper for the ai-config Claude skill `opposition-research`. Opposition research (aka `oppo`): mine a competitor product's community pages \u2014 issue trackers, feature-request boards, subreddits, Discourse/Discord, Stack Overflow tags, review sites \u2014 for features its users ask for and value, then map the on-scope ideas to our repos and file them as tracked issues. Studies what the rival's *users want*, not what the rival *shipped*. Use when asked to 'opposition research', 'oppo', 'do oppo research on X', 'what features does X's community want', 'mine X's issues/subreddit/forum for ideas', 'what are users asking competitor for', 'competitor feature research', or 'what do users wish product X had'. Invoke with /opposition-research or the alias /oppo. Use when Codex is asked to use `opposition-research`, `/opposition-research`, or the corresponding ai-config/Claude skill workflow."
---

# opposition-research (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/opposition-research/SKILL.md](../../skills/opposition-research/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/opposition-research/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/opposition-research`, resolve the symlink target for this wrapper directory first, then read `../../skills/opposition-research/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
