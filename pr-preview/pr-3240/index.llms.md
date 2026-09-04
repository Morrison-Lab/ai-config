# ai-config

Portable AI agent config — skills, memories, and commands synced across machines via git. Works with Claude Code, Codex, Cursor, VS Code Copilot, and any agent that reads markdown instruction files.

## What’s in this repo

| Directory | Purpose |
|----|----|
| `skills/` | Reusable workflow skills for Claude Code (`~/.claude/skills/`), Gemini CLI (`~/.gemini/skills/`), and Cursor |
| `codex-skills/` | Generated Codex wrappers (`~/.codex/skills/`) |
| `cursor-rules/` | User-global Cursor rules (plugin or `~/.cursor/rules/`) |
| `.cursor/rules/` | Project Cursor rules when this repo is the workspace |
| `.cursor-plugin/` | Cursor Plugin manifest (skills, rules, commands) |
| `AGENTS.md` | Universal vendor-neutral instruction file for all coding agents |
| `commands/` | Slash commands (`~/.claude/commands/`) |
| `.claude/agents/` | Read-only custom subagents (see [Agents](agents.llms.md)) |
| `memories/` | Persistent notes and preferences (shared with VS Code Copilot) |
| `shared/` | Single-topic guidance fragments shared with [UCD-SERG lab manual](https://ucd-serg.github.io/lab-manual/) |

## Three ways to use these skills

**Local CLI** — clone the repo and run `bootstrap.sh` once. It symlinks each directory into `~/.claude/`, `~/.gemini/`, `~/.codex/`, and — when no Cursor plugin is already serving them — `~/.cursor/rules/` (and, when no Cursor plugin or Claude skill catalog is already serving this repo, `~/.cursor/skills/`). Skills appear in Claude Code, Gemini CLI, and Cursor as `/skill-name`.

**Codex & Cursor** — the same bootstrap links generated wrappers from `codex-skills/` into `${CODEX_HOME:-$HOME/.codex}/skills` and, when no Cursor plugin is already serving them, user-global Cursor rules from `cursor-rules/` into `${CURSOR_HOME:-$HOME/.cursor}/rules`. This repo is also a Cursor plugin (`.cursor-plugin/plugin.json`). `AGENTS.md` acts as a universal entrypoint.

**Cloud sessions (other repos)** — this repo is a [plugin marketplace](https://github.com/Morrison-Lab/ai-config/blob/main/README.md#use-these-skills-in-another-repos-web-sessions-plugin-marketplace). Add `enabledPlugins` to your repo’s `.claude/settings.json` and skills load at session start, namespaced as `/ai-config:skill-name`.

**`@claude` bot on this repo’s PRs** — the `.claude/skills → ../skills` symlink is committed to `main`. Claude Code Action restores it on every PR run, so you can call `@claude ardi` (or any other skill) in PR comments.

## Quick links

- [Setup guide](setup.llms.md) — clone, bootstrap, verify, web sessions
- [Skills reference](skills.llms.md) — what skills exist and how to invoke them
- [Agents reference](agents.llms.md) — the read-only subagents skills fan work out to
- [Workflow guide](workflow.llms.md) — ARDI loop, issue-first, claim-PR, and more
- [GitHub repository](https://github.com/Morrison-Lab/ai-config) — source code

Back to top
