---
name: delegate-to-opencode
description: "Delegate sidecar work to OpenCode (Go subscription, Zen free, local Ollama) or OpenRouter models."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# delegate-to-opencode --- run sidecar work on OpenCode or OpenRouter models

The `opencode` CLI reaches an active OpenCode Go ($10/mo subscription), hosted free (`opencode Zen`), and local (`ollama`) tiers, plus OpenRouter as an activated provider for frontier and stealth models.
The free and local tiers cost no quota at all, so work small enough for them should not spend Claude's budget, Codex's window, or OpenRouter credits.
The local tier also keeps payloads strictly on the machine when loopback routing, local-only mode, and on-device model residency are verified.

Claude stays the orchestrator.
It writes the prompt, runs the delegate, validates what comes back, and does the synthesis.
This skill is the mechanism.
The budget preference it plugs into lives in `memories/preferences.md` ("Delegate heavy work to another CLI first").

## Why this is a shell-out and not a subagent

The `Agent` tool's `model` parameter is an enum of Claude aliases, and `.claude/agents/*.md` frontmatter takes the same aliases or `inherit`.
There is no per-agent hook for a third-party endpoint, so the only route to opencode is Bash --- the same shape [`delegate-to-codex`](../delegate-to-codex/SKILL.md) uses.

## When this fires

- "delegate to opencode", "use opencode", "run this on opencode", "run this on a local model", "use a free model", "keep this local", "dto"
- Proactively, before any **mechanical, bounded** read/extract/reformat pass --- a grep-and-summarize sweep, a bulk reformat, a first-pass triage of many files --- that would otherwise spend a metered budget.
- Whenever the work reads data that must not leave the machine, which routes to the local tier rather than the hosted one.

## When NOT to delegate

- **The task needs strong reasoning, judgment, or long-context synthesis --- unless explicitly routed to a frontier model.**
  Free models hosted via Zen and local Ollama models are small, unbenchmarked ids where a wrong answer costs more to detect than the quota saved.
  When delegating judgment-bearing work, route explicitly to OpenRouter stealth/frontier models or capable OpenCode Go tiers.
- **The critical-path edit the rest of the work waits on.**
  Do it inline, in this session, so progress does not block on a round-trip.
- **The result must conform to a schema and you have no cheap validator.**
  `opencode run` has no schema flag, so conformance is asked for in the prompt and checked on the way back rather than enforced at the boundary.
- **The destination tier is unavailable or exhausted.**
  OpenCode Go operates on windowed request limits (similar to 5-hour subscription windows); when exhausted, fall back to Codex or OpenRouter per the ladder.
  Zen free tier rate-limiting and Ollama daemon reachability are availability states rather than window exhaustion.

The first two transfer from `delegate-to-codex`, but for a reason that skill does not have.
There, work shape and model capability were independent.
Here they point the same way: authoring and judgment work is exactly what the free and local tiers are worst at.

## Hosted-free versus local: the routing rule

[`delegate-to-codex`](../delegate-to-codex/SKILL.md)'s "Data sensitivity is a second trigger" section says a repo can route work to codex because of **what the work reads**, that this trigger overrides the shape exceptions, and that when codex is busy the work waits rather than falling back.

That trigger does not transfer to opencode.
It **splits**, because opencode is more than one destination, and the destinations differ in the only property the trigger cares about.

**The split.**
`opencode/*` (hosted Zen gateway) and `opencode-go/*` (OpenCode Go subscription) are hosted destinations: the payload leaves the machine exactly as it does for any other hosted model.
Free or subscription-covered pricing is a **billing** fact and says nothing about where bytes go.
`ollama/*` is the only id on the whole ladder that *can* keep the payload on the machine --- not Claude, not Codex, not `agy`, and not `opencode/*` or `opencode-go/*`.

**Locality requires three conditions: loopback resolution, local-only mode, and local model residency.**
`ollama` is a user-authored provider entry in the opencode config, and its `options.baseURL` is an ordinary field in it.
Pointing that field at a LAN GPU box or a remote `OLLAMA_HOST` is ordinary usage rather than an edge case, and the id still reads `ollama/*` when it happens.
Furthermore, resolving `baseURL` to loopback only verifies the initial connection hop: if Ollama Cloud offloading is enabled or cloud models are targeted, payloads can be forwarded off-machine through the local daemon.
Locality is therefore licensed only when three conditions hold:
1. The endpoint check in step 1 resolves `baseURL` strictly to loopback (`127.0.0.1` or `::1`).
2. The Ollama daemon is configured in local-only mode (`OLLAMA_NO_CLOUD=1` or `disable_ollama_cloud: true`).
3. The targeted model is verified as locally resident on-device (`ollama list` confirms the model exists locally).
Run these checks before sending data-triggered work, and record the verified endpoint and residency.
Measured 2026-08-19 on this machine: `http://localhost:11434/v1`, resolving to `127.0.0.1` and `::1`.

