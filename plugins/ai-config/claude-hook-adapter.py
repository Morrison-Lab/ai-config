import sys
import json
import subprocess
import os

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
    hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
    
    if not os.path.exists(hooks_json_path):
        print(f"claude-hook-adapter: {hooks_json_path} not found", file=sys.stderr)
        if event_type == "PreInvocation":
            print(json.dumps({"injectSteps": []}))
        else:
            print(json.dumps({"decision": "allow"}))
        return

    try:
        with open(hooks_json_path, "r") as f:
            hooks_def = json.load(f)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to load {hooks_json_path}: {exc}", file=sys.stderr)
        if event_type == "PreInvocation":
            print(json.dumps({"injectSteps": []}))
        else:
            print(json.dumps({"decision": "allow"}))
        return

    hooks_to_run = []
    claude_payload = payload.copy()
    
    # Map common fields
    claude_payload["transcript_path"] = payload.get("transcriptPath")
    cwd = os.getcwd()

    if event_type == "PreToolUse":
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        cwd = args.get("Cwd") or os.getcwd()
        
        pre_tool_groups = hooks_def.get("hooks", {}).get("PreToolUse", [])
        
        if tool_name == "run_command":
            claude_payload["tool_name"] = "Bash"
            claude_payload["tool_input"] = {"command": args.get("CommandLine", "")}
            for group in pre_tool_groups:
                if group.get("matcher") == "Bash":
                    hooks_to_run.extend(group.get("hooks", []))
                    
        elif tool_name == "invoke_subagent":
            claude_payload["tool_name"] = "Agent"
            subagents = args.get("Subagents", [])
            first_sub = subagents[0] if subagents else {}
            claude_payload["tool_input"] = {
                "subagent_type": first_sub.get("TypeName"),
                "isolation": first_sub.get("Workspace"),
                "prompt": first_sub.get("Prompt")
            }
            for group in pre_tool_groups:
                if group.get("matcher") == "Agent":
                    hooks_to_run.extend(group.get("hooks", []))
                    
        elif tool_name == "send_message":
            claude_payload["tool_name"] = "SendMessage"
            claude_payload["tool_input"] = args
            for group in pre_tool_groups:
                if group.get("matcher") == "SendMessage":
                    hooks_to_run.extend(group.get("hooks", []))
                    
        elif tool_name == "define_subagent":
            claude_payload["tool_name"] = "Task"
            claude_payload["tool_input"] = args
            for group in pre_tool_groups:
                if group.get("matcher") == "Task":
                    hooks_to_run.extend(group.get("hooks", []))
                    
        elif tool_name.startswith("mcp__github__"):
            claude_payload["tool_name"] = tool_name
            claude_payload["tool_input"] = args
            for group in pre_tool_groups:
                if group.get("matcher") == "mcp__github__.*":
                    hooks_to_run.extend(group.get("hooks", []))
                    
    elif event_type == "Stop":
        stop_groups = hooks_def.get("hooks", {}).get("Stop", [])
        for group in stop_groups:
            hooks_to_run.extend(group.get("hooks", []))
            
    elif event_type == "PreInvocation":
        ups_groups = hooks_def.get("hooks", {}).get("UserPromptSubmit", [])
        for group in ups_groups:
            hooks_to_run.extend(group.get("hooks", []))

    # Run the matched hooks
    injected_messages = []
    
    for hook in hooks_to_run:
        cmd = hook.get("command")
        if not cmd:
            continue
            
        cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
        
        timeout_val = hook.get("timeout")
        if timeout_val is not None:
            try:
                timeout_val = float(timeout_val)
            except ValueError:
                timeout_val = None

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
            
            if result.returncode == 0 and result.stdout:
                if event_type == "PreInvocation":
                    # Claude UserPromptSubmit hooks usually just print text
                    text_out = result.stdout.strip()
                    if text_out:
                        injected_messages.append(text_out)
                else:
                    try:
                        hook_out = json.loads(result.stdout)
                        
                        if event_type == "PreToolUse":
                            hso = hook_out.get("hookSpecificOutput", {})
                            if hso.get("permissionDecision") == "deny":
                                reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
                                print(json.dumps({"decision": "deny", "reason": reason}))
                                return
                            if hso.get("additionalContext"):
                                print(f"Warning from {hook.get('script') or cmd}: {hso.get('additionalContext')}", file=sys.stderr)
                                
                        elif event_type == "Stop":
                            # Claude Stop hook block means we must continue
                            if hook_out.get("decision") == "block":
                                reason = hook_out.get("reason", "Blocked by Stop hook")
                                print(json.dumps({"decision": "continue", "reason": reason}))
                                return
                    except Exception as exc:
                        if event_type == "PreInvocation":
                            injected_messages.append(result.stdout.strip())
                        else:
                            print(f"claude-hook-adapter: failed to parse output from {cmd}: {exc}", file=sys.stderr)
                            if result.stderr:
                                print(f"stderr was: {result.stderr}", file=sys.stderr)
            elif result.returncode != 0:
                print(f"claude-hook-adapter: hook {cmd} failed with exit code {result.returncode}", file=sys.stderr)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

        except subprocess.TimeoutExpired:
            print(f"claude-hook-adapter: hook {cmd} timed out after {timeout_val}s", file=sys.stderr)
        except Exception as exc:
            print(f"claude-hook-adapter: execution of {cmd} failed: {exc}", file=sys.stderr)

    if event_type == "PreInvocation":
        if injected_messages:
            steps = [{"ephemeralMessage": "\n\n".join(injected_messages)}]
            print(json.dumps({"injectSteps": steps}))
        else:
            print(json.dumps({"injectSteps": []}))
    else:
        print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
