# register-oaicopilot-models: add new models to the OAICopilot extension config

Register one or more new models in the `johnny-zhao.oai-compatible-copilot` (“OAICopilot”) VS Code extension, so they show up in the Copilot Chat model picker. The extension’s own config lives in the user’s `settings.json` under the `oaicopilot.models` array. There’s no separate “oaic configuration” file.

## When this fires

- “register these models”, “register all these models in oaic configuration”, “add these models to oaicopilot”
- Handed a list or screenshot of served-model names (e.g. a Databricks Model Serving / MLflow endpoint list, an Azure AI Foundry deployment list) to make available in the Copilot model picker.

## When this does NOT fire

This skill is the **work-machine** route: it assumes the `johnny-zhao.oai-compatible-copilot` extension is installed and points at a provider’s own endpoint list. On a machine without that extension, VS Code’s **built-in** Copilot Chat plus core BYOK registration covers the same need with no extra extension, and this skill’s whole procedure edits a config nothing reads.

The two routes share almost all of their vocabulary — “Copilot Chat”, “model picker”, “Manage Models…”, “register a model”, “API key” — so the request never discriminates between them. Check the extension, not the wording:

``` bash
find ~/.vscode/extensions -maxdepth 1 -iname "*oai-compatible-copilot*"
```

Absent means take the core-BYOK route instead, whose mechanics — where the built-in extension lives, why `code --list-extensions` cannot see it, where the API key actually goes, and the `chat.agentHost.byokModels.enabled` gate that hides a registered model until it is turned on — are in [`memories/vscode-copilot-byok.md`](../../memories/vscode-copilot-byok.md). Note that route has no file to edit: the key reaches VS Code secret storage through the picker’s UI, so it cannot be seeded by a config write.

- **Do:** run the `find` above before Step 0, and switch routes when it returns nothing.
- **Don’t:** read “register these models in Copilot” as selecting this skill. The phrase fits both routes, and only the installed extension set decides.

## Step 0: Locate the config

The extension stores everything in VS Code’s **user** `settings.json` (or the workspace `.vscode/settings.json` if the user asked for project-scope registration), not a dedicated file. Find it:

``` bash
# macOS
"$HOME/Library/Application Support/Code/User/settings.json"
# Linux
"$HOME/.config/Code/User/settings.json"
# Windows (PowerShell)
"$env:APPDATA\Code\User\settings.json"
```

The Bash snippets in Steps 1 and 4 read `$SETTINGS`. Set it once from the path that matches this OS, so those snippets aren’t hardcoded to macOS:

``` bash
# macOS
SETTINGS="$HOME/Library/Application Support/Code/User/settings.json"
# Linux
SETTINGS="$HOME/.config/Code/User/settings.json"
```

Confirm the extension is actually installed before editing (`johnny-zhao.oai-compatible-copilot`):

``` bash
find ~/.vscode/extensions -maxdepth 1 -iname "*oai-compatible-copilot*"
```

Read the two relevant keys: `oaicopilot.baseUrl` (global default endpoint) and `oaicopilot.models` (the array of registered model entries; each has at least `id` and `owned_by`).

