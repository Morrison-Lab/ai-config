# Google Antigravity & `agy` CLI

## Hook architecture and schema mapping

Antigravity defines lifecycle events in `plugins/<plugin-name>/hooks.json`.

### Lifecycle events & payload mapping
- **`PreToolUse`**: Passed `{"toolCall": {"name": "<tool_name>", "args": { ... }}}`. Returns `{"decision": "allow" | "deny" | "ask", "reason": "..."}`.
  - `run_command` maps to Claude Code's `Bash` tool (`{"command": args.get("CommandLine")}`).
  - `invoke_subagent` passes an array `{"Subagents": [{"TypeName": "...", "Workspace": "...", "Prompt": "..."}]}`. A bridge adapter must evaluate all subagents in the list against agent policies (e.g., `flag-unassigned-worktree.py`).
  - `send_message` maps to `SendMessage`.
  - `define_subagent` maps to `Task`.
- **`Stop`**: Fired on termination attempt (`{"terminationReason": "model_stop", "transcriptPath": "..."}`).
  - To prevent termination (e.g. when unfulfilled obligations or unreviewed commits exist), Antigravity expects `{"decision": "continue", "reason": "..."}`.
  - Claude hooks output `{"decision": "block", "reason": "..."}`; an adapter must translate `block` to `continue`.
- **`PreInvocation`**: Fired before prompt evaluation (`{"invocationNum": N}`).
  - Context injection in Antigravity uses `{"injectSteps": [{"ephemeralMessage": "..."}]}`.
  - Claude `UserPromptSubmit` hooks output raw text to stdout; an adapter wraps non-empty text in `injectSteps`.

### Silent failure prevention
Harness bridge adapters must be gated by isolated unit tests in CI (`validate.yml`, e.g. `scripts/test_agy_hook_adapter.py`). Because an incomplete adapter simply returns `{"decision": "allow"}` when it misses an event, adapter gaps fail silently in production unless tested against synthetic payloads.

## `agy` CLI model execution & print mode

- Model names in `agy --model` must match the registered string format, e.g. `agy --model "Claude Sonnet 4.6 (Thinking)" -p "<prompt>"`.
- Print mode (`-p` / `--print`) runs a single turn. When prompting reasoning/thinking models (such as Claude Thinking models or reasoning Gemini models) non-interactively without tool access, enforce immediate output in the prompt (e.g., "Provide your full review immediately in this response; do not use tools or acknowledge with a conversational promise"). Otherwise, tool-using models may output an initial conversational acknowledgment expecting a subsequent tool-use turn.
