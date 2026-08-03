---
name: "ard"
description: "Codex wrapper for the ai-config Claude skill `ard`. Address, Rebut, Defer, or Acknowledge: respond to every review comment on a PR/MR with exactly one disposition. For each item a reviewer (human or bot) raises, choose one \u2014 fix it (Address), explain why it's correct as-is (Rebut), file a follow-up issue (Defer), or acknowledge a no-change-requested observation (Acknowledge). Silently ignoring a comment is never acceptable. Runs a round-close checklist before reporting the round done: every finding captured, every Address committed and pushed, every Defer tracked, every inline thread replied-to. Works on GitHub (gh) and GitLab (glab). Use after receiving a review, when asked to 'address reviews' / 'respond to the review' / 'ard this review', or as the inner loop of the `ardi` skill. Use when Codex is asked to use `ard`, `/ard`, or the corresponding ai-config/Claude skill workflow."
---

# ard (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/ard/SKILL.md](../../skills/ard/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/ard/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/ard`, resolve the symlink target for this wrapper directory first, then read `../../skills/ard/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
