# adv (Adversarial Review)

Runs a detailed and holistic local adversarial AI code review on outgoing branch commits using an alternate model/engine available on this machine (evaluating architecture, conventions, safety, tests, and diff impacts rather than perfunctory surface checks).

## When this fires

- “adv”, “run adv”, “get an adversarial review from another model”
- When the user wants a quick adversarial review using a different desktop subscription model (e.g., Codex, Claude, Cursor, OpenCode, Antigravity) without using their primary model’s context or quota.

## Usage

**Note:** Until this skill is merged to `main`, you must set `PRE_PUSH_REVIEW_LOCAL_DEV=1` in your environment to use the local branch copy.

Run the `pre-push-review.py` script with the `--engine alternate` flag to rotate through available models, or specify a specific engine.

``` bash
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


if [ -n "$AGENT_NAME" ]; then
  python3 "$REVIEW_SCRIPT" --engine alternate --exclude-engine "$AGENT_NAME"
else
  python3 "$REVIEW_SCRIPT" --engine alternate
fi
```

Or explicitly choose an alternate engine (e.g., if you are currently using Claude, you might use Codex or OpenCode):

``` bash
python3 "$REVIEW_SCRIPT" --engine codex
```

## How it works

1.  Computes the local outgoing diff against `origin/main` (or PR base).
2.  Dispatches the review to the selected alternate model/engine using plan/read-only mode to independently conduct both a detailed implementation defect audit and a holistic change assessment.
3.  Parses and validates the structured review findings.
4.  Exits with a nonzero code on blocking findings (unless `--allow-findings` is specified).

## Related

- `pre-push-review`: The underlying script and skill for pre-push reviews.

Back to top
