#!/usr/bin/env python3
"""Tests for hooks/no-merge-queue-claim-in-post-message.py (ai-config#5754).

Run: python3 hooks/test-no-merge-queue-claim-in-post-message.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-merge-queue-claim-in-post-message.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
passes = failures = 0


def transcript(first_line, extra=""):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write(first_line + "\n" + extra)
    f.close()
    return f.name


THREAD = transcript("You are a Thread Session.")
OTHER = transcript("You are the coordinator.")


def tool_use_line(name, tool_input):
    block = {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}
    return json.dumps({"type": "assistant", "message": {"content": [block]}}) + "\n"


def tool_result_line(text):
    block = {"type": "tool_result", "tool_use_id": "toolu_1", "content": text}
    return json.dumps({"type": "user", "message": {"content": [block]}}) + "\n"


ENQUEUED = transcript("You are a Thread Session.",
                      tool_use_line("mcp__github__enable_pr_auto_merge", {"pullNumber": 12}))
AUTO_CLI = transcript("You are a Thread Session.",
                      tool_use_line("Bash", {"command": "gh pr merge 12 --squash --auto"}))
CCR_AUTO = transcript("You are a Thread Session.",
                      tool_use_line("Bash", {"command": "gh api -X PUT repos/o/r/pulls/12/ccr/auto_merge"}))
POST_QUOTING = transcript("You are a Thread Session.",
                          tool_use_line(POST, {"text": "Not enqueued: no gh pr merge 12 --auto ran."}))
OWN_DENIAL =transcript("You are a Thread Session.", tool_result_line(hook.REASON))
BARE_MENTION = transcript("You are a Thread Session.",
                          '{"name": "mcp__github__enable_pr_auto_merge"}\ngh pr merge 12 --squash --auto\n')


def denied(text, tool=POST, tpath=THREAD, env=None):
    os.environ.pop(hook.OVERRIDE, None)
    if env:
        os.environ[hook.OVERRIDE] = env
    out = hook.denial({"tool_name": tool, "tool_input": {"text": text}, "transcript_path": tpath})
    os.environ.pop(hook.OVERRIDE, None)
    return out is not None


def check(name, cond):
    global passes, failures
    passes += bool(cond)
    failures += not cond
    print(("PASS: " if cond else "FAIL: ") + name)


check("thread saying it went into the merge queue is denied", denied("lds#2687 has gone into the merge queue."))
check("hyphenated merge-queue is denied", denied("It is in the merge-queue now."))
check("capitalized Merge Queue is denied", denied("Merge Queue: yes."))
check("the denial names the true wording", "waits on a merge in the runner" in hook.REASON)
check("coordinator is never blocked", not denied("It is in the merge queue.", tpath=OTHER))
check("an enable_pr_auto_merge call lets it through", not denied("It is in the merge queue.", tpath=ENQUEUED))
check("gh pr merge --auto lets it through", not denied("It is in the merge queue.", tpath=AUTO_CLI))
check("a ccr/auto_merge request lets it through", not denied("It is in the merge queue.", tpath=CCR_AUTO))
check("the hook's own earlier denial does not unlock a retry",
      denied("It is in the merge queue.", tpath=OWN_DENIAL))
check("a non-Bash tool_use quoting gh pr merge --auto does not unlock it",
      denied("It is in the merge queue.", tpath=POST_QUOTING))
check("a bare mention outside a tool_use block does not unlock it",
      denied("It is in the merge queue.", tpath=BARE_MENTION))
check("text without the phrase passes", not denied("Final head sent on; it waits on a merge in the runner."))
check("a different tool is ignored", not denied("merge queue", tool="Bash"))
check("override env lets it through", not denied("merge queue", env="1"))
check("unreadable transcript fails open", not denied("merge queue", tpath="/nonexistent/t.jsonl"))
check("non-dict payload fails open", hook.denial("oops") is None)

res = subprocess.run([sys.executable, SCRIPT], input="not json", capture_output=True, encoding="utf-8")
check("malformed stdin exits 0 quietly", res.returncode == 0 and not res.stdout.strip())

for p in (THREAD, OTHER, ENQUEUED, AUTO_CLI):
    os.unlink(p)
print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
