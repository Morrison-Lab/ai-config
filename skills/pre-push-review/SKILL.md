---
name: pre-push-review
description: "Run local adversarial AI code review using desktop subscription quota (Claude, Codex, OpenCode, Antigravity)."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# pre-push-review

Runs an automated, single-pass adversarial AI code review on outgoing branch commits,
drawing on desktop **Claude Pro/Team**, **ChatGPT**, **OpenCode**, or **Google AI Ultra** subscription quota.

## When this fires

- "review this before I push", "pre-push review", "check my diff locally", "run local review", `/pre-push-review`
- "alternate between models", "run adversarial review with codex/claude/cursor"
- Before running `/push` or `git push` on complex feature branches when you want a second opinion without consuming cloud CI API credits or Claude Code token quotas.

## How it works

1. Computes the local outgoing diff against `origin/main` (or the detected PR base / explicit base branch).
2. Injects universal repository standards (`AGENTS.md`).
3. Dispatches to the selected engine or auto-fallback chain in plan/read-only mode (`claude` -> `codex` -> `opencode` -> `agy`), or alternates round-robin across available models.
4. Strictly parses and validates structured findings (Summary Verdict, Critical Findings, Observations, Verification Steps, and Reviewed-Commit SHA).
5. Exits nonzero on blocking `Needs work` findings (unless `--allow-findings` is specified) and optionally posts verified review notes directly to the GitHub PR.

## Usage

```bash
# Resolve the review script relative to the installed skill
REVIEW_SCRIPT=$(python3 -c "import os; p=next((os.path.realpath(os.path.expanduser(f)) for f in ['~/.claude/skills/pre-push-review', '~/.gemini/skills/pre-push-review', '~/.cursor/skills/pre-push-review', '~/.codex/skills/pre-push-review'] if os.path.exists(os.path.expanduser(f))), 'skills/pre-push-review'); print(os.path.abspath(os.path.join(os.path.dirname(p), '..', 'scripts', 'pre-push-review.py')))")

# Auto-detect local AI CLI (priority: claude -> cursor -> codex -> opencode -> agy)
python3 "$REVIEW_SCRIPT"

# Alternate among available models/engines across successive runs
python3 "$REVIEW_SCRIPT" --engine alternate

# Review via Claude model through Antigravity CLI
python3 "$REVIEW_SCRIPT" --engine agy-claude

# Explicitly choose AI engine ('claude', 'codex', 'opencode', or 'antigravity')
python3 "$REVIEW_SCRIPT" --engine codex

# Pass custom model override
python3 "$REVIEW_SCRIPT" --engine codex --model gpt-5.6-sol

# Post the review report directly to the current GitHub PR
python3 "$REVIEW_SCRIPT" --post

# Save output to a markdown file
python3 "$REVIEW_SCRIPT" -o review.md
```

## Relationship to other skills & guards

- **`push` / pre-push guard**: Standalone multi-vendor adversarial review tool that can be run on-demand across all harnesses.
  Within Claude Code sessions, pre-push enforcement hooks require clean foreground `adversarial-reviewer` subagent audits.
- **`delegate-to-codex`**: General offloading of heavy analysis tasks to Codex CLI.
- **`ardi`**: PR-level review iteration in GitHub Actions.
