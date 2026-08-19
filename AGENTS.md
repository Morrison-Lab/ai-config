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

## Generalize instructions to every AI agent by default

Unless the user explicitly scopes an instruction to one agent, project, or
session, apply it to every available AI-agent configuration and shared
automation surface. Do not treat the currently speaking agent as an implicit
scope restriction.

## Interpret instructions broadly and maximize safe progress

Unless the user narrows a request, take the broad reading that advances its
obvious objective and complete every safe, authorized, relevant step. Do not
reduce an instruction to the smallest literal action when its context makes a
larger in-scope outcome clear.

## Status requests do not make issues report-only

Treat a request for status as a request to inspect live state and finish every
safe, in-scope, concrete action that inspection reveals. A report is the recap
after the work, not a substitute for it. When an issue cannot be fixed
directly, carry it forward with an actual next action. Every issue noticed,
however small or outside the current task's scope, must at minimum be filed in
the owning GitHub, GitLab, or equivalent tracker. File it before reporting it.

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

## Cursor Cloud specific instructions

This repo has no compiled app or long-running service.
The "product" is three things: a Quarto documentation website, a suite of
Python validators/tests under `scripts/`, and the enforcement hooks under
`hooks/`.
Standard commands are already documented --- lint/test steps in
[`.github/workflows/validate.yml`](.github/workflows/validate.yml), quality
gates and build/preview in [`README.md`](README.md) --- so consult those
rather than re-deriving them.
The startup update script keeps the `shared/sembr-skills` submodule current;
the system tools below (Quarto, the `python` shim, `pre-commit`) are already
present in the environment.

Non-obvious caveats worth knowing:

- **Lint:** `python3 scripts/validate-skills.py`, `python3 scripts/check-links.py`,
  and `npx --yes markdownlint-cli2@0.22.1` (config in
  `.markdownlint-cli2.jsonc`) are the fast, most-used checks.
- **Test:** the `scripts/test_*.py` suites (each runnable directly with
  `python3`); `validate.yml` lists the full set CI runs.
  `scripts/test_compare_shell_forms.py` spawns a real `bash` that invokes
  `python` (not `python3`), so it needs a `python` shim on `PATH`
  (`python-is-python3`); without it six of its subtests fail.
- **Build:** `quarto render` writes the static site to `_site/`
  (takes ~90s to render ~189 pages).
- **Run (dev):** `quarto preview --port 4444 --host 0.0.0.0 --no-browser`
  serves the site with hot reload; edits to a `.qmd` rebuild that page live.
  `quarto preview` also appends a redundant `/.quarto/` line to `.gitignore`
  on first run --- revert that incidental change before committing.
  `_site/` and `.quarto/` are already gitignored.
- **Submodule:** `shared/sembr-skills` must be initialized
  (`git submodule update --init`) or `validate-skills.py` warns and the plugin
  source check only ever reports its empty-directory branch.
- **pre-commit:** installed to `~/.local/bin`, which is not on `PATH` by
  default; run it as `~/.local/bin/pre-commit run --all-files`.
  Its first run builds the gitleaks (Go) and markdownlint (Node) hook
  environments, which is slow but cached thereafter.
