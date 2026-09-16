# Cancel Superseded Pipelines

Cancel older pipelines on the same branch that have been superseded by a newer push, freeing CI runners for the latest pipeline.

> **GitLab-only.** This skill drives `glab` against GitLab CI pipelines. There is no GitHub equivalent here — on a GitHub repo, cancel superseded runs with `gh run cancel <run-id>` instead (or rely on per-PR `concurrency` in the workflow, which auto-cancels superseded runs).

## When to use

- After pushing a fix commit when an older pipeline on the same branch is still running
- When runners are busy and newer pipelines are stuck in `pending`
- When asked to “cancel old pipelines”, “free up runners”, or “cancel superseded”
- Proactively during ARDI loops when multiple pushes happen in quick succession

## Procedure

0.  **Resolve the project ID once** (so the rest of the steps reference `$PROJECT_ID` instead of a manual placeholder):

``` bash
PROJECT_ID="$(glab api "projects?search=$(basename "$(git rev-parse --show-toplevel)")" 2>/dev/null | \
  python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")"
echo "PROJECT_ID=$PROJECT_ID"
```

If the search returns more than one project (same repo name in different groups), set `PROJECT_ID` by hand from `glab api "projects?search=<name>"`.

1.  **Identify the current branch and its latest pipeline:**

``` bash
BRANCH=$(git branch --show-current)
# Get pipelines for this branch, newest first
glab api "projects/$PROJECT_ID/pipelines?ref=$BRANCH&sort=desc&per_page=10" | \
  python3 -c "
import json, sys
try: pipelines = json.load(sys.stdin)
except json.JSONDecodeError: sys.exit(1)   # glab error already on stderr; don't add a traceback
for p in pipelines:
    print(f'{p[\"id\"]:>6}  {p[\"status\"]:12s}  {p[\"ref\"]}')
" | cat
```

2.  **Preview which pipelines would be canceled.** Keep the **first** (newest) pipeline; everything older that’s `running`/`pending`/`created` is a cancel candidate. This step only *prints* — nothing is canceled yet:

``` bash
glab api "projects/$PROJECT_ID/pipelines?ref=$BRANCH&sort=desc&per_page=10" | \
  python3 -c "
import json, sys
try: pipelines = json.load(sys.stdin)
except json.JSONDecodeError: sys.exit(1)   # glab error already on stderr; don't add a traceback
active = [p for p in pipelines if p['status'] in ('running', 'pending', 'created')]
if len(active) <= 1:
    print('Nothing to cancel — at most one active pipeline.'); sys.exit(0)
print(f'Keeping newest: #{active[0][\"id\"]} ({active[0][\"status\"]})')
for p in active[1:]:
    print(f'Would cancel:   #{p[\"id\"]} ({p[\"status\"]})')
" | cat
```

3.  **Execute the cancels.** Once the preview looks right, re-run the same query and pipe the emitted `glab api` commands into a loop — the IDs are filled in automatically (nothing to copy-paste), and each cancel’s resulting status is printed, so a failure is visible rather than silent:

``` bash
if ! CANCEL_CMDS=$(glab api "projects/$PROJECT_ID/pipelines?ref=$BRANCH&sort=desc&per_page=10" | \
  python3 -c "
import json, sys
try: pipelines = json.load(sys.stdin)
except json.JSONDecodeError: sys.exit(1)   # glab error already on stderr; don't add a traceback
active = [p for p in pipelines if p['status'] in ('running', 'pending', 'created')]
for p in active[1:]:
    print(f'glab api -X POST projects/$PROJECT_ID/pipelines/{p[\"id\"]}/cancel')
"); then
  echo "Pipeline query failed — check PROJECT_ID and glab auth (see stderr above)."
elif [ -z "$CANCEL_CMDS" ]; then
  echo "Nothing to cancel — at most one active pipeline."
else
  echo "$CANCEL_CMDS" | while read -r cmd; do
    echo "+ $cmd"
    eval "$cmd" 2>&1 | python3 -c "import json,sys; print('  ->', json.load(sys.stdin).get('status','?'))" 2>/dev/null \
      || echo "  -> FAILED (cancel did not return valid JSON)"
  done
fi
```

`$PROJECT_ID` inside the Python f-string is expanded by the **shell** before Python runs (the `python3 -c` body is in a double-quoted string), so each emitted line carries the real numeric project id — it is not a missing Python variable. `eval "$cmd"` is safe here: every emitted command is a fixed `glab api -X POST …/{id}/cancel` string whose only interpolated value is an integer pipeline `id` straight from the API — no user-controlled or free-text fields are evaled.

(The listing calls don’t redirect `2>&1` into Python: on an API error `glab` writes to stderr and Python sees empty stdin. The `try/except json.JSONDecodeError: sys.exit(1)` then exits cleanly — no Python traceback — so `glab`’s own stderr message is the sole diagnostic, and the non-zero exit drives the `if !` branch to “Pipeline query failed”. The `eval`-loop status parse is likewise wrapped with `2>/dev/null` so a non-JSON cancel response surfaces only as `FAILED`.)

> The preview (step 2) **is** the confirmation gate — eyeball it before running step 3. For a per-command y/n prompt instead, replace the loop body with `read -p "run: $cmd ? " a </dev/tty && [ "$a" = y ] && eval "$cmd"`.

4.  **For multi-branch cleanup** (e.g., after pushing fixes to multiple MR branches), cancel superseded pipelines on each ref in one pass, piping into the same status-surfacing loop as step 3:

``` bash
for BRANCH in branch1 branch2; do
  echo "=== $BRANCH ==="
  if ! CANCEL_CMDS=$(glab api "projects/$PROJECT_ID/pipelines?ref=$BRANCH&sort=desc&per_page=10" | \
    python3 -c "
import json, sys
try: pipelines = json.load(sys.stdin)
except json.JSONDecodeError: sys.exit(1)   # glab error already on stderr; don't add a traceback
active = [p for p in pipelines if p['status'] in ('running', 'pending', 'created')]
for p in active[1:]:
    print(f'glab api -X POST projects/$PROJECT_ID/pipelines/{p[\"id\"]}/cancel')
"); then
    echo "  Pipeline query failed — check PROJECT_ID and glab auth (see stderr above)."
    continue
  elif [ -z "$CANCEL_CMDS" ]; then
    echo "  Nothing to cancel — at most one active pipeline."
  else
    echo "$CANCEL_CMDS" | while read -r cmd; do
      echo "+ $cmd"
      eval "$cmd" 2>&1 | python3 -c "import json,sys; print('  ->', json.load(sys.stdin).get('status','?'))" 2>/dev/null \
        || echo "  -> FAILED (cancel did not return valid JSON)"
    done
  fi
done
```

To dry-run instead, `echo "$CANCEL_CMDS"` (or skip the `if`/`else` and just print the variable) — that shows the raw `glab api … cancel` commands without running them. For the friendly `Would cancel: #N` listing, run step 2’s preview per branch.

## Notes

- **Project ID**: step 0 resolves it automatically from the repo name. If that fails (ambiguous name, no API access), look it up manually with `glab api "projects?search=<repo-name>" | python3 -c "..."`.
- **Don’t cancel across branches** — only cancel older pipelines on the *same* ref.
- **Don’t cancel `success` or `failed`** pipelines — they’re already done.
- The `claude-review` job runs early and fast; the `check-package` job is usually what’s hogging the runner. Canceling a superseded pipeline frees the runner for the newer one.
- Always pipe `glab api` through `| cat` to avoid pager issues.

Back to top
