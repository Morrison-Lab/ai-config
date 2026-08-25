import sys
import json
import subprocess
import os

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    tool_call = payload.get("toolCall", {})
    if tool_call.get("name") != "run_command":
        print(json.dumps({"decision": "allow"}))
        return

    command = tool_call.get("args", {}).get("CommandLine", "")
    
    # Construct Claude Code payload
    claude_payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": command
        }
    }
    
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    hooks_json_path = os.path.join(repo_root, "hooks", "hooks.json")
    
    if not os.path.exists(hooks_json_path):
        print(json.dumps({"decision": "allow"}))
        return

    try:
        with open(hooks_json_path, "r") as f:
            hooks_def = json.load(f)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return
        
    pre_tool_hooks = hooks_def.get("hooks", {}).get("PreToolUse", [])
    bash_hooks = []
    for group in pre_tool_hooks:
        if group.get("matcher") == "Bash":
            bash_hooks.extend(group.get("hooks", []))
            
    # Run each hook
    for hook in bash_hooks:
        cmd = hook.get("command")
        if not cmd:
            continue
            
        # Replace ${CLAUDE_PLUGIN_ROOT} with repo_root
        cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", repo_root)
        
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                input=json.dumps(claude_payload), 
                text=True, 
                capture_output=True,
                env=os.environ
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    hook_out = json.loads(result.stdout)
                    hso = hook_out.get("hookSpecificOutput", {})
                    if hso.get("permissionDecision") == "deny":
                        reason = hso.get("permissionDecisionReason", "Denied by Claude Code hook")
                        print(json.dumps({
                            "decision": "deny",
                            "reason": reason
                        }))
                        return
                    if hso.get("additionalContext"):
                        print(f"Warning from {hook.get('script')}: {hso.get('additionalContext')}", file=sys.stderr)
                except Exception:
                    pass
        except Exception:
            pass

    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
