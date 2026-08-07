---
name: "use-preferred-style"
description: "Codex wrapper for the ai-config Claude skill `use-preferred-style`. Write or revise user-facing prose in the user's preferred style, per his Principles of Scientific Writing guide (psw, https://morrison-lab.github.io/psw/) --- limit dependent (subordinate) clauses, cut low-content filler and jargon, prefer plain Anglish words over Latin ones, prefer short declarative sentences and active voice, keep relative pronouns rather than dropping them, follow a demonstrative pronoun with the noun it refers to, and join ideas with coordinating conjunctions (and/but/so/or) over subordinate constructions. Apply when drafting or editing scientific prose, reviewing or redlining a manuscript or paper, or drafting/rewriting any other user-facing prose: PR/issue/commit text, docs, READMEs, comments, release notes, emails, or chat replies. Use when asked to 'use my style', 'apply my preferred style', 'rewrite in my voice', 'tighten this', 'plain-language this', 'review this manuscript', 'redline this paper', 'psw', or '/style'. Use when Codex is asked to use `use-preferred-style`, `/use-preferred-style`, or the corresponding ai-config/Claude skill workflow."
---

# use-preferred-style (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/use-preferred-style/SKILL.md](../../skills/use-preferred-style/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/use-preferred-style/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/use-preferred-style`, resolve the symlink target for this wrapper directory first, then read `../../skills/use-preferred-style/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
