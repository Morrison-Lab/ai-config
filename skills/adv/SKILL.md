---
name: adv
description: "Get an adversarial review from another model available on this machine."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# adv (Adversarial Review)

Runs a local adversarial AI code review on outgoing branch commits using an alternate model/engine available on this machine.

## When this fires

- "adv", "run adv", "get an adversarial review from another model"
- When the user wants a quick adversarial review using a different desktop subscription model (e.g., Codex, Claude, OpenCode, Antigravity) without using their primary model's context or quota.

## Usage

Run the `pre-push-review.py` script with the `--engine alternate` flag to rotate through available models, or specify a specific engine.

```bash
# Resolve the review script relative to the installed skill or local worktree
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$GIT_ROOT" ] && [ -f "$GIT_ROOT/scripts/pre-push-review.py" ]; then
  REVIEW_SCRIPT="$GIT_ROOT/scripts/pre-push-review.py"
else
  REVIEW_SCRIPT=$(python3 -c "import os; p=next((os.path.realpath(os.path.expanduser(f)) for f in ['~/.claude/skills/adv', '~/.gemini/skills/adv', '~/.cursor/skills/adv', '~/.codex/skills/adv'] if os.path.exists(os.path.expanduser(f))), 'skills/adv'); print(os.path.abspath(os.path.join(os.path.dirname(p), '..', 'scripts', 'pre-push-review.py')))")
fi

python3 "$REVIEW_SCRIPT" --engine alternate

# Or explicitly choose an alternate engine (e.g., if you are currently using Claude, you might use Codex or OpenCode)
python3 "$REVIEW_SCRIPT" --engine codex
```

## How it works

1. Computes the local outgoing diff against `origin/main` (or PR base).
2. Dispatches the review to the selected alternate model/engine using plan/read-only mode.
3. Parses and validates the structured review findings.
4. Exits with a nonzero code on blocking findings (unless `--allow-findings` is specified).

## Related

- `pre-push-review`: The underlying script and skill for pre-push reviews.
