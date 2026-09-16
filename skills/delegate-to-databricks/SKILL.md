---
name: delegate-to-databricks
description: "Dispatch sidecar work to Databricks-hosted LLMs."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# delegate-to-databricks --- run sidecar work on Databricks-hosted models via Codex CLI

Some institutions host a foundation-model catalog behind Databricks Model
Serving's OpenAI-compatible `/serving-endpoints` route, reachable
independently of any VS Code extension.
This skill routes dispatchable sidecar work there through the **Codex CLI**,
configured with Databricks as a custom `model_providers` entry, rather than
through a bespoke HTTP client.
Claude stays the orchestrator: it writes the prompt, dispatches Codex, and
validates what comes back.
The delegation-ladder preference this plugs into lives in
[`memories/delegation.md`](../../memories/delegation.md).
[`memories/databricks-hosted-llms.md`](../../memories/databricks-hosted-llms.md)
carries the underlying Codex/Databricks configuration facts this skill
builds on --- read it alongside this file rather than only this one; the two
sections below repeat only what changes the setup steps.

## Why this is a shell-out, not a subagent

Claude Code's `Agent` tool only reaches the Anthropic API, Amazon Bedrock, or
Google Vertex --- its `model` parameter is a fixed enum of Claude aliases with
no `base_url` override, so a Databricks-hosted endpoint is unreachable from
that tool directly.
This is the same constraint
[`delegate-to-codex`](../delegate-to-codex/SKILL.md) works around with a
Bash shell-out to the Codex CLI; this skill reuses that same shell-out,
pointed at a different `model_providers` entry.

## Why Codex CLI, not a raw HTTP wrapper or an `opencode` custom provider

Databricks' recommended interactive auth is OAuth U2M
(`databricks auth login`), which mints **short-lived** access tokens by
design, and PAT creation is not reliably available on every workspace (some
institutions disable it on certain workspaces entirely).
A delegation mechanism that wants a **static** API key --- `opencode`'s
custom-provider config, or a hand-rolled script that caches a bearer token ---
is a poor fit for that: either it needs a long-lived PAT that may not exist,
or it goes stale mid-session.

Codex CLI's `model_providers.<name>.auth` config table supports a
**command-backed** auth source instead of a static key: `auth.command` names
an external command Codex re-runs on a `refresh_interval_ms` cadence to mint
a fresh token, with no secret stored in `config.toml` at all.
That fits a re-derive-per-call OAuth token exactly, and gets you a full
agentic CLI (tool calls, sandboxing, hooks) backed by the Databricks-hosted
model, not just a bare chat-completion call.

## Which models are actually reachable this way

**Codex CLI 0.151.0+ hard-rejects `wire_api = "chat"`** at config-load time
(`wire_api = "chat" is no longer supported ... set wire_api = "responses"`,
per [`memories/databricks-hosted-llms.md`](../../memories/databricks-hosted-llms.md)'s
"Codex CLI 0.151.0+ hard-rejects `wire_api = "chat"`" section) --- this is
not a per-model choice or a "safer default," it is a hard requirement for
**every** custom `model_providers` entry, Databricks-backed or otherwise.
That means only Databricks endpoints that actually implement the Responses
route (`/serving-endpoints/responses`) are reachable from Codex at all.
That same memory entry names GPT-5.5 Pro, GPT-5.5, GPT-5.3 Codex, and the
GPT-5.6 family as Responses-capable, and Claude on Databricks as
Chat-Completions-only and therefore currently unreachable from Codex
regardless of `wire_api` --- the one model family this skill can positively
rule out. (This skill's own verification run, below, confirms one specific
GPT-5.6-family id, `databricks-gpt-5-6-sol`, actually works end to end ---
that specific id is this skill's own finding, not the cited memory's.)
The memory entry does not enumerate every other family's capability, and
Responses support is a vendor-catalog fact that changes over time, so
**check the current supported-models/Responses-capability documentation for
the specific workspace before writing a profile-layer file for any model**,
rather than assuming a name not listed here is either reachable or not.

For a model confirmed Chat-Completions-only on the target workspace (Claude
is the one family this skill can confirm), reach it through a
Chat-Completions client instead --- `opencode`'s custom provider, or a raw
HTTP client --- not through this Codex-CLI route.

