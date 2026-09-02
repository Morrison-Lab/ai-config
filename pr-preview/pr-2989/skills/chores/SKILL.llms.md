# chores — triage and wrap up dependency-bump PRs

Sweep a repo’s open **dependency-bump PRs** — the `chore(...)`-titled, bot-authored PRs from Dependabot/Renovate (pinned GitHub Actions, git submodules, package deps) — and clear them: merge the safe ones, flag the risky ones. These are CI-gated, not review-gated, so they need a different loop than a human PR.

**Default policy:** merge patch/minor bumps once CI is green; for **major** bumps, fetch the changelog, summarize the breaking-change risk, and surface it for the user’s call before merging.

## When this fires

- “handle chores”, “chores”, “do the chores”, “wrap up the chore PRs”
- “process the dependabot PRs”, “merge the dependency bumps”, “deal with the bump PRs”, “handle the dependency updates”
- A weekly Dependabot batch has piled up and you want it cleared.

## What counts as a chore PR

A PR is in scope when **either** of these holds:

- Its author is one of the dependency bots this skill exists for, matched in the exact login form the source returns: `app/dependabot`, `dependabot[bot]`, `app/renovate`, `renovate[bot]`. An explicit `chores` call names that population, which is what admits those two bots and no other author.
- It looks like a chore — the title starts with `chore(` (e.g. `chore(actions):`, `chore(submodule):`, `chore(deps):`), or the labels include `dependencies` — **and** it passes `memories/reviewing-prs.md`’s scope test for the invoking user: authored by the GitHub Actions app (`github-actions`, which opens `chore(submodule):` bumps) or by the invoking user or one of their aliases, assigned to one of them, or one the user explicitly asked this run to work on (a mention such as “do not touch” followed by a number is not a request).

Human-authored feature PRs are **out of scope** — those go through `ardia` / `gia` (review-to-clean), not this skill — and so is a chore-titled or `dependencies`-labelled PR whose author is another lab member or another bot, unless the invoking user is assigned to it or explicitly asked this run to work on it.

## Procedure

### 0. Establish the target repo

Default to the current repo; accept an explicit `owner/name` so you can sweep any repo without checking it out:

``` bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
# e.g. to target another repo:  REPO=owner/other-repo
```

This skill is GitHub-first (`gh`). For a GitLab repo, the same shape applies via `glab` and `@renovate`/`@dependabot`-equivalent commands.

### 1. List the open chore PRs

Set the three scope inputs first, the way `REPO` is set above. `PR_SCOPE_ALIASES` is the comma-separated list of other logins `memories/reviewing-prs.md` names as the same person as the resolved user (leave it unset when that file lists none for them), and `PR_SCOPE_REQUESTED` is the comma-separated list of PR numbers the user explicitly asked this run to work on, never a number merely mentioned or excluded (leave it unset when there are none). `PR_SCOPE_EXCLUDED` is the comma-separated list of PR numbers the user told this run not to touch (“chores, but do not touch” followed by a number); it is a veto checked before every positive arm, bot authors included, so an excluded dependency-bot PR is neither listed nor merged. With all three unset the filter keeps only the resolved login’s own PRs, the assigned ones, and the bots’, which is the fail-closed default.

``` bash
set -eo pipefail   # a failed command, or a failed gh pr list in the pipeline below, stops here
ME=$(gh api user --jq .login 2>/dev/null) || ME=""   # WHO_AM_I
if [ -z "$ME" ]; then
  # Fail closed, and say so: with no identity the author and assignee arms
  # stay unevaluated (aliases included), so only bot-authored and explicitly
  # requested PRs pass.
  PR_SCOPE_ALIASES=""
  echo "::warning::identity lookup failed; author/assignee arms unevaluated (report this)" >&2
fi
# e.g. PR_SCOPE_ALIASES=other-login      # from memories/reviewing-prs.md
# e.g. PR_SCOPE_REQUESTED=123,456       # PRs the user asked this run to work on
# e.g. PR_SCOPE_EXCLUDED=789            # PRs the user told this run not to touch
IDS=$(jq -cn --arg me "$ME" --arg al "${PR_SCOPE_ALIASES:-}" \
  '[$me] + ($al | split(",") | map(select(length > 0))) | map(select(length > 0)) | unique')
REQ=$(jq -cn --arg r "${PR_SCOPE_REQUESTED:-}" \
  '$r | split(",") | map(select(length > 0) | tonumber)')
EXC=$(jq -cn --arg x "${PR_SCOPE_EXCLUDED:-}" \
  '$x | split(",") | map(select(length > 0) | tonumber)')
gh pr list --repo "$REPO" --state open --limit 200 \
  --json number,title,author,assignees,labels,mergeable \
  | jq -r --argjson ids "$IDS" --argjson req "$REQ" --argjson exc "$EXC" '.[] | select(
          ((.number as $n | $exc | index($n)) == null)
          and (
          (.author.login | test("^(app/(dependabot|renovate)|(dependabot|renovate)\\[bot\\])$"))
          or (
            (
              (.author.login | test("^(app/github-actions|github-actions\\[bot\\]|github-actions)$"))
              or ((.author.login as $a | $ids | index($a)) != null)
              or any(.assignees[].login; . as $x | ($ids | index($x)) != null)
              or ((.number as $n | $req | index($n)) != null)
            ) and (
              (.title | startswith("chore("))
              or (([.labels[].name] | index("dependencies")) != null)
            )
          )
          )
        ) | "\(.number)\t\(.mergeable)\t\(.title)"'   # LIST_PRS
```

`--limit 200` because `gh pr list` defaults to 30 — a piled-up weekly backlog would otherwise be silently truncated.

