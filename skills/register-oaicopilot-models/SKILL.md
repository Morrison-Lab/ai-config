---
name: register-oaicopilot-models
description: "Register new models in the `oai-compatible-copilot` (OAICopilot) VS Code extension's `oaicopilot.models` setting, given a list or screenshot of available models (e.g. a Databricks Model Serving endpoint list). Diffs the requested models against what's already configured, infers each new entry's parameters (context length, max tokens, vision, apiMode, family) from the closest already-configured sibling of the same model family, and appends only the missing entries without disturbing existing ones. Use when asked to 'register these models', 'add these models to oaicopilot', 'register all these models in oaic configuration', 'add these to the model picker', or when handed a list/screenshot of served-model names to make available in GitHub Copilot Chat."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# register-oaicopilot-models — add new models to the OAICopilot extension config

Register one or more new models in the `johnny-zhao.oai-compatible-copilot`
("OAICopilot") VS Code extension, so they show up in the Copilot Chat model
picker. The extension's own config lives in the user's `settings.json` under
the `oaicopilot.models` array — there's no separate "oaic configuration" file.

## When this fires

- "register these models", "register all these models in oaic configuration",
  "add these models to oaicopilot"
- Handed a list or screenshot of served-model names (e.g. a Databricks Model
  Serving / MLflow endpoint list, an Azure AI Foundry deployment list) to make
  available in the Copilot model picker.

## Step 0 — Locate the config

The extension stores everything in VS Code's **user** `settings.json` (or the
workspace `.vscode/settings.json` if the user asked for project-scope
registration) — not a dedicated file. Find it:

```bash
# macOS
"$HOME/Library/Application Support/Code/User/settings.json"
# Linux
"$HOME/.config/Code/User/settings.json"
# Windows (PowerShell)
"$env:APPDATA\Code\User\settings.json"
```

Confirm the extension is actually installed before editing (`johnny-zhao.oai-compatible-copilot`):

```bash
find ~/.vscode/extensions -maxdepth 1 -iname "*oai-compatible-copilot*"
```

Read the two relevant keys: `oaicopilot.baseUrl` (global default endpoint) and
`oaicopilot.models` (the array of registered model entries — each has at
least `id` and `owned_by`).

A sanitized reference schema (endpoint templated as `<workspace-url>`, no
secrets) lives alongside this skill in
[`models-template.jsonc`](models-template.jsonc) — one representative entry
per model family. Use it as the per-family schema to copy from in Step 2, and
to seed `oaicopilot.models` on a fresh machine (swap in your workspace URL).

## Step 1 — Diff requested models against what's already registered

The model **name** the user hands you (e.g. from a served-endpoint list) is
almost always identical to the `id` field the extension expects — this
extension's convention is `id == owned_by-prefixed served-model name`
(`databricks-claude-opus-5`, `databricks-gemini-3-7-flash`, etc.). Extract the
existing `id`s and set-subtract:

```bash
python3 -c "
import json, re
path = '$HOME/Library/Application Support/Code/User/settings.json'
text = open(path).read()
# settings.json may have trailing commas / comments in some setups; if json.loads
# fails, fall back to a plain grep of \"id\": \"...\" instead of hand-parsing.
data = json.loads(text)
existing = {m['id'] for m in data.get('oaicopilot.models', [])}
print('\n'.join(sorted(existing)))
"
```

Compare against the requested list. Report which are already present
(no-op) and which are genuinely new before touching the file.

## Step 2 — Infer each new entry's parameters from its closest sibling

Never invent parameters from scratch. For each missing model, find the
**closest already-configured sibling** — same family prefix (same
`gpt-5.x`/`claude`/`gemini`/`llama` line) and, ideally, the most recent
version within that line — and copy its schema verbatim except for `id` (and
`family`, if the extension's `family` convention encodes the version, e.g.
`gpt-5.4` vs `gpt-5.4-mini`). Carry over unchanged:

- `baseUrl` / `apiMode` (per-provider, essentially never changes)
- `context_length`, `max_tokens` or `max_completion_tokens`
- `vision`
- `reasoning_effort` (GPT-family reasoning models only)
- `owned_by`

If a requested model has **no sibling at all** (a genuinely new model line,
e.g. a first-of-its-kind name), say so explicitly rather than guessing
silently — use the most structurally-similar existing entry as a starting
point (matching `vision`/`apiMode` conventions for that provider) and flag in
your final report that its `context_length`/`max_tokens` are placeholders the
user should confirm against the provider's actual model card.

## Step 3 — Append, don't disturb existing entries

Add only the missing entries to the end of the `oaicopilot.models` array.
Use `replace_string_in_file`/`multi_replace_string_in_file`, anchoring on the
**last existing array element plus the closing `],`**, and match the file's
existing indentation exactly. Never reorder, reformat, or rewrite entries
that already exist — a diff that touches unrelated array elements makes the
change harder to review and risks losing a hand-tuned parameter.

## Step 4 — Validate

```bash
python3 -c "import json; json.load(open('$HOME/Library/Application Support/Code/User/settings.json'))" && echo OK
```

(Or use `get_errors` on the file if editing through an assistant with that
tool.) A `settings.json` with a trailing comma or an unbalanced brace breaks
*all* of VS Code's settings, not just this extension's — always validate
before finishing.

## Step 5 — Report

State which models were added, which were already present (no-op), and flag
any model registered with guessed/placeholder parameters (Step 2's no-sibling
case). Tell the user they may need to reopen the Copilot Chat model picker
("Manage Models...") to see the new entries — no VS Code restart is required.

## Relationship to other skills

- **`select-model` / `assess-model-fit`** — once models are registered here,
  those skills help decide *which* registered model fits a given task; this
  skill only makes a model available, it doesn't choose one.
- **`skill-builder`** — used to author this skill.

## Anti-patterns

- Guessing parameters from scratch instead of copying a sibling's schema.
- Reformatting or reordering existing `oaicopilot.models` entries while adding
  new ones.
- Treating the display name/served-entity name as different from the `id`
  without checking — for this extension's Databricks convention they're the
  same string.
- Skipping the JSON validation step and leaving `settings.json` broken.
