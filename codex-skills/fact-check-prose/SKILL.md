---
name: "fact-check-prose"
description: "Codex wrapper for the ai-config Claude skill `fact-check-prose`. Assess the accuracy and clarity of prose in a PR/MR, file, or pasted text \u2014 check factual claims against domain knowledge and external sources, verify document-internal reasoning (formal mathematical derivations/proofs and informal arguments) step by step, and cross-check any computed value or figure the prose describes against the actual rendered output (a PR-preview site, a gh-pages branch, or a local render). Reports which claims are inaccurate, the specific source or check each verdict rests on, and proactively suggests additional citations wherever they'd help \u2014 not just where a claim is already flagged as uncited. Use when asked to 'fact-check this', 'check the math', 'verify this reasoning', 'check this proof', 'is this accurate', 'review this prose for accuracy', or as part of reviewing any PR/MR that touches documentation, lecture notes, or other narrative content. Use when Codex is asked to use `fact-check-prose`, `/fact-check-prose`, or the corresponding ai-config/Claude skill workflow."
---

# fact-check-prose (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/fact-check-prose/SKILL.md](../../skills/fact-check-prose/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/fact-check-prose/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/fact-check-prose`, resolve the symlink target for this wrapper directory first, then read `../../skills/fact-check-prose/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
