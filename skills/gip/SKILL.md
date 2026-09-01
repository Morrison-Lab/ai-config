---
name: gip
description: "Grab issues and implement in parallel."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
---

# GIP — Grab Issues in Parallel

Grab a batch of open issues and work them **at the same time** — one subagent
per issue, each in its own git worktree, each running the full grab-issue flow
(claim → check history → open draft PR → implement → mark ready → ARDI to
clean). Then assemble one combined report.

This is the **parallel** counterpart to [`gii`](../gii/SKILL.md), which is
**deliberately serial**. The whole job of this skill is to safely lift that
serialization — and that is only safe for issues that are **provably
independent**. Read *The independence gate* before fanning anything out; it is
the load-bearing part.

## When this fires

- "gip", "grab issues in parallel", "do these issues concurrently"
- "work several issues at once", "parallelize the backlog",
  "fan out the issue queue", "spin up a worker per issue"

It does **not** fire for a single issue (use [`gi`](../gi/SKILL.md)) or when the
issues are interdependent / stacked (use [`gii`](../gii/SKILL.md), which stacks).

## Why `gii` is serial — and when parallel is safe

`gii` runs one issue at a time on purpose, for three reasons:

1. **Base-branch stacking** — a later issue's branch may depend on a prior MR
   that hasn't merged yet, so it must branch from that MR's tip, not
   `<default-branch>`.
2. **Same-file conflicts** — two issues that edit the same files produce
   guaranteed merge conflicts if worked in parallel.
3. **Shared working tree** — a single checkout can't hold two in-progress
   branches at once.

Parallel is safe only when **(1) and (2) don't apply** and **(3) is removed by
worktree isolation**. So this skill fans out **only the independent subset** and
sends everything else back to the serial path.

## Procedure

### 0. Establish context (orchestrator, once)

Detect the forge (GitHub `gh` / GitLab `glab`) from `git remote get-url origin`
and note the default branch. Resolve `<owner>/<repo>` once so you can pass it to
every subagent. In a remote/web session, `gh` may be absent — use the GitHub MCP
tools instead (e.g. `mcp__github__add_issue_comment`,
`mcp__github__create_pull_request`, `mcp__github__search_pull_requests`).

### 1. Enumerate and triage (orchestrator)

List the open issues and prioritize them exactly as [`gi`](../gi/SKILL.md) does.
Decide which issues are in scope for this batch (respect any the user named).

### 2. The independence gate (orchestrator — do NOT skip)

Partition the in-scope issues into an **independent set** (safe to parallelize)
and a **dependent remainder** (must stay serial). An issue belongs in the
independent set only if **all** hold:

- **No stacking dependency** -- it can branch straight from
  `origin/<default-branch>`; it doesn't need another in-flight issue's unmerged
  branch as its base.
- **No file overlap** — its likely touched files don't intersect any other
  in-batch issue's likely files. When in doubt, read the issues and sketch each
  one's probable file footprint; if two plausibly collide, treat them as
  dependent.
- **Not blocked** — no "blocked by #N" / "depends on #N" marker pointing at
  another open item.

Anything failing a check drops to the **dependent remainder**. If two issues
overlap only with each other, keep one in the independent set and defer the
other to the remainder — don't fan out both.

> **When unsure, serialize.** A false "independent" call costs a merge conflict
> and a confused review; a false "dependent" call only costs some wall-clock
> time. Bias toward the remainder.

If the independent set has **0 or 1** issues, there's nothing to parallelize —
hand off to [`gii`](../gii/SKILL.md) (serial) and stop here.

### 3. Pick the concurrency cap (orchestrator)

Fan out **at most N at once** (default **N = 3**). Bound it because every
subagent pushes commits, triggers a review workflow, and polls for the result —
too many at once swamps shared CI runners and the review bot (the same
runner-contention reason [`ardia`](../ardia/SKILL.md) processes PRs one at a
time). If the independent set is larger than N, run it in waves of N.

### 4. Fan out — one worktree-isolated subagent per issue (concurrent)

Spawn the wave **in a single message with multiple `Agent` calls** so they run
at once. Give **every** subagent `isolation: "worktree"` — that hands each one
its own working directory over the shared `.git`, so concurrent edits, branches,
and commits never collide on one checkout. (This is the subagent form of the
same isolation [`session-lock`](../session-lock/SKILL.md) sets up for
independent top-level sessions.)

