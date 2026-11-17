#!/usr/bin/env python3
"""Tests for hooks/no-merge-queue-claim-in-post-message.py (ai-config#5754).

Run: python3 hooks/test-no-merge-queue-claim-in-post-message.py
"""
import importlib.util
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
ENQUEUED = transcript("You are a Thread Session.", '{"name": "mcp__github__enable_pr_auto_merge"}\n')
AUTO_CLI = transcript("You are a Thread Session.", "gh pr merge 12 --squash --auto\n")


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
