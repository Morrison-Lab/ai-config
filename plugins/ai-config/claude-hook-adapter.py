import sys
import json
import subprocess
import os
import re
import traceback

def run_hook_command(cmd, claude_payload, cwd, timeout_val):
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
            elif "command" in item:
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
    if payload.get("toolCall") is not None:
        event_type = "PreToolUse"
    elif payload.get("terminationReason") is not None:
        event_type = "Stop"
    elif payload.get("invocationNum") is not None:
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
                    print(f"claude-hook-adapter: invoke_subagent skipping non-dict subagent item: {type(sub).__name__}", file=sys.stderr)
                    continue
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
        for hooks_list, c_payload, cwd, desc in tasks_to_run:
            for hook in hooks_list:
                cmd = hook.get("command")
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
                        hso = hook_out.get("hookSpecificOutput", {})
                        if hso.get("permissionDecision") == "deny":
                            base_reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
                            reason = f"[{desc}] {base_reason}" if desc != "run_command" else base_reason
                            print(json.dumps({"decision": "deny", "reason": reason}))
                            return
                        if hso.get("additionalContext"):
                            print(f"Warning from {hook.get('script') or cmd}: {hso.get('additionalContext')}", file=sys.stderr)
                    except Exception as exc:
                        print(f"claude-hook-adapter: failed to parse output: {exc}", file=sys.stderr)

        print(json.dumps({"decision": "allow"}))
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
        for hook in hooks_to_run:
            cmd = hook.get("command")
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
                    if hook_out.get("systemMessage") or hook_out.get("additionalContext"):
                        msg = hook_out.get("systemMessage") or hook_out.get("additionalContext")
                        print(f"Warning from Stop hook: {msg}", file=sys.stderr)
                except Exception as exc:
                    print(f"claude-hook-adapter: failed to parse output: {exc}", file=sys.stderr)

        # Standard Antigravity response to allow stopping is an empty JSON object
        print(json.dumps({}))
        return

    elif event_type == "PreInvocation":
        ups_groups = hooks_def.get("hooks", {}).get("UserPromptSubmit", [])
        prompt_val = payload.get("prompt") or payload.get("userPrompt") or payload.get("message") or ""
        if not prompt_val and isinstance(payload.get("messages"), list) and payload["messages"]:
            last_msg = payload["messages"][-1]
            if isinstance(last_msg, dict):
                prompt_val = last_msg.get("content") or last_msg.get("text") or ""
            elif isinstance(last_msg, str):
                prompt_val = last_msg
                
        ups_payload = {
            "prompt": prompt_val,
            "invocation_num": payload.get("invocationNum"),
            "initial_num_steps": payload.get("initialNumSteps")
        }
        if transcript_path:
            ups_payload["transcript_path"] = transcript_path

        injected_messages = []
        hooks_to_run = extract_hook_list(ups_groups)
        for hook in hooks_to_run:
            cmd = hook.get("command")
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
                        injected_messages.append(text_out)

        if injected_messages:
            steps = [{"ephemeralMessage": msg} for msg in injected_messages]
            print(json.dumps({"injectSteps": steps}))
        else:
            print(json.dumps({"injectSteps": []}))
        return

if __name__ == "__main__":
    main()
