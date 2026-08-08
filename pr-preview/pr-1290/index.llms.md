# ai-config

Portable AI agent config — skills, memories, and commands synced across machines via git. Works with Claude Code, Codex, VS Code Copilot, and any agent that reads markdown instruction files.

## What’s in this repo

| Directory | Purpose |
|----|----|
| `skills/` | Reusable workflow skills for Claude Code (`~/.claude/skills/`) |
| `codex-skills/` | Generated Codex wrappers (`~/.codex/skills/`) |
| `commands/` | Slash commands (`~/.claude/commands/`) |
| `.claude/agents/` | Read-only custom subagents (see [Agents](agents.llms.md)) |
| `memories/` | Persistent notes and preferences (shared with VS Code Copilot) |
| `shared/` | Single-topic guidance fragments shared with [UCD-SERG lab manual](https://ucd-serg.github.io/lab-manual/) |

## Three ways to use these skills

**Local CLI** — clone the repo and run `bootstrap.sh` once. It symlinks each directory into `~/.claude/`. Skills appear in Claude Code as `/skill-name`.

**Codex** — the same bootstrap links generated wrappers from `codex-skills/` into `${CODEX_HOME:-$HOME/.codex}/skills`. Each wrapper reads the matching canonical workflow from `skills/`.

**Cloud sessions (other repos)** — this repo is a [plugin marketplace](https://github.com/d-morrison/ai-config/blob/main/README.md#use-these-skills-in-another-repos-web-sessions-plugin-marketplace). Add `enabledPlugins` to your repo’s `.claude/settings.json` and skills load at session start, namespaced as `/ai-config:skill-name`.

**`@claude` bot on this repo’s PRs** — the `.claude/skills → ../skills` symlink is committed to `main`. Claude Code Action restores it on every PR run, so you can call `@claude ardi` (or any other skill) in PR comments.

## Quick links

- [Setup guide](setup.llms.md) — clone, bootstrap, verify, web sessions
- [Skills reference](skills.llms.md) — what skills exist and how to invoke them
- [Agents reference](agents.llms.md) — the read-only subagents skills fan work out to
- [Workflow guide](workflow.llms.md) — ARDI loop, issue-first, claim-PR, and more
- [GitHub repository](https://github.com/d-morrison/ai-config) — source code

Back to top
