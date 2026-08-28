---
name: gii
description: "Grab issues and implement in series."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
---

# GII — Grab Issues Iteratively (aka GIS)

Loop: grab the highest-priority open issue → implement → open MR/PR → ARDI to
clean → repeat with the next issue. Stack MRs when needed.

## When this fires

- User says "gii", "gis", "grab issues", "work through the backlog"
- User says "keep going" / "do all the issues" / "next issue"
- User says "grab issues iteratively" / "stack them up"

## Procedure

### 0. Establish context

Detect the forge (GitHub / GitLab) from `git remote get-url origin`.
Note the default branch (`main` / `master`).

### 1. Enter the loop

For each iteration:

#### a. Invoke `gi` (Grab Issue)

Run the full GI procedure:
1. List open issues, triage/prioritize
2. Select the highest-priority issue automatically from the triage signals,
   state which one and why, and proceed without pausing for confirmation
3. Check history
4. Claim the issue
5. Create a branch
6. Open the draft PR up front, from an empty commit, before implementing —
   see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)
7. Implement
8. Push and mark the PR ready for review
9. ARDI to clean

#### b. Record the result

Track each completed issue in a running table:

| # | Issue | MR/PR | Rounds | Status |
|---|-------|-------|--------|--------|
| 1 | [#12](url) | [#30](url) | 2 | ✅ Clean |

(Examples use GitHub `#N` notation; on GitLab the MR IID is `!N`.)

#### c. Decide the next base branch (stacking)

A clean-but-unmerged MR is **not** a stopping point. Merging is human-gated
(you don't self-merge), but that gates only the merge, not the loop — keep
going to the next issue instead of pausing to wait for a human to merge first.
Stacking is what lets the loop keep moving without merges. See
[`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md).

After ARDI completes clean on the current MR/PR:

- **If the MR was merged** (user said "merge" or auto-merge is on):
  base the next branch on `origin/main` (which now includes the fix).
- **If the MR is open but clean** (not yet merged):
  base the next branch on the **current MR's branch** — this creates a
  stacked MR. Note the dependency in the new MR's description:

  > ⚠️ Stacked on [#30](url) — merge that first.

  Track the stack so the final report shows the merge order.

#### d. Check stopping conditions

Stop the loop when:
- No more open issues (backlog empty)
- User interrupts or says "stop" / "that's enough"
- A configurable max is reached (default: 5 issues), which ends the current
  **wave**, not the session — see below
- An issue is blocked and no other unblocked issues remain — otherwise
  **bypass** the blocked issue (surface it) and keep going with the rest

Hitting the max is a **wave boundary**, not a question to pose.
Wrap up one wave of PRs before starting another (user directive, 2026-08-28):
hold new issue grabs, babysit the wave's open PRs to completion (merge-ready,
and merged where a merge grant applies), then start the next wave
automatically.

- **Do:** hold at the boundary and drive the open wave to completion, then
  continue with the next wave without asking.
- **Don't:** ask "want me to keep going?" at the max — the wave boundary
  replaces that ask.
- **Don't:** read the boundary as forbidding parallel PRs *within* a wave.

#### e. Recurse

Go back to step (a) with the next issue.

## Delegate sidecar work when helpful

Within an iteration, hand independent sidecar work off to a subagent via the
`Agent` tool instead of doing it inline --- a history/precedent investigation,
a verification pass on the implementation, research into how a similar issue
was solved elsewhere. Keep the critical path (claim, draft PR, implement,
ARDI) on the main thread so the loop keeps moving; this is a single sidecar
call within one iteration, not a way to run whole issues concurrently --- for
that, see [`gip`](../gip/SKILL.md).

When the sidecar task is judgment-heavy (a tricky bug hunt, an
architecturally significant call, an adversarial review pass before the
implementation goes out for real review), give the subagent a stronger model
via the `Agent` tool's `model` parameter (e.g. `model: 'opus'`) instead of
leaving it at the session default. Symmetrically, override to a cheaper/faster
tier (`model: 'fable'` or `'haiku'`) for mechanical, bounded sidecar work --- a
lookup, a formatting check, a repeated verification --- rather than defaulting
to the session's own tier; see
[`select-model`](../../skills/select-model/SKILL.md)'s decision tree for both
directions. When the sidecar task is a heavy fan-out read/draft/verify pass
and a separately-billed provider is available (e.g. the `codex` CLI), prefer
spending that budget first and keep Claude/Agent-tool quota in reserve --- see
[`delegate-to-codex`](../delegate-to-codex/SKILL.md).

## Stacking rules

When stacking MRs (basing a new branch on an unmerged MR branch):

1. **Branch from the tip of the previous MR branch**, not from main:
   ```bash
   git checkout -b feat/<next-slug> <previous-mr-branch>
   ```

2. **Note the dependency** in the new MR description (use `#<N>` on GitHub,
   `!<N>` on GitLab):
   ```
   ⚠️ Stacked on #<N> (GitHub) / !<N> (GitLab) — merge that first.

   Depends on: #<N>
   ```

3. **If the base MR gets changes** (from ARDI on a later review round),
   rebase/merge the stacked MR on top of the updated base before its own
   ARDI round.

4. **Merge order** matters — report it clearly at the end.

## Final report

When the loop ends, print a summary:

```
## GII Session Summary — <timestamp>

| # | Issue | MR/PR | Rounds | Status |
|---|-------|-------|--------|--------|
| 1 | [#12](url) | [#30](url) | 2 | ✅ Clean |
| 2 | [#8](url)  | [#31](url) | 1 | ✅ Clean |
| 3 | [#15](url) | [#32](url) | 3 | ✅ Clean |

### Merge order
1. [#30](url) — fix: auth timeout
2. [#31](url) — feat: retry logic (stacked on #30)
3. [#32](url) — docs: v3 migration guide

**Stopping Point**: All 3 issues completed / backlog clear. Clean stopping point reached.
```

## Relationship to other skills

- **`gip`** — the **parallel** counterpart: when a batch of issues is provably
  independent (no stacking dependency, no file overlap), `gip` lifts that subset
  out and works it concurrently in worktree-isolated subagents instead of
  serially. This loop stays serial for everything `gip` can't prove independent.
- **`gi`** — the inner loop; each iteration is a full GI invocation
- **`pr-on-claim`** — each iteration opens its draft PR up front (step 6) so the
  in-flight issue is visible before implementing
- **`ardi`** — drives each MR/PR to clean review within GI
- **`check-history`** — invoked per-issue to avoid undoing past work
- **`split-concerns`** — if an issue's implementation grows too large, split
- **`defer-issue`** — if sub-tasks emerge, defer them (they'll be picked up
  in a later iteration of this very loop)
- **`sync-pr-branch`** — used when stacking to keep branches current
- **`select-model`** — decision tree for picking a subagent's model tier when
  delegating sidecar work (see "Delegate sidecar work when helpful")
- **`delegate-to-codex`** — when a sidecar task is a heavy fan-out
  read/draft/verify pass and codex is available, prefer it first

## Auto-proceed mode

Issue selection never pauses for confirmation, per `gi`'s step 3, so there is
no per-issue confirmation for "just go" to skip.
What the loop still does, in every mode:
- Still hold at the max-issues wave boundary — babysit the open wave to
  completion before the next wave, without asking
- Surface and **bypass** a blocked or ambiguous issue — note it and skip to the
  next rather than halting; stop only if no independent issues remain (per the
  stopping conditions above)

## Single-branch-scoped sessions cap a wave at one PR

Some web/remote sessions are scoped so the agent proxy allows pushing **only** to the harness-assigned branch --- see [`use-existing-pr-branch`](../../shared/workflow/use-existing-pr-branch.md)'s "Exception" section.
The stacking mechanics in step (c) above assume a fresh branch is available per issue;
under that exception it is not, since a push to any branch other than the assigned one is rejected outright and stacking a second issue's branch off the first would need one.

Detect this from the harness's own session instructions (a "Develop on branch `<name>`" directive with no mention of creating additional branches), not from a failed push --- discovering the restriction via a rejected push means the issue's implementation work already happened for nothing.
When it applies, treat the wave boundary in step (d) as reached after the **first** issue's PR goes clean, not after the configured max: report the single-PR wave as done, name the constraint, and stop rather than attempting to grab a second issue that has nowhere to land.

- **Do:** check for a single-branch harness restriction before starting the loop, and cap the wave at one issue when it applies.
- **Do:** name the constraint in the final report rather than silently stopping after one issue with no explanation.
- **Don't:** discover the restriction by attempting a second issue's branch and hitting a rejected push.
- **Don't:** ask the user whether to continue --- report the one-PR wave as the session's natural stopping point, per the wave-boundary handling above.

## Anti-patterns

- ❌ Stacking more than 3–4 MRs deep without asking (merge conflicts compound)
- ❌ Grabbing issues assigned to someone else
- ❌ Continuing after a blocked issue without telling the user
- ❌ Forgetting to note stack dependencies in MR descriptions
- ❌ Basing on main when the previous MR hasn't merged yet and the next issue
  would edit the same passages it changes — that almost always conflicts; run
  `stack-prs`'s decision gate (same file but different regions usually merges
  cleanly from main and doesn't need the stack)
- ❌ Pausing after a clean-but-unmerged MR to wait for a human merge — you don't
  self-merge, but that's no reason to stop; keep going and stack the next issue
- ❌ Running unbounded without a wave boundary — cap each wave at 5 and wrap
  the wave's PRs before grabbing more
- ❌ Asking to continue at the wave boundary — wrap up, then continue