So a data trigger routes to `ollama/*` and forbids `opencode/*` and `opencode-go/*`, where under codex the same trigger simply said "delegate".
Read a repo's approval as naming a **destination**, not as naming delegation in general: a `CLAUDE.md` rule permitting codex for restricted data says nothing about a hosted free tier nobody has cleared.

**The discriminator is the provider prefix, not the `-free` suffix.**
`opencode models` on 2026-08-19 listed `opencode/big-pickle` alongside six ids ending in `-free`, all under the same hosted provider.
The suffix answers a pricing question.
The prefix answers which tier a job goes to, which is the routing question.
It does not answer where that tier's endpoint points, which is what step 1's endpoint and residency checks settle.

**The fallback inverts differently than it does for codex.**
There, the inversion was "wait for the window instead of falling back to Claude".
Local has no window, so there is nothing to wait for, and the move that must be blocked is a **tier** fallback rather than a vendor one: re-running a slow or failed `ollama/*` job on `opencode/*` or `opencode-go/*` because the hosted tier is faster.
That retry is one flag value away and reads as ordinary troubleshooting, which is why it needs naming rather than leaving to judgment.
When the local tier cannot do a data-triggered job, fall back only to whatever the repo's own rule already permits --- which may be doing the work by hand.

As in the codex skill, do not infer a data trigger from a repo merely holding sensitive data.
It applies where the consuming repo has written the rule down, and that repo owns the path list.

- **Do:** run step 1's endpoint and local-residency check before data-triggered work, and record the endpoint it printed beside the model id so the destination is auditable afterwards.
- **Do:** send data-triggered work to an `ollama/*` id, and stop rather than re-route when the daemon is unavailable or the check refuses.
- **Don't:** retry a failed or slow local run on a hosted model.
- **Don't:** treat the `ollama/` prefix as the locality guarantee --- it names a provider entry whose endpoint is user-configurable and whose daemon can offload to cloud.
- **Don't:** read a `-free` suffix, or its absence, as evidence about where the payload goes.

## A third destination: OpenRouter, for models neither tier carries

`opencode` reaches OpenRouter as an ordinary provider, and one class of model makes that worth configuring: OpenRouter's **stealth** previews --- anonymized frontier models trialled under codenames, free while they last.
`stealth/ox-alpha` ("Ox Alpha", a reasoning model for coding and agentic work, 1,048,576-token context, pricing 0/0) was the roster's one entry on 2026-08-23.

The provider is carried by the models.dev registry opencode resolves models from --- stealth ids included --- but it stays **inactive until the config or the auth store references it**, which is why a machine with no openrouter entry lists no `openrouter/*` ids at all.
Any reference activates it: adding the entry below to the existing `provider` block of `opencode.jsonc` took this machine's `opencode models` from zero `openrouter/*` ids to 360 --- the full registry roster, including `stealth/ox-alpha` (which the registry already carried) and 359 ids the entry never named (measured 2026-08-23 on opencode 1.18.21).
An empty `"openrouter": {}` therefore activates the same roster;
a `models` entry earns its lines only by setting a display name, or by reaching an id the registry does not carry yet:

```jsonc
// merged into the existing "provider" block of opencode.jsonc --- not a standalone file
"openrouter": {
  "models": {
    "stealth/ox-alpha": { "name": "Ox Alpha (stealth, 1M context)" }
  }
}
```

The unauthenticated smoke test failed cleanly with `OpenRouter API key is missing` (same measurement).
Auth is the `OPENROUTER_API_KEY` environment variable, and the key is the user's to enter, never the agent's.
The interactive route is broken as of 1.18.21: `opencode auth login <provider>` failed with `Failed to load auth provider metadata ... fetch() URL is invalid` for every provider tried, with or without a config entry.
Measured 2026-08-23, tracked in [ai-config#2058](https://github.com/Morrison-Lab/ai-config/issues/2058) --- so have the user set the env var (`setx OPENROUTER_API_KEY <key>` on Windows) instead.
A rejected key answers `User not found`, and one measured cause (2026-08-23) is a paste that doubles the `sk-or-v1-` prefix --- the shape check that catches the paste error without exposing the value is length, 82 characters against a real key's 73 (`sk-or-v1-` is 9 characters plus 64 hex, matching OpenRouter's current key format).
The current stealth roster is one query, no key needed:

