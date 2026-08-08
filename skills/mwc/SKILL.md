---
name: mwc
description: "Grant standing session-scoped permission to merge fully-clean PRs autonomously, without asking per PR, for the rest of the current session. Use when the user says 'merge when confident', 'mwc', 'merge at will', 'maw', 'you can merge PRs when you're confident', or otherwise grants a forward-looking, session-wide merge exception."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Merge-When-Confident (MWC) Session Grant

`mwc` ("merge when confident") is an explicit, session-scoped user grant
that authorizes the AI assistant to merge fully-clean pull requests autonomously
for the duration of the current session,
without asking confirmation before every merge.

## Standing Scope & Policy

- **Baseline Prohibition**: AI assistants MUST NOT merge PRs/MRs
  without explicit user instruction for that specific PR.
  Pushing, building, or driving a PR to 100% clean CI
  DOES NOT grant permission to merge.
- **MWC Override Scope**: When the user explicitly issues `/mwc`,
  "merge when confident", "merge at will", or "maw",
  that baseline prohibition is suspended for the current session only.
- **Scope Limit**: An MWC grant applies ONLY to PRs that are 100% clean
  (all CI checks passing, review verdict clean, no unresolved comments, no open block labels).
  It NEVER authorizes merging a PR with failing CI, unresolved findings, or pending reviews.
- **Session Duration**: The grant expires automatically when the session ends
  or when explicitly revoked via `/mwc revoke` or `disable-mwc`.

## Session Lock & Hook Integration

`no-unauthorized-merge.py` enforces the baseline merge prohibition at the `PreToolUse` hook level,
blocking `gh pr merge`, `glab mr merge`, `gh api .../merge`, and `glab api .../merge`.

When MWC is enabled for a session:
1. `ai-session.sh enable-mwc` creates a `<sanitized-session-id>.mwc` marker file
   in the repository's git common directory (`$(git rev-parse --git-common-dir)/ai-sessions/`).
2. `no-unauthorized-merge.py` checks for the active session's `.mwc` marker file
   and validates that the session is alive (`is_session_alive()`).
3. If an active `.mwc` marker exists for the current session, `no-unauthorized-merge.py` allows merge tool executions.
4. `ai-session.sh disable-mwc` removes the `.mwc` marker file, restoring the strict prohibition immediately.

**The session id has to match on both sides, and that is the part that breaks.**
The guard resolves which session it is running under from the hook payload's own
`session_id` field, then the transcript filename stem, then `AI_SESSION_ID` /
`CLAUDE_SESSION_ID`.
It used to read only the two environment variables, and the hook process inherits
neither, so a grant made the sanctioned way was invisible to it and every merge was
blocked no matter what the user had granted (ai-config#1279).
Pass the harness session id explicitly when granting, since the shell script has no
payload to read.

`check-mwc` distinguishes three outcomes rather than reporting one sentence for all
of them, because "never granted" and "granted but the session reads dead" want
opposite responses:

| Exit | Meaning | What to do |
| :--- | :--- | :--- |
| 0 | active | nothing; the guard will honour it |
| 1 | no grant recorded | `enable-mwc --id <id>` |
| 2 | granted, but not currently honourable | the message names which case and the fix |

It is a **query**: it never prunes and never deletes the marker, so a stale read
cannot silently revoke a grant, and a `heartbeat` restores one.
Use `disable-mwc`, `release`, or `prune` to actually remove a grant.

## Procedure for Agents Handling `/mwc`

When the user gives an MWC grant (e.g. `/mwc` or "merge when confident"):

1. Run `skills/session-lock/scripts/ai-session.sh enable-mwc --id "<session id>"`
   (or `~/.claude/skills/session-lock/scripts/ai-session.sh enable-mwc --id "<session id>"`)
   to mechanistically set the session merge permission flag for `no-unauthorized-merge.py`,
   then acknowledge the grant in one sentence
   so the user knows it's active for the session,
   and what it does and doesn't cover.
   Pass `--id` explicitly unless `AI_SESSION_ID` or `CLAUDE_SESSION_ID` is set in
   the shell: without one the script cannot resolve an id and dies with
   "no session id".
   Its value is the harness session id, which is the transcript filename stem.
   Then confirm with `check-mwc --id "<session id>"`,
   which exits 0 only when the guard will actually honour the grant.
   Do not skip that confirmation:
   an `enable-mwc` that reports success still leaves the guard blocking if the
   two sides resolved different ids, which is exactly what ai-config#1279 was.
2. Proceed with the task (e.g. driving PRs to clean via `ardi`).
3. When a PR reaches 100% clean state, merge it immediately
   (default: squash merge via `gh pr merge <number> --squash --delete-branch`),
   verify the merge landed on GitHub/GitLab,
   and run the post-merge skill (`post-merge` / `ums`).
4. If the user revokes the grant, run `skills/session-lock/scripts/ai-session.sh disable-mwc` immediately.

## Quick Reference

| Command | Effect |
| :--- | :--- |
| `skills/session-lock/scripts/ai-session.sh enable-mwc --id "<id>"` | Enables session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh disable-mwc --id "<id>"` | Revokes session-wide merge grant |
| `skills/session-lock/scripts/ai-session.sh check-mwc --id "<id>"` | Checks the grant; exits 0 / 1 / 2 (see above) |

`--id` is optional only when `AI_SESSION_ID` or `CLAUDE_SESSION_ID` is set in the
shell, which in a Claude Code session it generally is not.
