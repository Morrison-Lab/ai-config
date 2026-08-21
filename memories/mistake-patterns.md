# Recurring Mistake Patterns & Fixes

Quick-reference index of common failure patterns observed in agent sessions, with cross-references to their canonical enforcement rules and deep treatments.

## Pattern 1: Assumption Over Verification
- **Mistake**: Assume an action succeeded without verifying the result from tool output or repository state.
- **Example**: Assuming `gh pr create` succeeded without checking URL / output or verifying the open PR exists.
- **Canonical Rule**: See [`preferences.md`](preferences.md) ("NEVER assume; ALWAYS verify").
- **Fix**: Inspect return codes, verify produced artifacts, and check state directly before proceeding.

## Pattern 2: Passivity on Standing Rules
- **Mistake**: Asking permission for routine, non-destructive steps already authorized by standing rules.
- **Example**: Asking "Should I open a PR?" when standing rules mandate opening PRs for completed changes.
- **Canonical Rule**: See `CLAUDE.md` ("Non-destructive repo and memory actions" and "Open a PR for every pushed feature branch").
- **Fix**: Execute standing instructions autonomously; reserve questions for genuine design ambiguity.

## Pattern 3: Give Up Instead of Diagnose
- **Mistake**: Treating a "command not found" or tool path error as a permanent blocker without searching.
- **Example**: Failing on `gh: command not found` without searching standard tool locations or checking PATH.
- **Canonical Rule**: See [`growth-mindset.md`](../shared/workflow/growth-mindset.md) ("First check the limitation is real").
- **Fix**: Probe standard paths (`/opt/homebrew/bin/`, `which`, package locations) and diagnose before concluding a capability is missing.

## Pattern 4: Incomplete Workflow Follow-Through
- **Mistake**: Executing an initial step but abandoning subsequent steps before the workflow completes.
- **Example**: Modifying files or pushing a commit but stopping before opening a PR or driving review to clean.
- **Canonical Rule**: See `CLAUDE.md` ("Request review and drive every started PR to clean" and "Watch and ARDI every PR you touch --- don't ask first"), and [`run-ums-proactively.md`](../shared/workflow/run-ums-proactively.md).
- **Fix**: Follow each workflow end-to-end: edit → test → commit → push → open PR → ARDI to clean.

## Pattern 5: Bypassing Existing Repo Knowledge
- **Mistake**: Taking actions without consulting existing memory files or project instructions.
- **Canonical Rule**: See [`MEMORY.md`](MEMORY.md) and project `CLAUDE.md` / `AGENTS.md`.
- **Fix**: Consult relevant memory files and project instructions at task start to align with existing conventions.

## Pattern 5b: Skipping Standing Rules That Already Exist
- **Mistake**: Completing a task without checking whether a standing rule already governs it, then getting corrected and saying "I'll remember" instead of recording the failure.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): wrote content, committed, but stopped before pushing/opening a PR.
  AGENTS.md line 63-72 already mandated the full delivery cycle.
  The fix was recorded verbally but not persisted.
- **Canonical Rule**: `AGENTS.md` ("Deliver completed implementation work"): commit → push → PR → share link, as one automatic sequence.
- **Fix**: Before acting on a task, grep AGENTS.md and project CLAUDE.md for rules that apply.
  After a correction, record it in mistake-patterns.md (don't just say you'll remember --- the next session won't have this conversation).

## Pattern 5c: Declaring PR Ready When CI Is Failing or Incomplete
- **Mistake**: Telling a user a PR is ready to merge without checking CI status, or saying "ready" when checks haven't finished.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): told user Morrison-Lab/ai-config#1677 was on the branch without checking that CI had failed (`new-line-breaks` check).
- **Canonical Rule**: `AGENTS.md` ("Request review and drive every started PR to clean") and `fully-clean.md` --- a PR is not ready until ALL CI checks pass AND review is clean.
- **Fix**: Always run `gh pr checks <N>` or `gh pr view <N> --json statusCheckRollup` before declaring a PR ready.
  Never say "ready to merge" unless every check is green.
  If CI is failing, say so and fix it first.

## Pattern 5d: Failing to Learn From Mistakes
- **Mistake**: Getting corrected, acknowledging the fix verbally ("I'll internalize that"), but not recording it --- so the next session makes the same mistake.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): corrected three times (didn't push, didn't open PR, declared ready with failing CI).
  Each time acknowledged the fix but only recorded it after being told to, and the first two corrections weren't recorded at all until prompted.
