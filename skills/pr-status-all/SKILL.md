---
name: pr-status-all
description: "Summarize all open PR statuses."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
---

# pr-status-all

Produce a **one-row-per-PR status table** for all open PRs. This is the
whole-queue version of [`pr-status`](../pr-status/SKILL.md): apply the same
"read the **latest** review and parse it for findings" discipline to every
open PR, then lay the results out as a table. It is **read-only** --- it reports
status, it does not push, merge, or run review loops (use
[`ardia`](../ardia/SKILL.md) for that, or
[`sync-pr-branch`](../sync-pr-branch/SKILL.md) to update a branch).

Because the per-PR signals are independent and read-only, gather them
**concurrently** --- one subagent per PR --- then assemble the table. See
*Why fan-out is safe here* for why this loop parallelizes and the write-loops
don't.

## When this fires

- "summarize all open PRs", "status table / dashboard of my PRs",
  "what's the state of every open PR", "which PRs are ready to merge".
- Whenever you'd otherwise report on more than one PR at once.

## CI green ≠ review clean

`gh pr checks <N>` going green is about **CI state**, not the review verdict. A
PR can have every check passing and still carry unaddressed review findings.
Report CI state and review verdict as **separate columns** --- never collapse
them into one "OK".
GitHub `mergeable` / `mergeStateStatus: CLEAN` is not a mergeable column.
A PR without a clean review verdict on the latest commit is not mergeable.
Do not describe it as mergeable.

## Procedure

### 1. Enumerate the open PRs (orchestrator, one cheap call)

```bash
gh pr list --state open --json number,title,headRefName,isDraft,author \
  --jq '.[] | "\(.number)\t\(.headRefName)\t\(.isDraft)\t\(.author.login)\t\(.title)"'   # LIST_PRS
```

This is fast and sequential --- a single call to get the work units.

### 2. Fan out --- one subagent per PR (concurrent)

Spawn **one subagent per open PR, all in a single batch** (multiple `Agent`
calls in one message) so they run at once. The fan-out is read-only, so it
needs **no worktrees** --- each subagent only reads PR signals, nothing mutates,
and there is nothing to collide on.

Give each subagent its PR number, `headRefName`, and `isDraft`, and have it gather the **seven independent signals** below and return one structured row.
Carry the disciplines into the prompt --- a subagent that doesn't follow *Read the LATEST review* will silently misreport:

A subagent starts **fresh** --- it sees only this prompt, not this skill file ---
so **inline the exact commands**; don't point it at a section it can't read.
Fill in `<N>`, `<headRefName>`, `<isDraft>`, `<owner>`, `<repo>` for each PR (resolve owner/repo once with `gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"'`):

