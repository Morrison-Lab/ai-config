# VS Code's built-in Copilot Chat and core BYOK model registration

Where VS Code keeps Copilot Chat and its "bring your own key" (BYOK) model registration, and why both are invisible to the checks you would naturally run for them.

Everything below was measured on the user's personal Windows 11 machine on **2026-08-23**, against **VS Code 1.134.0** (commit `110a328ea54b42367b803ec53ee0bf52ef26b419`) and the bundled **`GitHub.copilot-chat` 0.62.0**.
Both version numbers move on VS Code's monthly train, so re-measure rather than quoting these -- the *mechanisms* are the durable part, the versions are the timestamp.

Companion of the [`register-oaicopilot-models`](../skills/register-oaicopilot-models/SKILL.md) skill, which handles the third-party extension route this file's route replaces.
Not a companion of [`tools.md`](tools.md)'s "Personal machine setup" section, despite the name: that section documents the shiva login node, a different machine entirely.

## `code --list-extensions` cannot see a built-in extension, so an absent name is not an absent extension

VS Code 1.134 ships GitHub Copilot Chat **built in**, unpacked under the install's version-hash directory rather than the user extensions directory:

```
<install>/<version-hash>/resources/app/extensions/copilot/package.json
  publisher: GitHub
  name:      copilot-chat
  version:   0.62.0
```

On this machine that resolved to `%LOCALAPPDATA%\Programs\Microsoft VS Code\110a328ea5\resources\app\extensions\copilot`.
Note the directory is `copilot` while the manifest's `name` is `copilot-chat`, so a directory-name search for the extension id finds nothing either.

`code --list-extensions` enumerates **marketplace** extensions only.
The same session's output was three lines long -- `anthropic.claude-code`, `google.google-antigravity`, `sst-dev.opencode` -- with no Copilot entry, while Copilot Chat was installed and running the whole time.

The failure is quiet and reads as a finding rather than as a gap.
A short list looks like a complete answer, so "Copilot Chat is not installed here" arrives as a measured fact with a command behind it, and nothing in the output announces that a whole class of extension was excluded from the enumeration.
That is [`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md)'s shape one tool over: the query ran, returned cleanly, and answered a narrower question than the one asked.

- **Do:** check the install's `resources/app/extensions/` directory before concluding a Microsoft- or GitHub-published extension is absent.
- **Do:** read the manifest's `publisher`/`name`/`version` rather than trusting the directory name, which need not match the extension id.
- **Don't:** read an empty or short `code --list-extensions` as evidence that a named extension is not present -- it is evidence about the marketplace set only.

## BYOK model registration lives in VS Code core, and the API key never reaches a config file

The provider plumbing is in the core workbench bundle (`resources/app/out/vs/workbench/workbench.desktop.main.js`), not in a third-party extension: `clientByokEnabled`, `hasByokModels`, `byokModelIdentifier`, and an `isBYOK` flag on model metadata are all core symbols, reached through the chat model picker's **Manage Models...** flow.

The vendor set alongside that plumbing reads, verbatim:

```js
new Set(["openai","anthropic","gemini","ollama","openrouter","azure","xai",
         "customoai","customendpoint"])
```

Note `gemini`, not `google` -- a plausible-sounding substitution that the literal refutes, which is why this was copied out rather than recalled.
The set sits beside a `"3p-extension"` marker and a `["github.copilot-chat","github.copilot"]` list, so read it as the vendor names core knows about rather than as a certified enumeration of the picker's menu.

**The key itself is not written to `settings.json`.**
Core walks the submitted model configuration, and for each property its schema marks `secret` -- `apiKey` among them -- it writes the value to the secret storage service under a generated `SECRET_KEY_PREFIX` key and substitutes an encoded reference into the stored configuration.
So the config carries a pointer and the secret lives in VS Code secret storage, backed on Windows by `%APPDATA%\Code\User\globalStorage\state.vscdb`.

The consequence is operational: **a BYOK key cannot be seeded by editing a file.**
There is no `settings.json` edit, no dotfile, no scripted install step that puts a working key in place; entering it is a UI-only action the user has to perform.
Any procedure that claims otherwise is describing the third-party extension route below, not this one.

- **Do:** register BYOK models through the chat model picker's **Manage Models...** flow, and hand the key entry to the user as a manual step.
- **Do:** copy a provider list out of the bundle when you need one, since the obvious guess for a vendor name can be wrong.
- **Don't:** look for a BYOK API key in `settings.json`, or offer to write one there -- what lands in configuration is an opaque secret-storage reference.

## `chat.agentHost.byokModels.enabled` defaults to false, so a registered model stays invisible to agent sessions

Entering the key is necessary and not sufficient.
BYOK-registered models are hidden from agent sessions until this setting is turned on, and the symptom -- a model that registered without error and then does not appear -- looks like a failed registration rather than a gate.

Read out of the same core bundle's configuration schema, with the three agent-host switches together:

| Setting | Default |
|---------|---------|
| `chat.agentHost.byokModels.enabled` | `false` |
| `chat.agentHost.claudeAgent.enabled` | `true` |
| `chat.agentHost.codexAgent.enabled` | `false` |

All three carry `tags: ["experimental","advanced"]`, so they are hidden from the settings UI's default view and have to be searched for or written into `settings.json` directly.
Being experimental, they are also the most likely entries in this file to be renamed or removed by a later VS Code release.

- **Do:** set `chat.agentHost.byokModels.enabled` to `true` in the same pass that registers a BYOK model, and say so, since the default hides the result.
- **Do:** re-read the defaults out of the bundle when they matter, rather than quoting this table -- an experimental setting's default is exactly the kind of thing a monthly release changes.
- **Don't:** diagnose a missing BYOK model as a registration failure before checking this switch.

## Which route applies is a property of the machine, not a preference

Two routes reach the same outcome and they are not interchangeable:

- **Personal machine** -- built-in Copilot Chat plus core BYOK, per this file.
  No extra extension to install.
- **Work machine** -- the `johnny-zhao.oai-compatible-copilot` ("OAICopilot") extension against a Databricks Model Serving endpoint list, per the [`register-oaicopilot-models`](../skills/register-oaicopilot-models/SKILL.md) skill.

Confirmed on 2026-08-23 that `johnny-zhao.oai-compatible-copilot` is **not** installed on the personal machine, and that its user `settings.json` is 344 bytes -- far too small to hold an `oaicopilot.models` array.
So invoking `rom` here would edit a config for an extension that is not there.

The two routes' vocabularies overlap almost completely -- both say "Copilot Chat", "model picker", "Manage Models...", "register a model", "API key" -- so a procedure written for one reads as applicable to the other.
Settle it by checking which extension is installed, not by matching the words in the request.

- **Do:** check for the OAICopilot extension before applying its procedure, and fall to the core-BYOK route when it is absent.
- **Don't:** treat "register these models in Copilot" as naming a route; the phrase fits both, and only the installed extension set decides.

(Measured 2026-08-23; tracked as [ai-config#2064](https://github.com/Morrison-Lab/ai-config/issues/2064).)
