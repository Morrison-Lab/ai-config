---
name: cut-tools
description: "Audit and disable unneeded MCP tools."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# cut-tools --- audit and disable unneeded MCP servers and toolsets

Every active tool and MCP server injects parameter schemas and descriptions into
the model's base prompt on every interaction.
Disabling unused MCP servers and
tool sets directly buys context window space, reduces per-turn latency, costs
no quota, and requires no permanent code changes.

## When this fires

- "cut tools", "cut tool definitions", "disable unused MCP servers", "audit
  active tools", "free up context from tools", "disable unneeded extensions",
  "prune tool definitions"
- Proactively when context is constrained or before long, multi-step sessions
- When starting work in a repository that only requires local editing and CLI
  tools, but has extensive external MCP servers or plugins enabled

## Core principle

Tool definitions consume fixed context overhead on every single prompt turn
before any conversation history or workspace files are read.
An environment
configured with multiple heavyweight MCP servers (such as GitHub, database,
cloud infrastructure, browser automation, or search servers) can spend
thousands of tokens purely on tool parameter schemas.

Cutting unneeded tool definitions:
1. **Directly recovers context budget** for code, diffs, and reasoning.
2. **Costs zero quota** --- reducing system prompt size saves tokens on every
   turn.
3. **Eliminates tool selection ambiguity** --- reduces hallucinated or misrouted
   tool calls by presenting only relevant capabilities.

## Procedure

### 1. Audit active tools and MCP servers

Inspect which tools, plugins, and MCP servers are currently registered and
active in the session across project and user configuration:

- **Claude Code:** Run `claude mcp list` or inspect `~/.claude.json`,
  `.claude/settings.json`, and `.mcp.json`.
- **Cursor:** Check `.cursor/mcp.json` and Cursor Settings -> Features -> MCP.
- **Antigravity / Gemini CLI:** Check `.agents/plugins.json`, `.agents/skills.json`,
  and `~/.gemini/config/plugins.json`.
- **Codex / OpenCode:** Check active tool configurations and CLI flags.

### 2. Identify unused or redundant toolsets

Evaluate active tools against the repository and current task:

- **CLI redundancy:** If `gh` and `git` CLI tools are available in Bash,
  heavyweight GitHub MCP servers (which define dozens of PR, issue, and repo
  management schemas) may be redundant.
- **Domain irrelevance:** Database (Postgres, SQLite), cloud (AWS, Kubernetes),
  or communication (Slack) servers are unneeded for local code refactoring or
  documentation work.
- **Unused browser/search tools:** Web automation servers (Playwright,
  Puppeteer) when working entirely on offline or local unit tasks.
- **Dormant workspace plugins:** Repository or user plugins whose skills or
  tools are not applicable to the current project.

### 3. Disable unneeded toolsets

Disable identified servers at the workspace or project level where possible:

- **Claude Code:** Disable or remove unneeded servers for the project
  (`claude mcp remove <name>`, configure `disabledMcpServers` in settings, or
  scope `.mcp.json`).
- **Cursor:** Disable unneeded MCP servers in workspace settings or
  `.cursor/mcp.json`.
- **Antigravity / Gemini CLI:** Remove or comment out unneeded plugins/servers
  in `.agents/plugins.json` or workspace configurations.

### 4. Verify and confirm

- Confirm that essential core tools remain active.
- Report the disabled tools and the approximate context space recovered.

## Relationship to other skills

- **[`compress-session`](../compress-session/SKILL.md) / [`checkpoint`](../checkpoint/SKILL.md) / [`memorize`](../memorize/SKILL.md):**
  Manage conversation and memory context; `cut-tools` manages the *fixed base
  system prompt* and tool schema overhead.
- **[`select-model`](../select-model/SKILL.md):** Optimizes model tier; `cut-tools`
  optimizes prompt payload size.
- **[`delegate-to-codex`](../delegate-to-codex/SKILL.md) / [`delegate-to-opencode`](../delegate-to-opencode/SKILL.md):**
  Offloads bounded work to separate CLIs with their own tool configurations.

## Anti-patterns

- ❌ Disabling core development tools (`Bash`, `Read`, `Edit`, `Write`, `Grep`,
  `Glob`) required for baseline editing and verification.
- ❌ Disabling MCP servers globally when they are actively needed in other
  concurrent workspaces (prefer project/workspace scoping).
- ❌ Guessing which tools are active without auditing first.
- ❌ Keeping all external MCP servers enabled by default "just in case" during
  large, context-heavy refactors.
