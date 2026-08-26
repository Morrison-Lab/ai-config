import sys
import json
import subprocess
import os
import re
import traceback

def run_hook_command(cmd, claude_payload, cwd, timeout_val):
    # A timeout or a launch exception returns None, and every caller below
    # treats that the same way native Claude Code treats a PreToolUse hook
    # timeout: the hook is skipped and execution continues as if it had
    # never run (fail-open), not as a denial. This mirrors Claude Code's own
    # documented behavior rather than diverging from it, since command hooks
    # there only block via an explicit exit-code-2 (or JSON deny) response,
    # never via failing to answer at all.
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            input=json.dumps(claude_payload), 
            text=True, 
            capture_output=True,
            env=os.environ,
            cwd=cwd,
            timeout=timeout_val
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip() if result.stderr else f"process exited with code {result.returncode}"
            print(f"claude-hook-adapter: hook failed: {err_msg}", file=sys.stderr)
        elif result.stderr:
            print(f"claude-hook-adapter: hook stderr: {result.stderr.strip()}", file=sys.stderr)
        return result
    except subprocess.TimeoutExpired:
        print(f"claude-hook-adapter: hook timed out after {timeout_val}s", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"claude-hook-adapter: execution of hook failed: {exc}", file=sys.stderr)
        return None

def matches_tool(matcher_pattern, tool_name):
    if not matcher_pattern:
        return False
    if matcher_pattern == "*":
        return True
    if matcher_pattern == tool_name:
        return True
    try:
        return bool(re.fullmatch(matcher_pattern, tool_name))
    except re.error:
        return False

