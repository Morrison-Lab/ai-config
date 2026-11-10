#!/usr/bin/env python3
"""Tests for hooks/no-rc-outside-runner.py.

Run: python3 hooks/test-no-rc-outside-runner.py [hooks/no-rc-outside-runner.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-rc-outside-runner.py")
TOOL = "mcp__hearthbot__start_remote_control"
RUNNER = "cmsg_014QLd5McmoUEgMPRiXeVnjSRTRrasdmWDa2KQ6RfWFYmJ"
OTHER = "cmsg_014QLd5McmoUEgMPRiXeVnjSBG3A52FS2k73kHLtr4b73e"


def transcript(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def run(tool, path, env=None):
    payload = {"tool_name": tool, "tool_input": {"message_id": "cmsg_x"}, "transcript_path": path}
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=e)
    assert r.returncode == 0, r.stderr
    return "deny" in r.stdout


def thread_text(cmsg):
    return f'You are a Thread Session created by this project. <thread ts="{cmsg}">'


# (name, tool, transcript text or None for missing file, env, should_deny)
CASES = [
    ("non-runner thread denied", TOOL, thread_text(OTHER), None, True),
    ("runner thread allowed", TOOL, thread_text(RUNNER), None, False),
    ("coordinator (no thread session) allowed", TOOL, '<thread ts="cmsg_zzz"> project chat', None, False),
    ("other tool ignored", "mcp__hearthbot__post_message", thread_text(OTHER), None, False),
    ("env allowlist adds a runner", TOOL, thread_text(OTHER), {"RC_RUNNER_THREAD_IDS": OTHER}, False),
    ("unreadable transcript fails open", TOOL, None, None, False),
]


def main() -> int:
    bad = 0
    for name, tool, text, env, want in CASES:
        path = transcript(text) if text is not None else "/nonexistent/transcript.jsonl"
        got = run(tool, path, env)
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)
        if text is not None:
            os.unlink(path)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
