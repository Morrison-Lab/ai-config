# Google Antigravity & `agy` CLI
<!-- vintage: 2026-08-25 -->

## Hook architecture and schema mapping

Antigravity defines lifecycle events in `plugins/<plugin-name>/hooks.json`.

### Lifecycle events & payload mapping
- **`PreToolUse`**: Passed `{"toolCall": {"name": "<tool_name>", "args": { ... }}}`.
  Returns `{"decision": "allow" | "deny" | "ask", "reason": "..."}`.
  - In Antigravity's `hooks.json`, `PreToolUse` handlers are **grouped** under `{ "matcher": "...", "hooks": [ ... ] }`.
  - `run_command` maps to Claude Code's `Bash` tool (`{"command": args.get("CommandLine")}`).
  - `invoke_subagent` passes an array `{"Subagents": [{"TypeName": "...", "Workspace": "...", "Prompt": "..."}]}`.
    A bridge adapter evaluates all subagents in the list against `Agent` PreToolUse hooks.
    If any subagent triggers `deny`, the whole tool execution is denied.
  - `send_message` maps to `SendMessage`.
  - `define_subagent` maps to `Task`.
- **`Stop`**: Fired on termination attempt (`{"terminationReason": "model_stop", "transcriptPath": "..."}`).
  - In Antigravity's `hooks.json`, `Stop` handlers are **flat** (a direct list of `{ "type": "command", "command": "..." }` objects without `matcher`/`hooks` wrappers), per Antigravity hook specifications.
  - To prevent termination (e.g. when unfulfilled obligations or unreviewed commits exist), Antigravity expects `{"decision": "continue", "reason": "..."}`.
    Any other value (or `{"decision": "allow"}`) allows termination.
  - Claude hooks in `hooks/hooks.json` are grouped and output `{"decision": "block", "reason": "..."}`;
    an adapter must translate `block` to `continue`.
- **`PreInvocation`**: Fired before prompt evaluation (`{"invocationNum": N}`).
  - In Antigravity's `hooks.json`, `PreInvocation` handlers are also **flat**.
  - Context injection in Antigravity uses `{"injectSteps": [{"ephemeralMessage": "..."}]}`.
  - Claude `UserPromptSubmit` hooks output raw text to stdout;
    an adapter wraps non-empty text in `injectSteps`, joining multiple hook outputs with `\n\n`.

### Silent failure prevention
Harness bridge adapters must be gated by isolated unit tests in CI (`validate.yml`, e.g. `scripts/test_agy_hook_adapter.py`).
Because an incomplete adapter simply returns `{"decision": "allow"}` when it misses an event,
adapter gaps fail silently in production unless tested against synthetic payloads.

## `agy` CLI model execution & print mode

- Model names in `agy --model` must match the registered string format,
  e.g. `agy --model "Claude Sonnet 4.6 (Thinking)" -p "<prompt>"`.
- Print mode (`-p` / `--print`) runs a single turn.
  When prompting reasoning/thinking models (such as Claude Thinking models or reasoning Gemini models) non-interactively without tool access,
  enforce immediate output in the prompt (e.g., "Provide your full review immediately in this response; do not use tools or acknowledge with a conversational promise").
  Otherwise, tool-using models may output an initial conversational acknowledgment expecting a subsequent tool-use turn.
