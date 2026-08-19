# Universal AI Agent Instructions (AGENTS.md)

This file defines standardized, vendor-neutral instructions for AI coding agents operating within Morrison-Lab repositories (OpenAI Codex CLI, Gemini CLI / Antigravity, Claude Code, Cursor, Aider, etc.).

## Instruction layering

`AGENTS.md` is the compact, unconditional cross-agent contract.
Keep every rule that applies to all agents here, rather than duplicating it in
model-specific manuals.
Do not load `CLAUDE.md`, `GEMINI.md`, or their case records wholesale at
session start: consult the relevant section on demand when changing that
model's integration or resolving a model-specific workflow question.
Those manuals must defer to this file for universal policy.

## Keep ai-config and repo checkouts fresh

In every session --- at session start, and again periodically during long sessions --- refresh local state:

1. **The ai-config checkout.** Check that the local `ai-config` clone is on `main` and run `git pull --ff-only`.
2. **The consumer copies / symlinks.** Ensure `bootstrap.sh` has run so local agent config directories (`~/.gemini/skills`, `~/.claude`, `~/.codex/skills`, `~/.cursor/rules`) contain up-to-date symlinks.
3. **Working repo checkouts.** Keep `main` updated (`git fetch origin`, `git pull --ff-only`).

## Worktree isolation

- **Always use a worktree.**
  When starting write/edit tasks in a repository, isolate into a dedicated `git worktree` (e.g. via `session-lock` / `git worktree add`) so parallel sessions never step on or clobber each other's working directory or branch state.

## Timestamp recaps in local time

When printing a status recap or summary, include a timestamp in the user's local time zone (Pacific Time, `America/Los_Angeles` --- get it from `TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`).
Each reading expires immediately: run the command fresh for every recap rather than extrapolating elapsed time from a prior reading.

## File formatting & links

- Use GitHub-style markdown for all responses and documentation.
- When referencing files or code symbols in workspace paths, use relative markdown links (e.g. `[filename](relative/path/to/file)`) or inline code backticks (e.g. `` `path/to/file` ``).
- Preserve semantic line breaks (SemBr) and formatting conventions when editing markdown docs.

## Deliver completed implementation work

When asked to implement, edit, or write up a change on a feature branch, do
not stop at an uncommitted worktree.
Complete the delivery cycle: create the applicable tracking issue when
issue-first workflow applies, commit the scoped changes, push the branch, open
or update its Pull Request, request AI review after the final push, and drive
CI and review findings to a clean result.
This does not grant merge authority; the strict merge policy below still
applies.

## Antigravity Workspace Rules & Activation Scopes

- **Global rules**: Defined in `~/.gemini/GEMINI.md`.
- **Workspace rules**: Defined in `.agents/rules/` or root `AGENTS.md` (with backward compatibility for `.agent/rules/`).
- **Activation modes**:
  - *Always On*: Evaluated unconditionally in context (`alwaysApply: true` / root instruction files).
  - *Glob Scoped*: Evaluated when matching active workspace paths (`globs: [...]` or `applyTo: ...`).
  - *Model Decision*: Injected dynamically based on task context.
  - *Manual*: Triggered via `@mention` or explicit command.
- **Discovery manifests**: Configured via `.agents/skills.json` and `.agents/plugins.json`.

## Strict Merge Control Policy

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
- **Never merge over open review findings or treat a reviewer skip notice as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see
  [`fully-clean.md`](shared/workflow/fully-clean.md)).
  All findings across the PR history must be Addressed, Rebutted, or Deferred
  before merge.

## Request review and drive every started PR to clean

Whenever starting or working on a Pull Request:
1. **Trigger AI review when done pushing**: Request an AI review (`@claude review` comment or `@agy review` / dispatch `claude-review.yml`) **after completing all code pushes** for the round, not when the PR is first opened and empty.
2. **Drive to clean**: Run `ardi` / the review-and-iterate loop to ensure CI passes and all review findings are addressed until the PR reaches a clean verdict.
3. **Request human review only after AI approval or deadlock**: Per [`copilot-review-before-human.md`](shared/vendored/copilot-review-before-human.md), request human review (configured repo reviewers per `skills/request-pr-review/SKILL.md`) **only after** the AI review produces a clean/approved verdict, or if an impasse/deadlock occurs.

- **Do:** Trigger AI review (`@claude review`) after completing code pushes, and request human review only after the AI review is clean/approved (or upon an impasse).
- **Don't:** Request human review when the PR is first opened empty, before code pushes are complete, or before the AI review has passed / produced a clean verdict.