## When this fires

- "delegate to databricks", "use databricks as a subagent", "dispatch to a
  databricks-hosted model", "run this on databricks"
- Proactively, before mechanical, bounded sidecar work when a Databricks-hosted,
  Responses-capable model is the destination of choice for institutional,
  compliance, or cost reasons, or when the ordinary `codex` (ChatGPT-plan)
  window from [`delegate-to-codex`](../delegate-to-codex/SKILL.md) is
  exhausted but a Databricks-hosted budget is fresh.

## When NOT to delegate here

- Judgment-heavy, architecturally significant, or long-context synthesis work
  --- the same exclusion `delegate-to-codex`/`delegate-to-opencode` state, for
  the same reason: a wrong answer from a sidecar model costs more to detect
  than the quota it saves.
- The critical-path edit the rest of the work waits on --- do it inline.
- The target model is Chat-Completions-only on Databricks (Claude is the one
  family confirmed so here) --- this route cannot reach it; see "Which
  models are actually reachable" above, and check the current catalog for
  any other model not confirmed either way.
- No `model_providers.databricks` entry is configured yet on this machine, and
  setting one up is itself the task (see Setup below) --- that is setup work,
  not a dispatch.
- Institutional data-handling policy forbids sending this payload to the
  configured workspace --- check that before assuming a Databricks-hosted
  destination is safer than a public one merely because it is
  institution-operated.

## Setup (one-time, per machine)

Four pieces, none of which stores a long-lived secret in a config file.
Placeholders (`<WORKSPACE_HOST>`, `<PROFILE>`) stand for the specific
workspace hostname and CLI profile name in use --- this skill documents the
pattern, not any one institution's values.

### 1. An authenticated `databricks` CLI profile (human, interactive, one-time)

```bash
databricks auth login --host https://<WORKSPACE_HOST> --profile <PROFILE>
databricks auth profiles   # confirm Valid: YES
```

This opens a browser for OAuth U2M.
**Run this yourself, in your own terminal --- never delegate this step to an
agent.** It is the same category as `databricks configure --token`: an
interactive credential step that needs a human at the keyboard, not a
scriptable one.

### 2. A token-refresh script on `PATH`

A small wrapper that re-derives a fresh access token from the CLI's own
credential store on every call, so nothing static is cached:

```bash
#!/usr/bin/env bash
# Prints a fresh Databricks OAuth access token for the given profile
# (default: <PROFILE>) to stdout. The underlying refresh token lives in the
# OS keychain (databricks-cli's `auth_storage = secure` default) -- this
# script never stores a secret itself, it only re-derives one on demand.
#
# Usage: databricks-token [profile]
set -euo pipefail
profile="${1:-<PROFILE>}"
databricks auth token --profile "$profile" -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
```

Save as `~/.local/bin/databricks-token`, `chmod +x`.

### 3. A `model_providers` entry in `~/.codex/config.toml`

```toml
# Databricks-hosted foundation models, reached via the OpenAI-compatible
# Responses route. Auth is command-backed rather than a static env_key: the
# script re-derives a fresh OAuth access token from the databricks CLI's own
# keychain-backed storage on every refresh, so no secret is stored in this
# file. wire_api = "responses" is REQUIRED -- Codex CLI 0.151.0+ rejects
# "chat" outright for any custom model_providers entry (see "Which models
# are actually reachable this way" above).
[model_providers.databricks]
name = "Databricks"
base_url = "https://<WORKSPACE_HOST>/serving-endpoints"
wire_api = "responses"

[model_providers.databricks.auth]
command = "/Users/<you>/.local/bin/databricks-token"
timeout_ms = 5000
refresh_interval_ms = 300000
```

### 4. One profile-layer file per model, under `$CODEX_HOME`

Codex's `-p/--profile <name>` flag layers `~/.codex/<name>.config.toml` on
top of the base config (not the older `[profiles.<name>]` TOML-table form
some Codex versions also support --- check `codex --help` for which your
installed version uses).
One file per model you want to select by name, picking only from the
Responses-capable set described above:

