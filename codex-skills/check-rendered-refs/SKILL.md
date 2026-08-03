---
name: "check-rendered-refs"
description: "Codex wrapper for the ai-config Claude skill `check-rendered-refs`. Scan rendered output (HTML, or a deployed/preview URL) for broken Quarto/pandoc cross-references and citations \u2014 refs that failed to resolve at render time and leak into the page as literal `?@key` text (e.g. `?@def-coef-interp-procedure`), a missing citation rendered bold-with-question-mark (`**key?**`), or raw `[@key]`/`@key` citation syntax that citeproc never processed. Report each hit with file/URL and the surrounding text. Use when asked to 'check rendered refs', 'crr', 'check for broken crossrefs', 'check broken cross-references', 'find unresolved references in the rendered site', 'scan the HTML for `?@`', 'did any crossrefs/citations break in the render', or after rendering/previewing a Quarto book or website. Use when Codex is asked to use `check-rendered-refs`, `/check-rendered-refs`, or the corresponding ai-config/Claude skill workflow."
---

# check-rendered-refs (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/check-rendered-refs/SKILL.md](../../skills/check-rendered-refs/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/check-rendered-refs/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/check-rendered-refs`, resolve the symlink target for this wrapper directory first, then read `../../skills/check-rendered-refs/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
