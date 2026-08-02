# ARDIAEI — ARDIA + Edit Instructions

Clear the open-PR review queue **and** capture what doing so taught you, by composing two existing skills in sequence:

1.  **Phase 1 — `ardia`** ([ardia](../../skills/ardia/SKILL.llms.md), ARD + Iterate-All): drive every open PR/MR to a clean review verdict, in series.
2.  **Phase 2 — `ums`** ([ums](../../skills/ums/SKILL.llms.md), Update Memories and Skills): review what the ARDIA loop surfaced — recurring review findings, CI quirks, tool gotchas, workflow gaps — and persist it by editing memory files and skill definitions.

The order matters: run the full review loop **first** so Phase 2 has the complete set of lessons (every finding, rebuttal, deferral, and CI surprise) to draw on. “Edit instructions” = update the durable guidance (memories + skills), not the PR code.

## When this fires

- “ardiaei”, “ardia then ums”, “ardia + edit instructions”
- “clean all PRs and record what we learned”
- “drive everything to clean and update the instructions/memories/skills”

## Procedure

### Phase 1 — ARDIA (drive every open PR/MR to clean)

Run the full `ardia` procedure ([ardia](../../skills/ardia/SKILL.llms.md)): list every open PR/MR and drive each to a clean verdict in series. `ardia` handles forge detection (GitHub `gh` / GitLab `glab`) and all per-PR rules from `ardi`. If there are zero open PRs/MRs, Phase 1 is a no-op — note it and go to Phase 2.

**While iterating, keep a running lessons list** — the raw material Phase 2 persists. Capture anything reusable:

- Review findings that recurred across PRs (a class worth a skill rule).
- CI / workflow quirks hit during the loop (e.g. canceled review runs).
- Tool gotchas, repo conventions, or commands that worked / didn’t.

### Phase 2 — UMS (edit instructions)

Once every PR is clean, run the full `ums` procedure ([ums](../../skills/ums/SKILL.llms.md)) against the lessons list from Phase 1: for each lesson decide whether it belongs in a **memory** file, a **skill** definition, or both, and make the edits. Don’t invent lessons to look busy — if the loop was uneventful, say so and persist nothing.

> Phase 2 edits the durable guidance (memories/skills), which in this repo is committed and pushed like any other change — follow the repo’s normal commit/PR rules for those edits (they are separate from the Phase 1 PRs).

### Final report

Print one combined summary:

    ## ARDIAEI Session Summary — <timestamp>

    ### Phase 1 — PRs driven to clean
    | PR/MR | Rounds | Status |
    |-------|--------|--------|
    | [#16](url) | 4 | ✅ Clean |

    ### Phase 2 — instructions updated
    | Target | Change |
    |--------|--------|
    | memory: review-double-trigger | New — recorded canceling-review CI quirk |
    | skill: ardi | Added rule: don't double-trigger re-review |

## Stopping conditions

- Honor ARDIA’s asymptotic-noise guard in Phase 1: if a single PR won’t converge after 3–4 rounds, surface it and move on rather than spinning.
- If Phase 1 produced no durable lessons, Phase 2 records nothing — that’s a valid outcome; don’t manufacture edits.

## Orchestration

The ARDIA phase is serial by design — shared review runners, see `ardia` — so don’t fan out the push — re-review loop; at most orchestrate the read-only review survey across PRs. The UMS phase reasons over the whole session’s learnings at once and is not decomposable, so it stays inline. Consult `shared/workflow/when-to-orchestrate.md` (the shared-runner exception).

Phase 1 can still delegate sidecar work directly via the `Agent` tool within a single PR’s own ARDI round — see `ardia`’s “Lightweight sidecar delegation” note, including its guidance on giving a judgment-heavy sidecar task a stronger model, a mechanical one a cheaper tier, and a heavy fan-out pass to `codex` when available. Phase 2 has no sidecar-delegation angle of its own, per the non-decomposable note above.

## Relationship to other skills

- **`ardia`** / `adria` — Phase 1 in full (itself nests `ardi`, `ard`).
- **`ums`** / `update-memories-and-skills` — Phase 2 in full.
- **`record-learnings`** — the passive sibling of Phase 2; `ardiaei` is the explicit “do it now, after the loop” checkpoint.
- Use **`ardia`** alone to only clear the PR queue, or **`ums`** alone to only update instructions. `ardiaei` is the clean-then-capture combination.
- **`select-model`** — decision tree for picking a subagent’s model tier when Phase 1 delegates sidecar work (see Orchestration).

Back to top
