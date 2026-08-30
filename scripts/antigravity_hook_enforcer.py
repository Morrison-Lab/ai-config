#!/usr/bin/env python3
"""Antigravity hook enforcement daemon.
Continuously monitors Antigravity logs and runs the repository's 
Stop hooks against new messages.
"""
import os
import sys
import time
import json
import subprocess

def notify(title, message):
    """Fire a macOS native notification."""
    subprocess.run([
        "osascript", 
        "-e", "on run argv", 
        "-e", "display notification item 1 of argv with title item 2 of argv", 
        "-e", "end run", 
        message, 
        title
    ])

def get_hooks(root):
    hooks_path = os.path.join(root, "hooks", "hooks.json")
    try:
        with open(hooks_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load hooks.json: {e}", flush=True)
        return []

    hooks = []
    for group in data.get("hooks", {}).get("Stop", []):
        hooks.extend(group.get("hooks", []))
    return hooks

def get_active_transcripts(brain_dir, max_age_seconds=86400):
    """Find all transcripts modified in the last 24 hours."""
    transcripts = []
    if not os.path.isdir(brain_dir):
        return transcripts
    try:
        dirs = os.listdir(brain_dir)
    except Exception:
        return transcripts
        
    now = time.time()
    for d in dirs:
        try:
            t = os.path.join(brain_dir, d, ".system_generated", "logs", "transcript.jsonl")
            if os.path.isfile(t):
                if now - os.stat(t).st_mtime < max_age_seconds:
                    transcripts.append(t)
        except Exception:
            continue
    return transcripts

def scan_transcripts(known_mtimes, active_transcripts, root, is_startup=False):
    hooks = get_hooks(root)
    if not hooks:
        return

    # Ensure hooks can find python3 even when run from a minimal launchd environment
    env = os.environ.copy()
    python_dir = os.path.dirname(sys.executable)
    if python_dir not in env.get("PATH", ""):
        env["PATH"] = f"{python_dir}:{env.get('PATH', '')}"

    for path in active_transcripts:
        try:
            mtime = os.stat(path).st_mtime
        except Exception:
            continue
            
        if path not in known_mtimes:
            known_mtimes[path] = mtime
            if is_startup:
                continue
            
        elif mtime <= known_mtimes[path]:
            continue
            
        known_mtimes[path] = mtime
        
        payload = {"transcript_path": path}
        payload_str = json.dumps(payload)
        for hook in hooks:
            cmd = hook.get("command", "")
            if not cmd: continue
            cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", root)
            try:
                result = subprocess.run(cmd, shell=True, input=payload_str, text=True, capture_output=True, timeout=10, env=env)
                if result.returncode == 0 and result.stdout:
                    try:
                        out = json.loads(result.stdout)
                        script = hook.get("script", "guard")
                        
                        if out.get("decision") == "block":
                            reason = out.get("reason", "Hook violation")
                            print(f"BLOCK ({script}): {reason}", flush=True)
                            notify(f"Agent Hook Violation: {script}", reason)
                            
                        if "systemMessage" in out:
                            sys_msg = out["systemMessage"]
                            print(f"WARN ({script}): {sys_msg}", flush=True)
                            notify(f"Agent Hook Warning: {script}", sys_msg)
                            
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"Failed to run hook {cmd}: {e}", flush=True)

def main():
    print("Starting Antigravity hook enforcer daemon...", flush=True)
    known_mtimes = {}
    last_full_scan = 0
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    brain_dir = os.path.expanduser("~/.gemini/antigravity/brain")
    
    # Initial scan
    active_transcripts = get_active_transcripts(brain_dir)
    scan_transcripts(known_mtimes, active_transcripts, root, is_startup=True)
    last_full_scan = time.time()
    
    while True:
        now = time.time()
        # Full scan every 60 seconds
        if now - last_full_scan > 60:
            active_transcripts = get_active_transcripts(brain_dir)
            # Prune known_mtimes to prevent unbounded memory leak
            known_mtimes = {p: m for p, m in known_mtimes.items() if p in active_transcripts}
            last_full_scan = now
            
        scan_transcripts(known_mtimes, active_transcripts, root, is_startup=False)
        time.sleep(1.0)

if __name__ == "__main__":
    main()