If there are none, say so and stop.

That listing is a snapshot. Assignment, the title, and the labels can all change while the sweep runs, so re-fetch every input the predicate reads (author, assignees, title, labels) and reapply the same predicate, the `PR_SCOPE_EXCLUDED` veto included, immediately before each write action in steps 2-5 (closing a bump PR, a `@dependabot` comment, a merge), and drop and report a PR that no longer passes.

### 2. Classify each PR by bump size

Record the head, the base, and the title before classifying (GitHub only: the pins and the gate they feed have no GitLab form until [\#3021](https://github.com/Morrison-Lab/ai-config/issues/3021)), since the classification, every read in step 3, and the merge in step 4 are claims about one SHA on one target under one title, and Dependabot can replace the head or retitle the PR between any two of them:

``` bash
PINNED=$(gh pr view "$N" --repo "$REPO" --json headRefOid -q .headRefOid)   # VIEW_PR
BASE=$(gh pr view "$N" --repo "$REPO" --json baseRefName -q .baseRefName)   # VIEW_PR; a retarget at the same tip must not pass
TITLE=$(gh pr view "$N" --repo "$REPO" --json title -q .title)   # VIEW_PR; the classification below reads this title
```

If the head, the base name, or the title changes before the merge lands, start again from here, classification included. A retitle moves neither SHA and can turn a patch-looking bump into a major one.

Parse the version pair out of the title (`... from X to Y`) and compare the leading number:

- **patch / minor** — same major and the major is ≥ 1 (`3.0.2 → 3.0.3`, `2.4 → 2.7`) → **safe**.
- **`0.x` bump** (`0.4 → 0.5`, `0.4.1 → 0.4.2`) → **review**; under semver a `0.x` release may break between minor versions, and many `0.x` maintainers don’t respect patch semantics either — don’t wave these through as safe.
- **major** — leading number increases (`4 → 7`, `2 → 3`, `1 → 2`) → **review**.
- **submodule** (`chore(submodule):`) — no semver; it tracks a moving branch by design. Treat a green submodule bump as **safe** (auto-advancing the pointer is the whole point), unless the diff is unexpectedly large. If the repository has migrated to a native plugin for the vendored tool (e.g. `ai-config` as a plugin), close the bump PR and remove the redundant submodule instead per [`remove-redundant-plugin-submodules.md`](../../shared/workflow/remove-redundant-plugin-submodules.md).

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

Immediately before the merge command, require the live head to equal `$PINNED`, the live base name to equal `$BASE`, the live title to equal `$TITLE`, and the base tip to equal the one the currency check tested. That check’s one-liner assigns the base tip to `tip`, so keep it as `TIP=$tip` and restart the gate if the live tip differs. A regenerated head that already contains the base would otherwise pass a currency check with CI never read for it. Then run the base-currency check from [`fully-clean`](../../shared/workflow/fully-clean.md)’s stale-base rule (the Do bullets beginning “for a direct merge”), since a green head can still break the base when the base gained a check after the head’s CI ran. On a base that requires a merge queue, stop and report the bump as blocked: the queue form of the gate is [\#3030](https://github.com/Morrison-Lab/ai-config/issues/3030) and is out of scope until it lands. When that check finds the base stale, the bot-bump recovery is to update the branch pinned to `$PINNED`, wait until `headRefOid` differs from `$PINNED`, with a deadline of a few minutes (expiry is a failed update: stop and report it rather than restarting), and then start again from the top of step 2: re-record `$PINNED` and `$BASE`, re-classify the bump, and rerun the CI and conflict checks against the new pin (review stays skipped on bot PRs). The first different SHA is not necessarily the update’s result, since Dependabot or another writer can replace the head in the same window, so re-classification is what keeps the merge pinned to a head this skill has actually judged. `gh api -X PUT "repos/$REPO/pulls/$N/update-branch" -f expected_head_sha="$PINNED"` merges the base in, pinned to the head whose CI was read. A `422` whose message names an expected-head mismatch (match on the substring `expected head sha`, since the live text carries a curly apostrophe and a trailing period that this ASCII rendering cannot show) means the bot or another writer already replaced that head, so re-read before touching it. Any other `422` is a failed update: stop and read the message. `@dependabot rebase` rewrites the head onto the base branch and also clears a conflict. It too replaces the head, so it is followed by the same bounded wait and restart from step 2, never by a direct merge on the old `$PINNED`. With the pin current and the checks green, merge directly. Dependabot deletes its own branch on merge.

``` bash
gh pr merge "$N" --repo "$REPO" --squash --match-head-commit "$PINNED"   # MERGE_PR; $PINNED is the headRefOid recorded above
```

Pick a merge method the repo actually allows — `--squash` errors when squash merges are disabled; swap in `--merge` or `--rebase` to match the repo’s settings.

Do not arm `gh pr merge --auto` and do not hand the merge to `@dependabot squash and merge`. Auto-merge stays enabled across later pushes and fires on required checks alone, so the classified head can be replaced and different content merge without this skill’s scope and bump-risk checks rerunning. Wait for the checks and merge synchronously with the pin instead.

`@dependabot ...` comment commands do nothing on **Renovate** PRs. Merge those with the same pinned `gh pr merge`, not with the merge checkbox in Renovate’s Dependency Dashboard, which hands the merge to Renovate without the pin.

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
- ❌ Treating human feature PRs as chores (or vice-versa) — a dependency bot’s PR is a chore by author; any other PR needs the `chore(` title or `dependencies` label **and** an in-scope author or assignee, never the title or label alone.

Back to top
