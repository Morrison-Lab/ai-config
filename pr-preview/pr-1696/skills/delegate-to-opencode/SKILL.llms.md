# delegate-to-opencode — run sidecar work on a free or local model

The `opencode` CLI reaches two model tiers this corpus has no other route to: a hosted free tier (opencode Zen) and a fully local one (ollama). Both cost no quota at all, so work small enough for them should not spend Claude’s budget, codex’s window, or agy’s. The local tier also does something none of the other destinations can: it keeps the payload on the machine.

Claude stays the orchestrator. It writes the prompt, runs the delegate, validates what comes back, and does the synthesis. This skill is the mechanism; the budget preference it plugs into lives in `memories/preferences.md` (“Delegate heavy work to a separately-billed CLI first”).

## Why this is a shell-out and not a subagent

The `Agent` tool’s `model` parameter is an enum of Claude aliases, and `.claude/agents/*.md` frontmatter takes the same aliases or `inherit`. There is no per-agent hook for a third-party endpoint, so the only route to opencode is Bash — the same shape [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) uses.

## When this fires

- “delegate to opencode”, “use opencode”, “run this on opencode”, “run this on a local model”, “use a free model”, “keep this local”, “dto”
- Proactively, before any **mechanical, bounded** read/extract/reformat pass — a grep-and-summarize sweep, a bulk reformat, a first-pass triage of many files — that would otherwise spend a metered budget.
- Whenever the work reads data that must not leave the machine, which routes to the local tier specifically (see the next section).

## When NOT to delegate

- **The task needs strong reasoning, judgment, or long-context synthesis.** This is the exception with no codex analogue, so check it first. A wrong answer from a small model costs more to detect than the quota it saved.
- **The critical-path edit the rest of the work waits on.** Keep it local so progress does not block on a round-trip.
- **The result must conform to a schema and you have no cheap validator.** `opencode run` has no schema flag (see step 2), so conformance is asked for in the prompt and checked on the way back rather than enforced at the boundary.
- **The hosted tier is rate-limited, or the ollama daemon is down.** Neither is a window running out, because neither tier has a window. This is availability, not budget, and what it licenses depends on the routing rule below.

The first two transfer from `delegate-to-codex`, but for a reason that skill does not have. There, work shape and model capability were independent. Here they point the same way: authoring and judgment work is exactly what the free and local tiers are worst at.

## Hosted-free versus local: the routing rule

[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md)’s “Data sensitivity is a second trigger” section says a repo can route work to codex because of **what the work reads**, that this trigger overrides the shape exceptions, and that when codex is busy the work waits rather than falling back.

That trigger does not transfer to opencode. It **splits**, because opencode is two destinations rather than one, and the two differ in the only property the trigger cares about.

**The split.** `ollama/*` runs against the base URL the config declares for the ollama provider, `http://localhost:11434/v1` as of 2026-08-19. The payload does not leave the machine. No other destination on the ladder — not Claude, not codex, not agy, not opencode Zen — has that property. `opencode/*` is opencode Zen, a hosted gateway: the payload leaves the machine exactly as it does for any other hosted model. Free is a **billing** fact and says nothing about where bytes go.

So a data trigger routes to `ollama/*` and forbids `opencode/*`, where under codex the same trigger simply said “delegate”. Read a repo’s approval as naming a **destination**, not as naming delegation in general: a `CLAUDE.md` rule permitting codex for restricted data says nothing about a hosted free tier nobody has cleared.

**The discriminator is the provider prefix, not the `-free` suffix.** `opencode models` on 2026-08-19 listed `opencode/big-pickle` alongside six ids ending in `-free`, all under the same hosted provider. The suffix answers a pricing question. The prefix answers the routing one.

**The fallback inverts differently than it does for codex.** There, the inversion was “wait for the window instead of falling back to Claude”. Local has no window, so there is nothing to wait for, and the move that must be blocked is a **tier** fallback rather than a vendor one: re-running a slow or failed `ollama/*` job on `opencode/*` because the hosted tier is faster. That retry is one flag value away and reads as ordinary troubleshooting, which is why it needs naming rather than leaving to judgment. When the local tier cannot do a data-triggered job, fall back only to whatever the repo’s own rule already permits — which may be doing the work by hand.

As in the codex skill, do not infer a data trigger from a repo merely holding sensitive data. It applies where the consuming repo has written the rule down, and that repo owns the path list.

- **Do:** pick the destination by provider prefix, and name the exact model id in the report so the destination is auditable afterwards.
- **Do:** send data-triggered work to an `ollama/*` id, and stop rather than re-route when the daemon is unavailable.
- **Don’t:** retry a failed or slow local run on a hosted model.
- **Don’t:** read a `-free` suffix, or its absence, as evidence about where the payload goes.

## Where opencode sits in the budget ladder

`memories/preferences.md`’s “Delegate heavy work to a separately-billed CLI first” holds the order across `codex`, `agy`, and `opencode`. Read it there rather than re-deriving it here.

Two things follow from opencode not being a metered plan at all, and they are what make its position unlike the other two:

