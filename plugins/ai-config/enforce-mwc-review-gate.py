import sys
import json
import subprocess
import re

def main():
    payload = json.load(sys.stdin)
    tool_call = payload.get("toolCall", {})
    if tool_call.get("name") != "run_command":
        print(json.dumps({"decision": "allow"}))
        return

    args = tool_call.get("args", {})
    cmd = args.get("CommandLine", "")
    cwd = args.get("Cwd", ".")
    
    # Check if this is a merge command
    if not re.search(r'\b(gh pr merge|gh stack merge|git merge origin/main)\b', cmd):
        print(json.dumps({"decision": "allow"}))
        return
        
    # Block chained commands that include merge. Merging must be done as a standalone command
    # so we can reliably inspect the state of the PR before the command executes.
    if ";" in cmd or "&&" in cmd:
        print(json.dumps({
            "decision": "deny",
            "reason": "Merge commands (gh pr merge, etc) must be executed sequentially on their own. Do not chain them with other commands like 'gh pr create ; gh pr merge' because the hook cannot dynamically evaluate the PR's review status mid-execution."
        }))
        return
    
    try:
        pr_match = re.search(r'gh (?:pr|stack) merge (\S+)', cmd)
        pr_arg = pr_match.group(1) if pr_match else ""
        if pr_arg and pr_arg.startswith("-"):
            pr_arg = ""
        
        view_cmd = ["gh", "pr", "view", pr_arg, "--json", "reviews,comments"] if pr_arg else ["gh", "pr", "view", "--json", "reviews,comments"]
        result = subprocess.run(view_cmd, cwd=cwd, capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            reviews = data.get("reviews", [])
            comments = data.get("comments", [])
            
            has_human_review = any(r.get("author", {}).get("login") != "claude" and "bot" not in r.get("author", {}).get("login", "").lower() for r in reviews)
            
            # Check for bot approvals in comments (e.g. Claude Code, OpenCode)
            has_ai_approval = False
            for c in comments:
                body = c.get("body", "").upper()
                if re.search(r"\b(VERDICT: GREEN|READY FOR MERGE|APPROVE(D|S)?)\b", body) and not re.search(r"\b(NOT\s+(VERDICT: GREEN|READY FOR MERGE|APPROVE(D|S)?)|DISAPPROVE(D|S)?|UNAPPROVED?)\b", body):
                    # Make sure it is from a bot
                    author_login = c.get("author", {}).get("login", "")
                    if "bot" in author_login.lower() or author_login in ["github-actions", "claude"]:
                        has_ai_approval = True
                        break
            

            # If no reviews, or if Claude didn't review and no human reviewed
            if not has_human_review and not has_ai_approval and len(reviews) == 0:
                print(json.dumps({
                    "decision": "deny",
                    "reason": "Strict Merge Control Policy: AI reviewer skipped or deadlocked, and no human review is present. You cannot use mwc to bypass the review boundary. Request human review from the repository owner."
                }))
                return
        else:
            # gh pr view failed (e.g. PR doesn't exist)
            print(json.dumps({
                "decision": "deny",
                "reason": f"Hook failed to fetch PR reviews (gh pr view returned non-zero). Ensure the PR exists and is checked out. Output: {result.stderr}"
            }))
            return
            
    except Exception as e:
        print(json.dumps({
            "decision": "deny",
            "reason": f"Hook exception during PR review check: {str(e)}"
        }))
        return

    # Default: allow if we passed the checks (has human review or AI passed)
    print(json.dumps({"decision": "allow"}))

if __name__ == '__main__':
    main()
