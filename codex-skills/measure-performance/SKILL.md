---
name: "measure-performance"
description: "Codex wrapper for the ai-config Claude skill `measure-performance`. Measure and benchmark R code performance the Advanced R way: profile with profvis to find the real bottleneck first, then microbenchmark only that bottleneck with bench::mark(), read the numbers correctly (min and median rather than mean, absolute units, calls-per-second calibration, <GC> as a memory signal), and re-profile the whole realistic workload to confirm the win survives. Use when asked to 'measure performance', 'measure-performance', 'perf', 'benchmark', 'benchmark this', 'microbenchmark', 'profile this', 'profile the code', 'run profvis', 'use bench::mark', 'why is this slow', 'what is the bottleneck', 'find the hot spot', 'which version is faster', 'is this actually faster', 'time these two approaches', 'how much did that speed things up', or whenever a change claims a speedup with no numbers behind it. Use when Codex is asked to use `measure-performance`, `/measure-performance`, or the corresponding ai-config/Claude skill workflow."
---

# measure-performance (Codex wrapper)

This is a generated Codex wrapper around the canonical ai-config Claude skill.

Source: [skills/measure-performance/SKILL.md](../../skills/measure-performance/SKILL.md)

Before acting, read the source skill completely and follow its workflow, adapting it to Codex.

The source lives at `skills/measure-performance/SKILL.md` in the same ai-config checkout as this wrapper. If this wrapper was loaded through `${CODEX_HOME:-$HOME/.codex}/skills/measure-performance`, resolve the symlink target for this wrapper directory first, then read `../../skills/measure-performance/SKILL.md` relative to that real directory. Do not resolve that relative path from inside `${CODEX_HOME:-$HOME/.codex}/skills`, because it points back at the wrapper tree.

- Treat `user-invocable` and `allowed-tools` as Claude metadata, not Codex permissions.
- Use the tools available in this Codex session for equivalent operations.
- If the source mentions a Claude-only path such as `~/.claude/skills`, use this repository's `skills/` path while editing.
- Keep procedural changes in the canonical source skill unless the user specifically asks to change this wrapper.

## Tool mappings

The canonical skill names `gh`/`git` commands (and sometimes
`mcp__github__*` tools). Resolve those operations using the full per-model
reference at [tool-mappings.md](../../tool-mappings.md), preferring the
GitHub MCP tool when this Codex session has it and otherwise using the CLI.