```bash
curl -s https://openrouter.ai/api/v1/models \
  | python3 -c "import json,sys; [print(m['id'], '|', m['name'], '| ctx:', m['context_length']) for m in json.load(sys.stdin)['data'] if m['id'].startswith('stealth/')]"
```

Two routing consequences:

- **The data-sensitivity rule extends to OpenRouter and Go on the split's own terms.**
  A hosted destination's payload leaves the machine, so a data trigger forbids `openrouter/*`, `opencode-go/*`, and `opencode/*` alike --- and a stealth preview is the worse case, since the lab behind it is unnamed by construction.
- **A stealth model inverts the capability caveat rather than sharing it** --- the consequence the split cannot supply.
  The hosted-free ids are unbenchmarked *small* models, so the "no judgment work" exception binds them.
  A stealth id is an unbenchmarked *frontier preview*, so it can plausibly carry judgment-bearing work the free tier cannot --- but "plausibly" is the operative word: validate its output like any other delegate's, and timestamp any claim about a specific id.
  First probe rather than a benchmark: on 2026-08-23 `stealth/ox-alpha` scored 4/4 on a known-answer crash-diagnosis task with strict-JSON output, including a byte-level UTF-8 detail (0x9d as the tail of U+201D) --- one task, so it licenses trying such work, not trusting it unvalidated.

- **Do:** activate the provider with a config entry, and route to a stealth model as `openrouter/<model-id>`.
- **Do:** re-derive the stealth roster from the API on each use --- the ids expire without notice.
- **Don't:** read an empty `openrouter/*` listing as OpenRouter being unreachable --- an unreferenced provider is inactive, and one config entry activates the whole roster.
- **Don't:** send data-triggered work to `openrouter/*`, `opencode-go/*`, or `opencode/*` --- free or subscription pricing is a billing fact, and bytes still leave the machine.

## Where opencode sits in the budget ladder

`memories/preferences.md`'s "Delegate heavy work to another CLI first" holds the order across `codex`, `opencode`, and `openrouter` (`agy` API dispatch is out of service).
Read it there rather than re-deriving it here.

OpenCode spans multiple cost structures:
- **Free hosted models via Zen (`opencode/*-free`) & local Ollama tiers**: Consume no metered window or API tokens.
  For mechanical work a small model can perform, free/local tiers go ahead of Codex and Claude on cost.
- **OpenCode Go subscription (`opencode-go/*`, $10/mo)**: Active monthly windowed tier providing access to hosted frontier models without per-token charges.
- **OpenRouter prepaid balance (`openrouter/*`)**: Billed per token.
  Used when a task specifically benefits from frontier or stealth models not carried by desktop subscription quotas.

The practical shape is a filter rather than a queue: send mechanical bounded work to OpenCode's free/local tiers first, utilize active Go subscription and Codex windows next, draw on OpenRouter for specialized frontier/stealth models or fallback, and keep Claude for high-level orchestration and synthesis.

## Procedure

### 1. Confirm opencode is available and pick a tier

```bash
opencode --version
opencode models
```

**On Windows, the OpenCode desktop app does not provide the CLI, so "installed" and "available" diverge.**
Measured 2026-08-23: `@opencode-aidesktop` was present under `AppData\Local\Programs` while `opencode` resolved in neither Git Bash nor PowerShell, and `%APPDATA%\npm` was absent from the User `Path`.
How this file's 2026-08-19 measurements ran on the same machine is unrecorded --- an install surface since removed is one explanation --- so treat CLI availability as a per-session check rather than a machine property.
The recovery is two steps, both durable: `npm install -g opencode-ai` (landed 1.18.21), then add `%APPDATA%\npm` to the User `Path` if absent.
A User `Path` edit reaches **new** shells only, so the session that made it still prefixes the directory onto its own `PATH` (or calls the binary by full path) --- retrying the bare name in the same session reproduces the exact symptom the fix just cured.

- **Do:** treat `command not found` as an install-surface gap and run the npm install, even when the desktop app is visibly present.
- **Do:** export the npm directory onto the current session's `PATH` after the User `Path` edit, before retrying.
- **Don't:** read the desktop app's presence as the CLI being installed --- they are separate artifacts with separate install routes.