**That parameter errors when the session's own cwd is not inside a git
repository** -- `Cannot create agent worktree: not in a git repository and no
WorktreeCreate hooks are configured` -- which is the normal layout in a harness
whose cwd merely *holds* repos as subdirectories.
Don't read that as isolation being unavailable and fall back to a shared
checkout; create each worktree explicitly instead
(`git -C <repo> fetch origin <default-branch>`, then
`git -C <repo> worktree add --detach <path> origin/<default-branch>`) and hand
the subagent its path.
`<default-branch>` is the one step 0 above already had you note, not the
literal string `main`: hard-coding it fails with
`fatal: invalid reference: origin/main` on any repo whose default is named
otherwise.
Base every one of them on `origin/<default-branch>`, never on the bare branch
name: `add <path> <default-branch>` succeeds for the first agent in a wave and
refuses for every one after it, and when the wave is genuinely concurrent its
guard can race and put several agents on that branch at once, silently costing
the isolation this step exists to buy.
Leave the branch to the subagent, which cuts its own inside the worktree.
See [`memories/preferences.md`](../../memories/preferences.md) for the full
precondition, the measured concurrency numbers, and the stale local base this
form also avoids.

A subagent starts **fresh** — it sees only the prompt you hand it, not this
skill file — so **inline the entire per-issue procedure**. Don't point it at
`gi`/`ardi`; restate the steps. Fill in `<N>`, `<title>`, `<owner>`, `<repo>`,
and the default branch for each issue:

> Work GitHub issue **#<N>** ("<title>") in `<owner>/<repo>` end to end,
> on your own branch,
> in this worktree.
> You are one of several parallel workers —
> stay entirely within this worktree and touch only files relevant to this issue.
>
> 1. **Claim it** so no one else double-works it:
>    post a brief "Working on this --- please hold off until I'm done." comment on the issue
>    (`gh issue comment <N> --body "..."`, or the MCP `mcp__github__add_issue_comment` equivalent in a remote session).
>    End the body with the agent-disclosure marker every agent-posted comment carries: `_Posted by Claude Code (AI agent) --- not written by a human._`
> 2. **Check history** — before writing code,
>    scan merged/closed PRs that touched the same area so you don't undo past work or reintroduce a fixed bug (`gh pr list --state all --search "<keywords>"`).
>    If a past PR already solved this,
>    stop and report that instead of re-doing it.
> 3. **Research before writing code (DRW check)** --- before hand-rolling any custom code,
>    helpers, or utilities, do a research step to verify DRW (don't reinvent the wheel)
>    and check for existing libraries, functions, or package solutions (in our own repos
>    or upstream ecosystems like r-lib/tidyverse, PyPI, npm).
>    Follow `prefer-upstream`.
>    If custom implementation is required, note what was searched in the PR.
> 4. **Branch from current `<default-branch>`**:
>    `git fetch origin <default-branch> -q && git checkout -b <slug> origin/<default-branch>`.
>    Use a descriptive `<slug>`.
> 5. **Open the draft PR now** --- before implementing,
>    so this worktree's work is visible to the other parallel workers and no one double-grabs the issue (see [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)).
>    Give the branch a diff with an empty commit, push,
>    and open a **draft** PR into `<default-branch>` referencing `Closes #<N>`:
>    `git commit --allow-empty -m "start: <title> (closes #<N>)"`,
>    then `git push -u origin HEAD` (retry with backoff on a network error),
>    then `gh pr create --draft …` (or `mcp__github__create_pull_request` with `draft: true`).
>    A draft doesn't trigger the review bot on an empty diff.
> 6. **Implement** the change.
>    Keep the diff focused on this issue only — do **not** touch files another issue owns.
>    Follow the repo's conventions (its `CLAUDE.md` / lab manual).
>    Run the repo's pre-commit checks (render / lint / spell / tests) and fix what they flag.
> 7. **Commit and push** the implementation onto the draft PR with a clear
>    message referencing the issue (`Closes #<N>` so the PR auto-closes it),
>    then **mark the PR ready for review** --- `gh pr ready <N>` (or
>    `mcp__github__update_pull_request` with `draft: false`). Marking it ready
>    is what kicks off review.
> 8. **ARDI to clean** --- drive the PR to a clean review verdict: read the
>    LATEST review, Address every finding / Rebut what's wrong / Defer
>    out-of-scope items to a tracked issue, push, re-request review, repeat
>    until zero findings and CI is green. Don't stop at "review-clean, needs
>    approval."
>
> Return: the issue number, the PR number + URL, how many ARDI rounds it took,
> the final status (clean / blocked / needs-input), and a one-line summary of
> what you changed. If you hit something ambiguous or architecturally
> significant, stop and report it instead of guessing.

Keep the cheap, once-per-run setup (enumerate, triage, the independence gate)
in the orchestrator — never have each subagent re-do it.

### 5. Work the dependent remainder serially (orchestrator)

After the parallel wave, run the **dependent remainder** through the normal
serial [`gii`](../gii/SKILL.md) loop — it stacks branches and handles same-file
ordering correctly. Don't try to parallelize it. GII keeps going through that
remainder without pausing for merges — a clean-but-unmerged base is stacked on,
not waited on (see [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md)).

### 6. Combined report (orchestrator)

Collect each subagent's returned row and print one summary:

```
## GIP Session Summary — <timestamp>

### Parallel wave (independent issues)
| # | Issue | PR | Rounds | Status |
|---|-------|----|--------|--------|
| 1 | [#12](url) | [#30](url) | 2 | ✅ Clean |
| 2 | [#15](url) | [#31](url) | 1 | ✅ Clean |

### Serial remainder (dependent / overlapping issues)
| # | Issue | PR | Rounds | Status |
|---|-------|----|--------|--------|
| 3 | [#18](url) | [#32](url) | 3 | ✅ Clean (stacked on #30) |
```

Link every PR (`[#N](url)`, never bare `#N`). Call out anything a worker left
blocked or flagged for input, and note any stack/merge order from the serial
remainder.

## Graceful degradation to serial

If the `Agent` tool isn't available in the session, you can't fan out — fall
back to [`gii`](../gii/SKILL.md) and work the whole in-scope set serially. The
per-issue work and the final report are the same; only the concurrency is lost.

## Orchestration

GIP already fans out --- it is the manual form of this pattern, one
worktree-isolated subagent per provably-independent issue. When the harness
supports it, prefer driving that fan-out through a **Workflow** (per
`shared/workflow/when-to-orchestrate.md`): the deterministic pipeline gives each
issue the same implement --- open-PR --- ARDI chain plus worktree isolation,
rather than ad-hoc subagents. The independence gate and the concurrency cap stay
unchanged --- only provably-independent issues run at once, and still capped (the
shared-runner limit the fragment describes). Launch directly when an opt-in
signal is present; otherwise propose with a cost estimate first.

## Relationship to other skills

- **`gii`** / **`gis`** — the **serial** counterpart and the safe fallback. GIP
  is GII with the independent subset lifted out and run concurrently; everything
  GIP can't prove independent goes back through GII. (gii : gip :: the write
  loop stays series, the safe subset fans out.)
