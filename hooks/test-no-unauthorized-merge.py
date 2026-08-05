#!/usr/bin/env python3
"""Test the no-unauthorized-merge guard.

Must live in a file rather than a Bash heredoc so test runner (scripts/test_hooks.py)
can invoke it directly with sys.argv[1].
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else str(Path(__file__).parent / "no-unauthorized-merge.py")

if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")

BLOCK = [
    ("gh pr merge 411 --squash", "bare gh pr merge"),
    ('bash -c "gh pr merge 411 --squash"', "subshell bash -c gh pr merge inside double quotes"),
    ("sh -c 'gh pr merge 411 --squash'", "subshell sh -c gh pr merge inside single quotes"),
    ("eval \"gh pr merge 411\"", "eval string execution gh pr merge"),
    ("gh pr \\\n merge 411 --squash", "backslash-newline line continuation gh pr merge"),
    ("gh pr me\\\nrge 411 --squash", "mid-word backslash-newline continuation gh pr merge"),
    ('(gh pr merge 411)', "parenthesized subshell gh pr merge"),
    ('gh pr comment 123 --body "hi"\ngh pr merge 999', "multiline script: comment on line 1, merge on line 2"),
    ('gh pr comment 123 --body "Line 1\nLine 2\nLine 3"\ngh pr merge 999', "multiline comment body with multiple newlines before merge command"),
    ('gh pr comment 123 --body "updating status && checking CI"; gh pr merge 411 --squash', "multiline body with && followed by merge command"),
    ('gh pr comment 123 --body "foo; bar"; gh pr merge 411', "body with semicolon followed by merge command"),
    ('gh pr comment 123 --body "hi";gh pr merge 999', "semicolon without trailing space before merge command"),
    ("gh -R owner/repo pr merge 411 --squash", "gh pr merge with -R flag before subcommands"),
    ('gh -R "owner name/repo" pr merge 411', "gh pr merge with quoted repo containing spaces"),
    ("gh pr -R owner/repo merge 411 --squash", "gh pr merge with -R flag between pr and merge"),
    ("gh --repo owner/repo pr merge 411", "gh pr merge with --repo flag before subcommands"),
    ("/usr/bin/gh pr merge 411", "full executable path"),
    ("env gh pr merge 411", "env wrapper prefix"),
    ("exec gh pr merge 411", "exec wrapper prefix"),
    ("command gh pr merge 411", "command wrapper prefix"),
    ("echo $(gh pr merge 411)", "subshell command substitution"),
    ("glab mr merge 12", "glab mr merge"),
    ("glab -R owner/repo mr merge 12", "glab mr merge with -R flag before subcommands"),
    ("glab mr --repo owner/repo merge 12", "glab mr merge with --repo flag between mr and merge"),
    ("gh api -X PUT /repos/owner/repo/pulls/123/merge", "gh api PR merge with integer ID and PUT method"),
    ("gh api -X put /repos/owner/repo/pulls/123/merge", "gh api PR merge with lowercase put method"),
    ("gh api --method post /repos/owner/repo/pulls/123/merge", "gh api PR merge with lowercase --method post"),
    ('gh api --method PUT "/repos/owner/repo/pulls/123/merge"', "gh api PR merge with double-quoted URL and method PUT"),
    ("gh api --method PUT '/repos/owner/repo/pulls/123/merge'", "gh api PR merge with single-quoted URL and method PUT"),
    ("gh api -X POST /repos/owner/repo/merges -f base=main -f head=feature", "gh api repository merges API endpoint"),
    ("gh api -X PUT /repos/owner/repo/pulls/$PR_NUM/merge", "gh api PR merge with shell variable ID"),
    ("gh api -X PUT /repos/owner/repo/pulls/${PR_NUM}/merge", "gh api PR merge with braced shell variable ID"),
    ("gh api -X PUT repos/owner/repo/pulls/$(echo 123)/merge", "gh api PR merge with subshell PR number"),
    ("gh api graphql -f query='mutation { mergePullRequest(input: {...}) }'", "gh api GraphQL PR merge mutation with -f flag"),
    ("gh api graphql -f query='mutation { enablePullRequestAutoMerge(input: {...}) }'", "gh api GraphQL auto-merge mutation"),
    ("glab api -X PUT projects/1/merge_requests/2/merge", "glab api MR merge endpoint"),
    ("echo foo && gh pr merge 123", "compound command with merge segment"),
    ('gh pr merge 123 --body "ALLOW_MERGE=1"', "ALLOW_MERGE inside --body string argument"),
    ('gh pr merge 123 --subject "ALLOW_MERGE=1"', "ALLOW_MERGE inside unmasked custom flag argument"),
    ("gh pr merge 123 # ALLOW_MERGE=1", "ALLOW_MERGE inside trailing shell comment"),
]

ALLOW = [
    ("gh pr view 411", "read-only gh pr view"),
    ("gh api /repos/owner/repo/pulls/123/merge", "read-only REST GET PR merge status check"),
    ("gh pr checkout merge", "checking out branch named merge"),
    ("gh pr list --label merge", "listing PRs with label merge"),
    ("gh search prs --label merge", "searching PRs with label merge"),
    ("grep \"gh pr merge\" README.md", "grep search for gh pr merge string in docs"),
    ("git log --grep \"gh pr merge\"", "git log search for gh pr merge"),
    ("gh pr comment 123 --body-file /tmp/gh-pr-merge-notes.txt", "unquoted body-file path containing hyphens and merge keyword"),
    ('gh pr comment 123 --body "He said \\"gh pr merge\\""', "comment with escaped quotes around trigger text"),
    ('gh api /repos/owner/repo/issues/1/comments -f body="Discussing gh pr merge command"', "gh api -f body payload containing trigger text"),
    ('gh pr merge 123 --body "Merging PR" --allow-merge', "--allow-merge flag after quoted --body string"),
    ('gh pr merge 123 --body "Fix #1156" --allow-merge', "--allow-merge after body containing #"),
    ("gh pr comment 1157 --body \"This hook blocks unauthorized\ngh pr merge attempts.\"", "multiline body string containing trigger text across newlines"),
    ("gh pr comment 411 --body 'gh pr merge failed'", "quoted string containing trigger text"),
    ("gh pr comment 411 --body 'ALLOW_MERGE=1 in comment body'", "ALLOW_MERGE inside string argument"),
    ("ALLOW_MERGE=1 gh pr merge 411 --squash", "explicit ALLOW_MERGE=1 env flag"),
    ('ALLOW_MERGE="1" gh pr merge 411 --squash', "explicit ALLOW_MERGE=\"1\" env flag with double quotes"),
    ("ALLOW_MERGE='1' gh pr merge 411 --squash", "explicit ALLOW_MERGE='1' env flag with single quotes"),
    ("echo ALLOW_MERGE=1 && gh pr view 411", "ALLOW_MERGE in benign command"),
]


def verdict(cmd: str, env: dict = None) -> str:
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True,
        text=True,
        env=env,
    )
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode} on {cmd!r}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"


wrong = 0
print("should BLOCK:")
for cmd, desc in BLOCK:
    v = verdict(cmd)
    wrong += (v != "BLOCK")
    print(f"  {v:<6} {desc}")

print("\nshould ALLOW:")
for cmd, desc in ALLOW:
    v = verdict(cmd)
    wrong += (v != "allow")
    print(f"  {v:<6} {desc}")

# Test active MWC grant integration and session isolation with sanitized session IDs
script_path = Path(__file__).parent.parent / "skills" / "session-lock" / "scripts" / "ai-session.sh"
session_a = f"session:mwc-a/{os.getpid()}"
session_b = f"session:mwc-b/{os.getpid()}"

subprocess.run([str(script_path), "register", "--id", session_a], check=True, capture_output=True)
subprocess.run([str(script_path), "register", "--id", session_b], check=True, capture_output=True)
subprocess.run([str(script_path), "enable-mwc", "--id", session_a], check=True, capture_output=True)

try:
    # Session A (sanitized) has MWC enabled -> allowed
    env_a = dict(os.environ, AI_SESSION_ID=session_a)
    v_a = verdict("gh pr merge 411 --squash", env=env_a)
    wrong += (v_a != "allow")
    print(f"  {v_a:<6} active MWC grant for sanitized session A")

    # Session B (sanitized) does NOT have MWC enabled -> blocked (cross-session isolation)
    env_b = dict(os.environ, AI_SESSION_ID=session_b)
    v_b = verdict("gh pr merge 411 --squash", env=env_b)
    wrong += (v_b != "BLOCK")
    print(f"  {v_b:<6} cross-session isolation for sanitized session B")

    # Disable MWC for Session A -> must block immediately
    subprocess.run([str(script_path), "disable-mwc", "--id", session_a], check=True, capture_output=True)
    v_a_revoked = verdict("gh pr merge 411 --squash", env=env_a)
    wrong += (v_a_revoked != "BLOCK")
    print(f"  {v_a_revoked:<6} revoked MWC grant blocks for session A")
finally:
    subprocess.run([str(script_path), "release", "--id", session_a], check=True, capture_output=True)
    subprocess.run([str(script_path), "release", "--id", session_b], check=True, capture_output=True)

total = len(BLOCK) + len(ALLOW) + 3
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
