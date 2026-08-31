# delegate-to-opencode — run sidecar work on OpenCode or OpenRouter models

The `opencode` CLI reaches an active OpenCode Go (\$10/mo subscription), hosted free (`opencode Zen`), and OpenRouter tiers. Use only hosted providers. Never invoke an `ollama/*` model or another local inference runtime because local inference can crash the user’s computer.

Claude stays the orchestrator. It writes the prompt, runs the delegate, validates what comes back, and does the synthesis. This skill is the mechanism. The budget preference it plugs into lives in `memories/delegation.md`.

## Why this is a shell-out and not a subagent

The `Agent` tool’s `model` parameter is an enum of Claude aliases, and `.claude/agents/*.md` frontmatter takes the same aliases or `inherit`. There is no per-agent hook for a third-party endpoint, so the only route to opencode is Bash — the same shape [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) uses.

## When this fires

- “delegate to opencode”, “use opencode”, “run this on opencode”, “use a free model”, “dto”
- Proactively, before any **mechanical, bounded** read/extract/reformat pass — a grep-and-summarize sweep, a bulk reformat, a first-pass triage of many files — that would otherwise spend a metered budget.
- Do not use this skill when data must not leave the machine. Keep that work in the authoring session and use deterministic tools instead of model delegation.

## When NOT to delegate

