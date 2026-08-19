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

## Pattern 6: Answering the asked process question without fetching the PR
- **Mistake**: Treating a "why didn't you wait / did you fix it / why no reply" question as chat-only, so a review that landed during that exchange stays unread.
- **Example**: gha#511 (2026-08-18): answered the CI-wait question, never opened the Needs more work comment.
- **Canonical Rule**: See `CLAUDE.md` ("Re-check for latest review findings before reporting PR status") and `skills/pr-status/SKILL.md` ("When this fires").
- **Fix**: Fetch the latest review and CI before answering any question about a live PR, not only when the user said "status".
