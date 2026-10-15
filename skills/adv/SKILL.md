---
name: adv
description: "Adversarial review from another local model."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# adv (Adversarial Review)

Runs a detailed and holistic local adversarial AI code review on outgoing branch commits using an alternate model/engine available on this machine (evaluating architecture, conventions, safety, tests, and diff impacts rather than perfunctory surface checks).

## When this fires

- "adv", "run adv", "get an adversarial review from another model"
- When the user wants a quick adversarial review using a different desktop subscription model (e.g., Codex, Claude, Cursor, OpenCode, Antigravity) without using their primary model's context or quota.

## Usage

**Note:** Until this skill is merged to `main`, you must set `PRE_PUSH_REVIEW_LOCAL_DEV=1` in your environment to use the local branch copy.

Run the `pre-push-review.py` script with the `--engine alternate` flag to rotate through available models, or specify a specific engine.

```bash
# By default, use the trusted installed review script to prevent executing untrusted branch code.
# To override with a local checkout during development, set PRE_PUSH_REVIEW_LOCAL_DEV=1
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$PRE_PUSH_REVIEW_LOCAL_DEV" ] && [ -n "$GIT_ROOT" ] && [ -f "$GIT_ROOT/scripts/pre-push-review.py" ]; then
  REVIEW_SCRIPT="$GIT_ROOT/scripts/pre-push-review.py"
else
  TRUSTED_DIR=$(python3 -c "import os, sys; candidates = [os.environ.get('CLAUDE_PLUGIN_ROOT', ''), '~/.claude/skills/pre-push-review', '~/.gemini/skills/pre-push-review', '~/.cursor/skills/pre-push-review', '~/.codex/skills/pre-push-review', '~/.gemini/config/plugins/ai-config/skills/pre-push-review']; p = next((os.path.realpath(os.path.expanduser(f)) for f in candidates if f and os.path.exists(os.path.expanduser(f))), None); sys.exit('Error: Trusted pre-push-review skill not found') if not p else print(os.path.abspath(p if os.path.isdir(os.path.join(p, 'scripts')) else os.path.join(p, '..', '..')))")
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

```bash
python3 "$REVIEW_SCRIPT" --engine codex
```

## How it works

1. Computes the local outgoing diff against `origin/main` (or PR base).
2. Dispatches the review to the selected alternate model/engine using plan/read-only mode to independently conduct both a detailed implementation defect audit and a holistic change assessment.
3. Parses and validates the structured review findings.
4. Exits with a nonzero code on blocking findings (unless `--allow-findings` is specified).

## Posting review output to a PR

When posting the review result to a PR comment under a user login (e.g. from local or Remote Control sessions),
wrap the output in a header and verdict structure:

```markdown
## Cross-harness review (<engine>) of <HEAD_SHA>

Reviewed-Commit: <HEAD_SHA>

<verbatim review output>

### Verdict

Verdict: <Clean or Needs more work>

_Posted by <Agent Name> (AI agent) --- not written by a human._
```

This ensures `check-pr-fully-clean.py` admits the review by construction
and allows a clean verdict to supersede any earlier standing not-clean comments (#4425).

## Verify cross-model findings before presenting them

A reviewer from another model is a source of leads, not verdicts.
Measured 2026-10-15 (Gemini via `agy`): findings were partly false positives, such as mislabeling which section a reading box sits in, speculative "check whether" items, and mistaking a content-hidden math block for a macro definition.

- **Do:** check each finding against the file at the reviewed SHA (`gh api "repos/<o>/<r>/contents/<path>?ref=<sha>"`, quoted) before presenting it as a finding, and label anything unchecked as an unverified lead.
- **Do:** check PR state first.
  A merged PR gets no comment.
  Head SHAs move while a run is queued, and a queued review reads the head when it starts, so record in each comment the SHA actually read and note any drift.
- **Don't:** relay a speculative "check whether X" item as a defect.

## Name the PR's particular risk in the prompt

Put a `SPECIAL CHECK` paragraph in the cross-model prompt for the PR's own risk (paraphrase distance, link anchors, references to deleted files), not only the generic prompt.

- **Don't:** send only the generic prompt for a PR with a distinctive risk.

When a merge gate names this reviewer, a deterministic check does not replace the named read:
see [`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md#a-gate-that-names-a-reviewer-is-met-by-that-reviewer).

Invocation quirks for the `agy` engine (prompt syntax, no stdin, plan mode, Windows length cap) are in [`memories/antigravity.md`](../../memories/antigravity.md).

## Related

- `pre-push-review`: The underlying script and skill for pre-push reviews.
