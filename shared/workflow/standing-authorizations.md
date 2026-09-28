# Standing push and settings authorizations

Granted by the repository owner on 2026-09-28, for all sessions and all projects:

- **Non-force push to any repository the user has push access to.**
  Push to an existing branch, or create a new branch and push it, without asking first ---
  including a branch other than the one a session was started on,
  and a new branch for a separate PR, such as infrastructure split out of a content PR.
  This does not cover force pushes (`--force`, `--force-with-lease`, rewriting or deleting a remote branch):
  those still need explicit permission for the specific push,
  and `hooks/no-clobbering-push.py` still applies.
  Nor does it grant merging: [Strict Merge Control Policy](../../CLAUDE.md#strict-merge-control-policy) is unchanged.
- **Editing `.claude/settings.json`** in any repository,
  for example to enable the `ai-config` plugin or add `permissions.allow` rules.
  A session's own permission guard may still refuse the edit as self-modification;
  this grant does not license working around the guard.
  When it refuses, show the exact change and ask the user to approve it
  (switching the session out of auto mode lets them approve it directly).

- **Do:** push, and open the PR, without asking,
  and say in the same reply what you pushed and where.
- **Don't:** read "push" as covering a force push, a merge, or bypassing a tool's permission check.

The push grant applies to every agent, so `AGENTS.md`'s "Default to action without asking" states it too;
the `.claude/settings.json` grant concerns Claude Code alone.
