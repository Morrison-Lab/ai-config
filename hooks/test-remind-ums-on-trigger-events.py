#!/usr/bin/env python3
"""Tests for hooks/remind-ums-on-trigger-events.py (ai-config#4480)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "remind-ums-on-trigger-events.py")
failures = 0


def run(payload, tmp=None):
    tmp = tmp or tempfile.mkdtemp()
    p = subprocess.run([sys.executable, HOOK], input=payload if isinstance(payload, str) else json.dumps(payload),
                       capture_output=True, text=True, env=dict(os.environ, TMPDIR=tmp))
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def check(desc, ok):
    global failures
    failures += not ok
    print(f"  {'ok' if ok else 'WRONG':<6} {desc}")


def relay(reason, note):
    attr = f' reason="{reason}"' if reason else ""
    return (f'<coordinator-relay><relay from="coordinator" session="s"{attr}>'
            f"<note>{note}</note></relay></coordinator-relay>")


ups = lambda p: {"hook_event_name": "UserPromptSubmit", "prompt": p, "transcript_path": "/t"}
check("coordinator correction note reminds",
      "coordinator" in run(ups(relay("", "Install TinyTeX; do not defer to CI."))))
check("a spawn brief does not", run(ups(relay("spawn", "Fix the bug."))) == "")
check("a relay with an empty note does not", run(ups(relay("", "  "))) == "")
for grant in ("daytb", "yes, do it", "Your call.", "rec?"):
    check(f"grant {grant!r} reminds", "grant" in run(ups(grant)))
check("a grant inside a task sentence does not", run(ups("please do it in R and render the page")) == "")
check("plain prompt is silent", run(ups("fix the failing test")) == "")
check("compaction reminds", "compacted" in run({"hook_event_name": "SessionStart", "source": "compact", "session_id": "a"}))
check("startup does not", run({"hook_event_name": "SessionStart", "source": "startup", "session_id": "a"}) == "")
for cmd in ("git revert abc123", "cd r && git reset --hard origin/main"):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}})
    check(f"{cmd!r} adds context", "additionalContext" in out and "deny" not in out)
check("git status is silent",
      run({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git status"}}) == "")
tmp = tempfile.mkdtemp()
note = ups(relay("", "same note"))
check("fires once per distinct note", run(note, tmp) != "" and run(note, tmp) == "")
for raw in ("", "not json", "[1]"):
    check(f"malformed {raw!r} is silent", run(raw) == "")
print(f"\n{'FAILED' if failures else 'all passed'}: {failures} wrong")
sys.exit(1 if failures else 0)
