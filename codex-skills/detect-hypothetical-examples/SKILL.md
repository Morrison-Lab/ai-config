---
name: "detect-hypothetical-examples"
description: "Codex wrapper for the ai-config Claude skill `detect-hypothetical-examples`. Detect worked examples that illustrate a definition or theorem with invented, round-number quantities ('Suppose a binary covariate Z...', 'If 20% of the exposed group...') even though the document already has a real, loaded dataset it uses elsewhere. Greps for hypothetical/suppose/consider signal phrases and suspiciously round proportions inside a `#exm-`/`#def-` div, then confirms each hit against whether a real dataset with the needed variables exists, whether the example needs real numbers at all, and whether real numbers would erase the point. Fixing isn't mechanical substitution, so the fix menu includes finding a more illustrative real covariate or keeping clearly-hedged toy numbers. Use when asked to 'detect hypothetical examples', 'find hypothetical examples', 'replace hypothetical examples with real data', or 'detect-hypothetical-examples'. Also runs proactively in any PR/MR review that introduces new worked examples, alongside `detect-informal-definitions` and `find-ai-tells`. Use when Codex is asked to use `detect-hypothetical-examples`, `/detect-hypothetical-examples`, or the corresponding ai-config/Claude skill workflow."
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
