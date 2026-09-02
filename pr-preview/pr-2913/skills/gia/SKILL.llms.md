# GIA — Grab Issues + iterate-All

Clear the repo’s **entire** work queue end to end by composing two existing skills in sequence:

1.  **Phase 1 — [`ardia`](../../skills/ardia/SKILL.llms.md)** (ARD + Iterate-All): drive every *already-open* PR/MR to a clean review verdict.
2.  **Phase 2 — [`gii`](../../skills/gii/SKILL.llms.md)** (Grab Issues Iteratively): work through every open issue — grab, implement, open an MR/PR, ARDI it to clean, recurse.

PRs-first, then issues: clearing the existing review backlog first means new issue work lands on top of an already-clean queue (and may even unblock or close issues that the open PRs address).

**The sweep runs to the end of the queue without pausing for merges.** Merging is human-gated — you don’t self-merge — but that gates only the merge, not the run. A PR reaching clean-but-unmerged is not a stopping point in either phase; move to the next item, and when that item isn’t naturally independent of a completed-but-unmerged PR, **stack** it on that PR’s branch instead of waiting for a merge. See [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md).

## When this fires

- “gia”, “ardia+gii”, “adria+gii”, “gii+ardia”, “gii+adria”
- “clear the whole queue”, “clean all PRs then do all the issues”
- “burn down everything”, “tidy the repo end to end”, “empty the backlog”

## Procedure

### 0. Establish context

Detect the forge (GitHub `gh` / GitLab `glab`) from `git remote get-url origin`. Note the default branch (`main` / `master`).

**Confirm which repo first when several are in reach.** GIA (like `ardia` and `gii`) clears *one* repo’s queue, but a session may start in a directory holding several repos (e.g. a web session scoped to multiple repos). If the working dir isn’t itself a single repo, or more than one repo is in scope, ask which repo’s queue to clear before surveying — don’t assume the first one found.

**Confirm whose PRs are in scope, too.** Both phases act only on PRs the invoking user opened, is assigned to, or explicitly requested by name, plus PRs the GitHub Actions app authored (`github-actions[bot]`); `ardia`’s step 1 resolves that user, applies the filter, and reports what it dropped. An out-of-scope PR (one that fails that filter: another lab member’s, or any other bot’s) stays theirs, and an issue such a PR already fixes is left to it rather than grabbed.

### Phase 1 — ARDIA (existing open PRs/MRs)

Run the full [`ardia`](../../skills/ardia/SKILL.llms.md) procedure: list every open PR/MR and drive each to a clean verdict in series (claim → ARD every finding → push → post summary → re-request review → repeat until clean). Per-PR rules from `ardi` apply (sync main first, re-request even on Rebut/Defer-only rounds).

If there are **zero open PRs/MRs**, Phase 1 is a no-op — note “no open PRs” in the report’s Phase 1 section and go straight to Phase 2.

Carry forward an interim table:

