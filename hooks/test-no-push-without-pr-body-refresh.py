#!/usr/bin/env python3
"""Regression test for no-push-without-pr-body-refresh.py (ai-config#5871)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-push-without-pr-body-refresh.py")


def prompt(text="go"):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def call(name, **inputs):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inputs}]}}


def result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


PUSH = call("Bash", command="git push -u origin claude/x")
PUSH_C = call("Bash", command="git -C /repo push origin HEAD")
MCP_PUSH = call("mcp__github__push_files", owner="o", repo="r", branch="b", files=[])
EDIT_BODY = call("mcp__github__update_pull_request", owner="o", repo="r", pullNumber=1, body="x")
EDIT_TITLE = call("mcp__github__update_pull_request", owner="o", repo="r", pullNumber=1, title="t")
EDIT_OTHER = call("mcp__github__update_pull_request", owner="o", repo="r", pullNumber=1, draft=False)
CREATE = call("mcp__github__create_pull_request", owner="o", repo="r", title="t", head="b", base="main")
GH_EDIT = call("Bash", command="gh pr edit 12 --body-file /tmp/b.md")
GH_EDIT_LABEL = call("Bash", command="gh pr edit 12 --add-label P2")
GH_PATCH = call("Bash", command="gh api -X PATCH repos/o/r/pulls/12 -F body=@b.md")
GH_PATCH_COMMENT = call("Bash", command="gh api -X PATCH repos/o/r/pulls/comments/12 -f body=x")
GIT_LOG = call("Bash", command="git log --oneline -3")


def run(records, active=False):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.jsonl")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(r) for r in records))
        payload = json.dumps({"transcript_path": path, "session_id": "s" + str(id(records)),
                              "stop_hook_active": active})
        env = dict(os.environ, TMPDIR=tmp)
        return subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                              text=True, env=env, check=True).stdout


def check(label, records, blocks, active=False):
    out = run(records, active)
    got = bool(out.strip()) and json.loads(out).get("decision") == "block"
    assert got == blocks, f"{label}: got {out!r}"
    print(f"PASS: {label}")


check("git push with no body edit blocks", [prompt(), PUSH, result()], True)
check("git -C push with no body edit blocks", [prompt(), PUSH_C, result()], True)
check("MCP push_files with no body edit blocks", [prompt(), MCP_PUSH, result()], True)
check("update_pull_request body after the push is fine", [prompt(), PUSH, result(), EDIT_BODY], False)
check("update_pull_request title after the push is fine", [prompt(), PUSH, result(), EDIT_TITLE], False)
check("update_pull_request without title or body does not count",
      [prompt(), PUSH, result(), EDIT_OTHER], True)
check("create_pull_request after the push is fine", [prompt(), PUSH, result(), CREATE], False)
check("gh pr edit --body-file after the push is fine", [prompt(), PUSH, GH_EDIT], False)
check("gh pr edit --add-label does not count", [prompt(), PUSH, GH_EDIT_LABEL], True)
check("gh api PATCH on pulls/N after the push is fine", [prompt(), PUSH, GH_PATCH], False)
check("gh api PATCH on a review comment does not count", [prompt(), PUSH, GH_PATCH_COMMENT], True)
check("a body edit before the push does not count", [prompt(), EDIT_BODY, PUSH, result()], True)
check("a push in an earlier turn is not this turn's", [prompt(), PUSH, result(), prompt("next")], False)
check("no push is silent", [prompt(), GIT_LOG], False)
check("stop_hook_active never blocks again", [prompt(), PUSH, result()], False, active=True)
print("all passed")
