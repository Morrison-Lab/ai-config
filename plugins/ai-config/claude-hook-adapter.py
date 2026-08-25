import sys
import json
import subprocess
import os
import traceback

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"claude-hook-adapter: failed to read payload: {exc}", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    tool_call = payload.get("toolCall", {})
    if tool_call.get("name") != "run_command":
        print(json.dumps({"decision": "allow"}))
        return

    args = tool_call.get("args", {})
    command = args.get("CommandLine", "")
    cwd = args.get("Cwd") or os.getcwd()
    
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
                        print(f"Warning from {hook.get('script') or cmd}: {hso.get('additionalContext')}", file=sys.stderr)
                except Exception as exc:
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

    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
