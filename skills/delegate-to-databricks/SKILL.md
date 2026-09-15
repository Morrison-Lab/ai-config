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

Some institutions host a large foundation-model catalog (Claude, GPT-5.x,
Gemini, Llama, GPT OSS) behind Databricks Model Serving's OpenAI-compatible
`/serving-endpoints/<name>/invocations` route, reachable independently of any
VS Code extension.
This skill routes dispatchable sidecar work there through the **Codex CLI**,
configured with Databricks as a custom `model_providers` entry, rather than
through a bespoke HTTP client.
Claude stays the orchestrator: it writes the prompt, dispatches Codex, and
validates what comes back.
The delegation-ladder preference this plugs into lives in
[`memories/delegation.md`](../../memories/delegation.md).

## Why this is a shell-out, not a subagent

Claude Code's `Agent` tool only reaches the Anthropic API, Amazon Bedrock, or
Google Vertex --- its `model` parameter is a fixed enum of Claude aliases with
no `base_url` override, so a Databricks-hosted endpoint is unreachable from
that tool directly.
This is the same constraint
[`delegate-to-codex`](../delegate-to-codex/SKILL.md) and
[`delegate-to-opencode`](../delegate-to-opencode/SKILL.md) already work
around with a Bash shell-out; this skill is a third instance of the same
pattern, routed through Codex specifically because of the next section.

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

## When this fires

- "delegate to databricks", "use databricks as a subagent", "dispatch to a
  databricks-hosted model", "run this on databricks"
- Proactively, before mechanical, bounded sidecar work when a Databricks-hosted
  model is the destination of choice for institutional, compliance, or
  cost reasons, or when the ordinary `codex` (ChatGPT-plan) window from
  [`delegate-to-codex`](../delegate-to-codex/SKILL.md) is exhausted but a
  Databricks-hosted budget is fresh.

## When NOT to delegate here

- Judgment-heavy, architecturally significant, or long-context synthesis work
  --- the same exclusion `delegate-to-codex`/`delegate-to-opencode` state, for
  the same reason: a wrong answer from a sidecar model costs more to detect
  than the quota it saves.
- The critical-path edit the rest of the work waits on --- do it inline.
- No `model_providers.databricks` entry is configured yet on this machine, and
  setting one up is itself the task (see Setup below) --- that is setup work,
  not a dispatch.
- Institutional data-handling policy forbids sending this payload to the
  configured workspace --- check that before assuming a Databricks-hosted
  destination is safer than a public one merely because it is
  institution-operated.

## Setup (one-time, per machine)

Three pieces, none of which stores a long-lived secret in a config file.
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
databricks auth token --profile "$profile" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
```

Save as `~/.local/bin/databricks-token`, `chmod +x`.

### 3. A `model_providers` entry in `~/.codex/config.toml`

```toml
# Databricks-hosted foundation models, reached via the OpenAI-compatible
# /serving-endpoints route. Auth is command-backed rather than a static
# env_key: the script re-derives a fresh OAuth access token from the
# databricks CLI's own keychain-backed storage on every refresh, so no
# secret is stored in this file.
[model_providers.databricks]
name = "Databricks"
base_url = "https://<WORKSPACE_HOST>/serving-endpoints"
wire_api = "responses"

[model_providers.databricks.auth]
command = "/Users/<you>/.local/bin/databricks-token"
timeout_ms = 5000
refresh_interval_ms = 300000
```

`wire_api = "responses"` is the safer default: several Databricks-hosted
GPT-5.x families require the Responses API unconditionally, and others
(GPT-5.6) require it whenever a tool call carries `reasoning_effort` --- which
is exactly Codex's own agent-mode usage.
See "Caveats" below before overriding it to `"chat-completions"`.

### 4. One profile-layer file per model, under `$CODEX_HOME`

Codex's `-p/--profile <name>` flag layers `~/.codex/<name>.config.toml` on
top of the base config (not the older `[profiles.<name>]` TOML-table form
some Codex versions also support --- check `codex --help` for which your
installed version uses).
One file per model you want to select by name:

```toml
# ~/.codex/databricks.config.toml
model_provider = "databricks"
model = "databricks-<model-id>"
```

Repeat per model (e.g. `databricks-gpt-5-6-sol.config.toml`,
`databricks-claude-opus-5.config.toml`) so a specific one can be selected
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
`databricks-gpt-5-6-sol`, configured per the steps above, returned `OK`.

## Caveats (carried from the private per-institution runbook and this
skill's own verification run)

- **Codex's own model-list refresh 404s against Databricks, harmlessly.**
  Codex periodically queries `<base_url>/models` to refresh its model
  picker; Databricks has no such endpoint (`ENDPOINT_NOT_FOUND`, "Path must
  be of form /serving-endpoints/<endpoint_name>/invocations or
  .../served-models/<served_model_name>/invocations"). This is log noise,
  not a dispatch failure --- the actual `/invocations`/`/responses` calls the
  dispatch makes are unaffected.
- **"Model metadata ... not found. Defaulting to fallback metadata" is
  expected**, since Codex has no built-in profile for a
  `databricks-<model-id>` name. This means Codex's own context-window
  budgeting for that model is a guess, not the vendor's real figure --- keep
  dispatched prompts modest rather than trusting an advertised window, per
  the general finding that `context_length` is advisory rather than an
  enforced cap on this class of client.
- **ITPM ceilings are real and per-model-family**, and vary by workspace
  tier. Verify the current limits for the specific model before assuming
  headroom, especially for a burst of concurrent tool calls in agent mode
  rather than one sequential request.
- **Some model families require `wire_api = "responses"` unconditionally**
  (certain GPT-5.x variants), and others require it **only** when a tool
  call carries `reasoning_effort` (GPT-5.6-family models observed) ---
  agent mode always carries tool calls, so any such model needs the
  Responses route the moment it is used for dispatch, even if it served
  ordinary chat fine over Chat Completions.
- **Measured overhead**: a single-turn "reply with OK" dispatch through
  Codex against a Databricks-hosted GPT-5.6-family model consumed roughly
  49,000 tokens end to end (Codex's own agent-mode scaffolding, not the
  model's). Budget dispatches accordingly; this is a different overhead
  figure from OAICopilot's own measured ~83,000-token scaffolding, since the
  two are different agentic clients querying the same endpoint.

## Relationship to other skills

This is a **third Codex routing target**, distinct from
[`delegate-to-codex`](../delegate-to-codex/SKILL.md) (which reaches OpenAI's
own hosted models via the ChatGPT plan) and
[`delegate-to-opencode`](../delegate-to-opencode/SKILL.md) (OpenCode/Zen/
OpenRouter). Use this one specifically when a Databricks-hosted model is the
destination of choice, not as a general Codex-availability fallback --- the
ordinary `codex` ChatGPT-plan window and this Databricks-hosted route are
governed by separate quotas and do not substitute for each other
automatically.

- **Do:** verify `databricks auth profiles` reports the target profile as
  `Valid: YES` before dispatching --- a stale or missing profile fails the
  token-refresh script, and thus every dispatch, with no useful message from
  Codex itself.
- **Do:** treat the setup step's `databricks auth login` as a human-only,
  interactive, one-time action.
- **Don't:** cache a Databricks bearer token anywhere in `config.toml` or a
  committed file --- the whole point of the command-backed `auth.command`
  mechanism is that nothing static needs to be stored.
- **Don't:** assume every Databricks-hosted model needs `wire_api =
  "responses"` --- some serve ordinary Chat Completions fine until tool
  calls and `reasoning_effort` combine; check the specific model's
  requirements before overriding the safer default.
