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
# Alternate among available models/engines
python3 scripts/pre-push-review.py --engine alternate

# Or explicitly choose an alternate engine (e.g., if you are currently using Claude, you might use Codex or OpenCode)
python3 scripts/pre-push-review.py --engine codex
```

## How it works

1. Computes the local outgoing diff against `origin/main` (or PR base).
2. Dispatches the review to the selected alternate model/engine using plan/read-only mode.
3. Parses and validates the structured review findings.
4. Exits with a nonzero code on blocking findings (unless `--allow-findings` is specified).

## Related

- `pre-push-review`: The underlying script and skill for pre-push reviews.
