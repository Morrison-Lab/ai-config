---
name: "pending-decisions"
description: "Codex wrapper for the ai-config Claude skill `pending-decisions`. Sweep a repo's (or every in-scope repo's) open issues and PRs for ones waiting on a decision from the user \u2014 an explicit review-request escalation, a decision-style label, or an unanswered bot-posed question in the latest activity \u2014 then ask about each one, one at a time, most pressing first. The issue-tracker-scoped analog of `prompt-me`/`prompt-me-all`, which only see the current conversation. Use when asked to 'pending decisions', 'pd', 'what decisions are you waiting on', 'any decisions needed from me', 'check for pending decisions', 'sweep issues for decisions', 'is anything stalled on my input', or '/pending-decisions [owner/repo|all]'. Use when Codex is asked to use `pending-decisions`, `/pending-decisions`, or the corresponding ai-config/Claude skill workflow."
---

# pending-decisions (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/pending-decisions/SKILL.md](../../skills/pending-decisions/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/pending-decisions/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/pending-decisions`, resolve the symlink target for this wrapper directory first, then read `../../skills/pending-decisions/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
