import sys
import json
import subprocess
import os
import re

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
        if result.returncode != 0 and result.stderr:
            print(f"claude-hook-adapter: hook exited with code {result.returncode}: {result.stderr}", file=sys.stderr)
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
    if matcher_pattern == "*" or matcher_pattern == ".*":
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
    """Support both grouped ({'hooks': [...]}) and flat ([{'command': ...}]) hook lists."""
    out = []
    if not isinstance(groups_or_hooks, list):
        return out
    for item in groups_or_hooks:
        if isinstance(item, dict):
            if "hooks" in item and isinstance(item["hooks"], list):
                out.extend(item["hooks"])
            elif "command" in item:
                out.append(item)
    return out

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to read payload: {exc}", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    # Determine Antigravity event type
    event_type = None
    if "toolCall" in payload:
        event_type = "PreToolUse"
    elif "terminationReason" in payload:
        event_type = "Stop"
    elif "invocationNum" in payload:
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
        cwd = args.get("Cwd") or repo_root
        
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
                    tasks_to_run.append((extract_hook_list([group]), bash_payload))

        elif tool_name == "invoke_subagent":
            subagents = args.get("Subagents") or []
            for sub in subagents:
                agent_payload = {
                    "tool_name": "Agent",
                    "tool_input": {
                        "subagent_type": sub.get("TypeName"),
                        "isolation": sub.get("Workspace"),
                        "prompt": sub.get("Prompt")
                    }
                }
                if transcript_path:
                    agent_payload["transcript_path"] = transcript_path
                for group in pre_tool_groups:
                    if matches_tool(group.get("matcher", ""), "Agent"):
                        tasks_to_run.append((extract_hook_list([group]), agent_payload))

        elif tool_name == "send_message":
            send_payload = {
                "tool_name": "SendMessage",
                "tool_input": {
                    "recipient": args.get("Recipient"),
                    "message": args.get("Message")
                }
            }
            if transcript_path:
                send_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), "SendMessage"):
                    tasks_to_run.append((extract_hook_list([group]), send_payload))

        elif tool_name == "define_subagent":
            task_payload = {
                "tool_name": "Task",
                "tool_input": {
                    "name": args.get("name"),
                    "description": args.get("description"),
                    "system_prompt": args.get("system_prompt")
                }
            }
            if transcript_path:
                task_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), "Task"):
                    tasks_to_run.append((extract_hook_list([group]), task_payload))

        else:
            generic_payload = {
                "tool_name": tool_name,
                "tool_input": args
            }
            if transcript_path:
                generic_payload["transcript_path"] = transcript_path
            for group in pre_tool_groups:
                if matches_tool(group.get("matcher", ""), tool_name):
                    tasks_to_run.append((extract_hook_list([group]), generic_payload))

        # Execute PreToolUse hooks; if ANY hook denies, block tool execution immediately
        for hooks_list, c_payload in tasks_to_run:
            for hook in hooks_list:
                cmd = hook.get("command")
                if not cmd:
                    continue
                cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
                timeout_val = parse_timeout(hook.get("timeout")) or 30.0
                
                result = run_hook_command(cmd, c_payload, cwd, timeout_val)
                if result and result.returncode == 0 and result.stdout:
                    try:
                        hook_out = json.loads(result.stdout)
                        hso = hook_out.get("hookSpecificOutput", {})
                        if hso.get("permissionDecision") == "deny":
                            reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
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
            timeout_val = parse_timeout(hook.get("timeout")) or 30.0
            
            result = run_hook_command(cmd, stop_payload, repo_root, timeout_val)
            if result and result.returncode == 0 and result.stdout:
                try:
                    hook_out = json.loads(result.stdout)
                    decision = str(hook_out.get("decision", "")).strip().lower()
                    if decision == "block":
                        reason = hook_out.get("reason", "Blocked by Stop hook")
                        print(json.dumps({"decision": "continue", "reason": reason}))
                        return
                except Exception as exc:
                    print(f"claude-hook-adapter: failed to parse output: {exc}", file=sys.stderr)

        # Standard Antigravity response to allow stopping is an empty JSON object
        print(json.dumps({}))
        return

    elif event_type == "PreInvocation":
        ups_groups = hooks_def.get("hooks", {}).get("UserPromptSubmit", [])
        ups_payload = {
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
            timeout_val = parse_timeout(hook.get("timeout")) or 30.0
            
            result = run_hook_command(cmd, ups_payload, repo_root, timeout_val)
            if result and result.returncode == 0 and result.stdout:
                text_out = result.stdout.strip()
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
