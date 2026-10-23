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
- **The destination tier is unavailable or exhausted.** OpenCode Go operates on **dollar** caps rather than request counts. As of 2026-10-15 each model has its own monthly dollar limit. Its 5-hour limit is 20% of that and its weekly limit 50% (vendor docs, <https://opencode.ai/docs/go>, fetched 2026-10-15). DeepSeek V4.1 Flash is \$80 per month on Go and \$160 on Go Plus; DeepSeek V4 Pro and Kimi K3 are \$15 on Go. The vendor’s page lists the other models’ limits. Exhaustion shows as HTTP 429 `GoUsageLimitError` with `limitName` `weekly`, `5-hour` or `monthly`. On 2026-10-15 every model returned the weekly error at once, so the documented per-model limits did not isolate one model’s exhaustion from another’s. The response carries no reset time. When exhausted, fall back to Codex or OpenRouter per the ladder. Zen free tier rate-limiting is an availability state rather than window exhaustion.

The first two transfer from `delegate-to-codex`, but for a reason that skill does not have. There, work shape and model capability were independent. Here they point the same way: authoring and judgment work is exactly what the free tier is worst at.

## The one measured exception: authoring work a mechanical test can accept

The “needs strong reasoning, judgment, or long-context synthesis” bullet above rests on two grounds at once. The free tier is weakest at exactly that shape of work, and a wrong answer from it costs more to catch than the quota it saved. Only the second ground stops binding once a deterministic check settles correctness without the returned diff having to be reviewed for it. The first does not, so what the check buys is that a wrong answer is cheap rather than that it is unlikely — expect to re-run or re-route on a failed check. That is why this exception requires the check rather than merely permitting the dispatch.

One measurement bounds the exception rather than establishing a capability: one free-tier model id, on one R refactor, given a detailed brief and accepted because a mechanical suite passed rather than because the returned diff read well. [`memories/delegation.md`](../../memories/delegation.md)’s “opencode free tier: a full authoring task, validated mechanically” section is that record, and carries the date, the model id, the acceptance test, and the two failures from the same session that qualify it.

The separate “result must conform to a schema and you have no cheap validator” bullet is untouched by any of this. It never bound on that measurement, whose result was an R refactor with no schema to conform to, and it still binds on its own terms wherever a schema is required and no validator is cheap.

- **Do:** delegate authoring work to a free-tier model only when the brief carries literal paths, per [step 2, “Prepare the prompt”](#2-prepare-the-prompt), and the exact text each file the task creates should hold (the “exact new-file content” of the record cited above), *and* a mechanical acceptance test — a test suite, a linter, a byte comparison — decides correctness on its own.
- **Do:** settle the data question before the shape question — a mechanical acceptance test does not license a hosted dispatch the consuming repo’s data rules forbid.
- **Don’t:** condition the dispatch on the acceptance test alone — a vague brief with a passing check is a combination nobody measured.
- **Don’t:** let your own reading of the returned diff stand in for the mechanical check.
- **Don’t:** apply this exception to restricted data — a data trigger forbids OpenCode and OpenRouter dispatch, the free tier included, unless the consuming repository has explicitly approved that hosted destination.

## Hosted-only routing rule

[`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.llms.md)’s “Data sensitivity is a second trigger” section says a repo can route work to codex because of **what the work reads**, that this trigger overrides the shape exceptions, and that when codex is busy the work waits rather than falling back.

`opencode/*` (hosted Zen gateway) and `opencode-go/*` (OpenCode Go subscription) are hosted destinations. The payload leaves the machine exactly as it does for any other hosted model. Free or subscription-covered pricing is a **billing** fact and says nothing about where bytes go. OpenRouter is hosted too. A data trigger therefore forbids all OpenCode and OpenRouter model dispatch unless the consuming repository explicitly approves that hosted destination.

**The discriminator is the provider prefix, not the `-free` suffix.** `opencode models` on 2026-08-19 listed `opencode/big-pickle` alongside six ids ending in `-free`, all under the same hosted provider. The suffix answers a pricing question. The prefix answers which hosted tier a job goes to, which is the routing question.

**That answers where bytes go, not what a given account can actually call.** Measured 2026-09-04: on an account with no payment method on file, every non-`-free` `opencode/*` id returned `Error: No payment method.` immediately, before doing any work, while an `opencode/*-free` id and an `opencode-go/*` id both ran normally. So the prefix/suffix split above is right about routing and silent about reachability — check which ids actually run (a smoke test, per the Procedure below) before picking one for real work, rather than assuming every listed `opencode/*` id is callable.

As in the codex skill, do not infer a data trigger from a repo merely holding sensitive data. It applies where the consuming repo has written the rule down, and that repo owns the path list.

- **Do:** keep data-triggered work in the authoring session and use deterministic tools when no hosted destination is approved.
- **Don’t:** start or invoke Ollama, LM Studio, llama.cpp, or another local model.
- **Don’t:** read a `-free` suffix, or its absence, as evidence about where the payload goes.

## A third destination: OpenRouter, for models neither tier carries

OpenRouter bills pay-as-you-go from a prepaid balance, so under the subscriptions-only rule in [`memories/delegation.md`](../../memories/delegation.md) (Ezra, 2026-10-13) dispatch only to models priced 0/0, such as the stealth previews below, and never spend the balance.

`opencode` reaches OpenRouter as an ordinary provider, and one class of model makes that worth configuring: OpenRouter’s **stealth** previews — anonymized frontier models trialled under codenames, free while they last. `stealth/ox-alpha` (“Ox Alpha”, a reasoning model for coding and agentic work, 1,048,576-token context, pricing 0/0) was the roster’s one entry on 2026-08-23.

The provider is carried by the models.dev registry opencode resolves models from — stealth ids included — but it stays **inactive until the config or the auth store references it**, which is why a machine with no openrouter entry lists no `openrouter/*` ids at all. Any reference activates it: adding the entry below to the existing `provider` block of `opencode.jsonc` took this machine’s `opencode models` from zero `openrouter/*` ids to 360 — the full registry roster, including `stealth/ox-alpha` (which the registry already carried) and 359 ids the entry never named (measured 2026-08-23 on opencode 1.18.21). An empty `"openrouter": {}` therefore activates the same roster; a `models` entry earns its lines only by setting a display name, or by reaching an id the registry does not carry yet:

``` jsonc
// Insert inside the existing "provider" object in ~/.config/opencode/opencode.jsonc
// (add a comma after the preceding sibling entry):
"openrouter": {
  "models": {
    "stealth/ox-alpha": { "name": "Ox Alpha (stealth, 1M context)" }
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

## Cloud sessions: OpenCode Go over HTTP, no key needed

A claude.ai cloud session has no `opencode` CLI preinstalled (`npm i -g opencode-ai` installs one), but its agent proxy injects the OpenCode credential for `opencode.ai`, so `curl` to the chat endpoint works without a key (verified 2026-10-09). A GitHub Actions review job reported 401 `Missing API key` on the same call and no proxy variable (PR review run 37907648792, 2026-10-09), so do not assume it holds there. Use the Go endpoint `https://opencode.ai/zen/go/v1`, which both Go and Go Plus plans serve. Do not use the pay-as-you-go path `/zen/v1`, which has no funds and returns 402.

- `/chat/completions`: `glm-5.3`, `glm-5.3-flash`, `kimi-k3`, `deepseek-v4-pro`, and others. Use this endpoint in a cloud session. `qwen3.8-max` is documented under `/messages`, yet it returned a normal reply here on 2026-10-09, so it is usable on this endpoint.
- `/messages` (`claude-haiku-5-5`, `minimax-m3`) returned 401 `Missing API key` through the proxy on 2026-10-09, so it is not usable there.
- `/responses` and `/models` also exist; `/models` lists every id.
- Send a stable `x-opencode-session` UUID header for each conversation, or the request fails with 400 `MissingSessionID`.
- Models seen on `/models` on 2026-10-15 include `deepseek-v4.1-flash` (the vendor estimates about 87,000 requests per week on Go at 410 input, 71,300 cached and 310 output tokens per request, with input at \$0.15 per million tokens off-peak; a review that returns a longer answer gets fewer requests, and several smaller models list lower prices) and `gemini-4-argon-contributor` (the Argon model, 2x usage for a limited time). Treat `/models` as the authority, since the vendor says the list changes as models are added.
- `cat-jam-free` and `longcat-2.5-preview-free` answered through the proxy on 2026-10-15 while the Go quota was exhausted. Both are free for a limited time and reasoning models (a 16-token request returned only reasoning), so give them a generous `max_tokens`.
- **A review through these two ids worked on 2026-10-16, while every Go model returned the weekly `GoUsageLimitError`** ([ai-config#4581](https://github.com/Morrison-Lab/ai-config/issues/4581)). Stream with `"stream": true` and `max_tokens` 30000, and assemble `delta.content`; the text comes only after 40,000 to 70,000 characters of `reasoning_content`, about five minutes. On [ai-config#4572](https://github.com/Morrison-Lab/ai-config/pull/4572), `longcat-2.5-preview-free` found three real defects in the first push and then returned no text on the fix commit in two attempts, while `cat-jam-free` returned a clean verdict on both heads. Run both, treat an empty answer as no verdict rather than clean, and address, rebut or defer every defect in a list as for any review. The user accepted a clean verdict from one of these free models as the non-Claude gate while Go is exhausted (relayed by the coordinator session, 2026-10-16), with the other model’s empty answer counted as no verdict.
- **In a cloud session on 2026-10-16 these other routes did not work, so use the streamed Go-endpoint recipe above instead.** The free ids on the pay-as-you-go path `https://opencode.ai/zen/v1` (not the Go path) return `FreeTierError` with the message that the free tier can only be used from within OpenCode, whereas the paid ids on that path return the 402 above. With the CLI installed by `npm i -g opencode-ai` and the opencode API-key environment variable set to any non-empty value (the proxy supplies the real key), `opencode run -m opencode/<free id>` printed only its banner and hit a 280 to 420 second timeout. That held for `deepseek-v4.1-flash-free` and `nemotron-3-ultra-free`, each with the brief passed as the argument and with the brief attached by `-f`. A message placed after `-f` is read as a file name, because `-f` takes several files, so put the message before `-f`. `codex` and `agy` are not installed in a cloud session, no OpenRouter, Databricks or Gemini key is set, and `openrouter.ai` and `api.openai.com` are refused by the network policy.
- On 2026-10-15 the Argon model was blocked by the same weekly limit as every other Go model. Route the review to `agy` on a device, per `memories/delegation.md`.

A non-streaming call works for short prompts (such as a smoke test):

``` bash
curl -s https://opencode.ai/zen/go/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-opencode-session: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"model": "glm-5.3", "messages": [{"role": "user", "content": "Reply with exactly the word: PONG"}]}'
```

**Non-streaming requests fail for review-sized or substantial prompts.** Measured in a claude.ai cloud session on 2026-10-12, a non-streaming request with a ~22 KB diff failed: `glm-5.3` returned HTTP 502 after about 30 seconds, and `deepseek-v4-pro` returned an empty body with `upstream request failed` (while a `PONG` smoke test on the same endpoint returned 200 in 1.8 seconds). The roughly 30-second gateway cutoff requires streaming for anything longer than a trivial prompt.

**Always stream review-sized prompts and assemble `delta.content` chunks.** Add `"stream": true` to the payload, pass a generous `--max-time` (e.g. 600 or 900 seconds), and pipe into `scripts/parse-sse.py` (or an inline Python extractor):

``` bash
curl -N -s --max-time 900 https://opencode.ai/zen/go/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-opencode-session: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"model": "deepseek-v4-pro", "stream": true, "messages": [{"role": "user", "content": "Review this diff:\n..."}]}' \
  | python3 skills/delegate-to-opencode/scripts/parse-sse.py
```

Inline extractor alternative if running without the helper script:

``` bash
python3 -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if line.startswith("data:"):
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            break
        try:
            d = json.loads(chunk)
            c = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if c:
                sys.stdout.write(c)
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass
'
```

**Model reliability for large prompts in cloud sessions:** - `deepseek-v4-pro`: Verified reliable with `"stream": true` on review-sized prompts, returning complete reviews over several minutes. - `glm-5.3`: Unreliable on large prompts even when streaming. In testing, it sent ~4.8 MB of deltas in 290 seconds with no `delta.content` before timing out, or returned `upstream request failed`. Prefer `deepseek-v4-pro` for review-sized or multi-KB prompts.

**Python `urllib` returns 403 Forbidden; always use `curl`.** In a claude.ai cloud session (as observed on 2026-10-13), HTTP requests made via Python’s `urllib` (or `requests`) to `https://opencode.ai/zen/go/v1/chat/completions` fail with `403 Forbidden` from the cloud agent proxy, while `curl` with the identical body and headers returns `200 OK`. Always invoke `curl` in shell commands rather than Python HTTP libraries when calling the OpenCode Go API in cloud sessions.

**Per-model 502 upstream errors and fallback loop:** Both `glm-5.3` and `deepseek-v4-pro` can intermittently return `502 upstream request failed` (as observed on 2026-10-13) even on short diffs (e.g. 1 KB), while `kimi-k3` answers. When dispatching a review in a cloud session, implement a fallback loop over candidate models (`deepseek-v4-pro`, `kimi-k3`, `qwen3.8-max`, `glm-5.3`) so a single model’s transient 502 does not block the review:

``` bash
set -o pipefail 2>/dev/null || true
PAYLOAD_FILE=$(mktemp)
trap 'rm -f "$PAYLOAD_FILE"' EXIT
for model in deepseek-v4-pro kimi-k3 qwen3.8-max glm-5.3; do
  echo "Attempting review with $model..."
  # Build payload into a file to avoid Linux MAX_ARG_STRLEN (128 KiB) limits on large diffs
  python3 -c "import json, sys; json.dump({'model': sys.argv[1], 'stream': True, 'messages': [{'role': 'user', 'content': 'Review this diff:\n' + sys.stdin.read()}]}, open(sys.argv[2], 'w'))" "$model" "$PAYLOAD_FILE" < diff.patch
  if curl -N -s --max-time 900 https://opencode.ai/zen/go/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "x-opencode-session: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
    --data-binary "@$PAYLOAD_FILE" \
    | python3 skills/delegate-to-opencode/scripts/parse-sse.py > review.txt && [ -s review.txt ]; then
    break
  fi
done
rm -f "$PAYLOAD_FILE"
[ -s review.txt ] || { echo "Error: all candidate models failed" >&2; false; }
```

- **Do:** send `"stream": true` and assemble `delta.content` chunks for review-sized prompts.
- **Do:** run streaming requests with a generous `--max-time` (e.g. `--max-time 900`) in the background.
- **Do:** prefer `deepseek-v4-pro` over `glm-5.3` for large prompts or reviews in cloud sessions.
- **Do:** use `curl` rather than Python `urllib` in cloud sessions; the cloud agent proxy returns 403 Forbidden to `urllib`.
- **Do:** loop over candidate models (`deepseek-v4-pro`, `kimi-k3`, `qwen3.8-max`, `glm-5.3`) on 502 upstream failures.
- **Don’t:** use Python `urllib` to call the OpenCode Go API in cloud sessions.
- **Don’t:** send non-streaming requests for anything longer than a short prompt; the roughly 30-second gateway cutoff returns 502 or upstream request failure.
- **Don’t:** rely on `glm-5.3` for large prompts; it can stream megabytes of empty deltas or fail upstream.

Reuse one UUID across the turns of a conversation. Prefer Go models for bulk and mechanical work while Claude quota is low. The data rules above still apply: no student data (FERPA records) and no PHI to any hosted model. Review work must also meet the model-and-harness independence rule in [`adversarial-self-review`](../../shared/workflow/adversarial-self-review.md). When posting an OpenCode review result to a PR comment under a user login (e.g. from local or Remote Control sessions), wrap the output in a standardized envelope:

``` markdown
## Cross-harness review (OpenCode <model>) of <HEAD_SHA>

Reviewed-Commit: <HEAD_SHA>

<verbatim review output>

### Verdict

Verdict: <Clean or Needs more work>

_Posted by <Agent Name> (AI agent) --- not written by a human._
```

This ensures `check-pr-fully-clean.py` admits the review by construction and allows a clean verdict to supersede any earlier standing not-clean comments (#4425). Never use Codex for this routing.

## OpenCode 2.0

OpenCode 2.0 was first seen on 2026-10-15 (<https://opencode.ai/v2/docs>, <https://opencode.ai/v2/docs/migrate-v1/>). Nothing in this skill was measured on it. Every `opencode` measurement above is from 1.18.x.

- V2 reads the same config files as V1, including `~/.config/opencode/opencode.json(c)`, `<project>/opencode.json(c)` and `.opencode/`. Existing agent, command and skill definitions are documented to keep working.
- V1 plugin implementations do not run in V2. `docs/opencode-hook-mapping.md` depends on the oh-my-openagent plugin, so a V2 session would lose the hook bridge. Either stay on V1 until that plugin has a V2 port, or move to V2 and accept that the guards then run only under Claude Code.
- The V2 install commands are `curl -fsSL https://opencode.ai/v2/install | bash` and `npm install -g @opencode/cli`. The docs say `mise use -g opencode` installs V1 on a `mise` older than 2026.10.9. The migration guide says the V2 curl installer replaces the V1 binary, and says to remove a package-managed V1 install first. That is vendor-documented and untested here, so check `opencode --version` after any install. V1 and V2 share the config locations, so keep a copy of the V1 config before converting it.

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

**That gap is closed as of 2026-09-04.** `opencode run -m opencode-go/gpt-5.6-luna "Reply with exactly the word: PONG"` returned `PONG`, and a subsequent real dispatch (an adversarial prose review of a small diff) to the same id completed and returned a usable verdict. So `opencode-go/*` is a confirmed-working route for judgment-bearing sidecar work, not only an active-subscription claim — prefer it there over a bare `opencode/*` id, per the reachability caveat in the section above.

### 2. Prepare the prompt

As of 2026-08-19, `opencode run` takes the message as positional arguments, and `-f/--file` attaches files. Use `--dir` to point the run at a repo, and `--variant` for a provider-specific reasoning effort. Fetch anything from the network yourself and embed it in the prompt.

**There is no schema flag.** `opencode run --help` on 2026-08-19 offered `--format json`, which emits the raw event stream rather than a schema-constrained final message, and nothing equivalent to codex’s `--output-schema`. So ask for the structure in the prompt and validate it on return. Expect that validation to fail sometimes, because emitting strict JSON is one of the things small models are worst at.

**Name every target file’s literal path — do not hand the delegate a glob and expect it to resolve one.** Measured 2026-08-28 on opencode CLI 1.18.15 (macOS), during a Morrison-Lab/gha#682 delegated multi-file R refactor: under `opencode/nemotron-3-ultra-free`, the agent’s Glob tool returned zero matches for globs anchored under dot-prefixed directories — `**/test-description-version.R` and `.github/workflows/scripts/tests/*.R` both came back empty even though the files existed. The model recovered only because the brief also carried the literal file paths, which it then reached via `find` and a direct `Read` instead. A brief that described the file set only by pattern, with no literal fallback, would have had nothing to recover with.

- **Do:** enumerate every file the delegate must read or edit as a literal path in the brief, especially anything under `.github/` or another dot-prefixed directory.
- **Do:** treat a zero-match Glob under a dotted path as an expected gap on this model rather than a bug to debug mid-dispatch.
- **Don’t:** describe a target file set to an opencode delegate by glob pattern alone and assume it will resolve — a real, existing file under `.github/workflows/scripts/tests/` returned no matches on this model.

### 3. Run it

**`--agent plan` is now inert; the stall it was meant to work around still reproduces.** Measured 2026-09-04: `opencode run --agent plan -m <id> "<prompt>"` prints `agent "plan" is a subagent, not a primary agent. Falling back to default agent` and runs the default agent anyway — the exact remedy the paragraph below once prescribed no longer selects an agent at all, and the warning is easy to miss in a tail-trimmed transcript. The underlying stall reproduced the same day on a fresh default-agent run: a ~250-word review prompt produced zero output across a 300s foreground timeout and had still written nothing when backgrounded and checked later. So treat the section below as a historical account of a workaround that stopped working, not as a live instruction — there is currently no known `opencode run` flag that avoids the stall, and a stalled dispatch should be killed and retried rather than trusted to eventually finish.

`opencode run` defaults to the `build` agent, which runs with tools enabled. Measured 2026-08-23 on 1.18.21 with `openrouter/stealth/ox-alpha`: a ~350-word diagnosis prompt (a Python traceback plus a function body, JSON-only output requested) produced zero streamed output across two default-agent runs — one killed at a 5-minute timeout, the other left running in the background and never observed to finish — while `--agent plan` completed the identical prompt in 36 seconds, and the default agent answered trivial and medium prompts in 13-15 seconds throughout. A candidate explanation is the prompt’s file paths inducing tool use that goes nowhere headless, but that mechanism is unconfirmed. The measurements above are what this section asserts, over the version where `--agent plan` still worked.

- **Do:** treat a silent, multi-minute `opencode run` as a stall to kill and retry, on a different model or a shorter prompt — `--agent plan` no longer selects an agent as of 2026-09-04, so it is not an escape from the stall.
- **Don’t:** rely on `--agent plan` to avoid the default-agent stall. It now falls back to the default agent it was meant to replace.

**A recipe that avoided the stall, measured 2026-10-22 (Linux desktop, opencode 1.18.34).** A long review prompt (~6.7 KB) passed as one positional argument to `opencode run -m opencode/<id>` hit a 600 s `timeout` with 0 bytes of output, not even the `> build ·` banner. That happened four times, on `deepseek-v4.1-flash-free`, `nemotron-3-ultra-free` and `glm-5.3-flash-free`, from the repo root and from a scratchpad directory, with and without file paths in the prompt. A trivial prompt (`cd /tmp && opencode run -m opencode/glm-5.3-flash-free "Reply with exactly the word: PONG"`) returned in about 3 s. Putting the prompt in a file (7.6 KB), passing a short positional message before `-f <file>`, and running from `/tmp` completed with a full, usable review four times in a row, each within a few minutes, all on `glm-5.3-flash-free`:

``` bash
cd /tmp && opencode run -m opencode/glm-5.3-flash-free \
  "Follow the instructions at the top of the attached file and review the two diffs it contains. Do not use any tools." \
  -f <prompt-file>
```

Several things changed between the failing and working runs: the prompt moved from the positional argument into an attached file, the positional message became short, the cwd became `/tmp`, the prompt size differed (about 6.7 KB against 7.6 KB), and the working runs used one of the three models. A scratchpad cwd had already stalled, so a neutral directory alone did not prevent it. Which change fixed it is unknown.

- **Do:** put a long prompt in a file, pass a short positional message before `-f <file>`, and run it from `/tmp`, as the working runs did.
- **Don’t:** report the mechanism as known, or pass a multi-kilobyte prompt as one positional argument, which stalled in all four measured runs.

On that machine and date, `opencode models` listed no `opencode-go/*` ids, so `opencode-go/deepseek-v4-pro` returned “Model not found” (step 1’s “confirmed-working” claim for `opencode-go/*` therefore depends on the account and machine). The alternative delegation CLIs were also unusable there: agy returned HTTP 429 “Individual quota reached”, and gemini and cursor-agent were unauthenticated ([ai-config#4688](https://github.com/Morrison-Lab/ai-config/issues/4688)).

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