> Gather the status of PR **#<N>** (branch `<headRefName>`, draft: `<isDraft>`) in this repo and return a single structured row.
> Do not push, merge, or modify anything.
>
> 1. **Latest review verdict, checked for currency against the head, with hyperlinked comment URL.** Read
>    the *most recent* review comment (including its URL for hyperlinking), author, requested reviewers, and the timestamp of the latest commit:
>    ```bash
>    gh pr view "<N>" --json comments,commits,headRefOid,author,reviewRequests \
>      --jq '{
>        author: .author.login,
>        reviewRequests: [.reviewRequests[].login],
>        review: ([.comments[] | select(.author.login | startswith("claude"))] | last | {url: .url, body: .body, createdAt: .createdAt}),
>        lastCommitDate: (.commits[-1].committedDate),
>        headRefOid: .headRefOid
>      }'
>    ```
>    **This fetches more than `READ_PR_COMMENTS` maps to** -- [`tool-mappings.md`](../../tool-mappings.md)'s entry for that token is a comments-only MCP call, which returns neither `commits` nor `headRefOid`.
>    In a remote/MCP session without `gh`, fetch those fields with separate calls rather than assuming the token mapping covers this expanded query.
>    The reviewer login varies by setup: `gh pr view` reports `claude`; the REST API reports `claude[bot]`.
>    `startswith("claude")` matches both.
>    If `.review` is `null`, the reviewer may post as `github-actions[bot]` or another login -- **never report "clean"**; broaden the filter or say no review was found.
>    **If `.review.createdAt` is earlier than `.lastCommitDate`, the review predates the latest push** -- report `[⏳ In-Flight / Stale](url)` (or `in-flight`), not the review body's verdict, regardless of what it says (both are ISO 8601 UTC timestamps, so a plain string comparison works).
>    When the review body names the commit it reviewed (the `@claude` bot commonly writes "commit `<sha>`"), cross-check that mentioned SHA's prefix against `.headRefOid` (part of the same call above) as a corroborating signal.
>    Treat a mismatch as `[⏳ In-Flight](url)` even if the timing check alone would have said `clean`.
>    **When no SHA can be extracted from the body, don't fall back to trusting the timing check alone as proof of currency** -- report `[⚠️ Unverified](url)` (not `clean`) instead, since `committedDate` is the commit's local committer timestamp, not when GitHub received the push, and a commit authored earlier but pushed later can pass the timing check while still being newer than the review.
>    Only once the review postdates the last commit **and** a named SHA matches -- unconditionally, with no SHA named meaning `[⚠️ Unverified](url)`, not `clean`, full stop -- apply the bar for `clean`: "Looks good" / "no findings" / "approved" with zero follow-on bullets under any heading, hyperlinked as `[✅ Clean (Round N)](url)` or `[✅ Approved](url)`.
>    A rebuttal the reviewer still disputes is **open** (`[❌ Needs Work (Round N)](url)`), not clean.
> 2. **External reviewer verdict (a formal Copilot review, or a human's formal review at the head) -- read-only, don't request one.**
>    The comment above is the `@claude` bot only;
>    a formal review (Copilot's or a human's) is a separate object it won't show.
>    This step **only inspects existing reviews (Copilot's or a human's)** -- it never POSTs a review request.
>    Requesting a review is a mutation (triggers a review job, consumes quota, can collide with a concurrent `ardi` loop), which breaks this skill's whole justification for fanning out subagents concurrently (*read-only, side-effect-free*).
>    If no genuine verdict already exists at the current head, report that fact -- don't try to produce one; that's `ardi`'s job.
>    ```bash
>    set -o pipefail
>    head="$(gh pr view "<N>" --json headRefOid -q .headRefOid)"
>    review_id="$(gh api "repos/<owner>/<repo>/pulls/<N>/reviews" --paginate \
>      | jq -s --arg h "$head" \
>      '[.[][] | select(.user.login=="copilot-pull-request-reviewer[bot]" and .commit_id==$h)] | last | .id')"
>    if [ -n "$review_id" ] && [ "$review_id" != "null" ]; then
>      gh api "repos/<owner>/<repo>/pulls/<N>/reviews/$review_id" --jq '{state, body}'
>      gh api "repos/<owner>/<repo>/pulls/<N>/comments" --paginate \
>        | jq -s --arg rid "$review_id" \
>        '[.[][] | select(.pull_request_review_id == ($rid | tonumber))] | .[] | {line: (.line // .original_line), body}'
>    else
>      echo "no Copilot review exists at the current head"
>    fi
>    ```
>    Clean requires **three** things: an affirmative zero-new-findings overview (e.g. "generated no new comments" -- never a literally empty body), zero matched inline comments, **and no suppression block in the body**.
>    Match inside the `<summary>` heading, case-insensitively on `suppressed` -- not on either exact phrase, and not anywhere in the body.
>    A stub-like non-answer ("ineligible", "reached their quota limit") is not a verdict either.
>    **A human's formal review at the current head counts as an external verdict too** -- check for one whenever the Copilot half found no clean verdict, before settling on `no verdict at head`:
>    ```bash
>    set -o pipefail
>    head="$(gh pr view "<N>" --json headRefOid -q .headRefOid)"
>    gh api "repos/<owner>/<repo>/pulls/<N>/reviews" --paginate \
>      | jq -s --arg h "$head" \
>      '[.[][] | select(.user.type == "User" and .commit_id == $h
>                       and .state != "DISMISSED")]
>       | group_by(.user.login)
>       | map(sort_by(.submitted_at) | last
>             | {id, login: .user.login, state, submitted_at})'
>    ```
>    The `head=` line is repeated deliberately so this block is self-contained: shell state does not persist across separate Bash invocations, and a subagent that runs each fence as its own call would otherwise pass an empty `$h` that matches no review's `commit_id` -- a silent `[]` every time.
>    The `.state != "DISMISSED"` exclusion is load-bearing: GitHub's dismiss action flips the review's own `state` in place rather than adding a new review, and retracts neither its body nor its inline threads.
>    The `group_by(.user.login)` reduces **per reviewer** before taking each one's latest: two humans can review the same head, and a bare `| last` over the combined list would let a later clean "LGTM" from one reviewer silently drop an earlier reviewer's body-only findings.
>    Filter on `.user.type == "User"`, not on a login list -- a bot's REST user object carries `type: "Bot"`, so the type field needs no bot-login blocklist (measured 2026-08-15).
>    Judge each matched review by **substance, not state**: 106 of 106 formal reviews across 60 merged PRs on this repo are `COMMENTED`, zero `APPROVED` (measured 2026-07-30 on #668).
>    Fetch each matched review's body and inline comments.
>    An affirmative zero-findings read across every matched review means a genuine external verdict at the head.
>    Findings in any of them mean `N open`.
> 3. **CI state** -- `gh pr checks <N>` (`PR_CHECKS`); report `🟢 All Green` or `❌ Failing (<check-name>)` or `⏳ Pending (<check-name>)`.
> 4. **Reviewers Requested & Author Awareness** -- check `.author.login`, `.reviewRequests`, and human review status.
>    - If human review has requested changes, report `❌ Changes requested by <login>`.
>    - If `.author.login` is the current user / repo owner (`the repository owner`), report `*Self-authored* (GitHub prevents requesting review from author)`.
>    - If AI review is clean/approved and CI is green:
>      - If human reviewer is requested (e.g. `the repository owner`), report `the repository owner`.
>      - If `reviewRequests` is empty, report `⚠️ None (Request human review)`.
>    - If AI review is clean/approved but CI is failing or pending, report `- (CI in progress / failing)`.
>    - If AI review is still in-flight or unclean, report `- (AI review in progress)`.
> 5. **Unresolved threads** -- count open inline review threads (`READ_PR_REVIEW_COMMENTS`).
>    ```bash
>    gh api graphql -f query='query {
>      repository(owner:"<owner>", name:"<repo>") {
>        pullRequest(number:<N>) {
>          reviewThreads(first:100) {
>            totalCount
>            nodes { isResolved }
>          }
>        }
>      }
>    }' --jq '.data.repository.pullRequest.reviewThreads as $rt |
>      ($rt.nodes | map(select(.isResolved | not)) | length) as $open |
>      if $rt.totalCount > ($rt.nodes | length)
>      then "\($open)+ open (cap)"
>      else if $open == 0 then "resolved" else "\($open) open" end
>      end'
>    ```
> 6. **Behind main?** -- `git fetch origin main <headRefName> -q && git rev-list --count origin/<headRefName>..origin/main`.
> 7. **Blocking human `CHANGES_REQUESTED`** (`READ_PR_REVIEWS`):
>    ```bash
>    gh pr view "<N>" --json reviews \
>      --jq '[.reviews[] | select(.author.login != null and (.state == "APPROVED" or .state == "CHANGES_REQUESTED" or .state == "DISMISSED"))] | group_by(.author.login) | map(sort_by(.submittedAt) | last) | [.[] | select(.state == "CHANGES_REQUESTED") | .author.login]'
>    ```
>    Filter to only `APPROVED`/`CHANGES_REQUESTED`/`DISMISSED` states *before* reducing to each author's latest review -- reducing over all states first lets a later `COMMENTED` round hide an earlier `CHANGES_REQUESTED` (verified with synthetic fixtures).
>    Keep `DISMISSED` in the filter so an explicit dismissal clears an older `CHANGES_REQUESTED`.
>    Any non-empty result **blocks** regardless of what any bot says -- report `changes requested by <login>`.
>
> Return: PR number, Author, isDraft, AI Review (`[✅ Clean (Round N)](url)` / `[⏳ In-Flight](url)` / `[⚠️ Unverified](url)` / `[❌ Needs Work](url)` / `none found`), External Review (`clean` / `N open` / `no verdict at head`), Human Blocked (`none` / `changes requested by <login>`), CI State (`🟢 All Green` / `❌ Failing (<name>)` / `⏳ Pending (<name>)`), Reviewers Requested (`the repository owner` / `*Self-authored*` / `⚠️ None` / `❌ Changes requested by <login>` / `- (CI in progress / failing)` / `- (AI review in progress)`), Threads (`resolved` / `N open`), Behind-main (`up to date` / `N commits`), Next Step (computed per the deterministic transition rules).

### 3. Assemble (orchestrator)

Collect the rows the subagents return and **pair each with the `title`, `headRefName`, and `isDraft`** the orchestrator already has from step 1 (the subagent doesn't re-fetch these), then render the table + per-PR findings list (see *Output*) --- marking draft PRs clearly (e.g. `[#<N>](url) (Draft)`).

### Graceful degradation to series

If subagent fan-out is unavailable (no `Agent` tool in the session), fall back to gathering the seven signals **in series** -- loop the exact same per-PR gather (items 1-7 above, including the currency check, thread resolution, behind-main check, and the human `CHANGES_REQUESTED` check) over each PR from step 1.
The output is the same; it is just sequential.
Don't substitute a simplified comments-only query here -- that would silently drop the current-head, thread-resolution, and human-review guarantees the rest of this skill relies on.

## Output

### Primary Review Summary Table

A Markdown table, one row per open PR, with these columns:

| PR | Author | AI Review Verdict | CI State | Reviewers Requested | Next Step |
|:---|:---|:---:|:---:|:---:|:---|
| [#101](url) | `the repository owner` | [✅ Approved (Round 3)](url) | 🟢 All Green | *Self-authored* (GitHub prevents requesting review from author) | Ready for self-merge |
| [#102](url) | `external-dev` | [✅ Clean (Round 2)](url) | 🟢 All Green | `the repository owner` | Ready for human review |
| [#103](url) | `external-dev` | [✅ Clean (Round 1)](url) | 🟢 All Green | ⚠️ None (Request human review) | Request human review |
| [#104](url) | `external-dev` | [❌ Needs Work (Round 1)](url) | 🟢 All Green | - (AI review in progress) | Drive to clean (ARDI) |
| [#105](url) (Draft) | `external-dev` | - | ⏳ Pending (build) | - | Draft (Work in progress) |

- **PR** --- markdown link `[#<N>](https://github.com/<owner>/<repo>/pull/<N>)`, appended with `(Draft)` if `isDraft` is true.
- **Author** --- author login.
- **AI Review Verdict** --- hyperlinked directly to the latest review comment URL (e.g. `[✅ Clean (Round N)](https://github.com/...#issuecomment-...)`).
  Verified current with the latest commit (`.createdAt >= .lastCommitDate` and matching commit SHA).
  If the review predates the latest push, display `[⏳ In-Flight / Stale](url)`.
  If no SHA is named, display `[⚠️ Unverified](url)`.
- **CI State** --- `🟢 All Green` / `❌ Failing (<name>)` / `⏳ Pending (<name>)`.
- **Reviewers Requested** --- evaluates human review status per [`copilot-review-before-human.md`](../../shared/vendored/copilot-review-before-human.md).
  If human review has requested changes, flag `❌ Changes requested by <login>`.
  For self-authored PRs, note `*Self-authored*`.
  When AI review is clean and CI is green, list requested reviewers (e.g. `the repository owner`) or flag `⚠️ None (Request human review)`.
  When AI review is clean but CI is failing or pending, display `- (CI in progress / failing)`.
  When AI review is in-flight or unclean, display `- (AI review in progress)`.
- **Next Step** --- computed deterministically using the full state matrix:
  - If `isDraft`: `Draft (Work in progress)`.
  - If human `CHANGES_REQUESTED` is pending: `Blocked on human changes (<login>)` (overrides everything below).
  - If branch is behind main: `Resolve conflicts / Sync main (<N> commits behind)`.
  - If CI is failing: `Fix CI (<failing-check>)`.
  - If unaddressed review threads remain: `Resolve inline threads (<N> open)`.
  - If AI review or External review has open findings: `Drive to clean (ARDI)`.
  - If AI review is running: `In-flight AI review`.
  - If CI is pending: `Wait for CI (<pending-check>)`.
  - If neither AI review nor External review has a verified clean verdict at head: `Confirm review (no verified verdict at head)`.
  - If fully clean (no human blocks, at least one verified clean review at head with 0 open findings across all reviews, CI green, 0 open threads, up to date with main):
    - If `Author` is `the repository owner` (self-authored): `Ready for self-merge`.
    - If `Author` is external and human review is requested (`the repository owner`): `Ready for human review`.
    - If `Author` is external and human review is not yet requested: `Request human review`.

### Extended Technical Dashboard (Optional / On Request)

When detailed git/thread metrics are needed, include the extended columns:

| PR | Title | Branch | CI | Review | External | Human | Threads | Behind main | Next Step |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|

Below the table, list each PR's open findings briefly (or "none"), and call out anything needing action: branches behind main, failing CI, drafts, reviews that returned `null`, or a pending human review.
Do **not** label a PR "ready to merge" or "mergeable" unless it is **fully clean** -- **Human is `none`** (a blocking human review overrides everything below) *and* at least one of Review or External is `clean` at the current head *and* neither one has open findings *and* all CI workflows are green *and* it's not behind main *and* every inline review thread is resolved.
Never hedge with "ready except for one nit."

## Why fan-out is safe here (and the write-loops stay series)

This loop parallelizes because its units are **independent and side-effect-free**
--- each PR's signals are read-only and don't depend on any other PR. The
whole-queue *write* loops are different, and deliberately stay (mostly) series:

- **`ardia` / `iterate-all`** --- share one working directory, compete for CI
  runner capacity, and have human checkpoints. Parallelize only opt-in, with
  worktree isolation + bounded concurrency --- not by default.
- **`gii` / `gia`** --- intentionally sequential: a later issue's base branch
  depends on whether the prior MR merged, and same-file issues conflict.
  **`gip`** is the opt-in exception --- it fans out only the *provably
  independent* subset (no stacking dependency, no file overlap), each subagent
  in its own worktree, and sends everything else back through `gii`.

Rule of thumb: fan out a whole-queue loop only when its units are provably
independent and don't mutate shared state --- like this one.

## Notes

- Extended operational rationale, empirical measurements, and synthetic fixture histories live in [`pr-status-all.rationale.md`](pr-status-all.rationale.md).
- Skip draft PRs from the "ready" assessment but still show them (mark as
  draft).
- One unit of work per PR: in the parallel path that's one subagent per PR; in
  the series fallback it's one gather per PR. Either way, the *output* table and
  findings list are identical.

## Relationship to other skills

- **`pr-status`** --- the single-PR version; this applies its latest-review-only /
  `null`-not-clean discipline across the whole open-PR queue. (pr-status :
  pr-status-all :: `ardi` : `ardia`.)
- **`ardia` / `iterate-all`** --- the *write* counterpart: actually drive every
  open PR to clean. This skill only reports; see *Why fan-out is safe here* for
  why those loops stay series.
- **`sync-pr-branch`** --- offered for any PR the table flags as behind main.
- **`scripts/pr-sweep.py`** -- the cheap deterministic sweep that says *which*
  PRs this dashboard should be pointed at.
  It answers one narrower question ("which open PRs are stalled right now")
  across several repos in one GraphQL call, with a wall-clock staleness
  threshold this skill has no equivalent of.
  This skill then supplies the per-PR depth it deliberately omits.
  See [`derive-dont-enumerate`](../../shared/workflow/derive-dont-enumerate.md).
- **`scripts/pr-overlap.py`** -- the same sweep over *pairs* rather than over PRs: which open PRs share a file, and which share none.
  Reach for it whenever this dashboard's rows are about to be merged, since "collides" is a property of the pair and no per-PR column can carry it.
  It separates an identical file set (a duplicate to close) from a partial overlap (an order to pick), and reports pairs examined alongside pairs colliding.
  See [`batch-merge-and-resolve`](../../shared/workflow/batch-merge-and-resolve.md).
