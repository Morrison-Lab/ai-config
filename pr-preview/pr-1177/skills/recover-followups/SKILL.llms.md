# recover-followups — find follow-up items that closed PRs/issues promised but never tracked

The recovery counterpart to `defer-issue`. `defer-issue` files a follow-up *when you defer*; this skill goes back through **already-closed** PRs and issues to catch the follow-ups that were mentioned but never turned into a tracked open issue, then offers to file them.

## When this fires

- “recover followups”, “rfu”, “find untracked followups”
- “audit closed PRs for dropped follow-ups”, “what follow-ups slipped through?”, “did we lose any deferred work?”
- Periodically, or after a burst of merges, to make sure nothing promised in a review thread or PR body fell on the floor.

This is the retroactive, cross-PR sweep that the forward and single-scope skills don’t do. `defer-issue` files a follow-up at defer-time. `post-merge` checks only the one PR that just merged. `wrap-up` covers only the current session.

## Procedure

### 1. Scope the sweep (bound it)

Querying *every* closed PR/issue in a busy repo is slow and noisy. Default to a bounded window and **say what window you used**. Let `$ARGUMENTS` narrow it:

- a number → the last N closed PRs/issues (default `N=30`)
- a date → `--search "closed:>=2026-01-01"`
- a label / milestone → `--label tech-debt`, `--milestone v2`
- a specific `#N` → just that one PR/issue

``` bash
gh repo view --json nameWithOwner --jq .nameWithOwner   # confirm the repo
```

The commands below are written for GitHub/`gh`; step 2 also gives the GitLab/`glab` equivalents for the data-pull. Steps 3–5 use GitHub field names (`stateReason`, `closedByPullRequestsReferences`) that have direct GitLab analogues (an MR’s `merged` vs `closed` state, an issue’s closing MR); adapt them. If the matching CLI isn’t installed, say so and stop, and don’t hit the raw API blind.

### 2. Pull the closed items + their discussion

The follow-up promise can live in the body, a comment, or an inline review thread; fetch all three.

``` bash
# Closed PRs and issues in the window
gh pr list   --state closed --limit 30 --json number,title,url,closedAt,body   # LIST_PRS
gh issue list --state closed --limit 30 --json number,title,url,closedAt,body  # LIST_ISSUES

# Per PR: top-level comments + review summaries ...
gh pr view <N> --json number,title,url,body,comments,reviews   # VIEW_PR
# ... and inline review-thread comments (NOT in `gh pr view`):
gh api repos/{owner}/{repo}/pulls/<N>/comments --jq '.[] | {user: .user.login, body, url: .html_url}'   # READ_PR_REVIEW_COMMENTS

# Per issue: body + comments
gh issue view <N> --json number,title,url,body,comments   # VIEW_ISSUE
```

GitLab equivalents (same shape):

``` bash
# In GitLab, a completed MR is `merged`, NOT `closed` (which means abandoned) —
# sweep merged ones (the main follow-up source), and optionally abandoned ones:
glab mr list    --merged --per-page 30   # completed MRs — primary source
glab mr list    --closed --per-page 30   # abandoned MRs — optional
glab issue list --closed --per-page 30
glab mr view <N> --comments          # body + discussion
glab issue view <N> --comments
# inline MR-thread notes, the glab counterpart to `gh api …/pulls/<N>/comments`
# (`:id` is glab's placeholder for the current repo's project — auto-resolved
#  when run inside the repo; no numeric ID needed):
glab api "projects/:id/merge_requests/<N>/notes" --paginate
```

### 3. Extract candidate follow-up mentions

Scan the gathered text for **intent-to-defer** language, not just any keyword. Signal phrases:

- `follow-up`, `followup`, `follow up`
- `defer`, `deferred`, `leave for later`, `for later`, `down the line`, `eventually`, `out of scope`
- `separate PR`, `separate issue`, `future PR`, `another PR`, `in a follow-up`
- `TODO`, `FIXME`, `we should`, `we'll need to`, `should probably`, `worth doing`, `let's revisit`, `I'll open an issue`, `for the next release`
- ARD-summary sections — a `**Deferred**` or `**Acknowledged**` heading in a `@claude`/reviewer comment is the highest-value source: those are explicit “not doing this now” decisions.

A starting regex (tune per repo) — pipe the fetched bodies straight into it (`\b` is GNU-only, so this avoids word boundaries for portability to BSD/macOS grep; `TODO`/`FIXME` may over-match, which the false-positive cull below handles):