| PR/MR       | Rounds | Final status |
|-------------|--------|--------------|
| [\#25](url) | 3      | ✅ Clean     |

> **Why before issues:** a PR that’s already open may close an issue on merge (`Closes #N`). Finishing PRs first avoids grabbing an issue that a pending PR already resolves.

### Phase 2 — GII (open issues)

Once every pre-existing PR/MR is clean, run the full [`gii`](../../skills/gii/SKILL.llms.md) loop: grab the highest-priority open issue → check history → implement → open MR/PR → ARDI to clean → recurse. Stack MRs when a later issue depends on an earlier unmerged branch. Respect GII’s stopping conditions (backlog empty, user stop, or the default 5-issue wave boundary — wrap up the open wave of PRs, then **check in before starting the next wave** rather than continuing on your own; see “Stopping conditions” below).

> Each PR that GII opens in this phase is itself ARDI’d to clean, so it does **not** need a second pass through Phase 1.

### Final report

Print one combined summary covering both phases:

    ## GIA Session Summary — <timestamp>

    ### Phase 1 — existing PRs/MRs driven to clean
    | PR/MR | Rounds | Status |
    |-------|--------|--------|
    | [#16](url) | 3 | ✅ Clean |

    ### Phase 2 — issues grabbed & shipped
    | # | Issue | MR/PR | Rounds | Status |
    |---|-------|-------|--------|--------|
    | 1 | [#12](url) | [#30](url) | 2 | ✅ Clean |

    ### Merge order
    1. [#16](url)
    2. [#30](url) — fix: … (stacked on #16 if applicable)

List the merge order across **both** phases — Phase 1 PRs can be stacked on each other just as Phase 2 issue-PRs can, so a dependency may run PR → PR, PR → issue-PR, or issue-PR → issue-PR. Order so every base merges before whatever stacks on it.

## Stopping conditions

- If the trigger was ambiguous about whether to also burn down issues (e.g. a bare “clean up the PRs”), stop after Phase 1 and check in before starting Phase 2.
- Honor GII’s 5-issue wave boundary in Phase 2: wrap up the open wave of PRs (every PR from that wave merged, closed, or explicitly escalated), then **stop and ask** whether to continue into the next wave or archive the session, giving a recommendation either way – don’t continue on your own judgment. A wave is “completely finished” only once every item in it has reached a terminal state; a PR still in CI/review is not a finished wave, and the check-in loop that drives it to green continues uninterrupted. This is a deliberate exception to the standing “don’t stop to ask” grant the rest of this skill runs under: the wave boundary is the one place GIA hands the decision back, because a fresh wave is new, open-ended commitment (5 more issues, 5 more PRs, 5 more review rounds) rather than work already implied by the current wave. A UMS pass, and the PR it opens, is work the current wave implies rather than a new wave — run it at the boundary, per [`gii`](../../skills/gii/SKILL.llms.md)’s “A UMS pass is not a new wave” paragraph.
- If a PR or issue is blocked or ambiguous, **bypass** it — surface it and move on to the next item rather than halting the sweep. Stop only when every remaining item depends on that blocked one, so no independent work is left (see [`stack-dont-pause`](../../shared/workflow/stack-dont-pause.md)).
- If Phase 1’s reviewer and you deadlock on a specific item — argued back and forth with no understanding reached — escalate that item to a human and keep driving the rest. A run of rounds is not itself a reason to stop or to ask: see [`ardi`](../../skills/ardi/SKILL.llms.md)’s “Stopping conditions”.

## Orchestration

Both GIA phases push commits that trigger shared review runners, so neither fans out freely — the same constraint that makes `ardia` serial and caps `gip`. You may orchestrate the parts that touch no shared forge state (survey all open PRs’ reviews, prepare uncommitted patches per [`ardia`](../../skills/ardia/SKILL.llms.md)’s step 2, or triage the issue backlog) in parallel, but route the actual implement — push — review work through the serial or capped paths: `ardia` for the PR phase, `gip` for provably-independent issues. Consult `shared/workflow/when-to-orchestrate.md` (the shared-runner exception).

Within either phase, a single PR’s own round can still delegate lightweight sidecar work via the `Agent` tool — see `ardia`’s “Lightweight sidecar delegation” note (Phase 1) and `gii`’s “Delegate sidecar work when helpful” note (Phase 2), including their guidance on picking a stronger, cheaper, or `codex`-backed subagent per [`select-model`](../../skills/select-model/SKILL.llms.md) and [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md).

## Relationship to other skills

- **`ardia`** / `adria` — Phase 1 in full.
- **`gii`** / `gis` — Phase 2 in full (which itself nests `gi`, `ardi`, `check-history`, `sync-pr-branch`, `defer-issue`).
- Use **`ardia`** alone to only clear the PR queue, or **`gii`** alone to only work the issue backlog. `gia` is the both-in-one sweep.
- **`gip`** — when Phase 2’s issues are provably independent (no stacking dependency, no file overlap), run that phase with `gip` to work them concurrently instead of serially.

## Anti-patterns

- ❌ Interleaving the two phases — finish all open PRs before grabbing issues.
- ❌ Re-running Phase 1 on PRs that Phase 2 just opened (GII already ARDI’d them).
- ❌ Running Phase 2 unbounded — keep GII’s wave boundary.
- ❌ Starting the next wave on your own once the current one is fully finished — stop and ask, with a recommendation, per “Stopping conditions”.
- ❌ Grabbing an issue a pending Phase-1 PR already closes.
- ❌ Driving, reviewing, or editing a PR the user neither opened, is assigned to, nor explicitly requested by name, unless the Actions app authored it — “every open PR” means every one of the user’s.

Back to top
