---
name: "detect-hypothetical-examples"
description: "Codex wrapper for the ai-config Claude skill `detect-hypothetical-examples`. Detect worked examples that illustrate a definition or theorem with invented, round-number quantities \u2014 'Suppose a binary covariate Z...', 'If 20% of the exposed group experience the outcome...', 'Consider a hypothetical scenario...' \u2014 even though the document already has a real, already-loaded dataset it uses elsewhere. Greps for the recurring hypothetical/suppose/consider signal phrases and suspiciously round proportions inside a `#exm-`/`#def-` div, then confirms each hit against whether a real dataset with the needed variables is actually available, whether the example is illustrating a mechanism that doesn't need real numbers at all, and whether forcing real numbers would erase the point being taught (a deliberate edge case, a proof-of-concept before the real data is introduced). Fixing isn't mechanical substitution \u2014 a real dataset's effect size is often much less dramatic than an invented one, so the fix menu includes searching for a more naturally illustrative real covariate or keeping clearly-hedged toy numbers when no real substitute works. Use when asked to 'detect hypothetical examples', 'find hypothetical examples', 'replace hypothetical examples with real data', 'is this example using made-up numbers', 'this example should use the real dataset', or 'detect-hypothetical-examples'. Also runs proactively as part of any PR/MR review or self-review that introduces new worked examples, alongside `detect-informal-definitions`, `fix-forward-references`, `fact-check-prose`, and `find-ai-tells`. Use when Codex is asked to use `detect-hypothetical-examples`, `/detect-hypothetical-examples`, or the corresponding ai-config/Claude skill workflow."
---

# detect-hypothetical-examples (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/detect-hypothetical-examples/SKILL.md](../../skills/detect-hypothetical-examples/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/detect-hypothetical-examples/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/detect-hypothetical-examples`, resolve the symlink target for this wrapper directory first, then read `../../skills/detect-hypothetical-examples/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
