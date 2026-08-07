---
name: "check-info-quality"
description: "Codex wrapper for the ai-config Claude skill `check-info-quality`. Scan a target --- a file, a PR/MR diff, or pasted text --- for three information-quality problems that neither purge-hallucinations nor find-ai-tells catches: (1) out-of-date information (a version, API, guideline, or 'current' claim that's since been superseded), (2) irrelevant information (off-topic tangents, scope creep, a true-but-unrelated fact), and (3) misleading or out-of-context information (a technically-true statement that misleads through missing context, cherry-picked evidence, or a citation used to support a claim it doesn't actually support). Reports each finding with location, evidence, and severity, then proposes --- never silently applies --- a fix. Use when asked to 'check info quality', 'check-info-quality', 'ciq', 'is this out of date', 'is this still accurate', 'find stale information', 'is this relevant', 'does this belong here', 'is this misleading', 'does this citation support the claim', or 'audit this for information quality'. Use when Codex is asked to use `check-info-quality`, `/check-info-quality`, or the corresponding ai-config/Claude skill workflow."
---

# check-info-quality (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/check-info-quality/SKILL.md](../../skills/check-info-quality/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/check-info-quality/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/check-info-quality`, resolve the symlink target for this wrapper directory first, then read `../../skills/check-info-quality/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
