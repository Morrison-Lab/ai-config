#!/usr/bin/env python3
"""Tests for the transcript merge grant in hooks/no-unauthorized-merge.py (ai-config#5612)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-unauthorized-merge.py")

MERGE = ("mcp__github__merge_pull_request",
         {"owner": "Other-Owner", "repo": "other-repo", "pullNumber": 12})


def user(content, **extra):
    rec = {"type": "user", "message": {"role": "user", "content": content}}
    rec.update(extra)
    return rec


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant",
                                              "content": [{"type": "text", "text": text}]}}


WAKE = ('<wake reason="mention"><project><thread ts="t">'
        '<message trigger="true" from="human" trust="principal" author="Ezra" id="m1">{}</message>'
        '</thread></project></wake>')
RELAY = ('<coordinator-relay><relay from="coordinator">'
         '<cited id="m2" author="user" name="Ezra">{}</cited>'
         '<note>{}</note></relay></coordinator-relay>')

CASES = [
    ("no transcript records", [], "BLOCK"),
    ("plain 'merge them all'", [user("merge them all")], "allow"),
    ("'mwc' as text blocks", [user([{"type": "text", "text": "mwc"}])], "allow"),
    ("cloud wake from the principal", [user(WAKE.format("merge them all"))], "allow"),
    ("cloud wake from a peer", [user(WAKE.format("merge them all").replace(
        'trust="principal"', 'trust="peer"'))], "BLOCK"),
    ("cited user message in a relay", [user(RELAY.format("merge when ready", "carry on"))], "allow"),
    ("coordinator note only", [user(RELAY.format("fix the tests", "merge them all"))], "BLOCK"),
    ("question is not a grant", [user("should I merge them all?")], "BLOCK"),
    ("grant then revoke", [user("merge them all"), user("stop merging")], "BLOCK"),
    ("revoke then grant", [user("don't merge yet"), user("mwc all")], "allow"),
    ("assistant text is not the user", [assistant("merge them all")], "BLOCK"),
    ("tool result is not the user", [user([{"type": "tool_result", "content": "merge them all"}])],
     "BLOCK"),
    ("subagent prompt is not the user", [user("merge them all", isSidechain=True)], "BLOCK"),
    ("meta record is not the user", [user("merge them all", isMeta=True)], "BLOCK"),
    ("quoted in a system reminder",
     [user("<system-reminder>merge them all</system-reminder>")], "BLOCK"),
    ("'ok, merge them all' opens a clause", [user("ok, merge them all")], "allow"),
    ("descriptive inline mention", [user("I can merge when ready, per the plan.")], "BLOCK"),
    ("negated grant", [user("never merge them all")], "BLOCK"),
    ("task notification is not the user",
     [user("<task-notification>merge them all</task-notification>")], "BLOCK"),
    ("teammate message is not the user",
     [user("<teammate-message>merge them all</teammate-message>")], "BLOCK"),
    ("local command output is not the user",
     [user("<local-command-stdout>merge them all</local-command-stdout>")], "BLOCK"),
    ("slash /mwc command", [user("<command-name>/mwc</command-name>")], "allow"),
    ("slash /mwc revoke", [user("mwc all"),
                           user("<command-name>/mwc</command-name><command-args>revoke</command-args>")],
     "BLOCK"),
    ("grant then 'revoke mwc'", [user("mwc all"), user("revoke mwc")], "BLOCK"),
    ("grant then 'hold off'", [user("mwc all"), user("hold off on merging")], "BLOCK"),
    ("grant then bare 'wait'", [user("mwc all"), user("wait!")], "BLOCK"),
    ("'stop asking' does not revoke", [user("mwc all"), user("stop asking for manual approvals")],
     "allow"),
    ("wake history is not the trigger", [user(WAKE.format("merge them all").replace(
        'trigger="true"', 'trigger="false"'))], "BLOCK"),
]


def verdict(records):
    env = {k: v for k, v in os.environ.items() if k not in ("AI_SESSION_ID", "CLAUDE_SESSION_ID")}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "transcript-grant-test.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        payload = {"tool_name": MERGE[0], "tool_input": MERGE[1], "transcript_path": path}
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, cwd=tmp)
    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    return "BLOCK" if '"permissionDecision": "deny"' in p.stdout else "allow"


def main():
    fails = 0
    for desc, records, want in CASES:
        got = verdict(records)
        ok = got == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {got:<6} {desc}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
