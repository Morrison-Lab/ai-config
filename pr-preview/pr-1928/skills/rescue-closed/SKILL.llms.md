# rescue-closed — comb the graveyard for work worth reviving

Closed is not the same as resolved. Issues get auto-closed by stale bots, closed as “not planned” while the need still stands, or superseded by a PR that itself never merged. PRs get abandoned a hair from the finish line. This skill searches those closed items, ranks the ones still worth doing, and reopens or re-files the keepers — without re-litigating calls that were settled on purpose.

## When this fires

- “rescue closed issues”, “revive a closed PR”, “reopen abandoned work”
- “what closed issues/PRs should we revisit”, “comb the graveyard”
- “resurrect stale issues”, “salvage abandoned PRs”, “rescue-closed”
- Proactively: after clearing the open backlog (`gi` / `gii`), or during planning, when you want to recover threads that fell through.

Distinct from its sibling sweep:

- **`recover-followups`** mines the *content* of closed PRs/issues for promised sub-tasks that were never filed, then files **new** issues for them. It never reopens anything.
- **`rescue-closed`** (this skill) brings back the closed *item itself* — it **reopens** the abandoned PR or stale-closed issue as a whole unit.

Reach for `recover-followups` when a closed PR promised work it never tracked; reach for `rescue-closed` when the closed PR or issue itself should not have stayed closed.

## Procedure

### 1. Search — don’t touch anything yet

Pull closed issues and unmerged-closed PRs along with the signals you’ll triage on.

**GitHub — closed issues** (the not-planned ones are prime candidates):

``` bash
gh issue list --state closed --limit 100 \
  --json number,title,closedAt,stateReason,labels,url \
  --jq 'sort_by(.closedAt) | reverse
        | .[] | "\(.stateReason // "?")\t#\(.number)\t\(.title)\t\(.url)"'   # LIST_ISSUES
```

`NOT_PLANNED` means closed without being done — stale, dropped, or wontfix-for-now — so it is the most likely to be worth a second look. `COMPLETED` means finished; usually leave those closed.

**GitHub — closed PRs that never merged** (abandoned work):

``` bash
gh pr list --state closed --limit 100 \
  --json number,title,closedAt,mergedAt,headRefName,labels,url \
  --jq 'map(select(.mergedAt == null)) | sort_by(.closedAt) | reverse
        | .[] | "#\(.number)\t\(.headRefName)\t\(.title)\t\(.url)"'   # LIST_PRS
```

**GitLab equivalents:**

``` bash
glab issue list --closed --per-page 100 2>&1 | cat
# GitLab keeps "closed" and "merged" as separate MR states, so --closed already
# excludes merged MRs — no extra filtering needed (unlike gh, where closed
# includes merged):
glab mr list --closed --per-page 100 2>&1 | cat
```

### 2. Score what’s worth reviving

For each candidate, weigh:

- **Closed by a stale bot or as not-planned**, not by a deliberate “won’t do” → revive.
- **Still-live need** — the underlying problem still reproduces on current `main`. Run `check-history` to confirm it wasn’t already fixed elsewhere.
- **Interest** — reactions, several commenters, or later issues/PRs that reference it (`gh issue view <N>` / look for “referenced this”).
- **PRs near the finish** — had an approving review or only minor findings, and closed for inactivity rather than rejection. These are the cheapest to land.
- **Not a true duplicate** of something since merged.

Drop anything closed by an explicit human decision — “won’t fix”, “out of scope by design”, or “superseded” where the replacement actually merged. Reopening those re-litigates a settled call.

### 3. Present a ranked shortlist

Report a table to the user: link, type (issue / PR), why it closed, why it’s worth reviving, recommended action. Link every `#N` as a markdown link to its URL. Don’t act yet — let the user pick from the shortlist.

### 4. Rescue the picks

Before touching any item, **claim it** (`claim-pr`) so parallel sessions or the `@claude` bot don’t collide, and **check history** (`check-history`).

**Issue:**

``` bash
gh issue reopen <N> --comment "Reviving: <why it still matters>."   # REOPEN_ISSUE
```

If reopening is wrong — a messy thread, or scope has shifted — file a fresh issue that links the old one, then hand off to `st` / `gi`.

**PR — branch still exists:**

``` bash
gh pr reopen <N>                          # REOPEN_PR
git fetch origin                          # FETCH
git switch --track origin/<headRefName>   # explicit remote; on older Git:
                                          # checkout -b <headRefName> origin/<headRefName>
git merge origin/main                     # resync onto current main; resolve, run checks  # MERGE_BRANCH
```

**PR — branch still exists, but drifted far behind `main`:** when the branch is months stale, merging `origin/main` is a huge, mostly-irrelevant conflict (a regenerated lockfile, hundreds of files) and the real change is small — don’t fight the merge. Rebuild just the intended diff as one clean commit on current `main` and force-push it to the PR’s branch. This keeps the PR number, assignees, and review history while dropping the branch’s incidental churn (stale lockfiles, merge commits, “test” commits):

``` bash
gh pr reopen <N>                          # REOPEN_PR
git fetch origin                          # FETCH
git checkout -B rescue-<N> origin/main
# re-apply only the intended change by hand (not the old branch's byproducts), commit
git push --force-with-lease origin rescue-<N>:<headRefName>
```

After reopening, GitHub will likely flag the PR as having merge conflicts (`mergeableState: dirty`). That state reflects the stale branch, not the real change — the clean rebuild resolves it. Also re-bump the version if the stale branch’s bump now trails `main`. (If the session can only push to its own branch — see CLAUDE.md’s “Use the existing PR branch” exception — fall back to a new superseding PR instead of the force-push.)

**PR — branch was deleted:** recreate it from the old diff, then open a fresh PR that says “Revives \#”:

``` bash
gh pr diff <N> > /tmp/pr-<N>.patch   # DIFF_PR
git fetch origin main && git checkout -b revive-<N> origin/main
git apply /tmp/pr-<N>.patch   # resolve any rejects, run the repo's checks
```

### 5. Hand off

- Reopened issue → `gi` / `st` to implement.
- Reopened or recreated PR → `ardi` to drive to clean.

## Relationship to other skills

- **`check-history`** — read-only look back at merged + closed history before acting. `rescue-closed` is its action counterpart: it brings the worthwhile closed items back rather than just reading them.
- **`recover-followups`** — the sweep that mines closed items’ *content* for untracked follow-up sub-tasks and files fresh issues, instead of reopening the item itself. Use it when the value is a buried promise, not the whole closed item.
- **`gi` / `gii` / `st`** — implement a revived issue.
- **`ardi`** — drive a reopened or recreated PR to clean.
- **`claim-pr`** — claim the issue/PR before working it.
- **`clean-branches` / `prune`** — the opposite sweep: retire dead branches. Cross-check so you don’t recreate a branch `prune` just deleted on purpose.
- **`workaround-watcher`** — for an upstream item you’re blocked on, watch and auto-revert when it resolves, instead of manually reviving it later.
- **`defer-issue`** — the forward path (push work to a tracked issue); `rescue-closed` recovers the ones that still fell through.

## Anti-patterns

- ❌ Reopening items closed by deliberate decision (won’t-fix, or superseded-and-landed) — re-litigates settled calls.
- ❌ Reviving without confirming the need still exists on current `main` (skipping `check-history`).
- ❌ Acting before claiming — colliding with `@claude` or another session.
- ❌ Recreating a PR branch that `clean-branches` just retired on purpose.
- ❌ Bulk-reopening everything closed-as-not-planned. Triage to a shortlist and let the user choose.

Back to top
