# chores — triage and wrap up dependency-bump PRs

Sweep a repo’s open **dependency-bump PRs** — the `chore(...)`-titled, bot-authored PRs from Dependabot/Renovate (pinned GitHub Actions, git submodules, package deps) — and clear them: merge the safe ones, flag the risky ones. These are CI-gated, not review-gated, so they need a different loop than a human PR.

**Default policy:** merge patch/minor bumps once CI is green; for **major** bumps, fetch the changelog, summarize the breaking-change risk, and surface it for the user’s call before merging.

## When this fires

- “handle chores”, “chores”, “do the chores”, “wrap up the chore PRs”
- “process the dependabot PRs”, “merge the dependency bumps”, “deal with the bump PRs”, “handle the dependency updates”
- A weekly Dependabot batch has piled up and you want it cleared.

## What counts as a chore PR

A PR is in scope if **any** of these hold:

- Author is a bot: `app/dependabot`, `dependabot[bot]`, `app/renovate`, `renovate[bot]`.
- Title is a conventional-commit chore: starts with `chore(` (e.g. `chore(actions):`, `chore(submodule):`, `chore(deps):`).
- Labels include `dependencies`.

Human-authored feature PRs are **out of scope** — those go through `ardia` / `gia` (review-to-clean), not this skill.

## Procedure

### 0. Establish the target repo

Default to the current repo; accept an explicit `owner/name` so you can sweep any repo without checking it out:

``` bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
# e.g. to target another repo:  REPO=owner/other-repo
```

This skill is GitHub-first (`gh`). For a GitLab repo, the same shape applies via `glab` and `@renovate`/`@dependabot`-equivalent commands.

### 1. List the open chore PRs

``` bash
gh pr list --repo "$REPO" --state open --limit 200 \
  --json number,title,author,labels,mergeable \
  --jq '.[] | select(
          (.author.login | test("dependabot|renovate"))
          or (.title | startswith("chore("))
          or ([.labels[].name] | index("dependencies"))
        ) | "\(.number)\t\(.mergeable)\t\(.title)"'   # LIST_PRS
```

`--limit 200` because `gh pr list` defaults to 30 — a piled-up weekly backlog would otherwise be silently truncated.

If there are none, say so and stop.

### 2. Classify each PR by bump size

Parse the version pair out of the title (`... from X to Y`) and compare the leading number:

- **patch / minor** — same major and the major is ≥ 1 (`3.0.2 → 3.0.3`, `2.4 → 2.7`) → **safe**.
- **`0.x` bump** (`0.4 → 0.5`, `0.4.1 → 0.4.2`) → **review**; under semver a `0.x` release may break between minor versions, and many `0.x` maintainers don’t respect patch semantics either — don’t wave these through as safe.
- **major** — leading number increases (`4 → 7`, `2 → 3`, `1 → 2`) → **review**.
- **submodule** (`chore(submodule):`) — no semver; it tracks a moving branch by design. Treat a green submodule bump as **safe** (auto-advancing the pointer is the whole point), unless the diff is unexpectedly large.

When the title has no parseable version (some Renovate digests), fall back to the PR body’s update table or treat it as **review**.

### 3. Verify CI is fully green

A bump is only “safe to merge” if every required check passes. `skipping` is fine (path-filtered jobs); `pending` means wait, `fail` means stop.

``` bash
gh pr checks "$N" --repo "$REPO"   # PR_CHECKS
# pass / skipping → ok;  pending → not ready yet;  fail → do not merge
```

Also confirm it isn’t conflicting:

``` bash
gh pr view "$N" --repo "$REPO" --json mergeable,mergeStateStatus \
  --jq '"\(.mergeable) / \(.mergeStateStatus)"'   # VIEW_PR
```

If `CONFLICTING` / `DIRTY`, ask the bot to rebase rather than resolving by hand:

``` bash
gh pr comment "$N" --repo "$REPO" --body "@dependabot rebase"   # COMMENT_PR — Dependabot only
```

For a Renovate PR, tick the rebase checkbox in the PR body (or its Dependency Dashboard) — `@dependabot` comment commands do nothing on Renovate PRs.

### 4. Safe bumps (patch / minor / submodule + green) → merge

Merge directly. Dependabot deletes its own branch on merge.

``` bash
gh pr merge "$N" --repo "$REPO" --squash   # MERGE_PR
```

Pick a merge method the repo actually allows — `--squash` errors when squash merges are disabled; swap in `--merge` or `--rebase` to match the repo’s settings.