- **The task needs strong reasoning, judgment, or long-context synthesis — unless explicitly routed to a frontier model.** Free models hosted via Zen are small, unbenchmarked ids where a wrong answer costs more to detect than the quota saved. When delegating judgment-bearing work, route explicitly to OpenRouter stealth/frontier models or capable OpenCode Go tiers.
- **The critical-path edit the rest of the work waits on.** Do it inline, in this session, so progress does not block on a round-trip.
- **The result must conform to a schema and you have no cheap validator.** `opencode run` has no schema flag, so conformance is asked for in the prompt and checked on the way back rather than enforced at the boundary.
- **The destination tier is unavailable or exhausted.** OpenCode Go operates on windowed **dollar** caps rather than request counts: \$12 per 5 hours, \$30 per week, \$60 per month (vendor docs, <https://opencode.ai/docs/go>, fetched 2026-08-25). When exhausted, fall back to Codex or OpenRouter per the ladder. Zen free tier rate-limiting is an availability state rather than window exhaustion.

The first two transfer from `delegate-to-codex`, but for a reason that skill does not have. There, work shape and model capability were independent. Here they point the same way: authoring and judgment work is exactly what the free tier is worst at.

## Hosted-only routing rule

[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md)’s “Data sensitivity is a second trigger” section says a repo can route work to codex because of **what the work reads**, that this trigger overrides the shape exceptions, and that when codex is busy the work waits rather than falling back.

`opencode/*` (hosted Zen gateway) and `opencode-go/*` (OpenCode Go subscription) are hosted destinations. The payload leaves the machine exactly as it does for any other hosted model. Free or subscription-covered pricing is a **billing** fact and says nothing about where bytes go. OpenRouter is hosted too. A data trigger therefore forbids all OpenCode and OpenRouter model dispatch unless the consuming repository explicitly approves that hosted destination.

**The discriminator is the provider prefix, not the `-free` suffix.** `opencode models` on 2026-08-19 listed `opencode/big-pickle` alongside six ids ending in `-free`, all under the same hosted provider. The suffix answers a pricing question. The prefix answers which hosted tier a job goes to, which is the routing question.

As in the codex skill, do not infer a data trigger from a repo merely holding sensitive data. It applies where the consuming repo has written the rule down, and that repo owns the path list.

- **Do:** keep data-triggered work in the authoring session and use deterministic tools when no hosted destination is approved.
- **Don’t:** start or invoke Ollama, LM Studio, llama.cpp, or another local model.
- **Don’t:** read a `-free` suffix, or its absence, as evidence about where the payload goes.

## A third destination: OpenRouter, for models neither tier carries

`opencode` reaches OpenRouter as an ordinary provider, and one class of model makes that worth configuring: OpenRouter’s **stealth** previews — anonymized frontier models trialled under codenames, free while they last. `stealth/ox-alpha` (“Ox Alpha”, a reasoning model for coding and agentic work, 1,048,576-token context, pricing 0/0) was the roster’s one entry on 2026-08-23.

The provider is carried by the models.dev registry opencode resolves models from — stealth ids included — but it stays **inactive until the config or the auth store references it**, which is why a machine with no openrouter entry lists no `openrouter/*` ids at all. Any reference activates it: adding the entry below to the existing `provider` block of `opencode.jsonc` took this machine’s `opencode models` from zero `openrouter/*` ids to 360 — the full registry roster, including `stealth/ox-alpha` (which the registry already carried) and 359 ids the entry never named (measured 2026-08-23 on opencode 1.18.21). An empty `"openrouter": {}` therefore activates the same roster; a `models` entry earns its lines only by setting a display name, or by reaching an id the registry does not carry yet:

``` jsonc
// merged into the existing "provider" block of opencode.jsonc --- ensure commas separate provider entries and top-level properties
"provider": {
  "openrouter": {
    "models": {
      "stealth/ox-alpha": { "name": "Ox Alpha (stealth, 1M context)" }
    }
  }
}
```

The unauthenticated smoke test failed cleanly with `OpenRouter API key is missing` (same measurement). Auth is the `OPENROUTER_API_KEY` environment variable, and the key is the user’s to enter, never the agent’s. The interactive route is broken as of 1.18.21: `opencode auth login <provider>` failed with `Failed to load auth provider metadata ... fetch() URL is invalid` for every provider tried, with or without a config entry. Measured 2026-08-23, tracked in [ai-config#2058](https://github.com/Morrison-Lab/ai-config/issues/2058) — so have the user set the env var (`setx OPENROUTER_API_KEY <key>` on Windows) instead. A rejected key answers `User not found`, and one measured cause (2026-08-23) is a paste that doubles the `sk-or-v1-` prefix — the shape check that catches the paste error without exposing the value is length, 82 characters against a real key’s 73 (`sk-or-v1-` is 9 characters plus 64 hex, matching OpenRouter’s current key format). The current stealth roster is one query, no key needed:

``` bash
curl -s https://openrouter.ai/api/v1/models \
  | python3 -c "import json,sys; [print(m['id'], '|', m['name'], '| ctx:', m['context_length']) for m in json.load(sys.stdin)['data'] if m['id'].startswith('stealth/')]"
```

Two routing consequences:

- **The data-sensitivity rule extends to OpenRouter and Go on the split’s own terms.** A hosted destination’s payload leaves the machine, so a data trigger forbids `openrouter/*`, `opencode-go/*`, and `opencode/*` alike — and a stealth preview is the worse case, since the lab behind it is unnamed by construction.

- **A stealth model inverts the capability caveat rather than sharing it** — the consequence the split cannot supply. The hosted-free ids are unbenchmarked *small* models, so the “no judgment work” exception binds them. A stealth id is an unbenchmarked *frontier preview*, so it can plausibly carry judgment-bearing work the free tier cannot — but “plausibly” is the operative word: validate its output like any other delegate’s, and timestamp any claim about a specific id. First probe rather than a benchmark: on 2026-08-23 `stealth/ox-alpha` scored 4/4 on a known-answer crash-diagnosis task with strict-JSON output, including a byte-level UTF-8 detail (0x9d as the tail of U+201D) — one task, so it licenses trying such work, not trusting it unvalidated.

- **Do:** activate the provider with a config entry, and route to a stealth model as `openrouter/<model-id>`.

- **Do:** re-derive the stealth roster from the API on each use — the ids expire without notice.

- **Don’t:** read an empty `openrouter/*` listing as OpenRouter being unreachable — an unreferenced provider is inactive, and one config entry activates the whole roster.

- **Don’t:** send data-triggered work to `openrouter/*`, `opencode-go/*`, or `opencode/*` — free or subscription pricing is a billing fact, and bytes still leave the machine.

## Where opencode sits in the budget ladder

`memories/delegation.md`’s “Delegate heavy work to another CLI first” section holds the order across `codex`, `agy`, `opencode`, and `openrouter` — including where OpenCode’s hosted cost tiers (free Zen, the `opencode-go/*` subscription, and OpenRouter’s prepaid balance) sit relative to `codex` and `agy`’s usage windows. Read it there rather than re-deriving it here.

## Procedure

### 1. Confirm opencode is available and pick a tier

``` bash
opencode --version
opencode models
```

**On Windows, the OpenCode desktop app does not provide the CLI, so “installed” and “available” diverge.** Measured 2026-08-23: `@opencode-aidesktop` was present under `AppData\Local\Programs` while `opencode` resolved in neither Git Bash nor PowerShell, and `%APPDATA%\npm` was absent from the User `Path`. How this file’s 2026-08-19 measurements ran on the same machine is unrecorded — an install surface since removed is one explanation — so treat CLI availability as a per-session check rather than a machine property. The recovery is two steps, both durable: `npm install -g opencode-ai` (landed 1.18.21), then add `%APPDATA%\npm` to the User `Path` if absent. A User `Path` edit reaches **new** shells only, so the session that made it still prefixes the directory onto its own `PATH` (or calls the binary by full path) — retrying the bare name in the same session reproduces the exact symptom the fix just cured.

- **Do:** treat `command not found` as an install-surface gap and run the npm install, even when the desktop app is visibly present.
- **Do:** export the npm directory onto the current session’s `PATH` after the User `Path` edit, before retrying.
- **Don’t:** read the desktop app’s presence as the CLI being installed — they are separate artifacts with separate install routes.

`opencode models` prints ids as `provider/model`, which is the routing signal from the section above. A malformed config fails here rather than mid-run — see Troubleshooting. Smoke-test the exact hosted tier you intend to use:

``` bash
opencode run -m opencode/deepseek-v4-flash-free "Reply with exactly the word: PONG"
opencode run -m opencode-go/deepseek-v4-pro "Reply with exactly the word: PONG"
```

Measured 2026-08-19 on opencode 1.18.15, the hosted-free smoke test returned `PONG` in 7.9s. The OpenCode Go **subscription’s activation** was verified 2026-08-25; that check confirmed the subscription is active, not that the smoke test above ran — the `opencode-go/*` line is the recipe for that test, and its output was not observed in this session.

### 2. Prepare the prompt

As of 2026-08-19, `opencode run` takes the message as positional arguments, and `-f/--file` attaches files. Use `--dir` to point the run at a repo, and `--variant` for a provider-specific reasoning effort. Fetch anything from the network yourself and embed it in the prompt.

**There is no schema flag.** `opencode run --help` on 2026-08-19 offered `--format json`, which emits the raw event stream rather than a schema-constrained final message, and nothing equivalent to codex’s `--output-schema`. So ask for the structure in the prompt and validate it on return. Expect that validation to fail sometimes, because emitting strict JSON is one of the things small models are worst at.

**Name every target file’s literal path — do not hand the delegate a glob and expect it to resolve one.** Measured 2026-08-28 on opencode CLI 1.18.15 (macOS), during a Morrison-Lab/gha#682 delegated multi-file R refactor: under `opencode/nemotron-3-ultra-free`, the agent’s Glob tool returned zero matches for globs anchored under dot-prefixed directories — `**/test-description-version.R` and `.github/workflows/scripts/tests/*.R` both came back empty even though the files existed. The model recovered only because the brief also carried the literal file paths, which it then reached via `find` and a direct `Read` instead. A brief that described the file set only by pattern, with no literal fallback, would have had nothing to recover with.

- **Do:** enumerate every file the delegate must read or edit as a literal path in the brief, especially anything under `.github/` or another dot-prefixed directory.
- **Do:** treat a zero-match Glob under a dotted path as an expected gap on this model rather than a bug to debug mid-dispatch.
- **Don’t:** describe a target file set to an opencode delegate by glob pattern alone and assume it will resolve — a real, existing file under `.github/workflows/scripts/tests/` returned no matches on this model.

### 3. Run it

**Pass `--agent plan` for a text-only dispatch — the default agent stalled on exactly the prompt shape sidecar work sends.** `opencode run` defaults to the `build` agent, which runs with tools enabled. Measured 2026-08-23 on 1.18.21 with `openrouter/stealth/ox-alpha`: a ~350-word diagnosis prompt (a Python traceback plus a function body, JSON-only output requested) produced zero streamed output across two default-agent runs — one killed at a 5-minute timeout, the other left running in the background and never observed to finish — while `--agent plan` completed the identical prompt in 36 seconds, and the default agent answered trivial and medium prompts in 13-15 seconds throughout. A candidate explanation is the prompt’s file paths inducing tool use that goes nowhere headless, but that mechanism is unconfirmed. The measurements above are what this section asserts. The fix applies to the background pattern below too: a job that silently stalls under the default agent stalls the same way inside a background-runner-plus-DONE-marker dispatch, so pass `--agent plan` there as well for pure-text batch items.

- **Do:** dispatch pure-text work (diagnose, summarize, extract, reformat) with `--agent plan`, including inside the background-runner pattern below.
- **Don’t:** read a silent multi-minute default-agent run as model slowness — the same model answered in seconds under the plan agent.

There is no sandbox flag either. `opencode run --help` on 2026-08-19 listed none, and permissions come from the `permission` block in the opencode config. `--auto` auto-approves everything not explicitly denied, and its own help calls it dangerous, so scope the config rather than reaching for that flag. The root `opencode.json` in this repo is intentionally unscoped (`permission: allow` for all tools, `opencode.json:23-37`) to avoid interactive prompts for routine `gh`/`sh` pipelines. This is the config-scoped equivalent of `--auto` and is documented as deliberate here. Prefer this repo-level allow over per-invocation `--auto`.

For a long or multi-item run, borrow the background-runner-plus-DONE-marker *shape* from [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md) step 3 rather than making a foreground call that the tool timeout will kill. Borrow the shape and not the body. **Four things in that skill’s `run_one()` do not transfer**, and the fourth fails silently rather than erroring:

- **`-o <file>`**, which opencode has no equivalent of, so there is no per-item JSON file to write.
- **`--output-schema`**, which it has no equivalent of either.
- **stdin `-`**, which is not how a prompt is passed here. `opencode run` took the message as positional arguments as of 2026-08-19, so a literal `-` becomes the prompt text.
- **The `bytes=0` success gate**, which reads the `-o` file that was never written. It therefore reports `bytes=0` for every item, misclassifying a run that fully succeeded as one that entirely failed.

Capture stdout and gate on the exit status instead, per step 4.

**`MAXPAR` is the fifth, and it needs a provider-aware bound.** Hosted providers enforce their own rate and concurrency limits. Start with the provider’s documented limit and reduce parallelism when responses report throttling.

### 4. Detect failure

With no `-o` capture file, key on the exit status and on empty stdout. Then check something codex’s step 4 does not have to: a small model’s usual failure is a **fluent wrong answer** rather than an error, so output validation matters more here than exhaustion detection does. Re-run only the items that actually failed.

### 5. Collect, validate, synthesize

Read the results, re-derive every count and citation, and integrate. Claude owns this step.

## Troubleshooting

**Every invocation fails with a config error when a model declares `limit.context` without `limit.output`.** Reported 2026-08-19 in [ai-config#1693](https://github.com/Morrison-Lab/ai-config/issues/1693): `~/.config/opencode/opencode.jsonc` had `gemma4:12b` and `granite4:7b-a1b-h` each carrying `limit.context` alone, and every `opencode` call failed until both were given an `output` value. The schema wants the pair.

Two things make it a plausible first-run trap. The failure is total rather than scoped to the offending model, so it looks like a broken install rather than a config typo. And it fires on `opencode models` too, so the command you would reach for to diagnose it fails the same way.

The fix is to give every model that declares `limit.context` a `limit.output`, or to drop the `limit` block entirely — as of 2026-08-19 the models in that file carrying no `limit` at all were unaffected.

**A total, immediate hosted-free-tier failure is per-model availability, not a tier-wide outage — retry the identical prompt on a different `opencode/*-free` id before escalating.** Measured 2026-08-28 on opencode CLI 1.18.15 (macOS), during a Morrison-Lab/gha#682 delegated multi-file R refactor: `opencode/deepseek-v4-flash-free` failed a dispatch with `UnknownError: "Unexpected server error. Check server logs for details."` (carrying an `err_...` reference), exit 1, before doing any work — zero edits. Retrying the exact same prompt on `opencode/nemotron-3-ultra-free`, a different id on the same hosted-free tier, completed the task.

This is a different failure from the config error above: it happens mid-dispatch on an otherwise-working config, and the fix is a same-tier model swap rather than an edit to `opencode.jsonc`. This is a same-tier, cross-model retry among hosted providers.

- **Do:** on a total, immediate `UnknownError` from one `opencode/*-free` model, retry the identical prompt on a different free-tier model id before falling back to a metered CLI.
- **Do:** treat a per-model server error as availability noise for that model, not as proof the hosted-free tier itself is down.
- **Don’t:** read one free-tier model’s `UnknownError` as exhausting the hosted-free tier — a sibling free model completed the identical prompt immediately afterward.
- **Don’t:** use this retry rule for restricted data unless the repository explicitly approves the hosted destination.

## Relationship to other skills

- **[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md)** — the same shell-out shape aimed at a metered frontier CLI. Read its steps 2 to 5 for the background runner and DONE-marker poll rather than duplicating them here. What does not carry over is its data-sensitivity trigger, which splits into the routing rule above.
- **[`select-model`](../../skills/select-model/SKILL.llms.md)** — picks *which Claude model* runs a task. This skill decides whether the task runs on Claude at all.
- **[`agent-builder`](../../skills/agent-builder/SKILL.llms.md)** — an opencode model is a different model family from both Claude and codex, so it is a cheap cross-family second reader for that skill’s “paranoid reviewer” role. How much its agreement is worth is governed by [`self-review-fallback`](../../shared/workflow/self-review-fallback.md)’s cross-vendor section.
- **[`ums`](../../skills/ums/SKILL.llms.md)** — record new opencode mechanics here as they are measured, since the model list and the version above will go stale.

## Anti-patterns

- ❌ Sending data-triggered work to an `opencode/*`, `opencode-go/*`, or `openrouter/*` model because it is free or subscription-covered — billing facts say nothing about data leaving the machine.
- ❌ Passing `--auto` to widen a delegate’s permissions instead of scoping the config (repo root `opencode.json` uses a blanket-allow config intentionally as the scoped equivalent — see above — prefer that over `--auto` per-run).
- ❌ Quoting a count, a line number, or a citation a free model returned without re-deriving it.
- ❌ Skipping OpenCode’s hosted-free tier for small mechanical work because Codex is stronger — Codex has a window to conserve while OpenCode Zen consumes no quota.
- ❌ Handing a free hosted model the authoring or judgment task that needed Claude’s own context.

Back to top
