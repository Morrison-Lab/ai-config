# ARDIA — ARD + Iterate-All

Apply the ARDI loop (ARD + iterate) to every open PR/MR in the repo, driving each to a clean review verdict in series.

## Procedure

1.  **List the open PRs/MRs and decide which are in scope.**

    ``` bash
    gh pr list --state open --limit 100 \
      --json number,title,headRefName,baseRefName,isDraft,author,reviewDecision   # LIST_PRS
    ```

    On GitLab, use `glab api "projects/:id/merge_requests?state=opened&per_page=100"` and look for `source_branch` (≡ `headRefName`) and `target_branch` (≡ `baseRefName`) in the JSON — `glab mr list` alone does not expose these fields. State the scope rules when you report, so the user can correct:

    - **Skip drafts** by default (`isDraft: true`) — they aren’t ready for the clean-verdict bar. Include one only if the user explicitly asks.
    - **Only iterate PRs the user owns / is responsible for** by default. In a shared repo, don’t start review loops (which push commits) on other people’s PRs unless told to. If unsure who owns what, ask first.
    - If the list is empty, say so and stop — nothing to do.

    **Detect and sort stacked PRs.** Check each PR’s `baseRefName`. If any PR’s `baseRefName` matches another open PR’s `headRefName`, they are stacked. Sort the list so base PRs come before the PRs stacked on them — process bases first so derived PRs always sit on a clean, reviewed base. Note any stack in the scope report:

        Stacked PRs detected: #A → #B (process #A first)

    If a circular stack is found (impossible in practice but check anyway), surface it to the user and skip those PRs.

    **Tie-break with infrastructure-first.** Among PRs with no stacking relationship, when otherwise equally pressing, process internal infrastructure PRs (shared tooling, CI workflows, reusable actions, templates) slightly ahead of feature PRs — see [`pr-prioritization`](../../shared/workflow/pr-prioritization.md). This never overrides the stacking order above.

    Report the in-scope list (with bare PR URLs) **before** you start, so the user can veto any before the loop pushes commits.

2.  **For each PR/MR, in series, run ARDI** (the full single-PR loop — see the `ardi` skill): claim → sync main → read latest review → ARD every finding → push → post summary → re-request review → repeat until fully clean. Don’t reimplement that loop here; follow it per PR.

    **For stacked PRs:** the ideal flow is to merge the base PR before starting ARDI on the derived PR. If the base isn’t mergeable yet (pending CI, open review findings), complete ARDI on the base first to drive it to clean and merge it, then start the derived PR. Never run ARDI on a derived PR while its base is still open and unclean — you’d be reviewing against a moving target.

    A PR reaching **clean-but-unmerged** is that PR’s terminal state, **not** a reason to pause the sweep: merging is human-gated (you don’t self-merge), but that gates only the merge — move straight to the next PR rather than waiting for a human to merge first. See [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md), and use [`stack-prs`](../../skills/stack-prs/SKILL.llms.md) for the branch/PR mechanics when the next item needs to stack on a clean-but-unmerged PR.

    **Cascading the stack is part of ARDIA, not separate side work.** Every time a base advances — it merges into `main`, *or* its own head moves (a review fix, a main-sync commit) — every PR stacked above it goes `BEHIND`/`DIRTY` and must be re-synced: merge the base’s new head into the child, resolve conflicts (keeping *both* the base’s changes and the child’s own — e.g. a rename in the base and a new parameter in the child both survive), re-verify (run the repo’s own checks — build/lint/tests, plus any doc regeneration or character check), bump the child’s version above the base where the repo requires it, and push. This ripples: a single review-fix commit to a mid-stack PR puts every descendant behind, so one ARDIA pass may sync the same branch more than once as fixes land below it. When the user says “cascade” or “keep driving all these to clean,” that includes this conflict-resolution/re-sync loop up the whole stack — don’t treat “resolve merge conflicts” or “sync the stack” as out-of-scope. Process bottom-up: sync the lowest `BEHIND`/`DIRTY` PR first, then its children, since each sync advances a head the next child needs.

    Drive each to a terminal state:

    - **Clean** — zero flagged items under any heading; post the unclaim comment, record the round count.
    - **Asymptotic noise** — per ARDI’s guard, if after 3–4 rounds the reviewer keeps emitting *new* nits, stop that PR, record it “stalled (noise)”, move on.
    - **Blocked** — needs a human decision, has unresolvable conflicts, or fails preflight in a way your change didn’t cause. Record what’s blocking, move on.

    **Process PRs one at a time, not concurrently.** Each ARDI run pushes commits, triggers review workflows, and polls for the result; running them in parallel would interleave pushes, collide on shared review runners, and make per-PR status illegible. One PR stalling or blocking must not abort the batch — keep going to the next.

3.  **Report a summary table** at the end, with clickable links:

    | MR/PR       | Rounds | Final status                           |
    |-------------|--------|----------------------------------------|
    | [\#25](url) | 3      | ✅ Clean                               |
    | [\#26](url) | 4      | ⚠️ Stalled (noise) — open items: …     |
    | [\#27](url) | 1      | ⛔ Blocked — needs human decision on … |

    For any PR not driven to clean, **list its remaining open items** so triage is one glance, not a re-investigation. Don’t merge anything — opening merges is the user’s call.

## Orchestration

ARDIA drives PRs **one at a time on purpose** (see *Process PRs one at a time* above): each round pushes commits and triggers shared review runners, so parallel pushes collide and make per-PR status illegible. A Workflow does not change that external limit — do **not** fan out the push — re-review — merge loop. What you *can* orchestrate is the read-only survey: pull every open PR’s latest review and triage its findings in parallel, then feed that into the serial fix loop. Consult `shared/workflow/when-to-orchestrate.md` (the shared-runner exception); default to the serial loop, and propose the read-only fan-out only when there are many PRs to survey.

### Lightweight sidecar delegation

Separately from the Workflow-based survey fan-out above, a single PR’s ARDI round (see `ardi`) can delegate sidecar work directly via the `Agent` tool — verifying a disputed factual claim, investigating an unclear CI failure, or researching how a prior PR handled the same pattern — while the main thread keeps driving that round forward. This is a lighter-weight call than the Workflow tool covers above and needs no opt-in gate. Give the subagent a stronger model (e.g. `model: 'opus'` on the `Agent` tool call) for judgment-heavy sidecar work, and symmetrically a cheaper/faster tier (`model: 'fable'` or `'haiku'`) for a mechanical one — see [`select-model`](../../skills/select-model/SKILL.llms.md)’s decision tree for both directions. For a heavy fan-out survey/verify pass, prefer a separately-billed provider (e.g. the `codex` CLI) first when available — see [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md).

## Recurring / unattended runs

If asked to keep the queue clean on an interval, drive this skill from a recurring runner (e.g. the `loop` skill) rather than busy-waiting inside one invocation. Each tick re-enumerates open PRs (new ones appear, merged ones drop off) and runs the series loop over the current set.

Back to top
