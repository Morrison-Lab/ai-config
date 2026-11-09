#!/usr/bin/env python3
"""Tests for hooks/flag-reply-without-tool-search.py.

Run: python3 hooks/test-flag-reply-without-tool-search.py [hook path]

The notice is a Stop hook's JSON `decision`/`reason`, so each positive case parses
stdout and checks both.  Every case also asserts an empty stderr.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "flag-reply-without-tool-search.py")


def rec(**kw):
    return json.dumps(kw) + "\n"


def user(text="please switch your permission mode"):
    return rec(type="user", message={"role": "user", "content": text})


def use(name, **inp):
    return rec(type="assistant", message={"role": "assistant", "content": [
        {"type": "tool_use", "id": "t1", "name": name, "input": inp}]})


def result():
    return rec(type="user", message={"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]})


REPLY = "mcp__hearthbot__post_message"


def run(transcript, tag, tmp=None):
    with tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        fh.write(transcript)
        path = fh.name
    payload = {"transcript_path": path, "session_id": f"s-{tag}-{os.getpid()}"}
    # A fresh TMPDIR per run unless one is passed: the warn-once state lives there.
    with tempfile.TemporaryDirectory() as fresh:
        tmp = tmp or fresh
        env = dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp)
        try:
            return subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                                  capture_output=True, text=True, env=env)
        finally:
            os.unlink(path)


def fired(proc):
    assert proc.stderr == "", proc.stderr
    if not proc.stdout.strip():
        return False
    out = json.loads(proc.stdout)
    assert out.get("decision") == "block" or "systemMessage" in out, out
    assert "ToolSearch" in (out.get("reason") or out.get("systemMessage") or ""), out
    return True


def case(name, transcript, expect):
    got = fired(run(transcript, name))
    assert got == expect, f"{name}: expected fired={expect}, got {got}"
    print(f"ok  {name}")


case("reply-only turn fires",
     user() + use(REPLY, text="I can't switch my own permission mode, only you can."), True)
case("refusal worded any way still fires (no phrase match)",
     user() + use(REPLY, text="That setting is outside my control."), True)
case("ToolSearch before the reply does not fire",
     user() + use("ToolSearch", query="permission mode") + result()
     + use(REPLY, text="No tool for that."), False)
case("any other tool call does not fire",
     user() + use("Read", file_path="/x") + result() + use(REPLY, text="Done."), False)
case("no reply tool does not fire",
     user() + rec(type="assistant", message={"role": "assistant", "content": [
         {"type": "text", "text": "I can't."}]}), False)
case("earlier turn's tool call does not count for this turn",
     user("a") + use("Read", file_path="/x") + result() + use(REPLY, text="a")
     + user("b") + use(REPLY, text="b"), True)
case("earlier turn's reply-only does not fire a tooled later turn",
     user("a") + use(REPLY, text="a") + user("b") + use("Bash", command="ls") + result()
     + use(REPLY, text="b"), False)
case("unreadable transcript fails open", "not json\n", False)

# Two unrelated sessions replying alike (a reply with no text, or "Done.") share one TMPDIR,
# as real sessions do; each must still be warned (review of #5141).
with tempfile.TemporaryDirectory() as shared:
    for text in ({}, {"text": "Done."}):
        t = user() + use(REPLY, **text)
        assert fired(run(t, "sessA", shared)), f"first session {text} not warned"
        assert fired(run(t, "sessB", shared)), f"second session {text} suppressed"
print("ok  same reply in two sessions warns both")
print("all passed")
