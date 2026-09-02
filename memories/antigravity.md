# Google Antigravity & `agy` CLI

Claims below about Antigravity's runtime behavior were checked 2026-08-26 unless a claim carries its own date.
Re-verify against a live install before relying on any of them, since the primary docs were egress-blocked from this session.

## Hook architecture and schema mapping

Antigravity defines lifecycle events in `plugins/<plugin-name>/hooks.json`.

### `extensionPath` is not supported in command paths

A `command` value is resolved against the terminal's active working directory, not against the plugin's own directory --- and Antigravity has a known bug where that cwd can default to `$HOME` regardless of which project is open.
A relative command such as `python3 ./claude-hook-adapter.py` therefore fails to launch under conditions this repo cannot control, which fails open: no Stop, PreInvocation, or catalog PreToolUse hook runs at all, silently.

Unlike Claude Code, Antigravity does **not** interpolate variables like
`${extensionPath}` or `${CLAUDE_PLUGIN_ROOT}` in `hooks.json` commands.
Commands in `hooks.json` must use absolute paths
or a path relative to a stable directory like `~/.gemini/config/plugins/...`.
(Empirical finding verified on macOS 2026-08-29: Antigravity expands `~` when launching the command).
For example, `ai-config` uses
`~/.gemini/config/plugins/ai-config/claude-hook-adapter.py`
backed by a staging directory created in `bootstrap.sh`.

### Lifecycle events & payload mapping
- **`PreToolUse`**: Passed `{"toolCall": {"name": "<tool_name>", "args": { ... }}}`.
  Returns `{"decision": "allow" | "deny" | "ask", "reason": "..."}`.
  - In Antigravity's `hooks.json`, `PreToolUse` handlers are **grouped** under `{ "matcher": "...", "hooks": [ ... ] }`.
  - The plugin's `PreToolUse` list carries **two** groups rather than one, deliberately: a `"run_command"` group (literal matcher, unchanged since before this split) carrying `enforce-mwc-review-gate.py` and `claude-hook-adapter.py`, and a second group matched on the regex alternation `"invoke_subagent|send_message|define_subagent|mcp__github__.*"` carrying only `claude-hook-adapter.py`.
    Whether Antigravity treats `matcher` as a regex at all is unverified (2026-08-26), so the split is a de-risking measure: if that assumption is wrong, only the second group's coverage (the newer tool names) fails to fire, and the pre-existing `run_command` merge-control gate --- matched literally, so it does not depend on regex support --- is unaffected.
  - The second group's `mcp__github__.*` alternative assumes Antigravity names MCP tool calls with Claude Code's `mcp__<server>__<tool>` convention.
    That is unverified (2026-08-26): the confirmed Antigravity `toolCall.name` values are only `run_command`, `invoke_subagent`, `send_message`, and `define_subagent`, so if the real MCP names differ, the `mcp__github__.*` branch silently never fires --- re-verify against a live install before relying on it as a gate.
  - `run_command` maps to Claude Code's `Bash` tool (`{"command": args.get("CommandLine")}`).
  - `invoke_subagent` passes an array `{"Subagents": [{"TypeName": "...", "Workspace": "...", "Prompt": "..."}]}`.
    A bridge adapter evaluates all subagents in the list against `Agent` PreToolUse hooks.
    If any subagent triggers `deny`, the whole tool execution is denied.
  - `send_message` maps to `SendMessage`.
  - `define_subagent` maps to `Task`.
  - Claude PreToolUse hooks may also return a top-level `systemMessage` (shown to the user, independent of the `hookSpecificOutput.permissionDecision` deny/allow verdict).
    Antigravity's `PreToolUse` schema does not support this top-level field, so the adapter never forwards it directly.
    On deny it is concatenated into `reason`.
    On allow it is logged to stderr only.