If checks are still running and you want it to land once they pass:

``` bash
gh pr merge "$N" --repo "$REPO" --squash --auto   # MERGE_PR — needs auto-merge enabled; swap --squash for --merge/--rebase if squash is disabled
```

For **Dependabot** you can also hand the merge back to the bot — it waits for CI, merges, and deletes its branch (handy when the branch needs a rebase first):

``` bash
gh pr comment "$N" --repo "$REPO" --body "@dependabot squash and merge"   # COMMENT_PR — Dependabot only
```

`@dependabot ...` comment commands do nothing on **Renovate** PRs — for those, use `gh pr merge` (or tick the merge checkbox in Renovate’s Dependency Dashboard).

Batch the safe ones — merge them all in one pass, then report.

### 5. Major bumps → fetch the changelog, summarize, flag

Don’t merge a major bump blind, even when CI is green — a green build can still hide a behavior change. For each:

1.  **Read the release notes Dependabot already embedded in the PR body** — the fastest source:

    ``` bash
    gh pr view "$N" --repo "$REPO" --json body --jq .body   # VIEW_PR
    # look for the "Release notes", "Changelog", and "Commits" sections
    ```

2.  **If the body is thin, go to the source.** For a GitHub Action the title’s dependency name *is* the repo (`actions/checkout`), so:

    ``` bash
    gh api "repos/<dep-owner>/<dep-repo>/releases" --jq '.[] | "\(.tag_name): \(.name)"' | head
    ```

    or `WebFetch` the project’s releases/CHANGELOG page.

3.  **Summarize the breaking-change risk in one or two lines** per PR — required runtime bumps (e.g. a newer Node for `actions/*` v-major jumps), removed inputs, changed defaults — and give a recommendation (merge / hold / needs a workflow tweak first).

4.  **Surface it for the user’s call.** Always get an explicit sign-off before merging a major bump — that human checkpoint is the whole point of flagging it. Don’t self-clear a major because the changelog “looks safe.”

### 6. Report

A linked wrap-up table — every PR number a markdown link (repo policy) — plus a Pacific-time timestamp (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces PT on a machine set to any other zone):

    ## Chores swept — <repo> — <PT timestamp>

    | PR | Bump | Type | CI | Action |
    |----|------|------|-----|--------|
    | [#124](url) | r-spellcheck-action 3.0.2→3.0.3 | patch | ✅ | merged |
    | [#120](url) | actions/checkout 4→7 | major | ✅ | held — needs Node 20+ runtime check |

Group as **Merged**, **Flagged (major — your call)**, and **Skipped** (failing/pending/conflicting, with why). Never report “all clear” while a major bump is sitting unflagged.

## Relationship to other skills

- **`check-dependency-updates` / `cdu`** — the audit counterpart. `cdu` *finds* stale pins and opens/drives the bumps itself (or recommends a `dependabot.yml` that automates them); `chores` *processes* the bump PRs that land. Use `cdu` to catch what Dependabot misses, `chores` to clear what it opens.
- **`ardia` / `gia`** — the human-PR counterpart (drive feature PRs to a clean *review* verdict). `chores` is the bot-PR counterpart (CI-gated bumps). Don’t run `ardi` on a Dependabot PR — `@claude` review is skipped on them by design.
- **`pr-status-all`** — read-only status of every open PR; `chores` is the acting version scoped to bump PRs.
- **`clean-branches` / `cb`** — Dependabot deletes its own remote branch on merge, but if you checked any out locally, sweep the stragglers there.
- **`defer-issue`** — if a major bump needs a real code change before it can land (e.g. migrate a removed Action input), file a follow-up issue instead of leaving the PR to rot.
- **`wrap-up`** — a session-end bookend; `chores` is the focused bump-PR sweep.

## Anti-patterns

- ❌ Merging a major bump just because CI is green, or self-clearing one because the changelog “looks safe” — read the changelog and get an explicit sign-off.
- ❌ Running the full `ardi` review loop on a bot bump PR (review is skipped on them; they’re gated on CI, not a reviewer).
- ❌ Resolving a Dependabot merge conflict by hand — comment `@dependabot rebase` and let the bot redo it.
- ❌ Force-merging a PR with `pending` or `fail` checks.
- ❌ Reporting “chores done” while a flagged major bump is still open with no decision recorded.
- ❌ Treating human feature PRs as chores (or vice-versa) — scope by author / `chore(` title / `dependencies` label.

Back to top
