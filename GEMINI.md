# User-wide non-Claude AI-agent instructions

[Gemini CLI](https://github.com/google-gemini/gemini-cli) is an open-source AI assistant for the terminal. It stores user-wide config under `~/.gemini`. See [Google AI](https://ai.google.dev).

`AGENTS.md` is the authoritative, auto-read cross-agent contract.
It owns universal freshness, worktree, delivery, timestamp, formatting, merge,
and review rules; do not duplicate them here.
Read the relevant section of this file only for Gemini CLI or Antigravity
integration work.

## Antigravity Plugin & Customization Integration

- **Plugin manifest**: `plugins/ai-config/plugin.json` defines the `ai-config` plugin bundle for Google Antigravity.
- **Workspace discovery**: `.agents/skills.json` and `.agents/plugins.json` configure workspace-level skill and plugin discovery when opening this repository directly in Antigravity.
- **Global configuration**: Running `bootstrap.sh` writes `~/.gemini/config/plugins.json` registering this checkout's own `plugins/ai-config` path (no symlink) for user-wide Antigravity sessions.
