# Product Definition: `ai-config`

## Overview
`ai-config` is the centralized, portable configuration repository and multi-agent workflow framework for Morrison-Lab.
It provides vendor-neutral instruction layering, shared skills, memories, commands, hooks, and automated testing across diverse AI coding agent harnesses.

## Target Audience & Supported Harnesses (as of Aug 2026)
- **Claude Code**: Direct import via `@path`, custom commands, subagents, and hooks.
- **Google Antigravity & Gemini CLI**: Workspace discovery via `.agents/` manifests, global plugin bundles, and rules.
- **OpenAI Codex CLI**: Generated skill wrappers in `codex-skills/` and automated tool mapping.
- **Cursor IDE**: Exported rules in `.cursor/rules/` and skill symlinks.
- **OpenCode**: Native configuration via `opencode.json` and convention-based agent discovery.
- **VS Code Copilot & Aider**: Standardized markdown instructions and git-synced dotfiles.

## Core Capabilities & Architecture
1.
**Instruction Layering**: Compact, unconditional cross-agent contracts (`AGENTS.md`) complemented by modular, on-demand domain fragments (`shared/`, `memories/`).
2.
**Standardized Skills & Wrappers**: Single source-of-truth SKILL.md definitions compiled/synced across agent formats.
3.
**Automated Enforcement Hooks**: Pre-commit validation scripts, context-budget gates, link checkers, and markdown linters ensuring repo hygiene and deterministic constraints.
4.
**Worktree & Session Isolation**: Multi-session safety via dedicated git worktrees and branch tracking.
5.
**Adversarial Self-Review & Quality Control**: Explicit verification loops (`ardi`, `mwc`, review subagents) enforcing clean reviews and strictly preventing unauthorized merges.

## Quality Goals & Principles
- **No Empty Promises**: Every behavioral commitment ships an automated mechanism, hook, or durable tracking issue.
- **Canonical vs.
Generated Output**: Deterministic regeneration of wrappers with zero manual editing of generated files.
- **Broad Progress & Proactive Repair**: Agents maximize safe progress, diagnose live state, and verify end-to-end before completion.
