---
name: ardia
description: "Drive all open PRs to clean."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
---

# ARDIA — ARD + Iterate-All

Apply the ARDI loop (ARD + iterate) to every open PR/MR in the repo, driving
each to a clean review verdict in series.
Triage and local patch preparation may run in parallel first; every action that
mutates a PR stays serial.

## Procedure

1. **List the open PRs/MRs and decide which are in scope.**
   ```bash
   gh pr list --state open --limit 100 \
     --json number,title,headRefName,baseRefName,isDraft,author,reviewDecision   # LIST_PRS
   ```
   On GitLab, use `glab api "projects/:id/merge_requests?state=opened&per_page=100"`
   and look for `source_branch` (≡ `headRefName`) and `target_branch` (≡ `baseRefName`)
   in the JSON — `glab mr list` alone does not expose these fields.
   State the scope rules when you report, so the user can
   correct:
   - **Only the user's own PRs are in scope.**
     Keep a PR only when `author.login` is the user (`d-morrison` or
     `dem-extra1`) or the user is among its `assignees`;
     drop every other PR from the list before doing anything else, and name
     the dropped ones in the report so the user can reassign any they want
     driven.
     "Every open PR" below means every PR that survives this filter.
     A PR by another lab member or by a bot is not driven, reviewed, or
     edited, however clean it looks
     (see `memories/preferences.md`, "Only work PRs I opened or am assigned
     to"; measured on `UCD-SERG/serodynamics` 2026-09-01, where the sweep
     drove four other authors' PRs before the correction arrived).
   - **Include drafts** (`isDraft: true`) unless another agent is actively driving one.
     A draft is the corpus's own in-flight claim signal ---
     [`pr-on-claim`](../../shared/workflow/pr-on-claim.md) opens one from an empty `start:` scaffold commit before any code exists ---
     so read each draft's state rather than sorting by the flag:
     - **Skip a driven draft.**
       Any of these marks one:
       the head commit is still the `start:` scaffold (the implementer is mid-flight),
       a still-live claim comment stands (claims expire after 2 hours with no push or comment --- [`claim-pr`](../../shared/workflow/claim-pr.md)),
       another actor pushed recently,
       or the draft is deliberately held as a merge-order gate (`CLAUDE.md`'s "Surface merge-order constraints", surface 3).
     - **Include a parked draft.**
       Real implementation on the branch,
       no live claim,
       and no recent activity by another actor.
       The review bot skips drafts in most repos,
       so once its content passes the repo's checks,
       mark it ready for review --- a clean verdict is unreachable while it stays draft.
     Name each draft's disposition, and the signal that decided it, in the scope report,
     so the user can veto before the loop touches it.
   - **Only iterate PRs the user owns / is responsible for** by default. In a
     shared repo, don't start review loops (which push commits) on other
     people's PRs unless told to. If unsure who owns what, ask first.
   - **A green PR with no review check run is parked, not finished.**
     On a repo whose review workflow is `workflow_dispatch`-only, nothing
     fires on push, so a PR nobody ever reviewed presents exactly like one
     that passed: every check green, nothing pending.
     The tell is an **absence**, so no check state carries it, and the
     sweep's own triage is where that absence has to be caught.
     Read the review workflow's `on:` block once per repo, then treat "zero
     review check runs on the head" as its own triage outcome.
     `pull_request_read` `get_check_runs` answers it per PR.
     [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)'s dispatch-only
     section covers the single-PR case; the increment here is that a sweep
     classifying many PRs at once will otherwise sort these into the
     nothing-to-do pile.
     - **Do:** name such a PR's verdict as missing rather than clean, and
       dispatch a review for it --- pricing that round first, since a
       dispatch is a real spend and several of them are several spends.
     - **Don't:** read green checks with nothing pending as evidence a
       review passed; on a dispatch-only repo that is the steady state.

     (`Morrison-Lab/ai-config`, 2026-08-16: an `ardia` sweep found #1500 and
     #1509 parked 4h and 2h19m, both all-green with no verdict, because that
     repo's `claude-review.yml` carries no `pull_request` trigger.
     Both had never been reviewed; the dispatched rounds then returned
     "Needs more work" on each, with a blocking correctness bug in #1509.)
   - If the list is empty, say so and stop — nothing to do.

   **Detect and sort stacked PRs.** Check each PR's `baseRefName`. If any PR's
   `baseRefName` matches another open PR's `headRefName`, they are stacked.
   Sort the list so base PRs come before the PRs stacked on them —
   process bases first so derived PRs always sit on a clean, reviewed base. Note
   any stack in the scope report:
   ```
   Stacked PRs detected: #A → #B (process #A first)
   ```
   If a circular stack is found (impossible in practice but check anyway),
   surface it to the user and skip those PRs.

   **Tie-break with infrastructure-first.** Among PRs with no stacking
   relationship, when otherwise equally pressing, process internal
   infrastructure PRs (shared tooling, CI workflows, reusable actions,
   templates) slightly ahead of feature PRs — see
   [`pr-prioritization`](../../shared/workflow/pr-prioritization.md). This
   never overrides the stacking order above.

   Report the in-scope list (with bare PR URLs) **before** you start, so the
   user can veto any before the loop pushes commits.

2. **Optionally fan out read-only triage and local preparation.**
   Independent PRs may be inspected concurrently, one worker per PR, each in its
   own worktree.
   A worker may read the latest review and CI logs, trace a finding to its
   cause, run the repo's local checks, and prepare a focused patch.
   It must not claim a PR, post a comment, commit, push, request review, or
   otherwise mutate shared forge state --- every one of those belongs to the
   serial loop below.

   **Check for supersession before preparing a patch for an idle, non-clean PR.**
   Grep `origin/main` for the PR's distinctive added phrases; if they are all
   already there, the PR is `Superseded` (see step 3's terminal states) and its
   patch prep is wasted work --- flag it for closure instead.
   Run that grep over `main`'s whole Markdown corpus rather than over the PR's
   own file paths, for the reason step 3's terminal state gives.

   **The patch has to leave the worktree as an artifact, not sit in it as a
   dirty tree.**
   A worker's worktree is not durable: `isolation: 'worktree'` has reclaimed one
   mid-run before, which is the incident
   [`incidents-dont-repeal-decisions`](../../shared/workflow/incidents-dont-repeal-decisions.md)
   is written about.
   A dirty tree is also the one form the orchestrator cannot inspect, diff, or
   apply without re-entering that worktree, so it fails whether or not the
   worktree survives.
   Have each worker end by emitting a patch to an orchestrator-owned path, and
   return that path plus the SHAs below:

   ```bash
   git diff > "$ARTIFACT_DIR/pr-<N>.patch"    # no commit, no push, no forge state touched
   ```

   That keeps the no-mutation rule exactly as stated --- a patch file is not a
   commit --- while making the preparation survive the worker.

   Skip the fan-out for stacked PRs, for PRs whose likely file footprints
   overlap, and whenever independence is uncertain.
   Consolidate the prepared findings and patches before step 3 begins.

   **A prepared patch is a snapshot, not a decision.**
   Record the base and head SHAs the patch was prepared against, and re-check
   **all four** signals when the serial loop reaches that PR: those two refs,
   the latest review, and CI state.
   Re-derive the patch if any has moved.

   The two refs are the half that is easy to omit and the half that actually
   goes stale.
   A `main` advance or a new PR-head commit need not produce a new review or a
   new CI run, so a review-and-CI check alone returns "unchanged" for exactly
   the case that invalidates a patch --- which is the shape
   [`fail-fast`](../../shared/principles/fail-fast.md) warns about, where the
   pass path and the stale path print the same thing.

   ```bash
   base=$(git rev-parse origin/main); head=$(git rev-parse "origin/$branch")   # at prepare time
   git fetch origin -q                                                        # at apply time
   [ "$base" = "$(git rev-parse origin/main)" ] &&
   [ "$head" = "$(git rev-parse "origin/$branch")" ] || echo "stale -- re-derive"
   ```

   Applying a stale patch costs a review round rather than saving one.
   That staleness is what bounds the fan-out rather than runner contention:
   nothing here pushes, so the cost of going wider is that the last patch
   applied has waited longest and is likeliest to be stale.
   Default to a wave of about **3**, and shrink it when the queue is moving
   fast --- frequent merges to `main` invalidate preparation sooner, so a
   busy repo wants a narrower wave than a quiet one.
   Re-run preparation for a later wave rather than stretching one across
   every PR at once.

3. **For each PR/MR, in series, run ARDI** (the full single-PR loop --- see the
   `ardi` skill): claim → sync main → read latest review → ARD every finding →
   push → post summary → re-request review → repeat until fully clean. Don't
   reimplement that loop here; follow it per PR.

   **For stacked PRs:** the ideal flow is to merge the base PR before starting
   ARDI on the derived PR. If the base isn't mergeable yet (pending CI, open
   review findings), complete ARDI on the base first to drive it to clean and
   merge it, then start the derived PR. Never run ARDI on a derived PR while its
   base is still open and unclean — you'd be reviewing against a moving target.

   A PR reaching **clean-but-unmerged** is that PR's terminal state, **not** a
   reason to pause the sweep: merging is human-gated (you don't self-merge), but
   that gates only the merge — move straight to the next PR rather than waiting
   for a human to merge first. See
   [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md), and use
   [`stack-prs`](../stack-prs/SKILL.md) for the branch/PR mechanics when the
   next item needs to stack on a clean-but-unmerged PR.

   **Cascading the stack is part of ARDIA, not separate side work.** Every time
   a base advances — it merges into `main`, *or* its own head moves (a review
   fix, a main-sync commit) — every PR stacked above it goes `BEHIND`/`DIRTY`
   and must be re-synced: merge the base's new head into the child, resolve
   conflicts (keeping *both* the base's changes and the child's own — e.g. a
   rename in the base and a new parameter in the child both survive), re-verify
   (run the repo's own checks — build/lint/tests, plus any doc regeneration or
   character check), bump the child's version above the base where the repo
   requires it, and push. This ripples:
   a single review-fix commit to a mid-stack PR puts every descendant behind,
   so one ARDIA pass may sync the same branch more than once as fixes land
   below it. When the user says "cascade" or "keep driving all these to clean,"
   that includes this conflict-resolution/re-sync loop up the whole stack —
   don't treat "resolve merge conflicts" or "sync the stack" as out-of-scope.
   Process bottom-up: sync the lowest `BEHIND`/`DIRTY` PR first, then its
   children, since each sync advances a head the next child needs.

   Drive each to a terminal state:
   - **Clean** — zero flagged items under any heading; post the unclaim
     comment, record the round count.
   - **Escalated** --- every remaining **review finding** is deadlocked and waiting on a human ruling.
     Record which findings, move to the next PR, and return when the human rules.
     Escalating *some* findings is not this: keep driving the PR on everything else.
     A round count is never a terminal state at all --- see [`ardi`](../ardi/SKILL.md)'s "Stopping conditions".
   - **Blocked** --- an **external or operational** obstacle rather than a review finding: an unresolvable conflict, a needed human decision outside the review, or a preflight failure your change didn't cause.
     Record what's blocking, move on.
   - **Superseded** --- the PR's content already landed on `main` via a sibling PR, so its remaining findings and any conflict are moot and the right action is to close it, not drive it.
     Recognize this before spending rounds: an idle, non-clean PR whose `main`-merge conflict pits its own added lines against a better-formatted copy already on `main` is the tell, and grepping `origin/main` for the PR's distinctive added phrases confirms it (all present -> superseded, and resolving toward `main` would leave an empty diff).
     Recommend closure --- the content is preserved on `main` --- and name the superseding PR, rather than pushing an empty diff to clean.
     See [`sync-with-main`](../../shared/workflow/sync-with-main.md)'s duplicate-issue and whole-file-split cases, which already say to keep `main`'s version when a sibling published the same content.
     This is that judgment applied up front, at the whole-PR scale, with closure as the terminal action.

     **That grep needs a search space, and the whole corpus is the right one.**
     The prescription above says to grep `origin/main`, and does not say where
     in it.
     The reader supplies the narrow answer, because the PR's own file list is
     right there: compare each added line against its counterpart in the same
     path on `main`.

     That reading under-reports whenever `main` has since **relocated** the
     content --- a `.cases.md` or `.rationale.md` split, a rename, a section
     moved between fragments.
     The lines did land, somewhere else.
     A per-file check reports them missing, so a superseded PR reads as
     not-superseded and the sweep spends rounds driving a PR it should be
     recommending for closure.

     The error runs in the cheap direction, which is why nothing catches it.
     It never closes a PR wrongly, it only fails to close one, so there is no
     bad outcome to trace back and the wasted rounds look like ordinary work.

     Score both scopes when they can differ, and report both:

     ```bash
     base="$(git merge-base <head> origin/main)"
     git diff --name-only "$base" <head> | while read -r f; do
       git diff -U0 "$base" <head> -- "$f" | grep '^+' | tail -n +2 | sed 's/^+//'
     done
     # per line, normalized for whitespace and inline markup, ask twice:
     #   present in the same path on origin/main?
     #   present anywhere in origin/main's Markdown corpus?
     ```

     Scope the diff to one file at a time, so each `+++ b/<path>` header is
     dropped by **position** rather than by pattern.
     Neither shortcut survives a whole-PR diff, and they fail in opposite
     directions.
     A single `tail -n +2` drops only the first file's header and leaves the
     rest in the stream, where they read as content and inflate the score's
     denominator.
     A `grep -v '^+++ '` filter drops every header and also drops any added
     line whose own text begins `++ `, since the diff's own marker turns it
     into `+++ ` --- so that filter silently deletes real content, which is
     the worse of the two.
     No prefix pattern separates a header from its data, per
     [`fail-fast`](../../shared/principles/fail-fast.md)'s third pattern
     direction; per-file position does.

     Cross-check the extracted line count against `git diff --numstat`'s
     insertion column, which is computed by something other than this
     pipeline --- a disagreement means a header leaked in or a content line
     was swallowed, rather than anything about supersession.

     - **Do:** run the supersession grep over `main`'s whole Markdown corpus,
       not over the PR's own file paths.
     - **Do:** report both scores when they differ, since the gap names a
       relocation rather than missing content.
     - **Don't:** read a per-file shortfall as evidence the content did not
       land --- a split, a rename, or a section move produces exactly that.
     - **Don't:** treat the PR's file list as the search space merely because
       it is the list already in front of you.

     (Morrison-Lab/ai-config#1458, 2026-08-15.
     The same presence check, run after that PR merged to confirm its content
     had landed, scored its pre-routing head `009fc9ef` against `origin/main`:
     42 of 78 substantive added lines present in their own file's counterpart,
     and 78 of 78 present somewhere in the corpus --- 45 of 89 and 89 of 89
     counting every non-blank added line.
     Scoring examined the 333 Markdown files outside the generated
     `codex-skills/` mirror, of 514 tracked `.md` files in all.
     The whole gap is `main` having absorbed PR #1468's rule/rationale split:
     lines that head added to `shared/workflow/address-every-comment.md` now
     live in that file's `.rationale.md` companion, so the path they were
     added to no longer holds them.)

   `Escalated` and `Blocked` are disjoint by construction: the first is about the *review* deadlocking, the second about everything else.
   A PR meeting both is `Blocked`, since the external obstacle has to clear before the review matters.
   `Superseded` takes precedence over either: once the content has landed on `main`, the findings and any conflict no longer matter.

   **Process PRs one at a time, not concurrently.** Each ARDI run pushes
   commits, triggers review workflows, and polls for the result; running them
   in parallel would interleave pushes, collide on shared review runners, and
   make per-PR status illegible. One PR stalling or blocking must not abort the
   batch — keep going to the next.

4. **Report a summary table** at the end, with clickable links:

   | MR/PR | Rounds | Final status |
   |-------|--------|--------------|
   | [#25](url) | 3 | ✅ Clean |
   | [#26](url) | 4 | ⏸️ Escalated --- awaiting human on: … |
   | [#27](url) | 1 | ⛔ Blocked --- needs human decision on … |
   | [#28](url) | 0 | 🔁 Superseded --- content on `main` via [#N](url); recommend closing |

   For any PR not driven to clean, **list its remaining open items** so triage
   is one glance, not a re-investigation. Don't merge anything — opening merges
   is the user's call.

## Orchestration

ARDIA serializes every action that **mutates** a PR
(see *Process PRs one at a time* above):
each round claims, pushes, triggers shared review runners, and polls for the
result, so parallel pushes collide and make per-PR status illegible.
A Workflow does not change that external limit ---
do **not** fan out the claim --- push --- re-review --- merge loop.

What you *can* orchestrate is step 2:
the read-only survey, and the isolated local preparation that follows it and
feeds step 3's serial loop.
Step 2 states the worker's limits, and a Workflow relaxes none of them ---
spell them out in the worker's prompt, because a worker told only to "fix the
findings" will reach for `gh` and `git push` on its own.
Consult `shared/workflow/when-to-orchestrate.md` (the shared-runner exception);
default to the serial loop,
and propose the fan-out only when there are many PRs to survey.

### Lightweight sidecar delegation

Separately from the Workflow-based survey fan-out above, a single PR's ARDI
round (see `ardi`) can delegate sidecar work directly via the `Agent` tool ---
verifying a disputed factual claim, investigating an unclear CI failure, or
researching how a prior PR handled the same pattern --- while the main thread
keeps driving that round forward. This is a lighter-weight call than the Workflow
tool covers above and needs no opt-in gate. Give the subagent a stronger
model (e.g. `model: 'opus'` on the `Agent` tool call) for judgment-heavy
sidecar work, and symmetrically a cheaper/faster tier (`model: 'fable'` or
`'haiku'`) for a mechanical one --- see
[`select-model`](../../skills/select-model/SKILL.md)'s decision tree for both
directions. For a heavy fan-out survey/verify pass, prefer a
separately-billed provider (e.g. the `codex` CLI) first when available ---
see [`delegate-to-codex`](../delegate-to-codex/SKILL.md).

## Recurring / unattended runs

If asked to keep the queue clean on an interval, drive this skill from a
recurring runner (e.g. the `loop` skill) rather than busy-waiting inside one
invocation. Each tick re-enumerates open PRs (new ones appear, merged ones drop
off) and runs the series loop over the current set.
