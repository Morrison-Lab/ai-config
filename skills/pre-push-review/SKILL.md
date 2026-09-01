---
name: pre-push-review
description: "Run local adversarial AI code review."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# pre-push-review

Runs an automated, detailed, and holistic adversarial AI code review on outgoing branch commits,
drawing on desktop **Claude Pro/Team**, **ChatGPT**, **OpenCode**, or **Google AI Ultra** subscription quota
(evaluating implementation defects, architecture, conventions, safety, tests, and diff impacts rather than perfunctory surface checks).

## When this fires

- "review this before I push", "pre-push review", "check my diff locally", "run local review", `/pre-push-review`
- "alternate between models", "run adversarial review with codex/claude/cursor"
- Before running `/push` or `git push` on complex feature branches when you want a second opinion without consuming cloud CI API credits or Claude Code token quotas.

## How it works

1. Computes the local outgoing diff against `origin/main` (or the detected PR base / explicit base branch).
2. Injects universal repository standards (`AGENTS.md`).
3. Dispatches to the selected engine or auto-fallback chain in plan/read-only mode (`claude` -> `cursor` -> `codex` -> `opencode` -> `agy`), or alternates round-robin across available models, instructing both a detailed implementation defect audit and a holistic change assessment.
4. Strictly parses and validates structured findings (Summary Verdict, Critical Findings, Observations, Verification Steps, and Reviewed-Commit SHA).
5. Exits nonzero on blocking `Needs work` findings (unless `--allow-findings` is specified) and optionally posts verified review notes directly to the GitHub PR.

## Usage

**Note:** Until this skill is merged to `main`, you must set `PRE_PUSH_REVIEW_LOCAL_DEV=1` in your environment to use the local branch copy.

```bash
# By default, use the trusted installed review script to prevent executing untrusted branch code.
# To override with a local checkout during development, set PRE_PUSH_REVIEW_LOCAL_DEV=1
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$PRE_PUSH_REVIEW_LOCAL_DEV" ] && [ -n "$GIT_ROOT" ] && [ -f "$GIT_ROOT/scripts/pre-push-review.py" ]; then
  REVIEW_SCRIPT="$GIT_ROOT/scripts/pre-push-review.py"
else
  TRUSTED_DIR=$(python3 -c "import os, sys; candidates = ['~/.claude/skills/pre-push-review', '~/.gemini/skills/pre-push-review', '~/.cursor/skills/pre-push-review', '~/.codex/skills/pre-push-review', '~/.gemini/config/plugins/ai-config/skills/pre-push-review']; p = next((os.path.realpath(os.path.expanduser(f)) for f in candidates if os.path.exists(os.path.expanduser(f))), None); sys.exit('Error: Trusted pre-push-review skill not found') if not p else print(os.path.abspath(os.path.join(p, '..', '..')))")
  TMP_WORKTREE=$(mktemp -d)
  trap 'rm -rf "$TMP_WORKTREE"' EXIT
  git -C "$TRUSTED_DIR" archive origin/main | tar -x -C "$TMP_WORKTREE" 2>/dev/null || { echo "Error: Failed to extract trusted origin/main review script. Set PRE_PUSH_REVIEW_LOCAL_DEV=1 to use local branch."; exit 1; }
  REVIEW_SCRIPT="$TMP_WORKTREE/scripts/pre-push-review.py"
fi


# Auto-detect local AI CLI (priority: claude -> cursor -> codex -> opencode -> agy)
python3 "$REVIEW_SCRIPT"

# Alternate among available models/engines across successive runs
if [ -n "$AGENT_NAME" ]; then
  python3 "$REVIEW_SCRIPT" --engine alternate --exclude-engine "$AGENT_NAME"
else
  python3 "$REVIEW_SCRIPT" --engine alternate
fi
```

Review via Claude model through Antigravity CLI:
```bash
python3 "$REVIEW_SCRIPT" --engine agy-claude
```

Explicitly choose AI engine ('claude', 'cursor', 'codex', 'opencode', or 'antigravity'):
```bash
python3 "$REVIEW_SCRIPT" --engine codex
```

Pass custom model override:
```bash
python3 "$REVIEW_SCRIPT" --engine codex --model gpt-5.6-sol
```

Post the review report directly to the current GitHub PR:
```bash
python3 "$REVIEW_SCRIPT" --post
```

Save output to a markdown file:
```bash
python3 "$REVIEW_SCRIPT" -o review.md
```

## Relationship to other skills & guards

- **`push` / pre-push guard**: Standalone multi-vendor adversarial review tool that can be run on-demand across all harnesses.
  Within Claude Code sessions, pre-push enforcement hooks require clean foreground `adversarial-reviewer` subagent audits.
- **`delegate-to-codex`**: General offloading of heavy analysis tasks to Codex CLI.
- **`ardi`**: PR-level review iteration in GitHub Actions.