A sanitized reference schema (endpoint templated as `<workspace-url>`, no secrets) lives alongside this skill in [`models-template.jsonc`](models-template.jsonc), one representative entry per model family. Use it as the per-family schema to copy from in Step 2, and to seed `oaicopilot.models` on a fresh machine (swap in your workspace URL). For Databricks entries, its operational limits follow WAI’s [`tbl-databricks-oaicopilot-defaults`](https://github.com/Morrison-Lab/wai/blob/main/chapters/ai-tools/byok-vscode-databricks.qmd#tbl-databricks-oaicopilot-defaults), verified against Databricks’ pay-per-token limits on 2026-08-26. These values are deliberately smaller than some models’ provider maximum context windows. Check the current Databricks [`supported-models` catalog](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models) separately for model-specific API requirements; on 2026-08-26 it required the Responses API for GPT-5.5 and GPT-5.3 Codex.

## Step 1: Diff requested models against what’s already registered

The model **name** the user hands you (e.g. from a served-endpoint list) maps to the `id` field by this extension’s convention: `id == owned_by-prefixed served-model name` (`databricks-claude-opus-5`, `databricks-gemini-3-7-flash`, etc.). The served-endpoint list usually already carries that prefix, so the handed-in name and the `id` are typically the same string, but confirm the prefix is present rather than assuming it. Extract the existing `id`s and set-subtract:

``` bash
python3 -c "
import json
data = json.load(open('$SETTINGS'))
existing = {m['id'] for m in data.get('oaicopilot.models', [])}
print('\n'.join(sorted(existing)))
"
```

If `json.load` raises (a real-world `settings.json` may contain `//` comments or trailing commas, i.e. JSONC), fall back to a plain grep of the `id` values instead of hand-parsing:

``` bash
grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' "$SETTINGS" | sed -E 's/.*"([^"]+)"$/\1/'
```

Compare against the requested list. Report which are already present (no-op) and which are genuinely new before touching the file.

## Step 2: Infer each new entry’s parameters from its closest sibling

Never invent parameters from scratch. For each missing model, first classify its provider and quota tier, then find the **closest already-configured sibling**: same family prefix (same `gpt-5.x`/`claude`/`gemini`/`llama` line) and, ideally, the most recent version within that line, then copy its schema verbatim except for `id` (and `family`, if the extension’s `family` convention encodes the version, e.g. `gpt-5.4` vs `gpt-5.4-mini`). Carry over unchanged when the sibling has the same provider and quota tier:

- `baseUrl` (per-provider, essentially never changes)
- `context_length`, `max_tokens` or `max_completion_tokens`
- `delay` from the quota tier (omit it only when that tier’s delay is 0 ms)
- `vision`
- `reasoning_effort` (GPT-family reasoning models only)
- `owned_by`

Derive `apiMode` from the provider’s current catalog for the exact model; it is not provider-wide. For Databricks, use `openai-responses` whenever the catalog says the model requires the Responses API, and `openai` otherwise.

For Databricks pay-per-token endpoints, use the current WAI table linked in Step 0 rather than copying a provider-maximum window from a model card or a sibling in another tier. As verified on 2026-08-26, the operational groups are:

- GPT-5.6 Sol/Terra/Luna: 400,000 context, 16,000 output, no delay (omit the `delay` field).
- Claude, GPT-5.5 through GPT-5, and Gemini: 64,000 context, 16,000 output, and 15,000 ms delay.
- Inkling: 64,000 context, 8,192 output, and 15,000 ms delay.
- GPT OSS: 131,072 context, 25,000 output, no delay (omit `delay`).
- Llama 4, Llama 3, and Gemma 3: 128,000 context, 8,192 output, no delay (omit `delay`).

OAICopilot advertises input capacity as `context_length - max_tokens`. Therefore, the 64,000/16,000 default exposes about 48,000 input tokens and can be too small for a large agent harness’s system prompt. If that happens, reduce loaded tools/instructions or raise `context_length` only after checking the workspace’s actual quota tier or provisioned-throughput capacity. Record the departure as an intentional local override; do not silently replace the quota-aware default with the model’s full provider window.

Do not duplicate single-instance flags from the sibling (e.g. `useForCommitGeneration: true` — at most one model across the entire configuration should carry this flag).

If a requested model has **no sibling at all** (a genuinely new model line, e.g. a first-of-its-kind name), say so explicitly rather than guessing silently. Use the most structurally-similar existing entry as a starting point (matching `vision`/`apiMode` conventions for that provider) and flag in your final report that its `context_length`/`max_tokens` are placeholders the user should confirm against the provider’s actual model card.

## Step 3: Append, don’t disturb existing entries

Add only the missing entries to the end of the `oaicopilot.models` array, via whatever file-edit tool this environment provides (the `Edit` tool, or the assistant’s edit-a-string tool). Anchor on the **last existing array element plus the closing `]`**, and match the file’s existing indentation exactly. Never reorder, reformat, or rewrite entries that already exist: a diff that touches unrelated array elements makes the change harder to review and risks losing a hand-tuned parameter.

## Step 4: Validate

``` bash
python3 -c "import json; json.load(open('$SETTINGS'))" && echo OK
```

`settings.json` is officially JSONC, so this bare `json.load` will report failure on a perfectly valid file that merely contains a `//` comment or a trailing comma. If it fails, don’t conclude the file is broken; strip comments and trailing commas first, then re-check, so a valid-but-JSONC file isn’t a false alarm:

``` bash
python3 -c "
import json, re
def strip_jsonc(text):
    out, in_str, esc = [], False, False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == '\\\\':
                esc = True
            elif c == '\"':
                in_str = False
        else:
            if c == '\"':
                in_str = True
                out.append(c)
            elif c == '/' and i + 1 < len(text) and text[i+1] == '/':
                while i < len(text) and text[i] != '\n':
                    i += 1
                if i < len(text):
                    out.append(text[i])
            else:
                out.append(c)
        i += 1
    t = ''.join(out)
    return re.sub(r',(\s*[}\]])', r'\1', t)

t = open('$SETTINGS').read()
try:
    json.loads(t)
except Exception:
    json.loads(strip_jsonc(t))
print('OK')
"
```

(Or use the assistant’s own diagnostics on the file, e.g. `get_errors`, if editing through an assistant with that tool.) A `settings.json` with a genuine unbalanced brace or a truly malformed entry breaks *all* of VS Code’s settings, not just this extension’s, so always validate before finishing.

## Step 5: Report

State which models were added, which were already present (no-op), and flag any model registered with guessed/placeholder parameters (Step 2’s no-sibling case). Tell the user they may need to reopen the Copilot Chat model picker (“Manage Models…”) to see the new entries; no VS Code restart is required.

## Relationship to other skills

- **`select-model` / `assess-model-fit`**: once models are registered here, those skills help decide *which* registered model fits a given task; this skill only makes a model available, it doesn’t choose one.
- **`skill-builder`**: used to author this skill.

## Anti-patterns

- Guessing parameters from scratch instead of copying a sibling’s schema.
- Copying a provider-maximum context window into a quota-limited Databricks workspace without first applying the operational tier from WAI’s table.
- Reformatting or reordering existing `oaicopilot.models` entries while adding new ones.
- Assuming the served-entity name already carries the `owned_by-` prefix without checking. The `id` must be the prefixed form (`databricks-<served-name>`); a bare served-name missing the prefix will not match the extension’s convention.
- Treating a JSONC `settings.json` (one with `//` comments or trailing commas) as broken because a bare `json.load` rejected it. Strip comments first.
- Skipping the JSON validation step and leaving `settings.json` broken.

Back to top
