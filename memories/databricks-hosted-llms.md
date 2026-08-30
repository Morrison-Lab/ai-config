# Databricks-hosted LLMs: CLI and agent client configuration

Facts learned wiring Databricks-hosted models (Claude, GPT-5.x, Llama, and others) up as a provider for third-party CLI/agent clients (Codex CLI, opencode) and the ChatGPT desktop app.

## `~/.databrickscfg` is plaintext only for PAT profiles, not OAuth ones

A Databricks PAT written via `databricks configure --token` goes straight to `SaveToProfile` with no keyring call, so it lands in `~/.databrickscfg` as plaintext regardless of the file's `auth_storage` setting.
An OAuth U2M/M2M profile (`auth_type = databricks-cli`) is different: recent `databricks` CLI versions store its token in the OS-native secure store by default (Keychain on macOS, Credential Manager on Windows, Secret Service on Linux) per the CLI's own changelog, and such a profile's block in the config file carries no `token`/`refresh_token` field at all.

- **Do:** verify a credential-storage claim against the tool's actual current config and changelog before asserting it --- the storage mechanism can differ by *auth type within the same file*, not just by tool.
- **Do:** for an unattended/agent client that supports command-backed auth (e.g. Codex CLI's `[model_providers.<id>.auth]`), route through the existing OAuth credential (`databricks auth token`) rather than minting a new PAT.
- **Don't:** assert that a config file is "plaintext" (or "secure") as a blanket property of the file --- state it per auth type.

(Verified 2026-08-29 against an installed `ucdh-dev` profile, `security dump-keychain`, and the `databricks/cli` source and CHANGELOG.)

## Codex CLI 0.151.0+ hard-rejects `wire_api = "chat"`

Codex CLI's docs page (as WebFetch-summarized) says `wire_api` accepts `"chat"` or `"responses"`, chat being the default --- but that page is stale relative to the installed CLI.
As of Codex CLI 0.151.0 (Chat Completions support removed, `openai/codex#7782`), `wire_api = "chat"` on a custom `model_providers` entry fails config load outright: `wire_api = "chat" is no longer supported ... set wire_api = "responses"`.
Databricks does implement a real `/serving-endpoints/responses` route for Responses-capable models (GPT-5.5 Pro, GPT-5.5, GPT-5.3 Codex, GPT-5.6 family) --- a POST with a Responses-shaped body returns a genuine `object: "response"` payload.
The Claude family on Databricks is Chat-Completions-only, so it is currently unreachable from Codex CLI at all.

- **Do:** verify a fast-moving CLI's config semantics by actually running it (`codex exec --profile <name>`), not by trusting a WebFetch summary of its docs page.
- **Do:** for Codex CLI custom providers, set `wire_api = "responses"` and point at a Responses-capable Databricks endpoint.

(Verified 2026-08-29 against the installed Codex CLI 0.151.0 and a direct curl to a Databricks serving endpoint.)

## "Tools + `reasoning_effort` needs `/v1/responses`" is not scoped to two model families

A Databricks GPT reasoning-tier endpoint that receives *function tool definitions plus `reasoning_effort`* over `/v1/chat/completions` fails with "Function tools with reasoning_effort are not supported ... in /v1/chat/completions" --- and this hits any reasoning-tier GPT endpoint, not only the ones a given runbook happens to have flagged for it.
A model documented elsewhere as a lower reasoning tier and never called out for this constraint (GPT-5.4, "Medium") reproduces the identical error the moment a real agentic client (opencode's agent mode) sends tool definitions.
A bare curl test with no tools passes and proves nothing: the failure only appears once tools are in play.

- **Do:** verify a "GPT-5.x with tools" configuration with an actual tool-calling request or a real agentic client run, not a plain chat-completion test.
- **Do:** for a Chat-Completions-only client (opencode, aider), use only non-reasoning Databricks models (Claude, Llama, Gemma, GPT OSS);
  route every GPT-5.x reasoning variant through a Responses-API client (Codex CLI) instead.

(Verified 2026-08-29 via opencode's agent mode reproducing the failure on GPT-5.4.)

## The ChatGPT desktop app reads `~/.codex/config.toml` but its chat UI cannot select a custom provider

The ChatGPT desktop app and Codex CLI share the same `~/.codex/config.toml` (confirmed via Settings > Configuration's "Open config.toml" link), but the app's own model picker is a fixed 6-entry, OpenAI-only list --- a custom `model_providers` entry (e.g. a `databricks` block) is not selectable there, and there is no way to add one.
A GitHub issue about the app rejecting a custom provider's config on *validation* (`openai/codex#34709`, since fixed) is not evidence the app's UI *exposes* that provider's models in its chat window --- those are separate claims, easily conflated.
The custom provider stays usable only via `codex --profile <name>` in the terminal.

- **Do:** verify a claim about what a GUI exposes by looking at the GUI (computer-use, or ask the user), not by inferring it from a bug report about config-file validation.

(Verified 2026-08-29 via computer-use, live in the ChatGPT desktop app.)
