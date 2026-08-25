---
name: pre-push-review
description: "Run local adversarial AI code review using desktop subscription quota (Claude, Codex, OpenCode, Antigravity)."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# pre-push-review

Runs an automated, single-pass adversarial AI code review on your outgoing branch commits before pushing,
drawing directly on your desktop **Claude Pro/Team**, **ChatGPT**, **OpenCode**, or **Google AI Ultra** subscription quota.

## When this fires

- "review this before I push", "pre-push review", "check my diff locally", "run local review", `/pre-push-review`
- Before running `/push` or `git push` on complex feature branches when you want a second opinion without consuming cloud CI API credits or Claude Code token quotas.

## How it works

1. Computes the local outgoing diff against `origin/main` (or the detected PR base / explicit base branch).
2. Injects repository standards and guidelines (`AGENTS.md`, `GEMINI.md`).
3. Auto-detects and invokes the local AI CLI in plan/read-only mode (`claude` -> `codex` -> `opencode` -> `agy`), with automatic fallback on quota exhaustion.
4. Validates structured findings (Summary Verdict, Critical Findings, Observations, Verification Steps).
5. Optionally posts review verdicts directly to the GitHub PR bound to the reviewed commit SHA.

## Usage

```bash
# Auto-detect local AI CLI (priority: claude -> codex -> opencode -> agy)
python3 scripts/pre-push-review.py

# Review against a specific base branch
python3 scripts/pre-push-review.py --base origin/develop

# Explicitly choose AI engine ('claude', 'codex', 'opencode', or 'antigravity')
python3 scripts/pre-push-review.py --engine codex

# Pass custom model override
python3 scripts/pre-push-review.py --engine codex --model gpt-5.6-sol

# Post the review report directly to the current GitHub PR
python3 scripts/pre-push-review.py --post

# Save output to a markdown file
python3 scripts/pre-push-review.py -o review.md
```

## Integration with `push` skill

Before executing `git push`, run `pre-push-review` to verify that no logical bugs, edge cases, or guideline regressions exist.
Once clean, proceed with standard push guards.

## Relationship to other skills

- **`push`** --- The pre-push collision guard.
  Run `pre-push-review` to inspect code quality, then `push` to safely push commits.
- **`delegate-to-codex`** --- General offloading of heavy analysis tasks to Codex CLI.
- **`ardi`** --- PR-level review iteration in GitHub Actions.
