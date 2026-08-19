# User-wide non-Claude AI-agent instructions

[Gemini CLI](https://github.com/google-gemini/gemini-cli) is an open-source AI assistant for the terminal. It stores user-wide config under `~/.gemini`. See [Google AI](https://ai.google.dev).

## Universal instructions

Follow all universal instructions defined in [`AGENTS.md`](AGENTS.md) (freshness, worktree isolation, local timestamp recaps, status requests not report-only, broad interpretation, cross-agent generalization, strict merge control, autonomous delivery, and review workflows).

## Antigravity Plugin & Customization Integration

- **Plugin manifest**: `plugins/ai-config/plugin.json` defines the `ai-config` plugin bundle for Google Antigravity.
- **Workspace discovery**: `.agents/skills.json` and `.agents/plugins.json` configure workspace-level skill and plugin discovery when opening this repository directly in Antigravity.
- **Global configuration**: Running `bootstrap.sh` symlinks `plugins/ai-config` into `~/.gemini/config/plugins/ai-config` and registers `plugins.json` for user-wide Antigravity sessions.
