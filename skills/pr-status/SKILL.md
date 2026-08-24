---
name: pr-status
description: "Check PR latest review status."
user-invocable: true
allowed-tools:
  - Bash
---

# pr-status

Report a PR's review status honestly: based on the **most recent** review, with
its findings actually parsed — never on an earlier cached "verdict." A newer
review may have landed since (from the `@claude` bot, a human, or a
re-trigger), and it may carry findings the old one missed.

## When this fires

- "what's the status of PR #N", "is #N ready to merge", "is the review clean".
- Before you state, anywhere, that a PR is mergeable / clean / ready.
- Any other question about a live PR this session is driving, even when
  the user never said "status": "why didn't you wait", "did you fix it",
  "why haven't you responded to that comment".
  Fetch the latest review **and** CI before answering.
  The review may have landed while you were answering a different process
  question.
  (gha#511, 2026-08-18: the session answered a CI-wait question from chat
  and never opened the PR thread, so a Needs more work review sat
  unanswered.)

Commands below are annotated with their abstract operation token (e.g.
`VIEW_PR`, `PR_CHECKS`) — resolve to your model's tool via
[`tool-mappings.md`](../../tool-mappings.md) instead of the `gh` command shown
if this session doesn't have `gh`.

## Verify the PR is still open first

Before checking CI or review, confirm the PR hasn't merged or closed since
you last looked:

```bash
gh pr view <N> --json state,title --jq '"\(.state): \(.title)"'   # VIEW_PR
```

- `OPEN` → proceed with CI and review checks below.
- `MERGED` → stop; trigger `post-merge` instead of reporting CI details.
- `CLOSED` → stop; report the actual state to the user.

A PR can merge between a "status?" call and a follow-up "status?" in the
same session. Running `gh pr checks` on a merged PR returns stale data and
delays noticing the merge happened.

## CI green ≠ review clean

`gh pr checks <N>` (`PR_CHECKS`) going green is about **CI state**, not the review verdict. A
PR can have all checks passing and still have unaddressed review findings.
Always parse the latest **review body** for findings — don't infer "clean"
from green checks.

## Read the LATEST review, checked for currency

```bash
gh pr view "<N>" --json comments,commits,headRefOid,author,reviewRequests \
  --jq '{
    author: .author.login,
    reviewRequests: [.reviewRequests[].login],
    review: ([.comments[] | select(.author.login | startswith("claude"))] | last | {url: .url, body: .body, createdAt: .createdAt}),
    lastCommitDate: (.commits[-1].committedDate),
    headRefOid: .headRefOid
  }'
```

**This call fetches more than `READ_PR_COMMENTS` maps to** --
`tool-mappings.md` maps that token to a comments-only MCP call
(`pull_request_read(method=get_comments)`), which returns neither `commits`
nor `headRefOid`. In a remote/MCP session without `gh`, fetch those two
fields with a separate call (e.g. `pull_request_read(method=get)` for
`headRefOid`, plus the commits list) rather than assuming the token mapping
covers this expanded query.

