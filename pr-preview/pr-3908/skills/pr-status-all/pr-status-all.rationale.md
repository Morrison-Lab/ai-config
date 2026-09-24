# pr-status-all / pr-status Rationale & Verification History

This document records the load-bearing operational rationale, synthetic-fixture verifications, and empirical measurements supporting the signal gathering and verdict computation in `pr-status-all` and `pr-status`.

## 1. Currency Verification against Head Commit

- **Timing Comparison vs. Named Commit SHA**: Comparing `createdAt` of the latest review comment against `committedDate` of the head commit (`commits[-1].committedDate`) is necessary but not sufficient on its own.
  A review workflow started against an older commit can finish and post after a newer push lands, making `createdAt` appear current even though the reviewed diff is stale.
  Furthermore, `committedDate` reflects local committer authoring time rather than when GitHub received the push.
  Therefore:
  - If `.review.createdAt < .lastCommitDate`, the review predates the latest push and is reported as `[⏳ In-Flight / Stale](url)`.
  - When the review body names the reviewed commit (e.g. `@claude` writing "commit `<sha>`"), the prefix must match `.headRefOid`.
  - If no SHA is present in the review body to corroborate currency, the review is reported as `[⚠️ Unverified](url)`, never as `clean`.

## 2. External Reviewer Verification (Copilot & Humans)

- **Subprocess Shell Isolation (`head=` line repetition)**: In subagent fan-out and multi-step execution, environment variables do not persist across separate subagent tool invocations.
  Repeating `head="$(gh pr view "<N>" --json headRefOid -q .headRefOid)"` inside each code block guarantees `$head` is never an empty string that silently matches no review objects (`[]`).
- **Suppressed Low-Confidence Comments**: Copilot reviews can output "generated no new comments" in the main overview while collapsing real findings inside `<details>` blocks (verified on PR #660 review 4767752501 with 3 suppressed findings, and PR #1029 / #1031).
  Matching case-insensitively on `suppressed` in a `<summary>` element or in an ATX heading inside a collapsed `<details>` region catches these hidden findings without false-positive matching on ordinary overview prose.
  The control is ai-config#1038 review 4837572117, whose uncollapsed overview sentence reads "Aligns ARDI-family guidance on deadlocks, sweep scheduling, and suppressed Copilot findings" while its summary table contains no occurrence of the word (re-read 2026-09-04).
  A heading rather than `<summary>` alone, because ai-config#3084 review `5098574802` nests the block as a `### Suppressed comments (1)` heading under `<summary>Review details</summary>`;
  a heading rather than the whole `<details>` region, because that same review collapses its `Pull request overview` and `File summaries` prose into regions of their own (both measured 2026-09-03),
  so the collapsed region is no longer a proxy for "not ordinary overview prose" --- a region-wide match would readmit any collapsed overview that did mention suppressed findings.
  A body does exercise that case: ai-config#1036 review `4837539268` collapses a `Show a summary per file` table reading "Detects suppressed Copilot findings." and carries no suppression block at all.
  Enumerating Copilot review bodies from the `reviews` endpoint on 2026-09-04 --- 137 bodies across 39 PRs, from ai-config PRs 1000 through 1100 and 3060 through 3130 plus ai-config#660, ai-config#2913 and ai-config#2976 --- that is the region-wide form's only false positive and its only disagreement with the heading anchor, so it buys no measured coverage.
  It stays as a fallback on the cost asymmetry rather than on a clean record: a false zero merges over real findings while a false positive costs one re-read.
  - **Do:** treat a hit only the region-wide fallback finds as probably spurious, and re-read the region before recording a finding.
  - **Don't:** justify the fallback by saying no measured body turns it into a false positive --- `4837539268` does.
- **Every Copilot Review at the Head, Not the Last One**: Copilot submits more than one review per head, and a suppression block sits in each of them independently --- three reviews at head `6f10014` on ai-config#3084 (`5098574802`, `5098854246`, `5098881593`) each carried a `### Suppressed comments (1)` block (measured 2026-09-03 from `get_reviews`).
  A `| last` reduction over that id list therefore scans only the last review's block and never reads the other two's, and it reports `clean` outright in the case where the review it keeps is the finding-free one.
  The `group_by(.user.login)` guard used for human reviews does not help, because every Copilot review shares the one bot login.
  - **Do:** loop the body and inline-comment fetch over every Copilot review whose `commit_id` matches the head.
  - **Don't:** reduce that id list to a single review before scanning it for findings.
- **Substance over State for Human Reviews**: Empirical measurements across this repository (measured 2026-07-30 on #668: 106 of 106 formal reviews across 60 merged PRs were submitted as `COMMENTED`, with zero `APPROVED`).
  Keying on `state == "APPROVED"` would produce a permanent false negative ("no verdict at head") on PRs humans actively approved in review comments.
  Reviews are therefore evaluated by substantive zero-findings content.
- **`.user.type == "User"` Filter**: A GitHub REST API user object carries `type: "Bot"` for bot reviewers (such as Copilot and GitHub Actions) and `type: "User"` for real accounts (measured 2026-08-15).
  Filtering on `.user.type == "User"` cleanly isolates human reviews without requiring an unmaintainable blocklist of bot logins.

## 3. Human `CHANGES_REQUESTED` and Dismissal Filtering

- **State-Filtered Reduction Order**: GitHub maintains review history as a chronological log where a reviewer's decisive `CHANGES_REQUESTED` state persists across subsequent neutral `COMMENTED` reviews until explicitly `APPROVED` or `DISMISSED`.
  Filtering to `APPROVED`/`CHANGES_REQUESTED`/`DISMISSED` *before* grouping by author and taking the latest submitted review is essential.
  Synthetic fixture verification proved that a naive reduction across all states allowed a later `COMMENTED` review from the same author to incorrectly mask an outstanding `CHANGES_REQUESTED`.
- **Inclusion of `DISMISSED` in Pre-Reduction Filter**: GitHub's dismiss action updates the existing review's state to `DISMISSED` without deleting the review object.
  Including `DISMISSED` in the filter ensures that an explicit dismissal supersedes a prior `CHANGES_REQUESTED`.
  A second synthetic fixture verified that omitting `DISMISSED` from the pre-reduction filter caused an old `CHANGES_REQUESTED` to permanently block even after being dismissed.

## 4. Multi-Signal Next Step Decision Matrix

- **Exhaustive Signal Evaluation**: The transition matrix evaluates all gathered dimensions (draft status, blocking human reviews, branch sync with main, 3-way CI state `[Failing, Pending, Green]`, unresolved inline review threads, AI review findings, External review findings, and currency confirmation) before reaching the "fully clean" terminal state.
  Treating AI review alone as the sole review branch allowed PRs with open External review findings or unconfirmed review currency (`Unverified` / `no verdict at head`) to erroneously declare readiness.
  Similarly, distinguishing `CI is pending` (`Wait for CI`) from `CI is failing` (`Fix CI`) ensures in-flight CI runs do not fall through to unhandled transitions when reviews are clean.
  The matrix explicitly requires all reviews to be free of open findings and at least one verified clean review at head before transitioning to `Ready for self-merge` or `Ready for human review`.
