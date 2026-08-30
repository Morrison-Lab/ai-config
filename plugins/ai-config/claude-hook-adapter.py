import sys
import json
import subprocess
import os
import traceback
import re

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to read payload: {exc}", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    # Determine event type and Claude payload
    event_type = None
    claude_payload = {}
    target_groups = []
    cwd = os.getcwd()

    if "toolCall" in payload:
        event_type = "PreToolUse"
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        cwd = args.get("Cwd") or cwd
        
        if tool_name == "run_command":
            claude_tool_name = "Bash"
            claude_tool_input = {"command": args.get("CommandLine", "")}
        else:
            claude_tool_name = tool_name
            claude_tool_input = args
            
        claude_payload = {
            "tool_name": claude_tool_name,
            "tool_input": claude_tool_input
        }
        target_groups = ["PreToolUse"]
        
    elif "terminationReason" in payload:
        event_type = "Stop"
        claude_payload = {
            "transcript_path": payload.get("transcriptPath", "")
        }
        target_groups = ["Stop"]
        
    elif "invocationNum" in payload:
        event_type = "PreInvocation"
        claude_payload = {
            "transcript_path": payload.get("transcriptPath", "")
        }
        target_groups = ["UserPromptSubmit"]
        
    else:
        # Fallback if unknown
        print(json.dumps({"decision": "allow"}))
        return

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
    
    if not os.path.exists(hooks_json_path):
        print(f"claude-hook-adapter: {hooks_json_path} not found", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    try:
        with open(hooks_json_path, "r") as f:
            hooks_def = json.load(f)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to load {hooks_json_path}: {exc}", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return
        
    active_hooks = []
    
    for group_name in target_groups:
        groups = hooks_def.get("hooks", {}).get(group_name, [])
        for group in groups:
            matcher = group.get("matcher")
            if matcher and event_type == "PreToolUse":
                if not re.match(f"^{matcher}$", claude_payload.get("tool_name", "")):
                    continue
            active_hooks.extend(group.get("hooks", []))
            
    # Track results to merge
    injected_messages = []
    stop_reasons = []
    
    # Run each hook
    for hook in active_hooks:
        cmd = hook.get("command")
        if not cmd:
            continue
            
        # Replace ${CLAUDE_PLUGIN_ROOT} with repo_root
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
                stdout_str = result.stdout.strip()
                if not stdout_str:
                    continue
                    
                if event_type == "PreToolUse":
                    try:
                        hook_out = json.loads(stdout_str)
                        hso = hook_out.get("hookSpecificOutput", {})
                        if hso.get("permissionDecision") == "deny":
                            reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
                            print(json.dumps({
                                "decision": "deny",
                                "reason": reason
                            }))
                            return
                        if hso.get("additionalContext"):
                            print(f"Warning from {hook.get('script') or cmd}: {hso.get('additionalContext')}", file=sys.stderr)
                    except Exception as exc:
                        print(f"claude-hook-adapter: failed to parse output from {cmd}: {exc}", file=sys.stderr)
                
                elif event_type == "Stop":
                    try:
                        hook_out = json.loads(stdout_str)
                        if hook_out.get("decision") == "block":
                            reason = hook_out.get("reason", "Blocked by Stop hook")
                            stop_reasons.append(reason)
                    except Exception as exc:
                        print(f"claude-hook-adapter: failed to parse output from {cmd}: {exc}", file=sys.stderr)
                
                elif event_type == "PreInvocation":
                    # For UPS, it's typically raw string output
                    injected_messages.append({"ephemeralMessage": stdout_str})

            elif result.returncode != 0:
                print(f"claude-hook-adapter: hook {cmd} failed with exit code {result.returncode}", file=sys.stderr)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

        except subprocess.TimeoutExpired:
            print(f"claude-hook-adapter: hook {cmd} timed out after {timeout_val}s", file=sys.stderr)
        except Exception as exc:
            print(f"claude-hook-adapter: execution of {cmd} failed: {exc}", file=sys.stderr)

    # Finalize response based on event type
    if event_type == "PreToolUse":
        print(json.dumps({"decision": "allow"}))
    elif event_type == "Stop":
        if stop_reasons:
            combined_reason = "\n\n".join(stop_reasons)
            print(json.dumps({"decision": "continue", "reason": combined_reason}))
        else:
            print(json.dumps({"decision": "allow"}))
    elif event_type == "PreInvocation":
        if injected_messages:
            print(json.dumps({"injectSteps": injected_messages}))
        else:
            print(json.dumps({}))

if __name__ == "__main__":
    main()
