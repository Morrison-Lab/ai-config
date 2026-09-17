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


def raw(record):
    """A record emitted verbatim, for shapes the helpers cannot express."""
    return json.dumps(record)


def multi_text(texts):
    """One assistant record carrying several text blocks."""
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": x} for x in texts]
            },
        }
    )


def stamped(line, when):
    """Re-emit a helper's record carrying an explicit ISO-8601 timestamp."""
    record = json.loads(line)
    record["timestamp"] = when
    return json.dumps(record)


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


def run_twice(lines):
    """Run the hook twice over one transcript, sharing a TMPDIR."""
    tmpdir = tempfile.mkdtemp()
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        for line in lines:
            f.write(line + "\n")
    out = []
    for _ in range(2):
        res = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            text=True,
            capture_output=True,
            env=dict(os.environ, TMPDIR=tmpdir),
        )
        assert res.returncode == 0, f"exited {res.returncode}: {res.stderr}"
        out.append('"decision": "block"' in res.stdout)
    os.unlink(path)
    return out


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
        "Workflow tool counts as a dispatch",
        [dispatch("Workflow"), notification(), assistant(CLEAN)],
        True,
    ),
    (
        "Workflow dispatch, checked after the notification",
        [dispatch("Workflow"), notification(), liveness(), assistant(CLEAN)],
        False,
    ),
    (
        "invoke_subagent counts as a dispatch",
        [dispatch("invoke_subagent"), notification(), assistant(CLEAN)],
        True,
    ),
    (
        "a worktree query through run_command counts as a liveness check",
        [
            dispatch(),
            notification(),
            liveness("run_command", "git worktree list --porcelain"),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "a replayed liveness check does not discharge by file position alone",
        # A compaction appends an OLDER record below a newer one. By file
        # order the check follows the notification and would discharge the
        # guard; by its own timestamp it precedes the dispatch entirely.
        [
            stamped(dispatch(), "2026-09-17T10:00:00Z"),
            stamped(notification(), "2026-09-17T10:05:00Z"),
            stamped(liveness(), "2026-09-17T09:59:00Z"),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "a genuinely later liveness check still discharges when stamped",
        [
            stamped(dispatch(), "2026-09-17T10:00:00Z"),
            stamped(notification(), "2026-09-17T10:05:00Z"),
            stamped(liveness(), "2026-09-17T10:06:00Z"),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "a partly-stamped transcript is ambiguous, so it arms rather than "
        "trusting file order",
        [
            stamped(dispatch(), "2026-09-17T10:00:00Z"),
            notification(),
            stamped(liveness(), "2026-09-17T09:59:00Z"),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "an unstamped transcript still reads in file order",
        [dispatch(), notification(), liveness(), assistant(CLEAN)],
        False,
    ),
    (
        "mixed aware and naive stamps are ambiguous, so they arm",
        [
            stamped(dispatch(), "2026-09-17T10:00:00Z"),
            stamped(notification(), "2026-09-17T10:05:00"),
            stamped(liveness(), "2026-09-17T10:06:00Z"),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "an unparseable stamp is treated as unstamped, not as an error",
        [
            stamped(dispatch(), "not-a-time"),
            stamped(notification(), "not-a-time"),
            stamped(liveness(), "not-a-time"),
            assistant(CLEAN),
        ],
        False,
    ),
    # --- a dispatch AFTER the last liveness check re-arms (round 3) ----------
    (
        "a sidecar dispatched after the liveness check re-arms the guard",
        [
            dispatch(),
            notification(),
            liveness(),
            dispatch(),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "that sidecar's own notification does not discharge it either",
        [
            dispatch(),
            notification(),
            liveness(),
            dispatch(),
            notification(),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "a liveness check after the sidecar dispatch does discharge it",
        [
            dispatch(),
            notification(),
            liveness(),
            dispatch(),
            liveness(),
            assistant(CLEAN),
        ],
        False,
    ),
    # --- a declaration is not lost to a trailing text block (round 3) --------
    (
        "a text block after the declaration does not hide it",
        [
            dispatch(),
            notification(),
            multi_text([CLEAN, "Let me know if anything else comes up."]),
        ],
        True,
    ),
    (
        "a declaration in the first of several blocks still counts",
        [
            dispatch(),
            notification(),
            multi_text(["Working through it.", CLEAN, "Done."]),
        ],
        True,
    ),
    # --- one malformed record must not disable the guard (round 3) ----------
    (
        "a record whose message is a string does not disable the scan",
        [dispatch(), notification(), raw({"type": "user", "message": "hi"}),
         assistant(CLEAN)],
        True,
    ),
    (
        "a record that is a bare JSON list does not disable the scan",
        [dispatch(), notification(), json.dumps([1, 2, 3]), assistant(CLEAN)],
        True,
    ),
    (
        "a tool_use whose input is a string does not disable the scan",
        [
            dispatch(),
            notification(),
            raw({
                "type": "assistant",
                "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "input": "ls"}
                ]},
            }),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "a string-valued tool_use input does not cost the REST of its record",
        [
            dispatch(),
            notification(),
            raw({
                "type": "assistant",
                "message": {"content": [
                    {"type": "tool_use", "name": "Bash", "input": "ls"},
                    {"type": "tool_use", "name": "ListAgents", "input": {}},
                ]},
            }),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "a text block whose text is null does not disable the scan",
        [
            dispatch(),
            notification(),
            raw({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": None}]},
            }),
            assistant(CLEAN),
        ],
        True,
    ),
    # --- fence handling comes from scripts/lib/fences.py (round 3) -----------
    (
        "an UNCLOSED fence does not swallow the declaration below it",
        [
            dispatch(),
            notification(),
            assistant("Example:\n\n```\nsome output\n\n" + CLEAN),
        ],
        True,
    ),
    # --- previously unpinned behaviours (round 3) ---------------------------
    (
        "an assistant-role record carrying origin.kind is not a notification",
        [
            dispatch(),
            liveness(),
            raw({
                "type": "assistant",
                "origin": {"kind": "task-notification", "taskId": "t9"},
                "message": {"content": [{"type": "tool_result",
                                         "content": "done"}]},
            }),
            assistant(CLEAN),
        ],
        False,
    ),
    (
        "git worktree remove is not a liveness check",
        [
            dispatch(),
            notification(),
            liveness(tool="Bash", command="git worktree remove /tmp/wt"),
            assistant(CLEAN),
        ],
        True,
    ),
    (
        "a string-form content assistant record still supplies the declaration",
        [
            dispatch(),
            notification(),
            raw({"type": "assistant", "message": {"content": CLEAN}}),
        ],
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

# The sentinel lives in the temp directory, so run()'s fresh TMPDIR per case
# hides "fires at most once per distinct message" entirely. Sharing one TMPDIR
# across two invocations is the only way to observe it.
first, second = run_twice([dispatch(), notification(), assistant(CLEAN)])
if first is not True:
    failures.append("the guard must block the first time it sees a message")
    print("  [FAIL] blocks the first time it sees a message")
else:
    print("  [ok] blocks the first time it sees a message")
if second is not False:
    failures.append("the same message must not be blocked twice")
    print("  [FAIL] the same message is not blocked twice")
else:
    print("  [ok] the same message is not blocked twice")

if failures:
    print("\n".join(failures))
    raise SystemExit(1)
print(f"\nAll {len(cases) + 4} assertions passed.")
