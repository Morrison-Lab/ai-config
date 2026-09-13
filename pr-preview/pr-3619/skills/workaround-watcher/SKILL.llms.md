# workaround-watcher

Temporary workarounds for upstream bugs tend to become permanent: once the upstream issue is fixed, nobody remembers the workaround exists or why. This skill sets up a **self-removing workaround** — a scheduled workflow that polls the upstream issue/PR and, the moment it’s resolved, opens a PR that reverts your workaround to a known-good target you committed alongside it.

Generalized from `UCD-SERG/shigella`’s `check-upstream-claude-fix.yml`, which watched `anthropics/claude-code-action#1281` and auto-PR’d the revert of a direct-CLI bypass once the action bug was fixed.

## When to use it

- You’ve just added a workaround for a specific, tracked upstream bug (a GitHub issue or PR in another repo) and the “real” fix is “wait for upstream.”
- The workaround is non-trivial enough that you’d want it gone once it’s unnecessary, but you won’t be watching the upstream tracker daily.

Don’t bother for a one-line workaround you’ll obviously notice, or when there’s no concrete upstream artifact to watch.

## The pattern (three pieces)

1.  **The workaround** lives in its normal place (e.g. the modified `.github/workflows/claude.yml`, a pinned dependency, a patched config).
2.  **A committed “target” template** — the desired end-state, stored *outside* the active path so it isn’t itself executed/used (e.g. `.github/templates/<name>-simple.yml`). This is what the file should look like *after* the workaround is removed. Committing it makes the revert mechanical (`cp` + diff) instead of a from-memory rewrite months later.
3.  **The watcher workflow** — a `schedule:` + `workflow_dispatch:` job that checks the upstream artifact’s state and opens the revert PR when it’s resolved.

## Building the watcher

Create `.github/workflows/check-upstream-<slug>.yml`. Structure:

``` yaml
name: Check upstream <slug> fix
on:
  schedule:
    - cron: '0 12 * * 1'   # weekly is plenty; pick a quiet hour/day
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # full history so the revert branch pushes cleanly

      - name: Inspect upstream issue
        id: issue
        env: { GH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
        run: |
          set -euo pipefail
          data=$(gh issue view <N> --repo <owner>/<upstream-repo> \
            --json state,stateReason,url,title)
          state=$(echo "$data" | jq -r '.state')
          reason=$(echo "$data" | jq -r '.stateReason // "null"')
          # Only CLOSED + COMPLETED counts as fixed. NOT_PLANNED / DUPLICATE
          # do NOT mean a fix shipped; a REOPEN shows as OPEN.
          if [ "$state" = "CLOSED" ] && [ "$reason" = "COMPLETED" ]; then
            echo "fixed=true" >> "$GITHUB_OUTPUT"
          else
            echo "fixed=false" >> "$GITHUB_OUTPUT"
          fi
```

Then gate three follow-on steps on `steps.issue.outputs.fixed == 'true'`:

- **Already reverted?** `cmp -s <template> <active-file>` → if equal, nothing to do (`already == 'true'`). Prevents re-acting after the revert merges.
- **PR already open?** `gh pr list --head <revert-branch> --state open` → skip if one exists. Prevents a new duplicate PR every week.
- **Apply + open PR:** create the revert branch, `cp <template> <active-file>`, commit, push, `gh pr create` with a body that links the upstream artifact and gives the reviewer a pre-merge checklist (see below).

## Watching a PR instead of an issue

Use `gh pr view <N> --repo <owner>/<repo> --json state,mergedAt` and treat `state == "MERGED"` as fixed (a PR closed unmerged is not a fix). For a release/tag gate, `gh release view` / `gh api repos/.../releases/latest`.

## Things to get right

- **`CLOSED` is not enough — require `COMPLETED`.** Stale-bots and `NOT_PLANNED`/`DUPLICATE` closes are false positives that would revert a still-needed workaround. (PR-watch equivalent: require `MERGED`, not just `CLOSED`.)
- **Idempotency.** The `cmp` (already-reverted) and `gh pr list` (PR-exists) guards keep a weekly cron from spamming PRs or acting post-merge.
- **Don’t auto-merge.** Open a PR and let a human confirm the fix actually shipped in a version you consume. Put that in the PR body as a checklist:
  - confirm the upstream fix shipped (not closed as a side effect),
  - confirm your pinned version resolves to a release that includes it,
  - a quick post-merge smoke test,
  - “if it regresses, `git revert` — the workaround is preserved in history and the template stays for next time.”
- **Keep the template path out of `.github/workflows/`** so Actions doesn’t try to run it as a workflow. A comment at the top of both the template and the watcher should name the other, so a future editor doesn’t move/rename one and silently break the `cp`.

## Teardown

Once the revert PR merges, the watcher’s `cmp` guard makes it a harmless weekly no-op. You can leave it (cheap insurance if upstream regresses) or delete the watcher + template in the same PR that removes the workaround.

Back to top
