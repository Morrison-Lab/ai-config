---
name: "find-ai-tells"
description: "Codex wrapper for the ai-config Claude skill `find-ai-tells`. Scan a target text \u2014 a file, a PR/MR diff, or pasted prose \u2014 for the telltale signs of AI/LLM authorship (overused vocabulary like 'delve'/'tapestry'/'testament', the 'it's not just X, it's Y' antithesis, mechanical rule-of-three lists, hedging stacks, signposting filler, em-dash overuse, bold-leading bullets, emoji headers, promotional register) and report each tell with its location, severity, and a concrete de-slopped revision. Also a standing self-check: before presenting non-trivial prose I wrote, scan my own draft against this catalog first. Use when asked to 'find AI tells', 'find-ai-tells', 'ai-tells', 'does this sound like AI / ChatGPT', 'de-slop this', 'remove the AI tells', 'make this not sound AI-generated', or 'check if this was written by AI'. Use when Codex is asked to use `find-ai-tells`, `/find-ai-tells`, or the corresponding ai-config/Claude skill workflow."
---

# find-ai-tells (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/find-ai-tells/SKILL.md](../../skills/find-ai-tells/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/find-ai-tells/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/find-ai-tells`, resolve the symlink target for this wrapper directory first, then read `../../skills/find-ai-tells/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