```toml
# ~/.codex/databricks.config.toml
model_provider = "databricks"
model = "databricks-<model-id>"   # a Responses-capable id, e.g. databricks-gpt-5-6-sol
```

Repeat per model (e.g. `databricks-gpt-5-6-sol.config.toml`,
`databricks-gpt-5-5-pro.config.toml`) so a specific one can be selected
with `--profile databricks-<model-id>` without touching the default.

## Dispatch

```bash
codex exec --profile <profile-name> --sandbox read-only \
  --skip-git-repo-check "<prompt>" < /dev/null
```

- `--sandbox read-only` for a review/analysis sidecar; `workspace-write` if
  the sidecar needs to edit files in its own scope.
- `--skip-git-repo-check` when dispatching from a directory Codex has not
  been told to trust.
- `< /dev/null` (or otherwise close stdin) --- without it, Codex reads
  additional input from stdin before running, which hangs a non-interactive
  dispatch that supplies no piped input.
- Use `codex exec --profile <name> resume`/`fork` to continue a prior
  Databricks-backed session rather than starting fresh each time.

**Verified working 2026-09-15**: `codex exec --profile databricks --sandbox
read-only --skip-git-repo-check "Reply with exactly: OK" < /dev/null` against
`databricks-gpt-5-6-sol` (a Responses-capable model), configured per the
steps above, returned `OK`.

## Caveats

- **Codex's own model-list refresh 404s against Databricks, harmlessly.**
  Codex periodically queries `<base_url>/models` to refresh its model
  picker; Databricks has no such endpoint (`ENDPOINT_NOT_FOUND`, "Path must
  be of form /serving-endpoints/<endpoint_name>/invocations or
  .../served-models/<served_model_name>/invocations"). This is log noise,
  not a dispatch failure --- the actual `/responses` calls the dispatch makes
  are unaffected.
- **"Model metadata ... not found. Defaulting to fallback metadata" is
  expected**, since Codex has no built-in profile for a
  `databricks-<model-id>` name. This means Codex's own context-window
  budgeting for that model is a guess, not the vendor's real figure --- keep
  dispatched prompts modest rather than trusting an advertised window.
- **ITPM ceilings are real and per-model-family**, and vary by workspace
  tier. Verify the current limits for the specific model before assuming
  headroom, especially for a burst of concurrent tool calls in agent mode
  rather than one sequential request.
- **Measured overhead**: a single-turn "reply with OK" dispatch through
  Codex against a Databricks-hosted GPT-5.6-family model consumed roughly
  49,000 tokens end to end --- Codex's own agent-mode scaffolding, not the
  model's. Budget dispatches accordingly.

## Relationship to other skills

Codex-side, this reuses [`delegate-to-codex`](../delegate-to-codex/SKILL.md)'s
shell-out mechanism with a different `model_providers` entry: the ordinary
`codex` ChatGPT-plan window and this Databricks-hosted route are governed by
separate quotas and do not substitute for each other automatically, so use
this one specifically when a Databricks-hosted model is the destination of
choice, not as a general Codex-availability fallback.

[`delegate-to-opencode`](../delegate-to-opencode/SKILL.md) is a **separate**
CLI shell-out (the `opencode` binary, not Codex) and does not route through
this mechanism at all; it remains the route for a Chat-Completions-only
Databricks model (see "Which models are actually reachable this way" above),
via its own custom-provider config rather than this skill's command-backed
auth.

- **Do:** verify `databricks auth profiles` reports the target profile as
  `Valid: YES` before dispatching --- a stale or missing profile fails the
  token-refresh script, and thus every dispatch, with no useful message from
  Codex itself.
- **Do:** treat the setup step's `databricks auth login` as a human-only,
  interactive, one-time action.
- **Do:** confirm a target model is Responses-capable on the current
  workspace before writing a profile-layer file for it --- see "Which models
  are actually reachable this way" above.
- **Don't:** cache a Databricks bearer token anywhere in `config.toml` or a
  committed file --- the whole point of the command-backed `auth.command`
  mechanism is that nothing static needs to be stored.
- **Don't:** set `wire_api = "chat"` (or omit `wire_api`, which may default
  to it) on this or any custom `model_providers` entry --- current Codex CLI
  rejects it at config load regardless of which model the entry points at.