``` bash
gh pr view <N> --json body,comments,reviews --jq '.body, (.comments[].body), (.reviews[].body)' \
  | grep -inE "follow[- ]?up|defer|out of scope|separate (pr|issue)|future pr|another pr|for later|down the line|eventually|TODO|FIXME|we should|we'll need to|should probably|worth doing|let's revisit|i'll open an issue|leave .* later|for the next release|acknowledged"   # VIEW_PR
```

Keep, for each hit: the **source** (PR/issue \# + the comment’s `html_url`), the **snippet**, and a one-line **suggested issue title**. Discard obvious false positives, like a `TODO` quoted from code under review, or a follow-up that the same thread says was already done.

### 4. Cross-reference: tracked or untracked?

For each candidate decide whether it’s **already tracked**:

1.  **Does the snippet cite an issue?** (`#123`, `Followup: #123`, a `.../issues/123` URL.) If so, check that issue — and, if closed, *why* it closed:

    ``` bash
    gh issue view 123 --json number,state,stateReason,title,closedByPullRequestsReferences   # VIEW_ISSUE
    ```

    - exists & open → **tracked** (drop it).
    - exists & closed **as completed** — `stateReason == "COMPLETED"`, or a merged PR in `closedByPullRequestsReferences`, or a “fixed in \#X” comment → the work landed → tracked (drop it).
    - exists & closed **as not-planned** — `stateReason == "NOT_PLANNED"` (won’t-fix / duplicate) with no merged PR → the work did **not** land → still **untracked** (keep it; a won’t-fix close doesn’t mean done).
    - doesn’t exist → **dangling reference → untracked**.

2.  **No citation?** Search open issues for a match:

    ``` bash
    gh issue list --state open --search "<keywords from the snippet>" \
      --json number,title,url   # SEARCH_ISSUES
    ```

    - a plausible open issue exists → likely tracked, but **flag low-confidence matches** for the user rather than silently dropping.
    - nothing matches → **untracked follow-up**.

### 5. Report the untracked items

A linked table, never a bare `#N` (repo policy):

| Source | Promised follow-up | Raised in | Suggested issue title |
|----|----|----|----|
| [\#42](url) | “handle nested overrides in a follow-up” | [review thread](comment-url) | Handle nested overrides in session_env merge |

Order by confidence (explicit `**Deferred**` items first, fuzzy `we should…` last). Add the **window you swept** (“last 30 closed PRs + issues”) and a Pacific-time timestamp (`TZ=America/Los_Angeles date "+%Y-%m-%d %H:%M %Z"`; the explicit `TZ` enforces PT on a machine set to any other zone), so the user knows the coverage and the “as of when”.

If the sweep came back empty, say so plainly; don’t manufacture candidates.

### 6. Offer to file (hand off to `defer-issue`)

Don’t auto-file a pile of issues; that breeds duplicates and noise. Present the list, let the user pick which to file, then for each chosen one run the **`defer-issue`** flow: it composes the issue with a `Deferred from PR #X` context line and a back-reference, checks for a `followup`/`deferred` label, and prints the new issue URL. That keeps issue-creation in one place.

## Relationship to other skills

- **`defer-issue`** — the forward op (file at defer-time); step 6 hands off to it to file each recovered item.
- **`post-merge`** — checks deferrals for the single just-merged PR; `recover-followups` is the cross-PR backstop for the ones it (or no one) ever filed.
- **`wrap-up`** — session-level “what’s still open”; this is repo-level “what did past sessions drop”.
- **`pr-status-all`** — sibling whole-repo sweep, but over *open* PRs’ review state rather than *closed* items’ follow-ups.

## Anti-patterns

- ❌ Sweeping *every* closed PR in a large repo with no bound → slow and noisy. Bound the window and state it.
- ❌ Auto-filing every candidate as an issue → duplicates and noise. Present first, file on the user’s pick.
- ❌ Treating any `TODO` (e.g. one quoted from code under review) as a real follow-up → false positives. Match intent-to-defer language.
- ❌ Skipping the cross-reference against open issues → filing duplicates of follow-ups that are already tracked.
- ❌ Reporting bare `#N` instead of markdown-linked PR/issue numbers.
- ❌ Manufacturing candidates when the sweep is genuinely empty.

Back to top
