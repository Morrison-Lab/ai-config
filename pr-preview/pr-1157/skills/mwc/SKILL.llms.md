# Merge-When-Confident (MWC) Session Grant

`mwc` (“merge when confident”) is an explicit, session-scoped user grant that authorizes the AI assistant to merge fully-clean pull requests autonomously for the duration of the current session, without asking confirmation before every merge.

## Standing Scope & Policy

- **Baseline Prohibition**: AI assistants MUST NOT merge PRs/MRs without explicit user instruction for that specific PR. Pushing, building, or driving a PR to 100% clean CI DOES NOT grant permission to merge.
- **MWC Override Scope**: When the user explicitly issues `/mwc`, “merge when confident”, “merge at will”, or “maw”, that baseline prohibition is suspended **for the current session only**.
- **Scope Limit**: An MWC grant applies ONLY to PRs that are 100% clean (all CI checks passing, review verdict clean, no unresolved comments, no open block labels). It NEVER authorizes merging a PR with failing CI, unresolved findings, or pending reviews.
- **Session Duration**: The grant expires automatically when the session ends or when explicitly revoked via `/mwc revoke` or `disable-mwc`.

## Session Lock & Hook Integration

`no-unauthorized-merge.py` enforces the baseline merge prohibition at the `PreToolUse` hook level, blocking `gh pr merge`, `glab mr merge`, `gh api .../merge`, and `glab api .../merge`.

When MWC is enabled for a session: 1. `ai-session.sh enable-mwc` creates a `<sanitized-session-id>.mwc` marker file in the repository’s git common directory (`$(git rev-parse --git-common-dir)/ai-sessions/`). 2. `no-unauthorized-merge.py` checks for the active session’s `.mwc` marker file and validates that the session is alive (`is_session_alive()`). 3. If an active `.mwc` marker exists for the current session, `no-unauthorized-merge.py` allows merge tool executions. 4. `ai-session.sh disable-mwc` removes the `.mwc` marker file, restoring the strict prohibition immediately.

## Procedure for Agents Handling `/mwc`

When the user gives an MWC grant (e.g. `/mwc` or “merge when confident”):

1.  Run `skills/session-lock/scripts/ai-session.sh enable-mwc` (or `~/.claude/skills/session-lock/scripts/ai-session.sh enable-mwc`) to mechanistically set the session merge permission flag for `no-unauthorized-merge.py`, and acknowledge the grant in one sentence so the user knows it’s active for the session, and what it does and doesn’t cover.
2.  Proceed with the task (e.g. driving PRs to clean via `ardi`).
3.  When a PR reaches 100% clean state, merge it immediately (default: squash merge via `gh pr merge <number> --squash --delete-branch`), verify the merge landed on GitHub/GitLab, and run the post-merge skill (`post-merge` / `ums`).
4.  If the user revokes the grant, run `skills/session-lock/scripts/ai-session.sh disable-mwc` immediately.

## Quick Reference

| Command | Effect |
|:---|:---|
| `skills/session-lock/scripts/ai-session.sh enable-mwc` | Enables session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh disable-mwc` | Revokes session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh check-mwc` | Checks if session-wide merge grant is active |

Back to top
