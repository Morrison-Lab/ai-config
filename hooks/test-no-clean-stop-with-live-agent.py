"""Tests for no-clean-stop-with-live-agent.py.

The measured case (ai-config#3689) is the one to keep in view: every launched
agent HAD already notified `completed` when the clean declaration was written,
so a count of outstanding notifications decides nothing. What was missing was a
liveness check taken AFTER the last notification. `ordering_is_load_bearing`
below is the test that fails if that ordering is ever relaxed to a bare
"was a liveness tool ever used" check.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

CLEAN = "All merged.\n\n**Stopping Point**: Clean stopping point reached"
NOT_CLEAN = (
    "Still going.\n\n**Stopping Point**: Not a clean stopping point / "
    "work remains queued: PR 1 open."
)


def assistant(text):
    return json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    )


def dispatch(name="Agent"):
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": name, "input": {"prompt": "go"}}
                ]
            },
        }
    )


def notification():
    """A genuine notification: identified by origin.kind, not by body text."""
    return json.dumps(
        {
            "type": "user",
            "origin": {"kind": "task-notification", "taskId": "task_bg_1"},
            "message": {
                "content": [
                    {"type": "tool_result", "content": "agent finished"}
                ]
            },
        }
    )


def spoof_notification():
    """A tool_result whose TEXT contains the marker but with no origin.

    This is not a contrived input: the hook's own source, its test file, and
    its README row all contain the literal string, so reading any of them
    produces exactly this record.
    """
    return json.dumps(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "content": "<task-notification><status>completed</status></task-notification>",
                    }
                ]
            },
        }
    )


def liveness(tool="ListAgents", command=None):
    inp = {"command": command} if command else {}
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": tool, "input": inp}]
            },
        }
    )


def run(lines):
    tmpdir = tempfile.mkdtemp()
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        for line in lines:
            f.write(line + "\n")
    res = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        text=True,
        capture_output=True,
        env=dict(os.environ, TMPDIR=tmpdir),
    )
    os.unlink(path)
    assert res.returncode == 0, f"exited {res.returncode}: {res.stderr}"
    return '"decision": "block"' in res.stdout


cases = [
    # name, transcript, expect_block
    (
        "measured case: notified, then clean with no liveness check",
        [dispatch(), notification(), assistant(CLEAN)],
        True,
    ),
    (
        "liveness check after the notification discharges it",
        [dispatch(), notification(), liveness(), assistant(CLEAN)],
        False,
    ),
    (
        "ordering_is_load_bearing: liveness BEFORE the notification does not",
        [dispatch(), liveness(), notification(), assistant(CLEAN)],
        True,
    ),
    (
        "no subagent was ever dispatched",
        [assistant(CLEAN)],
        False,
    ),
    (
        "not-clean declaration is never blocked",
        [dispatch(), notification(), assistant(NOT_CLEAN)],
        False,
    ),
    (
        "dispatched but never notified, with no check",
        [dispatch(), assistant(CLEAN)],
        True,
    ),
    (
        "dispatched but never notified, checked after dispatch",
        [dispatch(), liveness(), assistant(CLEAN)],
        False,
    ),
    (
        "Task tool counts as a dispatch",
        [dispatch("Task"), notification(), assistant(CLEAN)],
        True,
    ),
    (
        "bash worktree query counts as a liveness check",
        [
            dispatch(),
            notification(),
            liveness("Bash", "git worktree list --porcelain"),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "an unrelated bash command does not count",
        [dispatch(), notification(), liveness("Bash", "git status"), assistant(CLEAN)],
        True,
    ),
    # The reviewer's round-2 finding on PR #3692: a MENTION of the check is not
    # the check. This direction is the dangerous one -- it silently discharges
    # the guard rather than falsely arming it.
    (
        "grepping for the tool name is not a liveness check",
        [
            dispatch(),
            notification(),
            liveness("Bash", 'grep -n "ListAgents" hooks/no-clean-stop-with-live-agent.py'),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "echoing the command text is not a liveness check",
        [
            dispatch(),
            notification(),
            liveness("Bash", 'echo "run git worktree list to check"'),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "the command inside a comment is not a liveness check",
        [
            dispatch(),
            notification(),
            liveness("Bash", "git status  # git worktree list would show locks"),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "a real worktree query still counts when chained",
        [
            dispatch(),
            notification(),
            liveness("Bash", "cd /tmp && git worktree list --porcelain"),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "a fenced declaration is not a declaration",
        [
            dispatch(),
            notification(),
            assistant("Example:\n\n```\n**Stopping Point**: Clean stopping point reached\n```\n\nStill working."),
        ],
        False,
    ),
    (
        "an inline-code declaration is not a declaration",
        [
            dispatch(),
            notification(),
            assistant("Say `**Stopping Point**: Clean stopping point reached` at the end."),
        ],
        False,
    ),
    (
        "declaration as a list item still counts",
        [
            dispatch(),
            notification(),
            assistant("- **Stopping Point**: Clean stopping point reached"),
        ],
        True,
    ),
    # The reviewer's finding on PR #3692. A tool_result carrying the literal
    # marker -- which reading this hook's own source produces -- must not
    # register as a notification and invalidate a real liveness check.
    (
        "spoof after a real liveness check does not re-block",
        [dispatch(), notification(), liveness(), spoof_notification(), assistant(CLEAN)],
        False,
    ),
    (
        "spoof alone is not a notification, so the dispatch is the baseline",
        [dispatch(), liveness(), spoof_notification(), assistant(CLEAN)],
        False,
    ),
    (
        "an assistant message quoting the marker is not a notification",
        [
            dispatch(),
            notification(),
            liveness(),
            assistant("The guard keys on <task-notification> records.\n\n" + CLEAN),
        ],
        False,
    ),
]

failures = []
for name, lines, expected in cases:
    got = run(lines)
    status = "ok" if got == expected else "FAIL"
    if got != expected:
        failures.append(f"{name}: expected block={expected}, got block={got}")
    print(f"  [{status}] {name}")

# Fail-open contract: an unreadable transcript must never block.
fd, bad = tempfile.mkstemp()
with os.fdopen(fd, "w") as f:
    f.write("not json at all\n")
res = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"transcript_path": bad}),
    text=True,
    capture_output=True,
)
os.unlink(bad)
if res.returncode != 0 or '"decision": "block"' in res.stdout:
    failures.append("malformed transcript must fail open")
    print("  [FAIL] malformed transcript fails open")
else:
    print("  [ok] malformed transcript fails open")

res = subprocess.run(
    [sys.executable, HOOK],
    input=json.dumps({"transcript_path": "/nonexistent/path"}),
    text=True,
    capture_output=True,
)
if res.returncode != 0 or '"decision": "block"' in res.stdout:
    failures.append("missing transcript must fail open")
    print("  [FAIL] missing transcript fails open")
else:
    print("  [ok] missing transcript fails open")

if failures:
    print("\n".join(failures))
    raise SystemExit(1)
print(f"\nAll {len(cases) + 2} assertions passed.")
