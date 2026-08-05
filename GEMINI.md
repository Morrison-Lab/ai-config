# User-wide Gemini CLI instructions

[Gemini CLI](https://github.com/google-gemini/gemini-cli) is an open-source AI assistant for the terminal. It stores user-wide config under `~/.gemini`. See [Google AI](https://ai.google.dev).

## Keep ai-config and repo checkouts fresh

In every session — at session start, and again periodically during long sessions — refresh local state:

1. **The ai-config checkout.** Check that the local ai-config clone is on `main` and run `git pull --ff-only`.
2. **The consumer copies / symlinks.** Ensure `bootstrap.sh` has run so `~/.gemini/skills` contains up-to-date symlinks to `skills/`.
3. **Working repo checkouts.** Keep `main` updated (`git fetch origin`, `git pull --ff-only`).

## Worktree isolation

- **Always use a worktree.**
  When starting write/edit tasks in a repository, isolate into a dedicated `git worktree` (e.g. via `session-lock` / `git worktree add`) so parallel sessions never step on or clobber each other's working directory or branch state.

## Timestamp recaps in local time

When printing a status recap or summary, include a timestamp in the user's local time zone (Pacific Time, `America/Los_Angeles` — get it from `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).

## File formatting & links

- Use GitHub-style markdown for all responses and documentation.
- When referencing files or code symbols in workspace paths, use relative markdown links (e.g. `[filename](relative/path/to/file)`) or inline code backticks (e.g. `` `path/to/file` ``).
- Preserve semantic line breaks and formatting conventions when editing markdown docs in this repo.

## Antigravity Plugin & Customization Integration

- **Plugin manifest**: `plugins/ai-config/plugin.json` defines the `ai-config` plugin bundle for Google Antigravity.
- **Workspace discovery**: `.agents/skills.json` and `.agents/plugins.json` configure workspace-level skill and plugin discovery when opening this repository directly in Antigravity.
- **Global configuration**: Running `bootstrap.sh` symlinks `plugins/ai-config` into `~/.gemini/config/plugins/ai-config` and registers `plugins.json` for user-wide Antigravity sessions.

## Strict Merge Control Policy

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").