`opencode models` prints ids as `provider/model`, which is the routing signal from the section above.
A malformed config fails here rather than mid-run --- see Troubleshooting.
The gemma/granite ollama entries that section describes were measured 2026-08-19 and are no longer in this machine's config, which was since rewritten around the opencode-quota plugin --- the schema constraint stands, the specific entries do not.

An `ollama/*` id appearing in that list only says the config declares it, not that the daemon is up, so smoke-test the exact id you intend to use:

```bash
opencode run -m ollama/qwen2.5-coder:3b "Reply with exactly the word: PONG"
opencode run -m opencode/deepseek-v4-flash-free "Reply with exactly the word: PONG"
opencode run -m opencode-go/deepseek-v4-pro "Reply with exactly the word: PONG"
```

Measured 2026-08-19 on opencode 1.18.15: smoke-tests returned `PONG` in 13.3s local and 7.9s hosted; Go subscription verified 2026-08-25.

Run `check-ollama-locality.py` (available in repository `scripts/` and packaged under `skills/delegate-to-opencode/scripts/`):

```bash
# In ai-config workspace:
python3 scripts/check-ollama-locality.py "qwen2.5-coder:3b"

# In consumer repository sessions (using installed skill bundle):
python3 ~/.claude/skills/delegate-to-opencode/scripts/check-ollama-locality.py "qwen2.5-coder:3b"
```

It exits 0 and prints the confirmation only when:
1. Every address `options.baseURL` resolves to is loopback (`127.0.0.1` or `::1`).
2. Local-only mode is verified (`OLLAMA_NO_CLOUD=1` in daemon environment or `disable_ollama_cloud: true` in `~/.ollama/server.json`).
3. The specified target model is strictly locally resident in `/api/tags` (refusing any remote-backed, cloud, or absent models).

Every other outcome refuses: missing target model argument, unreadable config, missing `ollama` provider or `baseURL`, off-machine endpoint, unverified local-only mode, unreachable tags API, zero resident models, remote-backed models, or an uninstalled target model.
Refusing on an unreadable config or unverified model is deliberate rather than defensive, per [`fail-fast`](../../shared/principles/fail-fast.md).
This check is what licenses the locality claim, so run it in the session that sends the data and quote its output, rather than carrying a verdict over from an earlier one.

### 2. Prepare the prompt

As of 2026-08-19, `opencode run` takes the message as positional arguments, and `-f/--file` attaches files.
Use `--dir` to point the run at a repo, and `--variant` for a provider-specific reasoning effort.
Fetch anything from the network yourself and embed it in the prompt.

**There is no schema flag.**
`opencode run --help` on 2026-08-19 offered `--format json`, which emits the raw event stream rather than a schema-constrained final message, and nothing equivalent to codex's `--output-schema`.
So ask for the structure in the prompt and validate it on return.
Expect that validation to fail sometimes, because emitting strict JSON is one of the things small models are worst at.

### 3. Run it

**Pass `--agent plan` for a text-only dispatch --- the default agent stalled on exactly the prompt shape sidecar work sends.**
`opencode run` defaults to the `build` agent, which runs with tools enabled.
Measured 2026-08-23 on 1.18.21 with `openrouter/stealth/ox-alpha`: a ~350-word diagnosis prompt (a Python traceback plus a function body, JSON-only output requested) produced zero streamed output across two default-agent runs --- one killed at a 5-minute timeout, the other left running in the background and never observed to finish --- while `--agent plan` completed the identical prompt in 36 seconds, and the default agent answered trivial and medium prompts in 13-15 seconds throughout.
A candidate explanation is the prompt's file paths inducing tool use that goes nowhere headless, but that mechanism is unconfirmed.
The measurements above are what this section asserts.
The fix applies to the background pattern below too: a job that silently stalls under the default agent stalls the same way inside a background-runner-plus-DONE-marker dispatch, so pass `--agent plan` there as well for pure-text batch items.

- **Do:** dispatch pure-text work (diagnose, summarize, extract, reformat) with `--agent plan`, including inside the background-runner pattern below.
- **Don't:** read a silent multi-minute default-agent run as model slowness --- the same model answered in seconds under the plan agent.

There is no sandbox flag either.
`opencode run --help` on 2026-08-19 listed none, and permissions come from the `permission` block in the opencode config.
`--auto` auto-approves everything not explicitly denied, and its own help calls it dangerous, so scope the config rather than reaching for that flag.
The root `opencode.json` in this repo is intentionally unscoped
(`permission: allow` for all tools, `opencode.json:23-37`)
to avoid interactive prompts for routine `gh`/`sh` pipelines.
This is the config-scoped equivalent of `--auto`
and is documented as deliberate here.
Prefer this repo-level allow over per-invocation `--auto`.

