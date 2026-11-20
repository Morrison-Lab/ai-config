#!/usr/bin/env python3
"""Regression tests for no-unmonitored-pr.py."""
import atexit
import importlib.util
import json
import os
import shutil
import sys
import tempfile

_TMPDIR = tempfile.mkdtemp()
atexit.register(lambda: shutil.rmtree(_TMPDIR, ignore_errors=True))
os.environ["TMPDIR"] = _TMPDIR
os.environ["TEMP"] = _TMPDIR
os.environ["TMP"] = _TMPDIR
tempfile.tempdir = None

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def transcript(blocks):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for block in blocks:
            stream.write(json.dumps({"type": "assistant", "message": {"content": [block]}}) + "\n")
    return path


opened = transcript([{"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}}])
scheduled = transcript([{"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}}, {"type": "tool_use", "name": "ScheduleWakeup", "input": {"after": "2m"}}])

# Antigravity transcript
def antigravity_transcript(records_list):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for rec in records_list:
            stream.write(json.dumps(rec) + "\n")
    return path

ag_opened = antigravity_transcript([
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create"}}]}
])
ag_scheduled = antigravity_transcript([
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create"}}]},
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "schedule", "args": {"DurationSeconds": 120}}]}
])

orig_state_dir = subject.STATE_DIR
try:
    assert subject.pending(opened)
    assert not subject.pending(scheduled)
    assert subject.pending(ag_opened)
    assert not subject.pending(ag_scheduled)
    assert subject.monitor_path("https://github.com/o/r/pull/1") == subject.monitor_path("https://github.com/o/r/pull/1")
    assert subject.monitor_path("https://github.com/o/r/pull/1") != subject.monitor_path("https://github.com/o/r/pull/2")

    # Verify extract_pr_urls
    multi_pr = transcript([
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr view 999"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/999"},
        {"type": "text", "text": "See also https://github.com/o/r/pull/888"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create --title 'A'"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/10"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create --title 'B'"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/20"}
    ])
    ag_multi_pr = antigravity_transcript([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create --title 'A'"}}]},
        {"source": "MODEL", "type": "GENERIC", "content": "https://github.com/o/r/pull/30"},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create --title 'B'"}}]},
        {"source": "MODEL", "type": "GENERIC", "content": "https://github.com/o/r/pull/40"}
    ])
    try:
        urls = subject.extract_pr_urls(multi_pr)
        assert urls == ["https://github.com/o/r/pull/10", "https://github.com/o/r/pull/20"], f"Got {urls}"
        ag_urls = subject.extract_pr_urls(ag_multi_pr)
        assert ag_urls == ["https://github.com/o/r/pull/30", "https://github.com/o/r/pull/40"], f"Got {ag_urls}"
    finally:
        os.unlink(multi_pr)
        os.unlink(ag_multi_pr)

    # Verify start_monitor_for_url early return when already alive
    with tempfile.TemporaryDirectory() as d:
        subject.STATE_DIR = d
        url1 = "https://github.com/o/r/pull/1"
        url2 = "https://github.com/o/r/pull/2"
        p1 = subject.monitor_path(url1)
        subject.write_json(p1, {"url": url1, "pid": os.getpid()})
        # url1 is alive -> returns False without error
        assert subject.start_monitor_for_url(url1, d) is False
        # url2 is not alive -> attempts to start (or starts)
        p2 = subject.monitor_path(url2)
        assert not os.path.exists(p2)
        # Verify PR 2 gets its own distinct state path and is not shadowed by PR 1
        assert p1 != p2

        # ai-config#4009: an unreadable state file must not spawn a second
        # poller; a missing one reads as empty and readable.
        url3 = "https://github.com/o/r/pull/3"
        p3 = subject.monitor_path(url3)
        with open(p3, "w", encoding="utf-8") as stream:
            stream.write("{not json")
        assert subject.read_state(p3) == (None, False)
        assert subject.start_monitor_for_url(url3, d) is False
        assert subject.read_state(os.path.join(d, "missing.json")) == ({}, True)
        # ...but one left unreadable past FRESH_SECONDS no longer blocks.
        old = subject.time.time() - subject.FRESH_SECONDS - 5
        os.utime(p3, (old, old))
        assert subject.recently_written(p3) is False
        assert subject.recently_written(os.path.join(d, "missing.json")) is False

        # ai-config#4009: a poller yields when the state file names another
        # live poller seen recently, and keeps polling otherwise.
        import subprocess as _sp
        import time as _time
        other = _sp.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            now = _time.time()
            assert subject.other_poller({"pid": other.pid, "checked_at": now}) is True
            assert subject.other_poller({"pid": other.pid, "started_at": now}) is True
            assert subject.other_poller({"pid": os.getpid(), "checked_at": now}) is False
            stale = now - subject.FRESH_SECONDS - 5
            assert subject.other_poller({"pid": other.pid, "checked_at": stale}) is False
            assert subject.other_poller({"pid": 2 ** 30, "checked_at": now}) is False
            assert subject.other_poller({}) is False
        finally:
            other.kill()
            other.wait()
finally:
    # Restored here, not after the `with`, so a failed assertion cannot leave
    # STATE_DIR pointing at the deleted temporary directory.
    subject.STATE_DIR = orig_state_dir
    os.unlink(opened)
    os.unlink(scheduled)
    os.unlink(ag_opened)
    os.unlink(ag_scheduled)

# ai-config#4790: a started poller is not a wake. A reply that waits on PR
# state is blocked until a re-invoking mechanism is armed.
import contextlib
import io

subscribed = transcript([
    {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}},
    {"type": "tool_use", "name": "mcp__claude-code-remote__subscribe_pr_activity", "input": {"pullNumber": 1}},
])
assert not subject.pending(subscribed)
os.unlink(subscribed)


def run_main(reply, stop_hook_active=False, started=True):
    path = transcript([
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/7"},
        {"type": "text", "text": reply},
    ])
    saved = (subject.shutil.which, subject.start_monitor_for_url, sys.stdin)
    subject.shutil.which = lambda _name: "/usr/bin/gh"
    subject.start_monitor_for_url = lambda _url, _cwd: started
    sys.stdin = io.StringIO(json.dumps({"transcript_path": path, "cwd": _TMPDIR,
                                        "stop_hook_active": stop_hook_active}))
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            subject.main()
    finally:
        subject.shutil.which, subject.start_monitor_for_url, sys.stdin = saved
        os.unlink(path)
    return json.loads(out.getvalue()) if out.getvalue().strip() else {}


# transcript() wraps each block in an assistant record
# ({"type": "assistant", "message": {"content": [block]}}), the shape last_reply reads.
assert subject.last_reply(transcript([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])) == "b"
waiting = "CI checks are still running; I'll merge once the review is clean."
for phrase in ("Waiting on CI for the new head.",
               "The checks are still running.",
               "I'll merge once CI passes.",
               "When the review comes back I'll address it."):
    assert subject.WAITING.search(phrase), phrase
# Replies that wait on nothing must not match (review of #5993).
for phrase in ("Opened the PR. No pending items remain.",
               "Done: all work in progress was merged.",
               "The pending review was resolved and merged.",
               "Merged after CI passed.",
               "I am not waiting on CI any more.",
               "No longer waiting for the review: it is clean."):
    assert not subject.WAITING.search(phrase), phrase
assert run_main(waiting).get("decision") == "block"
assert "re-invoke" in run_main(waiting)["reason"]
# An already-running poller is no wake either. start_monitor_for_url returns
# False when the PR's recorded poller is alive (asserted above with a live pid)
# and None when it cannot start one, so False is the already-running case.
already = run_main(waiting, started=False)
assert already.get("decision") == "block" and "re-invoke" in already["reason"]
# A poller that cannot start blocks for that reason, not the waiting one.
failed = run_main(waiting, started=None)
assert failed.get("decision") == "block" and "No local timer" in failed["reason"]
# A reply that waits on nothing passes with the poller's notice.
done = run_main("Merged the PR and closed the issue.")
assert "decision" not in done and "systemMessage" in done
# Never block twice in one turn.
assert "decision" not in run_main(waiting, stop_hook_active=True)

# Verify alive() liveness checking across valid, dead, and invalid PIDs
assert subject.alive(os.getpid()) is True
assert subject.alive(2 ** 30) is False
assert subject.alive(0) is False
assert subject.alive(-1) is False
assert subject.alive("not a pid") is False
if os.name == "nt":
    assert subject._alive_windows(os.getpid()) is True

# Every child process must be started without a console window on Windows.
# Checked structurally via AST: every subprocess.<spawner>(...) call in the
# hook must pass **NO_WINDOW with a floor assertion on total calls seen.
import ast as _ast
from pathlib import Path
_tree = _ast.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
_bare = []
_seen = 0
for _node in _ast.walk(_tree):
    if (isinstance(_node, _ast.Call) and isinstance(_node.func, _ast.Attribute)
            and _node.func.attr in ("run", "Popen", "call", "check_call", "check_output")
            and isinstance(_node.func.value, _ast.Name)
            and _node.func.value.id == "subprocess"):
        _seen += 1
        _passes = any(k.arg is None and isinstance(k.value, _ast.Name)
                      and k.value.id == "NO_WINDOW" for k in _node.keywords)
        if not _passes:
            _bare.append(_node.lineno)
# Two since ai-config#4733: `_run` (which every `gh pr view` read goes through,
# via scripts/lib/pr_view.py) and the `--poll` Popen.
assert _seen >= 2, f"matched only {_seen} subprocess calls; expected the 2 in the file"
assert not _bare, f"subprocess calls without NO_WINDOW at lines {_bare}"

print("PASS: detects an unmonitored PR, gives each PR a stable timer state file, and guards Windows process liveness and NO_WINDOW")