- **`Stop`**: Fired on termination attempt (`{"terminationReason": "model_stop", "transcriptPath": "..."}`).
  - In Antigravity's `hooks.json`, `Stop` handlers are **flat** (a direct list of `{ "type": "command", "command": "..." }` objects without `matcher`/`hooks` wrappers), per Antigravity hook specifications.
  - To prevent termination (e.g. when unfulfilled obligations or unreviewed commits exist), Antigravity expects `{"decision": "continue", "reason": "..."}`.
    Any other value (or `{"decision": "allow"}`) allows termination.
  - `systemMessage` is a **top-level** field accepted on every Claude Code hook event (confirmed in Claude Code's own hooks docs), independent of `decision`.
    Antigravity's own Stop event is reported to surface it as a warning in the interface, per the same secondary-source synthesis checked 2026-08-26.
    That surfacing behavior is unconfirmed against a live install, since the primary docs were egress-blocked from this session --- re-verify before relying on it.
    A warn-only Stop hook (no block/deny decision) still allows the stop, but its message rides along as `{"systemMessage": "..."}` rather than reaching only stderr.
  - Claude hooks in `hooks/hooks.json` are grouped and output `{"decision": "block", "reason": "..."}`.
    An adapter must translate `block` to `continue`.
- **`PreInvocation`**: Fired before the model call.
  Its documented input fields are `invocationNum`, `initialNumSteps`, `conversationId`, `workspacePaths`, `transcriptPath`, and `artifactDirectoryPath` --- **no prompt text field at all**.
  A seventh field, `modelName`, is an inference from secondary-source synthesis (checked 2026-08-26), not shown in the example payload those sources reproduce --- treat it as unconfirmed.
  The adapter's `prompt` extraction (`prompt` / `userPrompt` / `message`, then a `messages` scan for an explicit user/human-authored entry) is therefore a defensive fallback for a payload shape not observed in production, not a mapping of a documented field.
  Expect `prompt` to be empty on a real Antigravity invocation unless a future payload version adds one.
  The scan never falls back to an arbitrary last message regardless of role, since that could silently substitute the model's own prior turn for the user's prompt.
  - In Antigravity's `hooks.json`, `PreInvocation` handlers are also **flat**.
  - Context injection in Antigravity uses `{"injectSteps": [{"ephemeralMessage": "..."}]}`.
  - Claude `UserPromptSubmit` hooks may output raw text, or JSON carrying a `systemMessage`/`additionalContext` field, to stdout.
    The adapter parses JSON when present (falling back to the raw text otherwise), reading `systemMessage`, top-level `additionalContext`, or the nested `hookSpecificOutput.additionalContext` form, and emits one `ephemeralMessage` `injectSteps` entry per hook --- it does not join multiple hooks' output into a single joined string.
    The caps default to 10KB per message, 30KB total, and 20 messages, and are overridable via `AGY_ADAPTER_MSG_BYTE_CAP`, `AGY_ADAPTER_TOTAL_BYTE_CAP`, and `AGY_ADAPTER_MSG_CAP` (the subagent fanout cap is `AGY_ADAPTER_FANOUT_CAP`, default 50).

### Fail-open on a hook subprocess timeout or crash is intentional, not a gap

A catalog hook that times out or raises inside `subprocess.run` is skipped, and execution proceeds as if that hook had not run.
This matches Claude Code's own documented behavior for a command-hook PreToolUse timeout: the hook is killed and Claude continues, since command hooks only block via an explicit exit-code-2 (or a JSON deny) response, never via failing to answer.
Every hook actually shipped in this repo's catalog (`hooks/*.py`) signals a deny via JSON with exit 0, never via exit code 2, so this fail-open path is reached only by a genuine timeout, crash, or missing script --- never by a hook's own deliberate denial being silently discarded.

### Silent failure prevention
Harness bridge adapters must be gated by isolated unit tests in CI (`validate.yml`, e.g. `scripts/test_agy_hook_adapter.py`).
Because an incomplete adapter simply returns `{"decision": "allow"}` when it misses an event, adapter gaps fail silently in production unless tested against synthetic payloads.

## `agy` CLI model execution & print mode

- Model names in `agy --model` must match the registered string format, e.g. `agy --model "Claude Sonnet 4.6 (Thinking)" -p "<prompt>"`.
- Print mode (`-p` / `--print`) runs a single turn.
  When prompting reasoning/thinking models (such as Claude Thinking models or reasoning Gemini models) non-interactively without tool access, enforce immediate output in the prompt (e.g., "Provide your full review immediately in this response.
  Do not use tools or acknowledge with a conversational promise.").
  Otherwise, tool-using models may output an initial conversational acknowledgment expecting a subsequent tool-use turn.

## The merge gate is client-side only, and client hooks fail open --- server rules are the only enforcement that survives a delivery failure

Measured 2026-08-30 (Morrison-Lab/ai-config#2676): agy merged Lacaedemon/sparta#1427 over a "Needs more work" verdict.
Replaying the exact command against `plugins/ai-config/enforce-mwc-review-gate.py` returned deny, so the gate's deny never took effect in the merging session --- either the hook was not launched (this file's own fail-open section: a hook that fails to launch is skipped silently) or its deny was discarded by an adapter gap, and no artifact distinguishes the two.
Three layers had to fail together, and each is worth checking separately when auditing a bad merge:

1. **Client hook delivery.**
   No artifact records whether a hook ran;
   absence of a deny is not evidence of an allow decision.
2. **Gate logic.**
   Fix and 61 hermetic test cases are in ai-config#2678 (open as of 2026-08-30);
   the pre-rewrite gate allowed any PR carrying at least one formal review, whatever the verdict said.
3. **Server rules.**
   `require-review` (gha) is delivery-only by design --- it greens when a review ran and posted, saying nothing about the verdict (its own header comment states this).
   A ruleset with no required status checks (sparta's `main` at the time) blocks nothing.
   Opt-in verdict gating is proposed as Morrison-Lab/gha#767;
   sparta's required checks as Lacaedemon/sparta#1432.

- **Do:** treat required status checks in the ruleset as the enforcement layer, and the client hook as UX that catches the mistake earlier.
- **Don't:** read a green `require-review` as a clean verdict, or a quiet client hook as having allowed the merge.

## Forensics: agy conversations are sqlite DBs, and plugins.json points at the live checkout

- IDE sessions: `~/.gemini/antigravity/conversations/*.db`; CLI sessions: `~/.gemini/antigravity-cli/conversations/*.db`, with prompts in `~/.gemini/antigravity-cli/history.jsonl`.
  `strings <db> | grep <needle>` recovers commands and hook decisions without a sqlite client;
  mtimes bracket the session window.
- Two path layers decide which hook code agy actually runs:
  `~/.gemini/config/plugins.json` registers the plugin in a **staging runtime directory** (`~/.gemini/config/plugins/ai-config`),
  where `hooks.json` and `plugin.json` are copied so Antigravity runtime rewrites do not dirty the git checkout.
  Executable scripts and repository directories (`hooks/`, `scripts/`, `skills/`, `shared/`) are symlinked from the checkout into the staging directory,
  so adapter and gate updates take effect live while canonical source remains pristine.
  (Updated 2026-08-31 for Issue #2673).

## Reactive wakeup vs background task polling

- In Antigravity, background commands, subagents, and schedules resume execution reactively via incoming system messages (`MESSAGE_PRIORITY_HIGH`).
- Do not poll `manage_task(Action='status')` or run repetitive checks in a loop while waiting for a long-running background command or test suite to finish.
- After launching an asynchronous task or schedule timer, end the tool turn and let the reactive system wakeup resume execution when the process exits or the timer expires.
  (Observed in live Antigravity sessions 2026-08-30.)

## Python SDK (`antigravity-sdk-python`) vs declarative plugins and CLI

The [`google-antigravity/antigravity-sdk-python`](https://github.com/google-antigravity/antigravity-sdk-python) library is the programmatic Python SDK for building, orchestrating, and embedding Antigravity agents (evaluated 2026-08-31).

- **Declarative plugin & skill boundary:**
  Antigravity IDE, Desktop 2.0, and `agy` discover skills and hooks declaratively via `plugins/ai-config/plugin.json`, `hooks.json`, and markdown skills.
  The Python SDK is designed for embedding an agent inside a custom Python application or test process, not for authoring plugin configurations or ambient agent behavior.
- **Review dispatcher parity (`pre-push-review.py`):**
  Single-turn local code review uses `agy --print` (alongside `claude`, `codex`, `cursor`, `opencode`) to tap into the user's active local CLI subscription login without extra Python runtime dependencies or API key management.
- **Future adoption trigger:**
  Evaluate adopting `antigravity-sdk-python` if building Python-native automated agent benchmarking suites, synthetic skill evaluation harnesses, or headless CI pipelines that require typed step streams and programmatic tool registration.

## Asynchronous subagent dispatch and pre-push self-review (`invoke_subagent`)

- In Antigravity / Gemini CLI, `invoke_subagent` dispatches subagents asynchronously in the background, returning `{conversationId, ...}` immediately.
- The subagent's completed report arrives as an incoming reactive message from the subagent's conversation ID, rather than as the synchronous tool step result of `invoke_subagent`.
- Consequently, client-side pre-tool hooks (such as `no-push-without-self-review.py`) that parse the direct tool-result output of the subagent tool call will not find the verdict embedded in the initial dispatch step result.
- Once the asynchronous subagent has finished and returned its verified clean review report and fingerprint, use the authorized prefix `ALLOW_UNREVIEWED_PUSH=1` for the `git push` invocation (the guard's `AGENT_TOOLS` set intentionally rejects `Bash`/`run_command` outputs to prevent unauthenticated reviews).
  (Observed in live Antigravity sessions 2026-09-01.)


