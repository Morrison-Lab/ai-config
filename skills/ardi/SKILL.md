---
name: ardi
description: "Drive one PR to clean."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
---

# ARDI --- ARD + Iterate (single PR/MR)

Drive one PR/MR to a clean review verdict by looping: read every review → ARD every
finding from every reviewer → push → post summary → re-request review from those
reviewers → repeat until every reviewer's latest verdict is clean.
A later all-clear from one reviewer does not clear another reviewer's standing
not-clean, even with `mwc` active (ai-config#2274).

## Procedure

1. **Identify and claim the PR/MR.**
Use the current branch's open MR, or the one the user specified.
Post a brief claim comment (`COMMENT_PR`) so a parallel `@claude` CI run or another person doesn't start a colliding session.
The body carries a real blank line before the disclosure marker --- `\n` inside a bash double-quoted string is the two characters, not a newline:

```bash
gh pr comment <N> --body "Driving this PR to clean --- please hold off until done.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_PR
```
Skip if your most recent comment already says so and is still live --- claims expire 2 hours after the most recent push or comment, and an expired one needs reasserting, per [`claim-pr`](../../shared/workflow/claim-pr.md).
(`COMMENT_PR` and the other bracketed tokens below are abstract operation tokens --- resolve to your model's tool via [`tool-mappings.md`](../../tool-mappings.md).)

2. **Read every review, not only the latest.**
Pull the most recent reviewer comment --- the `@claude` bot's, or a human's ---
and every other review that still has a standing verdict.
Don't trust earlier cached verdicts --- actively poll until a review appears that references the commit you just pushed, then read **that** one.
If one review is all-clear and another raises findings or nits, the findings
win: ARD the union, then request fresh reviews.
Do not merge on the all-clear, even with `mwc` (ai-config#2274).
`gh pr checks` (`PR_CHECKS`) / `glab ci list` going green is about **CI state**, not the review verdict --- always parse the latest review *body* for findings.
A user question about this PR that is not the word "status" still requires
this fetch (see [`pr-status`](../pr-status/SKILL.md)).
Don't answer the chat question from session memory while a review comment
sits unread.

   **When the user provides a specific review link/ID** (e.g. `#pullrequestreview-4761444085`): Fetch that review directly via the GitHub API using its ID.
   Many bot reviews have a generic overview body but the actual findings live in **inline comments on specific lines** --- don't rely on the top-level review body alone.
   Fetch both the review overview and its inline comments:
   ```bash
   gh api "repos/<owner>/<repo>/pulls/<N>/reviews/<review-id>" --jq '{state, body}'
   gh api "repos/<owner>/<repo>/pulls/<N>/comments" --paginate --jq '.[] | select(.pull_request_review_id == <review-id>) | {line: (.line // .original_line), body}'
   ```
   The comments endpoint returns pages oldest-first -- without `--paginate`
   a later review's inline comments can sit past the first page and never
   reach the filter, making a review with real findings look empty.

   - **GitHub:**
     Filter on the body marker, not on an author login.
     Do not take `| last` as the only review to ARD
     (ai-config#2274).
     Claude, Antigravity, and skip notices can all post as `github-actions[bot]`,
     so a login filter silently drops a standing not-clean.
     ```bash
     gh api repos/<owner>/<repo>/issues/<N>/comments --paginate \
       | jq -s '[.[][] | select(.body | test("\\*\\*Claude finished|### Verdict|Antigravity Agent Report"; "i"))] | .[] | {created: .created_at, user: .user.login, body: .body}'   # READ_PR_COMMENTS
     ```
     Completed Claude runs start the body with `**Claude finished`.
     Read every matching comment, not only the newest.
     A later all-clear from a different reviewer does not clear another
     reviewer's standing not-clean.
     For a **human** reviewer (any login), also gather comments with the `ard`
     skill's step 1 (`gh pr view <N> --comments` plus the inline-thread API).

     **Copilot code review doesn't post as a PR comment at all -- it's a
     formal GitHub review**, invisible to the command above.

     **Do not request it while the Copilot moratorium stands.**
     `MORATORIUM_END` in
     [`hooks/no-unreviewed-pr.py`](../../hooks/no-unreviewed-pr.py) is the
     live value, and `memories/gh-cli.md` carries the directive it
     implements.
     While that date is in the future, skip the request and read whatever
     Copilot reviews already exist.
     A missing Copilot verdict is then not a gap to fill but the expected
     state, and
     [`self-review-fallback.md`](../../shared/workflow/self-review-fallback.md)
     governs the resulting absence exactly as it governs a quota-skipped
     `@claude` round.

     Otherwise request it
     (`REQUEST_COPILOT_REVIEW` -- abstract operation token; resolve to your
     model's tool via [`tool-mappings.md`](../../tool-mappings.md)) and check
     whether it posted a verdict *at the current head*. Finding a review
     object at the right `commit_id` only proves Copilot *looked* -- it says
     nothing about whether that review is clean. Fetch the matched review's
     own overview **and** its inline comments (same two-call shape as the
     review-link case above; the reviews list itself is `READ_PR_REVIEWS`)
     before treating it as an all-clear:
     `gh api`'s own `--jq` flag has no `--arg`/`--argjson` (see
     [`memories/gh-cli.md`](../../memories/gh-cli.md)'s `gh api`/`jq` note) --
     pipe the raw paginated output into standalone `jq -s` instead, which
     supports both:
     ```bash
     set -o pipefail
     head="$(gh pr view "<N>" --json headRefOid -q .headRefOid)"
     review_id="$(gh api "repos/<owner>/<repo>/pulls/<N>/reviews" --paginate \
       | jq -s --arg head "$head" \
       '[.[][] | select(.user.login=="copilot-pull-request-reviewer[bot]" and .commit_id==$head)] | last | .id')"
     if [ -n "$review_id" ] && [ "$review_id" != "null" ]; then
       gh api "repos/<owner>/<repo>/pulls/<N>/reviews/$review_id" --jq '{state, body}'
       gh api "repos/<owner>/<repo>/pulls/<N>/comments" --paginate \
         | jq -s --arg rid "$review_id" \
         '[.[][] | select(.pull_request_review_id == ($rid | tonumber))] | .[] | {line: (.line // .original_line), body}'
     else
       echo "no fresh review yet -- wait or re-request"
     fi
     ```
     A genuine clean Copilot overview is **not** an empty string -- it reads something like "Copilot reviewed N files and generated no new comments."
     Don't require a literally empty body; parse the overview for a zero-new-findings phrasing **and** confirm zero matched inline comments -- both, not either alone, since zero inline comments with no affirmative zero-findings overview doesn't rule out a non-verdict formal review.
     **A "no new comments" overview can still carry real findings in a collapsed suppression block** -- these are genuine flagged items under the fully-clean rule (address every finding regardless of confidence label), even though they never become formal inline comment objects the `/comments` endpoint returns (verified: PR #660's review 4767752501 read "generated no new comments" in its overview while its full body carried 3 suppressed findings; PR #1029 repeated the shape from round 3 onward).
     A third condition is required: the raw review **body** must not contain a suppression block at all.
     **Match the suppression block on its heading --- a `<summary>` element, or an ATX heading inside a collapsed `<details>` region --- case-insensitively on `suppressed`, not on either exact phrase, not on `<summary>` alone, and not anywhere in the body or anywhere in the region.**
     GitHub changed the wording and dropped the reason: PR #660 emits `<summary>Comments suppressed due to low confidence (3)</summary>`, while PRs #1029 and #1031 emit `<summary>Suppressed comments (4)</summary>`.
     So a literal grep for `Comments suppressed` returns **zero** against a current body that plainly has the block, which produced a real false negative during the ai-config#1029 loop.
     A body-wide match over-corrects, though, and would keep a clean PR permanently non-clean: ordinary overview prose contains the word, verified on review 4837572117, whose summary table reads "suppressed Copilot findings" outside any collapsed block.
     Scope the match to headings rather than to `<summary>` alone, and accept every heading: measured 2026-09-03 on ai-config#3084 review `5098574802`, the block arrives as a `### Suppressed comments (1)` heading nested under `<summary>Review details</summary>`, so a `<summary>`-only match returns zero against a body that plainly has it.
     Scoping to the whole `<details>` region instead would readmit the *class* of false positive a body-wide match produces, because that same review wraps its `Pull request overview` and `File summaries` prose in collapsed `<details>` regions of their own --- 4837572117's table was uncollapsed, so it controls only for prose sitting outside a `<details>` region.

     The stakes are why this matters: from round 3 of ai-config#1029 onward *every* substantive finding arrived suppressed, under a "generated no new comments" overview with zero inline comments -- including CRLF silently disabling a failure path repo-wide.
     So a suppressed finding is not a lower-value one, on the evidence available here --- which is a run of valuable suppressed findings, not a measured correlation.
     GitHub's own docs do not document suppression at all, so expect the label to keep moving and key on the stable token within that scope.
     And dispositioning a finding-bearing review's comments yourself does **not** make that same review the all-clear -- the fully-clean bar needs a *later* review, at the still-current head, that doesn't re-raise them.
     So the all-clear is either (a) a review with a zero-new-findings overview, zero inline comments, and no suppressed- findings block, or (b) a later review at the same head as a finding-bearing one, confirming nothing remains -- never the finding-bearing review itself, however thoroughly you addressed its findings.
     A review object existing at the current `commit_id` with unresolved findings inside it is not clean, it's just current.
     A stub-like non-answer ("ineligible", "reached their quota limit") is also not a verdict -- treat it the same as a skipped/stub `@claude` run (see the "Do the review yourself" fallback in `CLAUDE.md`) and retry later or fall back accordingly.
   - **GitLab:** poll the MR notes (`sort=desc`) for a review note that
     references your latest short SHA before proceeding; if none has appeared,
     wait and retry rather than reading a stale verdict.

   **If the latest review is a cancellation, the live verdict is stale --- don't re-do already-applied fixes.**
   A `cancel-in-progress` cancellation (on setups that cancel superseded review runs) means the last *complete* review's findings may already have been fixed by a commit that landed after it, with the confirming re-review killed before it could post.
   Before treating those findings as outstanding work, **diff the current code against each one** to see what's already addressed --- then push only what's genuinely needed and let a fresh review confirm.
   Re-applying fixes that are already in the tree wastes a round and muddies the diff.
   If *nothing* remains outstanding (every finding is already applied), don't push an empty commit --- skip to step 6 and re-request the review directly.

   **Execute the sequential multi-provider review loop** defined in `shared/workflow/adversarial-self-review.md`.
   You must pin all available providers (including external reviewers and the local `adversarial-reviewer` subagent).
   You must query them sequentially, one at a time.
   Do not request them in parallel.
   **When the loop reaches the local self-review step, don't perform it.**
   Hand the review to a separate [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent (foreground, read-only), briefed with the base ref, the paths, and the standards that apply --- never with your rationale for the change, which is what makes a reviewer agree with you.
   The session that wrote the diff knows what it was meant to say, so an inline pass reads the artifact and recovers the intent: confirmation rather than review, and indistinguishable from the real thing in the output (see [`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md)).
   Its brief covers what an inline pass would have done: independently assessing both line-level implementation defects and the whole change (requirements, intent, cross-file consistency, integration, regression risk, and validation), explicitly reporting both passes in the structured verdict.
   This includes the current PR diff against its base, each changed call path and edge case, the focused tests, and the relevant lint/documentation checks.
   You must Address, Rebut, or Defer every finding it returns.
   If a provider skips or cannot produce a verdict (quota, offline), note the skip in your ARD summary comment.
   **Re-check reviewer availability every round, not just once:**
   A reviewer that was unavailable a few pushes ago can become available mid-session.
   A skipped review is never a clean external verdict on its own and does not authorize marking the PR as approved.
   See [*The bar: "fully clean"*](#the-bar-fully-clean).
   It requires clean verdicts at the current head from all reachable providers in your pinned quorum, not just a self-review.

3. **ARD every finding --- regardless of severity label.**
   "Informational", "Not a blocker", "minor", "nit", "optional", "consider", "if you want" are for the user's prioritization, not a pass for the implementer.
   For each flagged item, choose exactly one:
   - **Address** --- fix it, commit.
   - **Rebut** --- explain why it's correct (with evidence).
   - **Defer** --- file a follow-up issue, link it (use the `defer-issue` skill).

4. **Push fixes** (if any). If main moved ahead of the branch, sync it in
   *before* you push, so the next review evaluates against current main:
   ```bash
   git fetch origin main
   git log --oneline ..origin/main | head   # any commits? merge them in
   git merge origin/main
   ```
   Resolve conflicts, run the repo's pre-commit checks, then re-scan the PR's touched files with whitespace-normalizing search for merge-status hedges that `main` may have falsified (`still open`, `not yet merged`, `once that merges`, `as of`, `will live at`, `proposed in`) before pushing.
   Do not use line-oriented literal grep; semantic line breaks can split the phrase this check needs to find.
   Don't rebase/squash a published branch -- a merge commit matches GitHub's "Update branch" button. (The `sync-pr-branch` skill does exactly this.)

   **Resolve inline threads as you go --- including outdated ones.**
   After pushing fixes for a round, resolve the corresponding inline review threads immediately (`RESOLVE_REVIEW_THREAD`) via `mcp__github__pull_request_review_write` with `method: resolve_thread` and the `threadId` (returned by `READ_PR_REVIEW_COMMENTS` --- `mcp__github__pull_request_read` with `method: get_review_comments`).
   Don't wait until fully-clean to do thread housekeeping.
   For threads marked *outdated* in GitHub (the underlying code changed), confirm the fix is in the current tree, then resolve.
   Threads whose fixes are already in the tree but were never resolved still block the "fully clean" check --- clear them as soon as you confirm the code is right.

   **Opportunistic conflict sweep.**
   After pushing (or after any round where all findings were Rebutted/Deferred with no push), scan other open PRs in the same repo for merge conflicts:
   ```bash
   gh pr list --state open --json number,title,headRefName,author,assignees,mergeable,mergeStateStatus,comments   # LIST_PRS
   ```
   Filter that list by `memories/reviewing-prs.md`'s scope test first, as `ardia` step 1 does (opened by or assigned to the invoking user, explicitly requested by name, or authored by the GitHub Actions app (`github-actions`));
   an out-of-scope conflicting PR is reported to the user and left untouched (no comment, no push);
   they can assign or name it if they want it resolved.
   For each in-scope PR where `mergeable == "CONFLICTING"` **or `"UNKNOWN"`** (see `resolve-conflicts`, "Verify before you act" --- `UNKNOWN` can mean GitHub hasn't finished computing yet, not that there's no conflict), verify with `git merge-tree --write-tree origin/main origin/<branch>` (git ≥ 2.38) before acting, then check claim status (most recent comment) and fix unclaimed ones --- same cascade procedure as `post-merge` step 1.5 (claim → isolated worktree → fetch main → merge → `resolve-conflicts` skill → push → unclaim).
   A merge to `main` during your ARDI loop can create new conflicts in sibling PRs; clearing them while waiting for the next verdict is better than letting them pile up.

5. **Post the ARD summary** as a comment on the MR/PR (table format per the
   ARD skill).

6. **Re-request review --- but don't double-trigger.**
How depends on the repo's review trigger first, and on whether this round pushed code second.
**Read the review workflow's `on:` block once per repo** (the first time you push to a PR there) before applying the branches below --- the first one is wrong for a repo that has no push-based trigger, and nothing about the PR's appearance will tell you.
   - **Code was pushed, and the review workflow carries a push-based trigger** (`pull_request:` with `synchronize`): the push **already** triggers the review.
     Do **NOT** also post "@claude review again".
     On workflows with `concurrency: cancel-in-progress`, the push-triggered and mention-triggered runs **cancel each other**, leaving the latest commit with a canceled, never-posted verdict.
     Just wait for the push-triggered review.
   - **Code was pushed, and the review workflow is dispatch-only** --- its `pull_request:` trigger is absent or commented out, leaving `workflow_dispatch` (and perhaps `issue_comment`), which is how a repo disables automatic review on PR activity.
     The push fires **nothing**, so you must dispatch explicitly, **after the round's last push** rather than once when the PR opened: `gh workflow run <review-workflow>.yml -R <owner>/<repo> --ref <PR-branch> -f pr_number=<N>`, taking the input's name from that workflow's own file.
     **There IS a cancel-in-progress race here, and it is one you create yourself** --- dispatching after each push means each dispatch cancels the last, since the group is keyed on the PR number rather than on the trigger.
     Finish pushing, then dispatch once.
     Pass `--ref` as well, or the cancelled run's failing review gate attaches to the default branch and never appears on the PR.
     See [`ardi`](../../shared/workflow/ardi.md)'s "Dispatch once, after the round's LAST push".
     This is the branch that fails silently: CI still goes green on each push, so watching CI to green feels like watching the PR, and a verdict from an earlier head stands unchallenged for as long as you keep pushing.
     (UCD-SERG/serocalculator, 2026-08-07: `claude-code-review.yml` has its `pull_request:` trigger commented out with the note "reviews are on request only".
     Six pushes across several hours were each followed by watching CI to green.
     No review was ever dispatched, and a verdict from roughly 20 hours earlier stood until the user asked whether the PR had a clean review.)
   - **No code pushed** (all Rebut/Defer): no push occurred, so nothing
     auto-triggers --- you **must** explicitly re-request (post `@claude review`,
     or the forge's equivalent). This is the only case where you post the
     mention.
   - **Heads-up --- some repos' review workflow is *not* comment-triggered.**
     Some Quarto / R-package repos run `claude-code-review.yml` on `pull_request` (`opened, synchronize, ready_for_review, reopened`) and `workflow_dispatch` (input `pr_number`), not on an `@claude` comment.
     A new push auto-fires it.
     To force a fresh review on an existing PR **without a new commit**, prefer `workflow_dispatch`: `gh workflow run claude-code-review.yml --ref <PR-branch> -f pr_number=<N>`.
     Without `gh`, use the REST `.../actions/workflows/claude-code-review.yml/dispatches` endpoint, or your GitHub MCP workflow-dispatch tool.
     Closing+reopening the PR also works (fires `reopened`) but adds timeline noise.
     See [`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md).
   - **Marking a draft ready seconds after its final push is another cancel-in-progress race** --- the ready-event and synchronize runs fire a second apart and the cancellation can land on the newer (current-head) run; see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md) for the diagnosis and the `gh run rerun` remedy.
   - **A review ends up canceled with no comment:** first check whether a **newer run for this same PR** is already in flight.
     Under `concurrency: cancel-in-progress` a fresh dispatch is what cancelled the old run, so a retry cancels the new one --- possibly a review a human just asked for, since `claude-bot.yml`'s `review-workflow-file` re-dispatches this very workflow into the same per-PR group.
     Attribute each in-flight run to a PR from its own `gather-context` log, since `gh run list`'s branch column reads `main` for all of them, and **wait** rather than retry if one is running.
     Only when nothing is running, trigger one cleanly via `gh workflow run claude-review.yml --ref <PR-branch> -f pr_number=<N>` (input is `pr_number`) and don't push/comment again until it posts.
     Pass `--ref` rather than omitting it: without it the dispatch runs against the default branch, so the run's check runs attach to `main`'s tip instead of the PR's head commit, leaving the PR's own review check stale and making a check-runs query at that head useless as the in-flight pre-check above.
     See [`review-verdict-pitfalls`](../../shared/workflow/review-verdict-pitfalls.md)'s "A `cancelled` review is the one case where retrying is the cause rather than the remedy", and its follow-on on why the cheap PR-side pre-check needs that ref.
     Note: a review run on a **bot-pushed** commit may show as `action_required` (gated) and never run --- the explicit `workflow_dispatch` bypasses that.

   **Don't let the trigger phrase leak into prose.**
   The `issue_comment` trigger fires on the bare bot `@`-mention **anywhere** in a comment body --- even inside a sentence saying you're *not* triggering a review.
   In ARD summaries and status comments, refer to it obliquely ("re-request review", "the review-trigger mention") or split the tokens (e.g. `@ claude`, with a space, so the raw body never contains the contiguous handle); paste the literal `@`-mention only when you actually intend to dispatch.
   A stray mention spawns a run that cancels the push-triggered review on `cancel-in-progress` setups.
   On some mention-bot setups it also starts a session whose residual-commit sweep can churn the branch.

    Then wait for the new verdict **and** for CI.

    A CI-fix push is not handled when the first few jobs go green.
    Read the full rollup: pending, queued, and in-progress jobs are still running;
    a cancelled job has finished but is not clean and still needs investigation or a rerun before the rollup counts as done.
    Arm [`wait-for-results`](../wait-for-results/SKILL.md) (or the timer
    below) instead of returning to chat with a partial `gh pr checks` read.
    (gha#511, 2026-08-18: lint/link went green, a sibling job sat in
    setup then cancelled, and the session left without waiting; the user
    asked why.)

    **Set a timer when ending a turn waiting for AI reviews.**
    Whenever ending a turn while waiting for AI reviews or CI completion after pushing code, launch a `schedule` timer (e.g. 120s) and follow the check-and-reschedule procedure in [`shared/workflow/ardi.md`](../../shared/workflow/ardi.md) when it fires.

   **While waiting, keep checking for merge conflicts.**
   Other PRs in this repo can become conflicting at any time (someone merges to `main` while the review runs).
   Poll every few minutes with `/loop` or a manual re-check:
   ```bash
   gh pr list --state open --json number,title,headRefName,author,assignees,mergeable,mergeStateStatus,comments \
     --jq '.[] | select(.mergeable == "CONFLICTING" or .mergeable == "UNKNOWN")'   # LIST_PRS
   ```
   Apply the same scope test as the sweep above before touching a candidate;
   an out-of-scope one is reported to the user and left untouched.
   Verify each in-scope candidate with `git merge-tree --write-tree origin/main
   origin/<branch>` (git ≥ 2.38; see `resolve-conflicts`, "Verify before you act") before
   claiming --- `UNKNOWN` isn't proof of a real conflict, and `CONFLICTING` can
   be stale if a sibling PR merged since GitHub last computed it. Claim and
   fix confirmed conflicts using the cascade procedure in `post-merge` step
   1.5. Re-check after each resolution --- new ones can appear at any time.
   This turns idle wait time into productive conflict prevention.

### Per-round checklist

**Pause point: before advancing to the next round.**
Do-Confirm; per
[`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md).

- [ ] **Killer item:** the latest review analyzed is for the current head
      commit, not a stale prior run.
      Marked because getting this wrong invalidates the whole round rather
      than leaving a gap in it: a reviewer's snapshot predating your rebuttal
      re-raises an item you already answered, and a verdict from an older head
      says nothing about the code you just pushed.
      Compare the review run's `started_at` against your last reply and the
      head SHA.
- [ ] Every finding from that review has an ARD disposition.
- [ ] If code changed, main was synced in first when needed, merge-status
      hedges in touched files were re-scanned with whitespace normalization,
      then fixes were pushed.
- [ ] If source comments or generated inputs changed, the repository's
      generator was run after the final edit and its generated paths are clean
      against the index; stage any resulting artifacts before pushing.
- [ ] ARD summary was posted and corresponding inline-thread replies/resolutions
      were handled.
- [ ] Re-review trigger was chosen correctly, reading the repo's trigger class
      first: rely on the push alone only where the review workflow carries a
      push-based trigger; dispatch explicitly after **every** push where it is
      dispatch-only; post the mention only when no code was pushed.
      A green CI run at the current head is not a review in flight.

7. **Repeat from step 2** until the PR/MR is **fully clean** (see [*The bar: "fully clean"*](#the-bar-fully-clean) -- zero findings **and** all CI workflows and check runs green and completed **and** every inline thread resolved).
   Don't exit on a clean review body alone.

## Fix broken CI/workflows too

If the PR's CI checks are failing (not just the review), investigate and fix them as part of the ARDI loop --- don't declare "clean" with red CI.
This includes:

- **Workflow syntax errors** --- fix them in this repo.
- **Upstream template bugs** --- if the failure is in a reusable workflow from
  a shared CI library (e.g., HACtions) or a GitHub Action, file an issue (or open a PR) upstream using
  the `sup` skill, then either pin a working version or apply a local
  workaround until the upstream fix lands.
- **Flaky / infra failures** --- retry once; if it persists, investigate root
  cause.

The goal is green CI + clean review, not just clean review.

## Delegating sidecar work

Some steps benefit from a subagent rather than blocking the round on the main
thread --- investigating a CI failure whose cause isn't obvious (see above),
verifying a reviewer's factual claim before Addressing/Rebutting it, or
checking a sibling PR for a merge conflict during the opportunistic sweep.
Delegate that via the `Agent` tool and keep driving the round itself (ARD,
push, post summary, re-request review) on the main thread.

For a judgment-heavy sidecar task (a subtle root-cause hunt, adjudicating a deadlocked rebuttal before escalating to a human), give the subagent a stronger model via the `Agent` tool's `model` parameter (e.g. `model: 'opus'`).
Symmetrically, drop to a cheaper/faster tier (`model: 'fable'` or `'haiku'`) for a mechanical sidecar task --- see [`select-model`](../../skills/select-model/SKILL.md)'s decision tree for both directions.
For a heavy fan-out investigation/verification pass, prefer a separately-billed provider (e.g. the `codex` CLI) first when available --- see [`delegate-to-codex`](../delegate-to-codex/SKILL.md).

## The bar: "fully clean"

The loop ends only at **fully clean**, which means **both**:

1. **All CI workflows and check runs are green and completed** --- every check,
   not just required ones and not just the review job; never still queued or
   in progress (see *Fix broken CI/workflows too* above, and
   `shared/workflow/fully-clean.md` for the check-run-vs-workflow-run and
   API-casing gotchas).
2. **Every reviewer's latest verdict is totally clean** --- zero flagged items under any heading.
   "Looks good" / "no findings" / "approved" with no follow-on bullets.
   Every item that wasn't directly **Addressed** is either **Deferred** to a tracked issue or **Rebutted with a rebuttal that actually convinced the reviewer** (they didn't re-raise it on the next round).
   A rebuttal the reviewer still disputes does **not** count as clean.
   Don't stop at "ready with one minor nit."
   A later all-clear from one reviewer does not clear another reviewer's standing
   not-clean, even with `mwc` (ai-config#2274).
   **That review must be a genuine posted verdict at the current head, from an external reviewer if one is reachable** -- check availability again right before declaring clean, not just at the round where self-review first started; an inferred "probably clean" from green CI and resolved threads does not satisfy this.

**Threads:** at fully-clean, every **inline** review thread is resolved, and
the only conversation left open is the final all-clear exchange --- the
reviewer's all-clear comment (usually a top-level PR comment, not an inline
thread) and your reply to it. (Thread mechanics live in the `ard` skill, step
4b.)

### Fully-clean exit checklist

**Pause point: before declaring "clean" or reporting the PR ready.**
Do-Confirm; per
[`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md).

- [ ] **Run automated clean check**: `python3 scripts/check-pr-fully-clean.py --quorum <number-of-reachable-providers> <pr-number>` returned exit code `0` (confirming all CI check runs completed with success AND clean review comments for current HEAD SHA have been posted).
- [ ] **Killer item:** all workflows and check runs are green **and completed** for the current head --- re-fetched and re-counted now, not checked off from the names you were watching.
  Marked because a posted verdict does not mean the review job finished, the check set can *grow* mid-run as jobs spawn others, and two check runs can share a name (a stale green plus a live one), so matching on name returns the wrong one.
  Key on check-run id, and read `status` before `conclusion`.
- [ ] Every reviewer's latest verdict has zero findings and no disputed rebuttals.
- [ ] You have obtained genuine posted clean verdicts at the current head from ALL reachable providers in your pinned quorum -- re-checked right before declaring clean.
- [ ] Every self-review posted along the way was produced by a separate `adversarial-reviewer` subagent rather than inline, and its findings were dispositioned ([`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md)).
- [ ] Every inline review thread is resolved.
- [ ] The only open conversation is the final all-clear exchange (the reviewer's all-clear comment and your reply --- normally a top-level PR comment, not an inline thread).

## Stopping conditions

**There is no round limit.
Always request another review.**
The loop on a single PR ends on exactly three things:

1. **A totally clean review on the latest pushed commit** -- no nits, no non-blocking comments, no informational notes, everything Addressed or agreed Deferred, evaluating the exact HEAD SHA currently on the branch.
   **Crucial:** Pushing fixes for a review starts a new review cycle. The ARDI loop is **NEVER** finished when you push fixes for a finding-bearing review or post an ARD summary. You must wait for the new review run evaluating your latest pushed commit to post, fetch and parse that review, and confirm it contains zero findings before ending the loop. See [*The bar: "fully clean"*](#the-bar-fully-clean).
2. **Nothing actionable remains** --- every open item has been escalated to a human and is waiting on their decision, so there is no next action you can take.
   Not "some items are deadlocked"; *all* of them.
3. **The user says stop.**

Nothing else.
Not a round count, not a sense that findings are getting smaller, not a judgment that the reviewer is nitpicking.

**Deadlock is per-item, and it does not stop the loop.**
If you and the reviewer can't reach consensus on one finding (your rebuttal didn't convince them, and their re-raise didn't convince you), **escalate that item to a human reviewer** rather than looping on it or unilaterally overriding.
Request `the repository owner` via the `request-pr-review` skill, `@`-mention them in a comment summarizing the impasse, and surface the open item to the user.
The raw `gh pr edit <N> --add-reviewer <reviewer>` form bypasses that skill and so does **not** inherit its `Lacaedemon/sparta` exception.
In sparta, escalate to the user in chat rather than requesting a reviewer at all.
Then **keep driving the PR**: address every other finding, push, and request the next review.
Only when *every* remaining item is an escalated deadlock does condition 2 above fire, and even then the loop resumes the moment the human rules.

### Sweep-level scheduling is a different question

[`ardia`](../ardia/SKILL.md) and [`gia`](../gia/SKILL.md) drive *many* PRs.
When one of those is waiting on a human --- a deadlocked item, a blocked dependency, an unresolvable conflict --- the sweep records it and moves to the next PR so the batch keeps moving.
That is **scheduling**, not a stopping condition for the loop: the sweep returns when the human rules, and nothing about it licenses accepting unaddressed findings on the PR itself.

### "Asymptotic noise" is an anti-pattern, not a signal

This skill used to carry a guard saying that after 3-4 rounds of new nits you should surface the pattern and ask whether to continue.
**That guard is removed, and reasoning of that shape must not be reintroduced.**
It fails three ways:

- **It fires on round count, not on finding quality.**
A round producing genuine, reproducible correctness bugs is indistinguishable from a round producing style churn if all you count is rounds.
- **It reads as diligence**, which is exactly why it goes unexamined. Stopping
  to ask feels like respecting the user's time.
- **It hands triage back to the user** --- the precise move [`address-every-comment`](../../shared/workflow/address-every-comment.md) already forbids for individual findings.
  The guard reintroduced at loop scale the thing that fragment bans at item scale.

The tell is any sentence of the form "the reviewer keeps finding things, so maybe we should stop."
Replace it with another review request.

Two things that are **not** this anti-pattern and stay:

- **The per-item hold.**
When a reviewer re-raises one already-deferred item verbatim each round, reply once pointing at the tracked issue and hold on *that item*, while continuing to fix every new finding.
That is about not re-litigating one item; it never stops the loop.
- **Reporting the round count.**
Saying "round 7, 23 findings, all Addressed" is useful information.
Attaching "shall I stop?" to it is the anti-pattern.

(ai-config#1029 is the case record: six rounds, 23 findings, all Addressed, with rounds 2-6 each finding real bugs in *earlier rounds' own fixes* --- including CRLF silently disabling a failure path repo-wide, a `--compare` reporting a zero delta, and a traversal-order-dependent measurement.
The loop stopped to ask twice under the old guard; both times the answer was to keep going, and the next round found four more real bugs.)

## On clean

Post an unclaim comment (`COMMENT_PR`) to unblock any parallel sessions that backed off in step 1:

```bash
gh pr comment <N> --body "Done --- PR is free.

_Posted by Claude Code (AI agent) --- not written by a human._"   # COMMENT_PR
```

**Then run `ums`, before reporting ready.**
The clean verdict is still a proactive-UMS checkpoint for this PR, not the
merge, but it is not the first one: run a pass when you read the review,
including a Rebut/Defer round, rather than holding everything for the
verdict.
See `CLAUDE.md`'s "Run UMS proactively, as learnings accumulate".
The loop's whole point is that it ends here and hands the merge to a human,
so a pass deferred to the merge is deferred to a moment this session may
never see.
Everything the review lifecycle taught -- recurring findings, corrections,
guidance given along the way -- is complete as of the verdict.

Always provide a clickable link to the MR/PR in the final message.

Report the final verdict and round count. Don't merge unless asked.
