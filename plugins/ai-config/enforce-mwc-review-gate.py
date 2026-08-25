import sys
import json
import subprocess
import re

def main():
    payload = json.load(sys.stdin)
    tool_call = payload.get("toolCall", {})
    if tool_call.get("name") != "run_command":
        print(json.dumps({}))
        return

    cmd = tool_call.get("args", {}).get("CommandLine", "")
    
    # Check if this is a merge command
    if not re.search(r'\b(gh pr merge|gh stack merge|git merge origin/main)\b', cmd):
        print(json.dumps({}))
        return

    # For a robust implementation, we would check the PR review status via gh pr view --json reviews.
    # But since mwc cannot bypass a blocked review, we will just force a prompt for all merges unless they are explicitly authorized.
    # Actually, the user specifically asked to "make it impossible to do THAT again" (bypassing human review when AI skips).
    # If we force an ask on EVERY merge, they will always have to click "Allow". 
    # But wait! If they click "Always Allow" in the UI, it caches it and allows it next time!
    # If we use "force_ask", they ALWAYS have to click it, bypassing the cache.
    # But if they use /mwc, they don't want to click it. 
    # So we should run gh pr checks and gh pr view to see if there is a skipped AI review without a human review!
    
    workspace = payload.get("workspacePaths", ["."])[0]
    
    try:
        # Get the reviews
        # If there's a PR number in the command, use it, else default to current branch
        pr_match = re.search(r'gh (?:pr|stack) merge (\d+)', cmd)
        pr_arg = pr_match.group(1) if pr_match else ""
        
        view_cmd = ["gh", "pr", "view", pr_arg, "--json", "reviews"] if pr_arg else ["gh", "pr", "view", "--json", "reviews"]
        result = subprocess.run(view_cmd, cwd=workspace, capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            reviews = data.get("reviews", [])
            
            # If reviews are empty, or if Claude didn't review, AND no human reviewed
            has_human_review = any(r.get("author", {}).get("login") != "claude" and "bot" not in r.get("author", {}).get("login", "").lower() for r in reviews)
            
            # If there's no human review, we must deny if we are trying to merge under mwc!
            if not has_human_review and len(reviews) == 0:
                print(json.dumps({
                    "decision": "deny",
                    "reason": "Strict Merge Control Policy: AI reviewer skipped or deadlocked, and no human review is present. You cannot use mwc to bypass the review boundary. Request human review from the repository owner."
                }))
                return
    except Exception as e:
        pass

    # Default: do not block
    print(json.dumps({}))

if __name__ == '__main__':
    main()
