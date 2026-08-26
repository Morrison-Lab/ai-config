# Specification: Pre-Push AI Code Review Integration

## Overview
Integrate and standardize the `pre-push-review` tool and skill across all supported AI agent harnesses (Antigravity/Gemini, Claude Code, Codex CLI). The tool executes a single-pass adversarial code review on local outgoing branch commits against the base branch, utilizing local desktop subscription quota (`agy`, `claude`, `codex`) rather than consuming cloud CI tokens or API credits.

## Functional Requirements
1. **Engine Selection & Auto-Detection**:
   - Support explicit `--engine` selection (`claude`, `codex`, `opencode`, `antigravity`).
   - If `--engine auto` (or omitted), detect available installed CLIs in priority order (`claude` -> `codex` -> `opencode` -> `agy`).
   - Allow optional `--model` flag to pass specific model strings to the target engine.
2. **Context & Guideline Extraction**:
   - Extract git diff against detected PR base or merge-base with `origin/main` / `main`.
   - Incorporate universal repository guidelines (`AGENTS.md`) into the prompt.
   - Enforce structured adversarial review output (Summary Verdict, Critical Findings, Observations, Verification Steps, and Reviewed-Commit SHA).
3. **Forge PR Posting & Attribution Compliance**:
   - When `--post` is specified, post review verdict/comments directly to GitHub PR via `gh pr comment`.
   - Enforce lab-wide disclosure policy (`_Posted by <Engine> (AI agent) --- not written by a human._`) without robot emojis.
4. **Skill Packaging & Synchronization**:
   - Maintain canonical `skills/pre-push-review/SKILL.md`.
   - Generate wrapper for OpenAI Codex in `codex-skills/pre-push-review/SKILL.md` via `scripts/sync-codex-skill-wrappers.py`.
   - Discover via `.agents/skills.json` directory registration and validate with `scripts/validate-skills.py`.

## Non-Functional & Quality Requirements
- Purely local CLI execution using configured user desktop tools and subscriptions.
- High test fidelity: Comprehensive test suite in `scripts/test_pre_push_review.py` verifying diff extraction, fallback logic, CLI arguments, and formatting.
- Strict clean execution under repository validation linters and link checkers.

## Acceptance Criteria
- [x] `scripts/pre-push-review.py` handles auto-detection, fallback, and all engine modes cleanly.
- [x] PR posting includes standardized forge disclosure without robot emojis.
- [x] `scripts/test_pre_push_review.py` passes all unit tests.
- [x] `python3 scripts/validate-skills.py` and `python3 scripts/check-links.py` pass without errors.
- [x] Skill wrappers in `codex-skills/` are fully in sync.

## Out of Scope
- Automatic git pre-push hook installation (this is an on-demand skill/tool).
- Multi-turn interactive PR discussion bots.
