# mwc — merge-when-confident (session-scoped merge permission)

## What this grants

Merging is normally human-gated (see `ardi.md`, `merge-it`): a PR gets driven to fully-clean and reported ready, then I wait for an explicit “merge it” per PR. `mwc` is a standing exception the user grants **once per session**: for the rest of **this** session, I may squash-merge any PR I’m driving once it reaches **fully clean** (`fully-clean.md`) and I’m confident in it — no separate “merge it” needed for each one.

## When this fires

- “merge when confident”, “mwc”
- “merge at will”, “maw” (an earlier phrasing for the same grant)
- “you can merge PRs when you’re confident (and they’re green with all-clear reviews)”, “merge PRs on your own this session”, or any similar explicit, forward-looking grant

Distinguish from `merge-it`: `merge-it` means “merge THIS PR now”; `mwc` means “stop asking me per PR, for the rest of the session.”

## Scope and limits

- **Session-scoped, not a standing preference.** Applies only to the current conversation; a fresh session (new tab, `/clear`, container restart) starts without it. Don’t write this grant into `memories/preferences.md` — the point is that the user asks for it explicitly, session by session, not that it becomes a silent default everywhere.
- **Still requires fully-clean.** Never merge a PR that isn’t fully clean (`fully-clean.md`: every CI workflow and check run is green and completed, latest review has zero outstanding findings) just because `mwc` is active — it removes the “ask first” step, not the CI-green / review-clean bar. Merging while any CI workflow or check run is still in progress, queued, or pending, or before the latest review’s verdict has actually been posted and confirmed clean, is strictly forbidden.
- **Still requires actual confidence.** If a merge call is genuinely ambiguous, CI status is unclear, or `mergeStateStatus` is blocked (see `merge-it`’s branch-protection note), stop and ask even with `mwc` active — the grant covers routine, unambiguous merges, not judgment calls. Concretely: a **required** check reporting failure is a “stop and ask” case even when you’ve independently verified the underlying content is clean (e.g. a genuine “Ready for merge” review verdict that a buggy guard script misreported as a failure, per `fully-clean.md`) — self-judging a required check’s redness as a false positive and merging past it is not covered by `mwc`, and the harness’s own permission system will (correctly) block the attempt. Report the evidence and let the human decide. (Sparta#594/#598, 2026-07-02.)
- **Doesn’t override a deadlock escalation you yourself initiated.** Per `ardi.md`’s deadlock rule, when a review finding can’t be resolved through rebuttal, the correct move is to request a specific human reviewer and stop looping — that request is a commitment to wait for THAT human’s actual decision, not a formality to clear before resuming self-service. Gathering stronger evidence afterward (a better rebuttal, an authoritative citation, even an independent bot re-confirmation) doesn’t retroactively substitute for the human’s sign-off you asked for — `mwc` still doesn’t cover merging past it until they weigh in, even once you’re personally confident the item is settled. The harness’s own permission system enforces this the same way it enforces the required-check case above. (Sparta#852, 2026-07-14: escalated a disputed review finding to a named human reviewer, then — after posting a stronger citation and getting the bot’s independent agreement — attempted to merge anyway; correctly blocked pending the human reviewer’s own response.)
- **Applies session-wide unless the user narrows it.** If the user scopes the grant to one PR or repo (“mwc for \#42 only”), honor that narrower scope instead of extending it everywhere.
- **Merge permission only.** Force-push, `--no-verify`, deleting a branch outside the normal `post-merge` tidy, and every other destructive action stay gated exactly as before — `mwc` doesn’t extend to those.
- **Revocable immediately.** An explicit “stop merging on your own” (or the session ending) revokes the grant right away.

## Procedure

1.  Acknowledge the grant in one sentence so the user knows it’s active for the session, and what it does and doesn’t cover.
2.  For the rest of the session, when a PR I’m driving (via `ardi` or otherwise) reaches fully-clean, run `merge-it`’s merge + verify + post-merge chain directly instead of stopping to report “ready, merge it?” and waiting. **The chain is not optional follow-up — it’s part of the merge action itself.** The instant the merge tool call reports success, treat `post-merge` (verify → tidy → UMS) as still in flight, the same as if the merge and the wrap-up were one atomic step. Reporting “merged!” and moving on to the next thing — including responding to other things the user said in the meantime — without having run it is the exact gap this bullet exists to close. **This is easiest to drop in a busy, multi-threaded conversation** — the user firing off several observations/questions right as the merge lands makes it natural to context-switch to answering those and let the merge’s own follow-through quietly slide. Don’t let it: finish the chain (or at least kick off UMS) before or alongside answering the other threads, not deferred until “things calm down.” A user having to explicitly say “ums first” after a merge already happened is this failure mode, not a normal request.
3.  Because the grant is a live, explicit user instruction rather than a self-authored one, it’s safe to bake a self-merge step into a `ScheduleWakeup`/`/loop` prompt while `mwc` is active for that session — this is the one case where `ardi.md`’s “never bake a self-merge directive into a wakeup prompt” caveat doesn’t apply, because the merge authorization already came from the human, not from a prior Claude turn.

## Relationship to other skills

- **`merge-it`** — the actual merge mechanics (squash, verify, chain to `post-merge`). `mwc` just removes the per-PR “merge it” trigger requirement for the rest of the session.
- **`ardi`** — drives a PR to fully-clean; `mwc` is what lets that loop merge on its own once it gets there, instead of stopping to report ready.
- **`ardia` / `gia`** — multi-PR sweeps; `mwc` lets them merge each PR as it clears, instead of accumulating a batch of “ready” reports for the user to approve one by one.

## Anti-patterns

- Merging a PR that isn’t fully clean because `mwc` is active — the bar for “clean” doesn’t move.
- Treating `mwc` as a standing preference and writing it into `preferences.md` — it’s granted per session by the user, not banked as a default.
- Assuming `mwc` survives past the session it was granted in.
- Merging through genuine ambiguity (a branch-protection block, unclear CI, a deadlocked review) just because asking first is now optional.
- Merging past your own deadlock escalation once you’ve personally gathered enough evidence to feel sure — the escalation was a commitment to the human’s decision, not a placeholder you can outrun with a stronger argument. (Sparta#852, 2026-07-14.)
- Reporting a merge as done and stopping there — via a summary, or by moving on to other conversation threads — without having run (or at least started) the post-merge → UMS chain. (Sparta `#818`, 2026-07-13: merged via `mwc`, reported a summary, then answered a stream of concurrent follow-up questions instead of chaining into UMS — the user had to explicitly ask for it.)

Back to top
