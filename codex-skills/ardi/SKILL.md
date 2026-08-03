---
name: "ardi"
description: "Codex wrapper for the ai-config Claude skill `ardi`. ARD + Iterate: apply the ARD framework within an iterate loop on a single PR/MR. Read the latest review, Address/Rebut/Defer every finding, push fixes, post the ARD summary, then re-request review --- repeating until the verdict is clean. Runs a per-round checklist before each re-review trigger (latest review analyzed for current head, all findings dispositioned, fixes pushed and summary posted) and a fully-clean exit checklist before declaring clean (all CI green, zero findings, all inline threads resolved, only final all-clear exchange open). Use when asked to 'ardi', 'dc', 'drive', 'clean', 'drive to clean', 'iterate', 'iterate until clean', 'iterate this MR', 'drive this PR to clean', 'address the review comments', '@claude review again and fix what it finds', or after receiving a review you want to resolve completely / carry a PR all the way to mergeable. Use when Codex is asked to use `ardi`, `/ardi`, or the corresponding ai-config/Claude skill workflow."
---

# ardi (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/ardi/SKILL.md](../../skills/ardi/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/ardi/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/ardi`, resolve the symlink target for this wrapper directory first, then read `../../skills/ardi/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