**If `.review.createdAt` is earlier than `.lastCommitDate`, the review
predates the latest push** -- treat it as stale, not current, regardless of
what its body says (both are ISO 8601 UTC timestamps, so a plain string
comparison works). This timing check alone is **not proof of currency**:
`committedDate` is the commit's local committer timestamp, not when GitHub
received the push, so a commit authored earlier but pushed later can pass
the timing check while still being newer than the review. When the review
body names the commit it reviewed (the `@claude` bot commonly writes
"commit `<sha>`"), cross-check that SHA's prefix against `.headRefOid`.
**Require a SHA match to call it `clean`** -- when the review passes the
timing check but names no SHA (or the mentioned SHA doesn't match), report
**`unverified`**, not clean, every time, not just when the gap "looks
small" (there's no reliable way to judge that from the timing check alone).

The reviewer's bot login **varies by API and setup**:

- `gh pr view` reports it as `claude`
- the REST API (`gh api .../comments`) reports it as `claude[bot]`
- some setups post reviews as `github-actions[bot]`

`startswith("claude")` matches the @claude bot across both `gh pr view` and
`gh api`. If your reviewer posts under a different login (e.g.
`github-actions[bot]`), **broaden the filter** — otherwise the `--jq` returns
`null` and you silently false-pass a PR with open findings. (Structured MCP
GitHub tools like `mcp__github_ci__get_ci_status` are an alternative where the
`gh` JSON parsing gets fragile.)

## Check for a genuine external verdict, not just self-review

The `@claude` comment above isn't the whole picture. Per
[`fully-clean.md`](../../shared/workflow/fully-clean.md), reporting a PR
clean/ready requires a **genuine posted verdict at the current head from an
external reviewer, whenever one is reachable** -- a self-review (posted when
`@claude` was skipped or stubbed) is a fallback, never a substitute, once an
external reviewer becomes available again. Formal reviews (e.g. Copilot)
don't show up in the comments query above at all -- they're a separate
review object.

**This is a status query -- inspect an existing Copilot or human review,
don't request one.**
Requesting a review is a mutation: it triggers a review job,
consumes reviewer quota, and can collide with an active `ardi` loop driving
the same PR. Use the read-only half of
[`ardi`'s step 2](../ardi/SKILL.md) -- fetch the matched review's body +
inline comments at the current `commit_id` and require a zero-findings
verdict -- but skip the `POST /requested_reviewers` call. If no genuine
Copilot verdict exists at the current head, check for a human's formal
review at the head (next subsection) before reporting `no verdict at head`;
only when neither exists, report that and
offer to run `ardi` (which can request one); don't request it yourself here.
Green CI plus a clean self-review is not sufficient on its own if an
external reviewer is reachable.

### A human's formal review at the current head is an external verdict too

The Copilot query above matches only Copilot's own login,
so it cannot see a review a real person submitted through GitHub's review UI.
Without this check, a PR a human already reviewed at the current head
gets reported `no verdict at head` --
the gap #668 tracks.
Fetch the formal reviews and keep the non-bot ones at the current head
(`READ_PR_REVIEWS`):

```bash
set -o pipefail
head="$(gh pr view "<N>" --json headRefOid -q .headRefOid)"   # VIEW_PR
gh api "repos/<owner>/<repo>/pulls/<N>/reviews" --paginate \
  | jq -s --arg h "$head" \
  '[.[][] | select(.user.type == "User" and .commit_id == $h
                   and .state != "DISMISSED")]
   | group_by(.user.login)
   | map(sort_by(.submitted_at) | last
         | {id, login: .user.login, state, submitted_at})'
```

**Exclude `DISMISSED` reviews before reading anything.**
GitHub's dismiss action flips the review's own `state` in place
rather than adding a new review,
and it retracts neither the review's body nor its inline threads --
so without the exclusion,
a dismissed review is still its reviewer's latest at the head,
and a substance read would report findings
an explicit dismissal already resolved.
Dismissal is one of the two resolution paths
the *Check for a blocking human CHANGES_REQUESTED* section below
already documents;
this filter keeps the two checks consistent about it.

**Reduce per reviewer, not across all reviewers at once.**
The `group_by(.user.login)` mirrors the `CHANGES_REQUESTED` check below,
and for the same reason:
two humans can review the same head,
and a bare `| last` over the combined list
would return only the chronologically latest review --
so a later clean "LGTM" from one reviewer
would silently drop an earlier reviewer's body-only findings
(inline findings would still surface through the thread count,
but a finding stated only in a review body has no thread to catch it).
The command returns each human reviewer's latest review at the head;
read **every** one of them.

**Filter on `.user.type == "User"`, not on a login list.**
A bot's REST user object carries `type: "Bot"`,
so the type field separates humans from every bot
without maintaining a login blocklist
(measured 2026-08-15 on this repo:
`copilot-pull-request-reviewer[bot]`'s review objects report `type: "Bot"`,
and the human reviewers' report `type: "User"`).

**Judge each matched review by its substance, not its `state`.**
Keying on `state == "APPROVED"` reads as the obvious check
and on this repo would never fire:
106 of 106 formal reviews across 60 merged PRs are `COMMENTED`,
zero `APPROVED`, humans included
(measured 2026-07-30 on #668),
because reviews here are posted as comments
rather than through GitHub's approve flow.
A check that can never fire is worse than none --
it reports `no verdict at head` on PRs a human did review,
and the failure is invisible,
since a check that never fires looks the same as a repo with no human
reviews.
So read each matched review the way the Copilot step reads its own:
fetch its body plus its inline comments at that `commit_id`,
and apply the same zero-findings bar.
Clean-by-substance human reviews at the current head,
with no matched review carrying findings,
are a genuine external verdict;
any matched review with findings is open items to report,
whatever the other reviewers said.
An `APPROVED` state, where a repo's convention does produce one,
still qualifies -- it just cannot be the key.
A `CHANGES_REQUESTED` stays blocking
via the *Check for a blocking human CHANGES_REQUESTED* section below,
regardless of anything this subsection finds.

## Parse for findings before declaring clean

Read the full latest review body and scan for any "Findings", "Issues",
"Remaining", "Non-blocking", "Minor", "Could improve", "Consider", etc.
section. The bar for reporting **clean**: "Looks good" / "no findings" /
"approved" with **zero** follow-on bullets under any heading. A posted rebuttal
the reviewer is still disputing is **open**, not clean — a rebuttal counts only
once it convinced the reviewer (they dropped the item).

## Check for a blocking human CHANGES_REQUESTED

A bot's clean verdict does **not** clear a human's formal review state. A
`CHANGES_REQUESTED` review submitted via GitHub's review UI is invisible to
the comments query above -- it's a separate object, and often has an
**empty** top-level body with the actual finding in an inline comment
(`READ_PR_REVIEWS` -- abstract operation token; resolve to your model's
tool via [`tool-mappings.md`](../../tool-mappings.md)):

```bash
gh pr view "<N>" --json reviews \
  --jq '[.reviews[] | select(.author.login != null and (.state == "APPROVED" or .state == "CHANGES_REQUESTED" or .state == "DISMISSED"))] | group_by(.author.login) | map(sort_by(.submittedAt) | last) | .[] | select(.state == "CHANGES_REQUESTED") | "\(.author.login) \(.submittedAt)"'
```

**`--json reviews` returns the full review history, not one entry per
reviewer, and a reviewer's *decisive* state persists across neutral
comments** -- GitHub only clears `CHANGES_REQUESTED` when that same
reviewer later `APPROVED`s, or via an explicit dismissal; a neutral
`COMMENTED` review in between does **not** clear it (verified against
GitHub's own docs and community reports). Filtering to only `APPROVED`/
`CHANGES_REQUESTED`/`DISMISSED` states *before* reducing to each author's
latest review is required -- reducing over *all* states first would let a
later `COMMENTED` round hide an earlier `CHANGES_REQUESTED` (verified with
a synthetic fixture: a `CHANGES_REQUESTED` followed by a `COMMENTED` from
the same author incorrectly produced no output under the naive reduction,
and correctly still blocked once state-filtered first). **`DISMISSED` must
stay in the filter, not just `APPROVED`/`CHANGES_REQUESTED`** -- an
explicit dismissal is itself one of the two ways a `CHANGES_REQUESTED`
clears, so dropping it before the per-author reduction lets an older
`CHANGES_REQUESTED` win over its own later dismissal (verified with a
second synthetic fixture: `CHANGES_REQUESTED` then `DISMISSED` from the
same author incorrectly still returned the author as blocking under an
`APPROVED`/`CHANGES_REQUESTED`-only filter, and correctly returned nothing
once `DISMISSED` was included in the filter). The final `select(.state ==
"CHANGES_REQUESTED")` still excludes `DISMISSED` reviews from the
blocking list -- only its *presence* in the pre-reduction filter matters.

If this returns anything, the PR is **blocking** regardless of what any bot
says -- only the human (or an explicit dismissal) resolves it. Report it as
open and name the reviewer; don't let a later "Ready for merge" bot comment
paper over it.

A PR is only **fully clean / ready to merge** when **at least one** of the
`@claude` comment or an external reviewer's verdict (see *Check for a
genuine external verdict* above) is clean at the current head -- the
canonical rule needs one genuine external verdict, not both; if a reachable
external reviewer hasn't posted a current-head verdict at all, that's `no
verdict at head`, not automatically a fail, but it means the `@claude`
comment alone has to carry the "clean" claim *and* no human
`CHANGES_REQUESTED` review is outstanding *and* all CI
workflows are green *and* every inline review thread is resolved (the
only open conversation being the final all-clear and your reply to it — see
*Check thread-resolution state* below). Do **not** report "ready to merge with
one minor nit noted" / "harmless as-is" / "can address if you want" — that
hedging just pushes triage back to the user. If there are open items, report
them as open (and offer to run `ardi` to clear them).

## Check thread-resolution state

A clean review *body* isn't the whole bar — unresolved inline threads count as
open too. Count the unresolved ones via GraphQL:

```bash
gh api graphql -f query='query {
  repository(owner:"<owner>", name:"<repo>") {
    pullRequest(number:<N>) {
      reviewThreads(first:100) {
        totalCount
        nodes { isResolved }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads as $rt |
  ($rt.nodes | map(select(.isResolved | not)) | length) as $open |
  if $rt.totalCount > ($rt.nodes | length)
  then "\($open)+ open (totalCount \($rt.totalCount); cap reached — may undercount)"
  else "\($open)"
  end'
```

Interpret the output as:

- `0` — all threads resolved; clean on this dimension.
- A plain non-zero number (e.g. `3`) — that many threads are unresolved.
- A `+`-suffixed string (e.g. `0+ open (totalCount 150; cap reached — may undercount)`) — the 100-thread cap was hit. **Cannot confirm clean**, even if the visible count is 0; treat as unresolved until the cap is lifted or the PR is confirmed clean another way.

(The resolve mutation lives in the `ard` skill, step 4b.)

## Output

Render a **Review Summary Table** for the PR:

| PR | Author | AI Review Verdict | CI State | Reviewers Requested | Next Step |
|:---|:---|:---:|:---:|:---:|:---|
| [#<N>](https://github.com/<owner>/<repo>/pull/<N>) | `<author>` | [✅ Clean (Round N)](<review.url>) | 🟢 All Green | `d-morrison` | Ready for human review |

- **PR** --- markdown link `[#<N>](https://github.com/<owner>/<repo>/pull/<N>)`.
- **Author** --- author login.
- **AI Review Verdict** --- hyperlinked directly to the latest review comment URL (e.g. `[✅ Clean (Round N)](https://github.com/...#issuecomment-...)`). Verified current with the latest commit (`.createdAt >= .lastCommitDate` and matching commit SHA). If the review predates the latest push, display `[⏳ In-Flight / Stale](url)`. If no SHA is named, display `[⚠️ Unverified](url)`.
- **CI State** --- `🟢 All Green` / `❌ Failing (<name>)` / `⏳ Pending`.
- **Reviewers Requested** --- evaluates human review status per [`copilot-review-before-human.md`](../../shared/vendored/copilot-review-before-human.md). For self-authored PRs, note `*Self-authored* (GitHub prevents requesting review from author)`. When AI review is clean and CI is green, list requested reviewers (e.g. `d-morrison`) or flag `⚠️ None (Request human review)`.
- **Next Step** --- computed next transition:
  - `Ready for self-merge` (Self-authored, AI approved, CI green).
  - `Ready for human review` (External author, AI approved, CI green, human review requested).
  - `Request human review` (External author, AI approved, CI green, human review not yet requested).
  - `Drive to clean (ARDI)` (AI review has open findings).
  - `Fix CI / In-flight` (CI failing or review in progress).
  - `Resolve conflicts (Sync main)` (Behind main).

State, plainly: the latest review's verdict, who/what posted it, and the list
of any open findings (or "none"). If you read `null`, say the filter didn't
match a reviewer login — don't report it as clean.