def parse_timeout(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def extract_hook_list(groups_or_hooks):
    """Support grouped ({'hooks': [...]}), flat ([{'command': ...}]), and single group dicts."""
    if isinstance(groups_or_hooks, dict):
        groups_or_hooks = [groups_or_hooks]
    elif not isinstance(groups_or_hooks, list):
        return []
    out = []
    for item in groups_or_hooks:
        if isinstance(item, dict):
            if "hooks" in item and isinstance(item["hooks"], list):
                out.extend(item["hooks"])
            elif "command" in item or "script" in item:
                out.append(item)
            else:
                print(f"claude-hook-adapter: ignoring unrecognized hook item: {item}", file=sys.stderr)
    return out

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to read payload: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    # Determine Antigravity event type
    event_type = None
    if isinstance(payload.get("toolCall"), dict):
        event_type = "PreToolUse"
    elif payload.get("terminationReason") is not None:
        event_type = "Stop"
    elif isinstance(payload.get("invocationNum"), (int, float)) and not isinstance(payload.get("invocationNum"), bool):
        event_type = "PreInvocation"

    if not event_type:
        print(json.dumps({"decision": "allow"}))
        return

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    claude_hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
    
    if not os.path.exists(claude_hooks_json_path):
        print(f"claude-hook-adapter: {claude_hooks_json_path} not found", file=sys.stderr)
        if event_type == "PreInvocation":
            print(json.dumps({"injectSteps": []}))
        elif event_type == "Stop":
            print(json.dumps({}))
        else:
            print(json.dumps({"decision": "allow"}))
        return

    try:
        with open(claude_hooks_json_path, "r", encoding="utf-8") as f:
            hooks_def = json.load(f)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to load {claude_hooks_json_path}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if event_type == "PreInvocation":
            print(json.dumps({"injectSteps": []}))
        elif event_type == "Stop":
            print(json.dumps({}))
        else:
            print(json.dumps({"decision": "allow"}))
        return

    # Common fields for Claude payload
    transcript_path = payload.get("transcriptPath")

    if event_type == "PreToolUse":
        tool_call = payload.get("toolCall") or {}
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args") or {}
        tool_cwd = args.get("Cwd") or repo_root
        
        pre_tool_groups = hooks_def.get("hooks", {}).get("PreToolUse", [])
        tasks_to_run = []
        
        if tool_name == "run_command":
            bash_payload = {
                "tool_name": "Bash",
                "tool_input": {"command": args.get("CommandLine", "")}
            }
            if transcript_path:
                bash_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), "Bash"):
                    tasks_to_run.append((extract_hook_list(group), bash_payload, tool_cwd, "run_command"))

        elif tool_name == "invoke_subagent":
            raw_subagents = args.get("Subagents")
            if raw_subagents is None:
                reason = "invoke_subagent missing required 'Subagents' argument"
                print(json.dumps({"decision": "deny", "reason": reason}))
                return
            if isinstance(raw_subagents, dict):
                raw_subagents = [raw_subagents]
            elif isinstance(raw_subagents, str):
                try:
                    parsed_sub = json.loads(raw_subagents)
                    raw_subagents = [parsed_sub] if isinstance(parsed_sub, dict) else parsed_sub
                except Exception as exc:
                    reason = f"invoke_subagent received malformed JSON string for Subagents: {exc}"
                    print(json.dumps({"decision": "deny", "reason": reason}))
                    return
            if raw_subagents is not None and not isinstance(raw_subagents, list):
                reason = f"invoke_subagent Subagents argument must be a list (received {type(raw_subagents).__name__})"
                print(json.dumps({"decision": "deny", "reason": reason}))
                return
            subagents = raw_subagents if isinstance(raw_subagents, list) else []
            if len(subagents) > 50:
                reason = f"invoke_subagent exceeded maximum supported fanout limit of 50 subagents (received {len(subagents)})"
                print(json.dumps({"decision": "deny", "reason": reason}))
                return
            for idx, sub in enumerate(subagents):
                if not isinstance(sub, dict):
                    reason = f"invoke_subagent Subagents item at index {idx} must be an object (received {type(sub).__name__})"
                    print(json.dumps({"decision": "deny", "reason": reason}))
                    return
                agent_name = sub.get("TypeName") or sub.get("typeName") or f"subagent_{idx}"
                agent_payload = {
                    "tool_name": "Agent",
                    "tool_input": {
                        "subagent_type": sub.get("TypeName") or sub.get("typeName"),
                        "isolation": sub.get("Workspace") or sub.get("workspace"),
                        "prompt": sub.get("Prompt") or sub.get("prompt")
                    }
                }
                if transcript_path:
                    agent_payload["transcript_path"] = transcript_path
                for group in pre_tool_groups:
                    if matches_tool(group.get("matcher", ""), "Agent"):
                        tasks_to_run.append((extract_hook_list(group), agent_payload, repo_root, f"invoke_subagent ({agent_name})"))

        elif tool_name == "send_message":
            send_payload = {
                "tool_name": "SendMessage",
                "tool_input": {
                    "recipient": args.get("Recipient") or args.get("recipient"),
                    "message": args.get("Message") or args.get("message")
                }
            }
            if transcript_path:
                send_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), "SendMessage"):
                    tasks_to_run.append((extract_hook_list(group), send_payload, repo_root, "send_message"))

        elif tool_name == "define_subagent":
            task_payload = {
                "tool_name": "Task",
                "tool_input": {
                    "name": args.get("name") or args.get("Name"),
                    "description": args.get("description") or args.get("Description"),
                    "system_prompt": args.get("system_prompt") or args.get("systemPrompt") or args.get("SystemPrompt")
                }
            }
            if transcript_path:
                task_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), "Task"):
                    tasks_to_run.append((extract_hook_list(group), task_payload, repo_root, "define_subagent"))

        else:
            generic_payload = {
                "tool_name": tool_name,
                "tool_input": args
            }
            if transcript_path:
                generic_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), tool_name):
                    tasks_to_run.append((extract_hook_list(group), generic_payload, repo_root, tool_name))

        # Execute PreToolUse hooks; if ANY hook denies, block tool execution immediately
        system_messages = []
        for hooks_list, c_payload, cwd, desc in tasks_to_run:
            for hook in hooks_list:
                cmd = hook.get("command") or hook.get("script")
                if not cmd:
                    continue
                cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
                timeout_val = parse_timeout(hook.get("timeout"))
                if timeout_val is None:
                    timeout_val = 30.0

                result = run_hook_command(cmd, c_payload, cwd, timeout_val)
                if result and result.returncode == 0 and result.stdout:
                    try:
                        hook_out = json.loads(result.stdout)
                        # systemMessage is a top-level field Claude Code hooks
                        # may return on every event, shown to the user rather
                        # than fed back to the model; forward it regardless
                        # of the deny/allow decision below.
                        if hook_out.get("systemMessage"):
                            system_messages.append(str(hook_out.get("systemMessage")))
                        hso = hook_out.get("hookSpecificOutput", {})
                        if hso.get("permissionDecision") == "deny":
                            base_reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
                            reason = f"[{desc}] {base_reason}" if desc != "run_command" else base_reason
                            deny_response = {"decision": "deny", "reason": reason}
                            if system_messages:
                                deny_response["systemMessage"] = "\n\n".join(system_messages)
                            print(json.dumps(deny_response))
                            return
                        if hso.get("additionalContext"):
                            print(f"Warning from {hook.get('script') or cmd}: {hso.get('additionalContext')}", file=sys.stderr)
                    except Exception as exc:
                        print(f"claude-hook-adapter: failed to parse output: {exc}", file=sys.stderr)

        allow_response = {"decision": "allow"}
        if system_messages:
            allow_response["systemMessage"] = "\n\n".join(system_messages)
        print(json.dumps(allow_response))
        return

    elif event_type == "Stop":
        stop_groups = hooks_def.get("hooks", {}).get("Stop", [])
        stop_payload = {
            "termination_reason": payload.get("terminationReason"),
            "fully_idle": payload.get("fullyIdle"),
            "error": payload.get("error")
        }
        if transcript_path:
            stop_payload["transcript_path"] = transcript_path
            
        hooks_to_run = extract_hook_list(stop_groups)
        warn_messages = []
        for hook in hooks_to_run:
            cmd = hook.get("command") or hook.get("script")
            if not cmd:
                continue
            cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
            timeout_val = parse_timeout(hook.get("timeout"))
            if timeout_val is None:
                timeout_val = 30.0

            result = run_hook_command(cmd, stop_payload, repo_root, timeout_val)
            if result and result.returncode == 0 and result.stdout:
                try:
                    hook_out = json.loads(result.stdout)
                    decision = str(hook_out.get("decision", "")).strip().lower()
                    if decision in ("block", "deny"):
                        reason = hook_out.get("reason", "Blocked by Stop hook")
                        print(json.dumps({"decision": "continue", "reason": reason}))
                        return
                    msg = hook_out.get("systemMessage") or hook_out.get("additionalContext")
                    if msg:
                        warn_messages.append(str(msg))
                except Exception as exc:
                    print(f"claude-hook-adapter: failed to parse output: {exc}", file=sys.stderr)

        # A warn-only Stop hook (no block/deny decision) still allows the
        # agent to stop, but its message is forwarded via the top-level
        # systemMessage field -- shown to the user in Antigravity's
        # interface on every event, independent of `decision` -- rather
        # than dropped after only reaching stderr. No warning still allows
        # stopping via the standard empty JSON object.
        if warn_messages:
            print(json.dumps({"systemMessage": "\n\n".join(warn_messages)}))
        else:
            print(json.dumps({}))
        return

    elif event_type == "PreInvocation":
        ups_groups = hooks_def.get("hooks", {}).get("UserPromptSubmit", [])
        # Antigravity's documented PreInvocation payload carries no prompt
        # text at all (invocationNum, initialNumSteps, conversationId,
        # workspacePaths, transcriptPath, artifactDirectoryPath, modelName),
        # so "prompt" / "userPrompt" / "message" and this "messages" scan
        # are defensive fallbacks for a payload shape this adapter has not
        # observed in production, not a documented field. The scan only
        # accepts an entry explicitly authored by the user; it never falls
        # back to the last entry regardless of role, since that can silently
        # substitute the model's own prior turn for the user's prompt.
        prompt_val = payload.get("prompt") or payload.get("userPrompt") or payload.get("message") or ""
        if not prompt_val and isinstance(payload.get("messages"), list):
            for msg in reversed(payload["messages"]):
                if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
                    prompt_val = msg.get("content") or msg.get("text") or ""
                    break

        if isinstance(prompt_val, list):
            prompt_val = " ".join(str(p.get("text", p) if isinstance(p, dict) else p) for p in prompt_val)
        elif not isinstance(prompt_val, str):
            prompt_val = str(prompt_val)

        ups_payload = {
            "prompt": prompt_val,
            "invocation_num": payload.get("invocationNum"),
            "initial_num_steps": payload.get("initialNumSteps")
        }
        if transcript_path:
            ups_payload["transcript_path"] = transcript_path

        injected_messages = []
        total_injected_bytes = 0
        hooks_to_run = extract_hook_list(ups_groups)
        for hook in hooks_to_run:
            if len(injected_messages) >= 20:
                break
            cmd = hook.get("command") or hook.get("script")
            if not cmd:
                continue
            cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
            timeout_val = parse_timeout(hook.get("timeout"))
            if timeout_val is None:
                timeout_val = 30.0
            
            result = run_hook_command(cmd, ups_payload, repo_root, timeout_val)
            if result and result.returncode == 0 and result.stdout:
                text_out = result.stdout.strip()
                if text_out:
                    try:
                        parsed = json.loads(text_out)
                        if isinstance(parsed, dict):
                            text_out = parsed.get("systemMessage") or parsed.get("additionalContext") or ""
                    except Exception:
                        pass
                    if text_out:
                        # Cap single injected message at 10KB (in UTF-8 bytes) and total cumulative bytes at 30KB
                        raw_bytes = text_out.encode("utf-8")[:10000]
                        chunk = raw_bytes.decode("utf-8", errors="ignore")
                        chunk_bytes = len(chunk.encode("utf-8"))
                        if total_injected_bytes + chunk_bytes <= 30000:
                            injected_messages.append(chunk)
                            total_injected_bytes += chunk_bytes
                        elif total_injected_bytes < 30000:
                            remaining_bytes = 30000 - total_injected_bytes
                            encoded_trimmed = chunk.encode("utf-8")[:remaining_bytes]
                            trimmed_chunk = encoded_trimmed.decode("utf-8", errors="ignore")
                            injected_messages.append(trimmed_chunk)
                            total_injected_bytes += len(trimmed_chunk.encode("utf-8"))

        if injected_messages:
            steps = [{"ephemeralMessage": msg} for msg in injected_messages[:20]]
            print(json.dumps({"injectSteps": steps}))
        else:
            print(json.dumps({"injectSteps": []}))
        return

if __name__ == "__main__":
    main()
