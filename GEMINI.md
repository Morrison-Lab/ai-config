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
Each reading expires immediately: run the command fresh for every recap rather than extrapolating elapsed time from a prior reading.
A single honest measurement earlier in the session is what most easily licenses an invented timestamp later, because the memory of having consulted the clock obscures that the measurement has expired.

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
- **Never merge over open review findings or treat skip notices as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see [`fully-clean.md`](shared/workflow/fully-clean.md)).
  A reviewer skip notice (e.g. for workflow edits or quota limits) never clears or supersedes prior review findings.
  All findings across the PR history must be fully Addressed, Rebutted, or Deferred before merge.

## Autonomously deliver completed changes to a PR

- **Never stop at uncommitted working tree changes**: When asked to write up, edit, or implement changes in a repository on a worktree/feature branch, do not finish the round by leaving modified files sitting uncommitted or unpushed.
- **Complete the delivery cycle**: Commit the changes (linking the tracking issue created per issue-first), push the branch to origin, open a Pull Request if not already opened, trigger AI review (`@claude review` / dispatch review workflow), and drive to clean.

## Request review and drive every started PR to clean

Whenever starting or working on a Pull Request:
1. **Trigger AI review when done pushing**: Request an AI review (`@claude review` comment or `@agy review` / dispatch `claude-review.yml`) **after completing all code pushes** for the round, not when the PR is first opened and empty.
2. **Drive to clean**: Run `ardi` / the review-and-iterate loop to ensure CI passes and all review findings are addressed until the PR reaches a clean verdict.
3. **Request human review only after AI approval or deadlock**: Per [`copilot-review-before-human.md`](shared/vendored/copilot-review-before-human.md), request human review (configured repo reviewers per `skills/request-pr-review/SKILL.md`) **only after** the AI review produces a clean/approved verdict, or if an impasse/deadlock occurs.

- **Do:** Trigger AI review (`@claude review`) after completing code pushes, and request human review only after the AI review is clean/approved (or upon an impasse).
- **Don't:** Request human review when the PR is first opened empty, before code pushes are complete, or before the AI review has passed / produced a clean verdict.