- **Canonical Rule**: `AGENTS.md` ("Deliver completed implementation work") plus the UMS principle: every correction is a learning to bank, not a conversation to end.
- **Fix**: After any correction, immediately record it in `mistake-patterns.md` (or the appropriate memory file) with enough context that a cold reader can avoid it.
  Don't wait to be told to learn --- the correction IS the instruction.

## Pattern 6: Answering the asked process question without fetching the PR
- **Mistake**: Treating a "why didn't you wait / did you fix it / why no reply" question as chat-only, so a review that landed during that exchange stays unread.
- **Example**: gha#511 (2026-08-18): answered the CI-wait question, never opened the Needs more work comment.
- **Canonical Rule**: See `CLAUDE.md` ("Re-check for latest review findings before reporting PR status") and `skills/pr-status/SKILL.md` ("When this fires").
- **Fix**: Fetch the latest review and CI before answering any question about a live PR, not only when the user said "status".

## Pattern 7: Stale PR body figures surviving iteration pushes
- **Mistake**: Pushing changes or review fixes that alter file counts, diff stats, or commit SHAs without updating the verification table in the PR body.
- **Example**: Morrison-Lab/ai-config#1531: at `3a373100`, the body still claimed +31/-3 across 1 file at `685b5dc8`, while HEAD had moved to +35/-4 across 2 files.
- **Canonical Rule**: See `shared/workflow/ardi.md` and `scripts/check-pr-body-figures.py` (Morrison-Lab/ai-config#1549).
- **Fix**: Run `python3 scripts/check-pr-body-figures.py` to mechanically compare stated figures and derivation SHAs against the HEAD commit.

## Pattern 8: Taking Shortcuts That Remove Features
- **Mistake**: When fixing a bug or error, removing the feature that's broken rather than fixing it properly.
- **Example**: matt.contracts SAP article had `format: html/docx/revealjs`
  causing a build error.
  Removed the format block entirely
  instead of fixing it to use the correct pattern.
- **Anti-pattern**: Deleting code/config that causes an error,
  disabling a feature to make CI green,
  commenting out a failing test,
  removing a dependency instead of fixing the integration.
- **Canonical Rule**: none states this case directly --- the nearest is
  [`dont-incur-technical-debt.md`](../shared/principles/dont-incur-technical-debt.md)
  ("shipping the version that routes around it"), which covers routing around a
  needed change rather than deleting the feature that exposed it.
  Tracked as a gap in Morrison-Lab/ai-config#1746.
- **Fix**: Diagnose the root cause and fix it while preserving the feature.
  If unsure how, use a subagent to research the correct approach
  or check sibling repos for the working pattern.
  The only valid reason to remove a feature is the user explicitly asking for it.

## Pattern 9: Working on the primary checkout instead of a worktree
- **Mistake**: Committing directly to the primary checkout --- to `main` or to an existing feature branch already checked out there --- instead of isolating the work in a dedicated `git worktree`.
- **Example**: 2026-08-19 session (cwd `wai`, working `Morrison-Lab/ai-config`): committed memory updates straight onto `fix/quote-yaml-placeholders` on the primary ai-config checkout, where a parallel session sharing that checkout would have collided with them.
- **Canonical Rule**: `AGENTS.md` ("Worktree isolation"), which requires a dedicated worktree for write/edit tasks so parallel sessions never clobber each other's working directory or branch state.
  See also [`git-worktrees.md`](git-worktrees.md) for the liveness rules that decide when a worktree may be touched or reclaimed.
- **Fix**: Create the worktree before the first edit (`git worktree add`), not after the first commit.
  Treat the primary checkout as read-only during a write session, and push early --- a pushed commit survives anything that happens to a working tree.