For a long or multi-item run, borrow the background-runner-plus-DONE-marker *shape* from [`delegate-to-codex`](../delegate-to-codex/SKILL.md) step 3 rather than making a foreground call that the tool timeout will kill.
Borrow the shape and not the body.
**Four things in that skill's `run_one()` do not transfer**, and the fourth fails silently rather than erroring:

- **`-o <file>`**, which opencode has no equivalent of, so there is no per-item JSON file to write.
- **`--output-schema`**, which it has no equivalent of either.
- **stdin `-`**, which is not how a prompt is passed here.
  `opencode run` took the message as positional arguments as of 2026-08-19, so a literal `-` becomes the prompt text.
- **The `bytes=0` success gate**, which reads the `-o` file that was never written.
  It therefore reports `bytes=0` for every item, misclassifying a run that fully succeeded as one that entirely failed.

Capture stdout and gate on the exit status instead, per step 4.

**`MAXPAR` is the fifth, and it half-transfers: it applies to the hosted tier and not to the local one.**
Local runs share one machine's GPU and memory, so raising parallelism against a single ollama daemon contends for the same hardware instead of fanning out.
The crossover point is unmeasured here, so treat local work as serial until somebody measures it.

### 4. Detect failure

With no `-o` capture file, key on the exit status and on empty stdout.
Then check something codex's step 4 does not have to: a small model's usual failure is a **fluent wrong answer** rather than an error, so output validation matters more here than exhaustion detection does.
Re-run only the items that actually failed.

### 5. Collect, validate, synthesize

Read the results, re-derive every count and citation, and integrate.
Claude owns this step.

## Troubleshooting

**Every invocation fails with a config error when a model declares `limit.context` without `limit.output`.**
Reported 2026-08-19 in [ai-config#1693](https://github.com/Morrison-Lab/ai-config/issues/1693): `~/.config/opencode/opencode.jsonc` had `gemma4:12b` and `granite4:7b-a1b-h` each carrying `limit.context` alone, and every `opencode` call failed until both were given an `output` value.
The schema wants the pair.

Two things make it a plausible first-run trap.
The failure is total rather than scoped to the offending model, so it looks like a broken install rather than a config typo.
And it fires on `opencode models` too, so the command you would reach for to diagnose it fails the same way.

The fix is to give every model that declares `limit.context` a `limit.output`, or to drop the `limit` block entirely --- as of 2026-08-19 the models in that file carrying no `limit` at all were unaffected.

## Relationship to other skills

- **[`delegate-to-codex`](../delegate-to-codex/SKILL.md)** --- the same shell-out shape aimed at a metered frontier CLI.
  Read its steps 2 to 5 for the background runner and DONE-marker poll rather than duplicating them here.
  What does not carry over is its data-sensitivity trigger, which splits into the routing rule above.
- **[`select-model`](../select-model/SKILL.md)** --- picks *which Claude model* runs a task.
  This skill decides whether the task runs on Claude at all.
- **[`agent-builder`](../agent-builder/SKILL.md)** --- an opencode model is a different model family from both Claude and codex, so it is a cheap cross-family second reader for that skill's "paranoid reviewer" role.
  How much its agreement is worth is governed by [`self-review-fallback`](../../shared/workflow/self-review-fallback.md)'s cross-vendor section.
- **[`ums`](../ums/SKILL.md)** --- record new opencode mechanics here as they are measured, since the model list and the version above will go stale.

## Anti-patterns

- ❌ Sending data-triggered work to an `opencode/*`, `opencode-go/*`, or `openrouter/*` model because it is free or subscription-covered --- billing facts say nothing about data leaving the machine.
- ❌ Retrying a failed or slow `ollama/*` run on the hosted tier.
- ❌ Passing `--auto` to widen a delegate's permissions instead of scoping the config (repo root `opencode.json` uses a blanket-allow config intentionally as the scoped equivalent --- see above --- prefer that over `--auto` per-run).
- ❌ Pointing a codex-style `MAXPAR` fan-out at one ollama daemon and expecting hosted-style throughput.
- ❌ Quoting a count, a line number, or a citation a free model returned without re-deriving it.
- ❌ Skipping OpenCode free/local tiers for small mechanical work because Codex is stronger --- Codex has a window to conserve while OpenCode Zen and Ollama consume no quota.
- ❌ Handing a free or local model the authoring or judgment task that needed Claude's own context.