- **It consumes no window, so there is no budget to conserve by skipping it.** For work a small model can do, it goes ahead of codex and agy rather than behind them.
- **Capability is the binding constraint instead, and it is unmeasured here.** The local ids carry their parameter counts (2B to 30B as of 2026-08-19); the hosted ids are preview names this corpus has not benchmarked. So every figure one returns gets re-derived, per the same treatment `preferences.md` records for `agy` after it read a file correctly and miscounted its lines.

The practical shape is a filter rather than a queue: send what opencode can do to opencode, send what it cannot to codex or agy, and keep Claude for orchestration and the residue.

## Procedure

### 1. Confirm opencode is available and pick a tier

``` bash
opencode --version
opencode models
```

`opencode models` prints ids as `provider/model`, which is the routing signal from the section above. A malformed config fails here rather than mid-run — see Troubleshooting.

An `ollama/*` id appearing in that list only says the config declares it, not that the daemon is up, so smoke-test the exact id you intend to use:

``` bash
opencode run -m ollama/qwen2.5-coder:3b "Reply with exactly the word: PONG"
opencode run -m opencode/deepseek-v4-flash-free "Reply with exactly the word: PONG"
```

Measured 2026-08-19 on opencode 1.18.15: both returned `PONG`, in 13.3s local and 7.9s hosted.

### 2. Prepare the prompt

`opencode run` takes the message as positional arguments, and `-f/--file` attaches files. Use `--dir` to point the run at a repo, and `--variant` for a provider-specific reasoning effort. Fetch anything from the network yourself and embed it in the prompt.

**There is no schema flag.** `opencode run --help` on 2026-08-19 offered `--format json`, which emits the raw event stream rather than a schema-constrained final message, and nothing equivalent to codex’s `--output-schema`. So ask for the structure in the prompt and validate it on return. Expect that validation to fail sometimes, because emitting strict JSON is one of the things small models are worst at.

### 3. Run it

There is no sandbox flag either. `opencode run --help` lists none, and permissions come from the `permission` block in the opencode config. `--auto` auto-approves everything not explicitly denied, and its own help calls it dangerous, so scope the config rather than reaching for that flag.

For a long or multi-item run, use the background-runner-plus-DONE-marker pattern in [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) step 3 rather than a foreground call that the tool timeout will kill. One thing there does not transfer: **that runner’s `MAXPAR` fan-out applies to the hosted tier and not to the local one.** Local runs share one machine’s GPU and memory, so raising parallelism against a single ollama daemon contends for the same hardware instead of fanning out. The crossover point is unmeasured here, so treat local work as serial until somebody measures it.

### 4. Detect failure

With no `-o` capture file, key on the exit status and on empty stdout. Then check something codex’s step 4 does not have to: a small model’s usual failure is a **fluent wrong answer** rather than an error, so output validation matters more here than exhaustion detection does. Re-run only the items that actually failed.

### 5. Collect, validate, synthesize

Read the results, re-derive every count and citation, and integrate. Claude owns this step.

## Troubleshooting

**Every invocation fails with a config error when a model declares `limit.context` without `limit.output`.** Reported 2026-08-19 in [ai-config#1693](https://github.com/Morrison-Lab/ai-config/issues/1693): `~/.config/opencode/opencode.jsonc` had `gemma4:12b` and `granite4:7b-a1b-h` each carrying `limit.context` alone, and every `opencode` call failed until both were given an `output` value. The schema wants the pair.

Two things make it a plausible first-run trap. The failure is total rather than scoped to the offending model, so it looks like a broken install rather than a config typo. And it fires on `opencode models` too, so the command you would reach for to diagnose it fails the same way.

The fix is to give every model that declares `limit.context` a `limit.output`, or to drop the `limit` block entirely — as of 2026-08-19 the models in that file carrying no `limit` at all were unaffected.

## Relationship to other skills

- **[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md)** — the same shell-out shape aimed at a metered frontier CLI. Read its steps 2 to 5 for the background runner and DONE-marker poll rather than duplicating them here. What does not carry over is its data-sensitivity trigger, which splits into the routing rule above.
- **[`select-model`](../../skills/select-model/SKILL.llms.md)** — picks *which Claude model* runs a task; this skill decides whether the task runs on Claude at all.
- **[`agent-builder`](../../skills/agent-builder/SKILL.llms.md)** — an opencode model is a different model family from both Claude and codex, so it is a cheap cross-family second reader for that skill’s “paranoid reviewer” role. How much its agreement is worth is governed by [`self-review-fallback`](../../shared/workflow/self-review-fallback.md)’s cross-vendor section.
- **[`ums`](../../skills/ums/SKILL.llms.md)** — record new opencode mechanics here as they are measured, since the model list and the version above will go stale.

## Anti-patterns

- ❌ Sending data-triggered work to an `opencode/*` model because it is free — free is a billing property, and the payload still leaves the machine.
- ❌ Retrying a failed or slow `ollama/*` run on the hosted tier.
- ❌ Passing `--auto` to widen a delegate’s permissions instead of scoping the config.
- ❌ Pointing a codex-style `MAXPAR` fan-out at one ollama daemon and expecting hosted-style throughput.
- ❌ Quoting a count, a line number, or a citation a free model returned without re-deriving it.
- ❌ Skipping opencode for small mechanical work because codex is stronger — codex has a window to conserve and opencode does not.
- ❌ Handing a free or local model the authoring or judgment task that needed Claude’s own context.

Back to top
