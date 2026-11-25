#!/usr/bin/env python3
"""Tests for hooks/require-ums-before-resolve.py (ai-config#4480).

Run: python3 hooks/test-require-ums-before-resolve.py [path-to-hook]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "require-ums-before-resolve.py")
RESOLVE = "mcp__hearthbot__set_thread_resolved"


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def result():
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


def run(records, payload_extra, sentinel_dir, times=1):
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    outs = []
    try:
        for _ in range(times):
            payload = dict(payload_extra, transcript_path=tpath)
            p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                               capture_output=True, text=True,
                               env=dict(os.environ, TMPDIR=sentinel_dir))
            if p.returncode != 0:
                sys.exit(f"FATAL: exit {p.returncode}\n{p.stderr}")
            outs.append(p.stdout.strip())
    finally:
        os.unlink(tpath)
    return outs if times > 1 else outs[0]


def resolve(resolved=True, thread=None):
    """A thread resolving itself by default; `thread` makes it a resolve by id."""
    inp = {"resolved": resolved}
    if thread:
        inp["thread_id"] = thread
    return {"hook_event_name": "PreToolUse", "tool_name": RESOLVE, "tool_input": inp}


failures = 0


def check(desc, ok):
    global failures
    failures += not ok
    print(f"  {'ok' if ok else 'WRONG':<6} {desc}")


def fresh():
    return tempfile.mkdtemp()


work = [user("fix the bug"), tool("Edit", {"file_path": "/r/x.py"})]
print("PreToolUse on set_thread_resolved:")
sd = fresh()
out = run(work, resolve(), sd)
check("denied when no UMS since the last user message", '"deny"' in out)
sd = fresh()
outs = run(work, resolve(), sd, times=2)
check("second attempt is denied too (ai-config#6027)", '"deny"' in outs[0] and '"deny"' in outs[1])


def read(thread, report, uid="r1", older=None, newer_status=False, raw=None):
    """A read_thread call and its result, in the shape the hearthbot tool returns.

    `raw` replaces the whole result text, for malformed-result cases.
    """
    msgs = [{"author": "agent", "created_at": "2026-11-20T09:55:43Z", "body": report}]
    if older:
        msgs.append({"author": "agent", "created_at": "2026-11-20T08:00:00Z", "body": older})
    if newer_status:
        msgs.insert(0, {"author": "agent", "created_at": "2026-11-20T09:59:00Z",
                        "body": '{"kind":"status","text":"checklist"}'})
    text = raw if raw is not None else "Untrusted content follows.\n<wrap>" + json.dumps(
        {"thread_id": thread, "messages": msgs}) + "</wrap>"
    call = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": uid, "name": "mcp__hearthbot__read_thread",
         "input": {"thread_id": thread}}]}}
    res = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": uid, "content": [{"type": "text", "text": text}]}]}}
    return [call, res]


print("Coordinator resolving another thread by id:")
done = "Stopping Point: clean. UMS executed: recorded the hook quirk."
check("allowed after reading that thread's UMS report",
      run(work + read("cmsg_A", done), resolve(thread="cmsg_A"), fresh()) == "")
check("a report read from a different thread does not count",
      '"deny"' in run(work + read("cmsg_B", done), resolve(thread="cmsg_A"), fresh()))
check("a read with no UMS report line does not count",
      '"deny"' in run(work + read("cmsg_A", "PR is open, UMS run is owed"),
                      resolve(thread="cmsg_A"), fresh()))
check("a report read before the last user message does not count",
      '"deny"' in run(read("cmsg_A", done) + work, resolve(thread="cmsg_A"), fresh()))
check("a stale report in an older reply does not count",
      '"deny"' in run(work + read("cmsg_A", "Pushed the fix.", older=done),
                      resolve(thread="cmsg_A"), fresh()))
check("a newer checklist card does not hide the report",
      run(work + read("cmsg_A", done, newer_status=True), resolve(thread="cmsg_A"), fresh()) == "")
check("the caller's own UMS does not stand in for the thread's",
      '"deny"' in run(work + [tool("Skill", {"skill": "ums"})], resolve(thread="cmsg_A"), fresh()))
for desc, raw in [
    ("not JSON", "UMS executed: but no JSON envelope"),
    ("truncated JSON", '{"thread_id": "cmsg_A", "messages": [{"author": "agent", "body": "UMS executed: x"'),
    ("a non-list messages value", '{"thread_id": "cmsg_A", "messages": 7}'),
    ("a true messages value", '{"thread_id": "cmsg_A", "messages": true}'),
]:
    check(f"a read_thread result with {desc} denies (fails closed)",
          '"deny"' in run(work + read("cmsg_A", "", raw=raw), resolve(thread="cmsg_A"), fresh()))
for prose in ("No UMS executed yet.", "Wait until UMS completed before resolving.",
              "UMS executed later, maybe"):
    check(f"prose {prose!r} is not a report",
          '"deny"' in run(work + read("cmsg_A", prose), resolve(thread="cmsg_A"), fresh()))
check("a report after a sentence on the same line counts",
      run(work + read("cmsg_A", "PR is up. UMS executed: nothing to record."),
          resolve(thread="cmsg_A"), fresh()) == "")
check("the by-id deny tells the coordinator to read the thread",
      "read_thread" in run(work, resolve(thread="cmsg_A"), fresh()))
check("a thread's own resolve (no thread_id) gets the run-ums deny",
      "end your reply" in run(work, {"hook_event_name": "PreToolUse", "tool_name": RESOLVE,
                                     "tool_input": {"resolved": True}}, fresh()))
sd = fresh()
check("a different thread is refused again",
      '"deny"' in run(work, resolve(thread="cmsg_A"), sd)
      and '"deny"' in run(work, resolve(thread="cmsg_B"), sd))
for desc, rec in [
    ("Skill ums", tool("Skill", {"skill": "ums"})),
    ("Agent prompt naming UMS", tool("Agent", {"prompt": "Run UMS on this thread"})),
    ("Bash invoking update-memories-and-skills", tool("Bash", {"command": "echo update memories"})),
    ("Write under ai-config", tool("Write", {"file_path": "/h/ai-config/shared/x.md"})),
    ("invoke_subagent with Subagents list", tool("invoke_subagent", {"Subagents": [{"Prompt": "Run UMS"}]})),
    # Spellings the shared scripts/lib/tool_names.py added (ai-config#3740).
    ("invoke_subagent with a JSON-object Subagents string",
     tool("invoke_subagent", {"Subagents": '{"Prompt": "Run UMS"}'})),
    ("spawn_agent prompt naming UMS", tool("spawn_agent", {"prompt": "Run UMS"})),
    ("PowerShell command", tool("PowerShell", {"command": "echo update memories"})),
    ("NotebookEdit under ai-config",
     tool("NotebookEdit", {"notebook_path": "/h/ai-config/shared/x.ipynb"})),
    ("edit_file with Cursor's filePath", tool("edit_file", {"filePath": "/h/ai-config/memories/x.md"})),
    ("Antigravity PLANNER_RESPONSE invoke_subagent",
     {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [
         {"name": "invoke_subagent", "args": {"Subagents": [{"Prompt": "Run UMS"}]}}]}),
]:
    check(f"allowed after {desc}", run(work + [rec], resolve(), fresh()) == "")
skill_body = {"type": "user", "isMeta": True, "sourceToolUseID": "x",
              "message": {"content": [{"type": "text", "text": "Base directory for this skill: ums"}]}}
check("allowed after Skill ums followed by its isMeta skill body (ai-config#6039)",
      run(work + [tool("Skill", {"skill": "ums"}), result(), skill_body], resolve(), fresh()) == "")
check("an isMeta record does not hide a later real user message",
      '"deny"' in run(work + [tool("Skill", {"skill": "ums"}), result(), skill_body, user("more")],
                      resolve(), fresh()))
wakeup = {"type": "user", "isMeta": True, "promptSource": "sdk",
          "message": {"content": [{"type": "text", "text": "Check CI on the PR"}]}}
check("a scheduled continuation (isMeta, no sourceToolUseID) is a real turn",
      '"deny"' in run(work + [tool("Skill", {"skill": "ums"}), result(), wakeup],
                      resolve(), fresh()))
check("a thread report read before an isMeta skill body still counts",
      run(work + read("cmsg_A", done) + [skill_body], resolve(thread="cmsg_A"), fresh()) == "")
check("UMS before the last user message does not count",
      '"deny"' in run([tool("Skill", {"skill": "ums"}), user("more work")], resolve(), fresh()))
check("Antigravity USER_INPUT user message invalidates earlier UMS",
      '"deny"' in run([tool("Skill", {"skill": "ums"}),
                       {"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "more work"}],
                      resolve(), fresh()))
check("a tool_result record is not a user message",
      run([user("go"), tool("Skill", {"skill": "ums"}), result()], resolve(), fresh()) == "")
check("resolved:false (reopen) is not gated", run(work, resolve(resolved=False), fresh()) == "")
check("another tool is ignored",
      run(work, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "ls"}}, fresh()) == "")
check("missing transcript fails open",
      subprocess.run([sys.executable, HOOK], input=json.dumps(
          dict(resolve(), transcript_path="/nonexistent")), capture_output=True,
          text=True).stdout == "")
for raw in ("", "not json", "[1]"):
    p = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True)
    check(f"malformed stdin {raw!r} is silent", p.returncode == 0 and p.stdout == "")

print("UserPromptSubmit merge event:")
merged = ('<wake reason="external-event"><event source="github" kind="pull_request_merged">'
          '{"number": 4480}</event></wake>')
other = ('<wake reason="external-event"><event source="github" kind="check_run">'
         '{"conclusion": "success"}</event></wake>')
sd = fresh()
outs = run([], {"hook_event_name": "UserPromptSubmit", "prompt": merged}, sd, times=2)
check("merge event reminds once", "post-merge" in outs[0] and outs[1] == "")
check("a CI event does not remind",
      run([], {"hook_event_name": "UserPromptSubmit", "prompt": other}, fresh()) == "")
check("the word merged in plain chat does not remind",
      run([], {"hook_event_name": "UserPromptSubmit", "prompt": "the PR merged yesterday"}, fresh()) == "")
check("state merged inside event JSON reminds",
      "post-merge" in run([], {"hook_event_name": "UserPromptSubmit", "prompt":
          '<event source="github" kind="pull_request">{"state": "merged"}</event>'}, fresh()))

print(f"\n{'FAILED' if failures else 'all passed'}: {failures} wrong")
sys.exit(1 if failures else 0)
