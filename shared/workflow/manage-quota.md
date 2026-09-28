# Actively manage quota usage: models, compaction, and workflow structure

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#actively-manage-quota-usage-models-compaction-and-workflow-structure) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Treat quota as something to manage continuously through a session, not only at a wrap-up or fan-out moment.
Three levers; when any applies, act on it without waiting to be asked.

**Model tier.**
For dispatched work (`Agent` calls, `Workflow` `agent()` calls), route model and effort per [`when-to-orchestrate`](when-to-orchestrate.md)'s "Route each agent's model/effort" section.
Cheap tier for mechanical, bounded work; inherit or escalate only for judgment-heavy work.
Don't default every dispatched call to the conductor's own tier out of caution.

The conductor's own tier cannot be switched from inside the conversation --- it's client-side only (`memories/preferences.md`).
So the lever there is to **recommend** a change rather than make one.
When the current tier is clearly underpowered for the task ahead, say so and suggest escalating via `/model` or `select-model`.
When a long stretch of ahead-of-time-known mechanical work doesn't need the current tier, say so and prefer delegating it instead.
That means a cheaper-tier subagent, or a separately-billed agent CLI before spending this session's own quota, rather than burning the conductor's tier on it.
Active delegation budgets include `codex` (ChatGPT plan, operationalized by
`delegate-to-codex`), `opencode` (OpenCode Go subscription and free hosted
models via Zen, operationalized by `delegate-to-opencode`), `agy` CLI
(headless dispatch available since the 2026-08-25 clarification), and
OpenRouter (prepaid credit balance for frontier/stealth previews).
Local and on-device models are prohibited because they can crash the user's
computer.
When hosted quota is unavailable, report the blocker or use
deterministic checks instead of starting a local inference runtime.
`agy` (Google Antigravity)'s **API** route was retired for dispatched work on 2026-08-20 (ai-config#1776), and a 2026-09-01 retest (`workflow_dispatch` run 33557587761) still failed, now with `request failed (code 403): Spend cap breached` rather than the original 429.
The `agy --print` CLI is a separate path and was never affected --- it is confirmed working on Windows as of 2026-09-02 via a fresh install from the official `antigravity-cli` GitHub release (user directives that day: "start using agy as a subagent where feasible", "use agy cli for it").
Route dispatchable subagent work to the `agy` CLI accordingly.
The interactive subscription/extension was never affected and was never at quota.
`memories/delegation.md` carries the rule, the usage-window semantics across `opencode`, `codex`, and `agy`, the prepaid-balance details, and the Windows install/mechanics writeup.
Ground the recommendation in `assess-model-fit`/`select-model` rather than a guess.

**Compaction.**
Already covered by two `CLAUDE.md` sections --- [the `/clear` flag](../../CLAUDE.md#flag-good-moments-to-clear-in-long-running-sessions) for a clean stopping point, and [the `compress-session` flag](../../CLAUDE.md#flag-good-moments-to-run-compress-session-too) for mid-task bloat.
Add quota/usage pressure itself as a trigger for both, distinct from context size alone.
The agent has no direct view into it, though --- the usage bar lives in the client's UI, not in the conversation (`memories/preferences.md`).
So key this off what's actually visible: the user naming or showing usage pressure, or --- inside a `Workflow` run with a stated token target --- `budget.spent()`/`budget.remaining()`.
Either is reason enough to compress or recommend a lighter model, on the same terms those sections already set out.

**Workflow structure.**
[`restructure-for-efficiency`](restructure-for-efficiency.md)

The two levers above spend less on the work **as shaped**, and their saving expires with the session.
This one changes the shape, so it pays every future session --- and it is the one that never announces itself, because following an expensive procedure correctly reads as compliance, and pulling either lever above reads as having managed quota.
So ask separately what a procedure costs *by construction*: always-loaded content only some sessions read, a judgment made twice that wants an instrument, a serial loop the base outruns, a monitoring loop polling state only a human can change, an enumerated brief that should have been a query, work at this tier a free CLI could do.
The deliverable is a change to the corpus --- fixed in stride when small, filed with its measurement when not, per `report-mistakes-proactively` --- never a quieter run of the same procedure.
That last clause covers a loop you armed yourself: once repeated firings return the same reading, delete the routine rather than lengthening its interval.
`python3 scripts/check-context-closure.py` is the built instrument for the always-loaded pool.
Its budget is advisory by design, so read an over-budget line as the prompt it is.
Two boundaries.
Efficiency never outranks correctness, so no saving is bought with a skipped check.
And the restructuring goes in its own issue or PR rather than happening inside whatever task noticed it.

Human steps are in scope too --- a merge method, a batching habit, a review-request convention each shape the procedure and each has a price.
Naming one and stopping there is `no-empty-promises` pointed outward, so every suggestion about human behaviour ships a mechanism in the same reply: a written rule at minimum, then a visible marker at the moment of the action, then a guard, then a setting that removes the option.
Pick the rung from the cost of the mistake rather than the strength of the opinion, and leave the decision with the user, per `flag-practice-slippage`.

- **Do:** ask what a procedure costs by construction, separately from what this run costs.
- **Do:** ship a mechanism in the same reply that names a human behaviour change.
- **Don't:** read a pulled lever as having answered the structural question.
- **Don't:** name a behaviour change with nothing behind it.

When several levers genuinely apply at once, do the self-directed ones first.
Compress, compact, or file the structural finding before asking the user to act on a model change.
Only the model change costs them a step.