- **`gi`** / **`grab-issue`** — the per-issue flow each subagent runs (claim →
  history → open draft PR → implement → mark ready → ARDI). GIP restates it
  inline because subagents start fresh.
- **`prefer-upstream`** --- search existing packages, standard libraries, and lab
  repos before writing custom code to avoid reinventing the wheel
- **`pr-on-claim`** --- the rule behind each subagent's step 5: open the draft PR
  up front so parallel workers see the in-flight issue before implementing.
- **`gia`** — clears the whole queue (clean open PRs, then work issues); compose
  GIP into its issue phase when that phase's issues are independent.
- **`ardi`** — each subagent ARDIs its own PR to clean.
- **`ardia`** — the whole-queue *PR* write loop; it stays **series** for the
  same runner-contention reason GIP caps its concurrency. Contrast, not overlap.
- **`pr-status-all`** — the read-only fan-out exemplar (one subagent per PR).
  GIP is the *write* fan-out: same one-subagent-per-unit shape, but it needs
  worktree isolation and an independence gate because its units mutate state.
- **`check-history`** — each subagent runs it before implementing.
- **`session-lock`** — the worktree isolation GIP gives each subagent is the
  subagent form of the isolation session-lock sets up for top-level sessions.
- **`defer-issue`** / **`split-concerns`** — used inside a subagent when its
  issue spawns sub-tasks or grows too large.

## Anti-patterns

- ❌ Fanning out issues that touch the same files — guaranteed merge conflicts.
  Run them serially (gii) instead.
- ❌ Fanning out a stacked issue whose base is another unmerged in-batch branch.
  It belongs in the serial remainder.
- ❌ Hand-rolling custom code without researching existing libraries or lab packages first (violating DRW).
- ❌ Skipping `isolation: "worktree"` — parallel subagents in one checkout
  clobber each other's edits and branches.
- ❌ Skipping the independence gate and parallelizing the whole backlog
  blindly — the failure mode `gii` exists to avoid.
- ❌ Unbounded fan-out — swamps CI runners and the review bot. Cap at ~3 and run
  in waves.
- ❌ Writing the subagent prompt as if it inherits this skill's text — it
  doesn't; restate the full per-issue procedure inline.
- ❌ Re-running the triage / independence gate inside each subagent — that's
  once-per-run orchestrator work.
