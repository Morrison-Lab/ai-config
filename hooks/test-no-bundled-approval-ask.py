#!/usr/bin/env python3
"""Tests for hooks/no-bundled-approval-ask.py (ai-config#4875).

Run: python3 hooks/test-no-bundled-approval-ask.py [hooks/no-bundled-approval-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-bundled-approval-ask.py")
POST = "mcp__hearthbot__post_message"
DEC = "mcp__hearthbot__request_decision"
RC = "mcp__hearthbot__start_remote_control"

CASES = [
    ("runners plus ssh key", POST,
     {"text": "May I add two more CI runners? Also, may I use the ssh key ~/.ssh/id_ed25519_condor to submit jobs?"}, True),
    ("two plain asks", POST,
     {"text": "Shall I rebase the branch? Can I also delete the old branch?"}, True),
    ("credential ask plus second question", POST,
     {"text": "I need your approval to use the API token for the upload. Do you want me to rerun the build too?"}, True),
    ("decision card bundling key", DEC,
     {"question": "May I add runners and may I use the condor ssh key?",
      "options": [{"label": "Yes", "consequence": "Both happen"}, {"label": "No", "consequence": "Neither"}]}, True),
    ("rc brief cites yes for both", RC,
     {"message_id": "m", "instructions": "Ezra said yes, which covers both: add the runners and use the ssh key."}, True),
    ("rc brief cites yes with credential", RC,
     {"message_id": "m", "instructions": "Ezra approved this. Use the condor ssh key to submit jobs."}, True),
    ("single ask", POST, {"text": "May I add two more CI runners on cf463-01?"}, False),
    ("single credential ask", POST, {"text": "May I use the ssh key ~/.ssh/id_ed25519_condor to submit jobs?"}, False),
    ("exempt: bare yes covers only first", POST,
     {"text": "May I add runners? May I also use the key? A bare yes covers only the first."}, False),
    ("status report", POST, {"text": "I added the runners and submitted the jobs. All green."}, False),
    ("mwc ask", POST, {"text": "Type `mwc` and I merge all three."}, False),
    ("rc brief without yes", RC, {"message_id": "m", "instructions": "Run the tests on cf463-02 and report."}, False),
    ("rc brief exempt wording", RC,
     {"message_id": "m", "instructions": "Ezra said yes, which covers only the first: add the runners. Separately, use the condor ssh key as already allow-listed."}, False),
    ("rc brief routine allow-listed credential", RC,
     {"message_id": "m", "instructions": "Ezra approved adding the runners. Use the already-allow-listed API token to run the nightly script as usual."}, False),
    ("rc brief says no approval is needed", RC,
     {"message_id": "m", "instructions": "The job will use the API token to authenticate; no user approval is needed."}, False),
    ("rc brief negated approval still denied for a bundle", RC,
     {"message_id": "m", "instructions": "No approval is required for this. It covers both: add runners and use the condor ssh key as agreed."}, True),
    ("rc brief cites yes for one action", RC,
     {"message_id": "m", "instructions": "Ezra said yes to adding the runners. Add them."}, False),
    ("quoted code ignored", POST,
     {"text": "Fixed.\n```\nMay I? May I? May I?\n```"}, False),
    ("unrelated tool", "Bash", {"command": "May I? May I?"}, False),
]


def run(tool, tool_input):
    payload = {"tool_name": tool, "tool_input": tool_input}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, tool_input, deny in CASES:
        rc, out = run(tool, tool_input)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
