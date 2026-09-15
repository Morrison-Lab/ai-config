#!/usr/bin/env python3
"""Stop-hook guard: a clean stopping point needs a liveness check, not a notification.

`require-stopping-point.py` checks that a declaration EXISTS.
`no-unshipped-commit.py` checks this session's own commits.
Neither can see a dispatched subagent that is still working, because its
commits live in its own worktree on its own branch -- so a session can pass
both guards while an agent it launched is mid-task.

The trap is that a subagent's completion notification reads as terminal and is
not. The harness says so in the notification body:

    A task-notification fires each time this agent stops with no live
    background children of its own. The user can send it another message and
    resume it, so the same task-id may notify more than once.

Measured 2026-09-15 (ai-config#3689): a UMS subagent notified `completed`, the
session acted on that result, merged the resulting PR, ran a full state sweep,
and declared a clean stopping point. The agent then ran another hour on the
same task-id and opened a third PR. The sweep had even PRINTED the evidence --

    fatal: cannot remove a locked working tree, lock reason:
      claude agent agent-af661a39e42b3366c (pid 51581 ...)

-- in the same message as the clean declaration, where it was read as
housekeeping rather than as live state.

So a count of outstanding notifications cannot decide this: at declaration time
every launched agent HAD notified. What was missing was a liveness check taken
AFTER the last notification. That is the decidable condition:

    the final message declares a CLEAN stopping point
    AND a subagent was dispatched in this session
    AND no liveness check appears after the last task-notification

Monitors are deliberately out of scope. A monitor watching an already-merged PR
is not outstanding work, and blocking on one would fire on nearly every session
that ever armed a watch -- which is how a guard gets switched off, taking the
real cases with it (`shared/principles/deterministic-tools.md`).

Blocks rather than warns, because the claim is wrong to SEND: a clean
declaration is what tells a reader the session may be closed, so its cost is
paid by whoever acts on it. The remedy costs one tool call.

Fails OPEN on any parse trouble, and fires at most once per distinct message.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

FENCE_OPEN_RX = re.compile(r"^\s{0,3}(`{3,}|~{3,})(?:[a-zA-Z0-9_-]+)?\s*$")
FENCE_CLOSE_RX = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
INLINE_CODE_RX = re.compile(r"`[^`\n]+`")

# Only the CLEAN arm. "Not a clean stopping point" is the honest declaration
# this guard exists to steer toward, so it must never fire on it. That needs no
# negative lookahead: the pattern is line-anchored and the trailing class
# matches whitespace only, so `Clean` has to follow the colon directly and
# `Not a clean` cannot reach it. A lookahead was written here first and removed
# as dead code -- mutation testing found it by SURVIVING its own deletion,
# which is the one signal that distinguishes a redundant guard from a load-
# bearing one.
RX_CLEAN = re.compile(
    r"^\s*(?:[-*]\s+|\d+\.\s+|#{1,6}\s+)?(?:\*\*)?Stopping Point:?(?:\*\*)?:?\s*"
    r"Clean\b",
    re.IGNORECASE,
)

# Tools that dispatch a subagent whose work outlives the call.
DISPATCH_TOOLS = {"agent", "task"}

# Tools that answer "is it still running?". ListAgents is the direct one; a
# worktree lock query is the indirect one the measured case had in hand.
LIVENESS_TOOLS = {"listagents"}

try:
    # `globals().get` rather than a bare `__file__`: the suite may exec this
    # module, where a bare reference is unbound.
    _SELF = globals().get("__file__") or sys.argv[0]
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(_SELF))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import git_subcommand, simple_commands
except Exception as _exc:  # broken install
    print("no-clean-stop-with-live-agent: cannot load scripts/lib/shellcmd.py "
          "({0}); bash liveness checks will not be recognized".format(_exc),
          file=sys.stderr)
    git_subcommand = simple_commands = None


def is_liveness_command(command):
    """True when `command` actually RUNS a worktree-liveness query.

    Parsed into simple commands rather than matched as text. A regex over the
    raw command string counts a mere MENTION as a check -- `grep -n
    "ListAgents" hooks/no-clean-stop-with-live-agent.py` looks exactly like
    the real thing to a substring matcher, and silently discharges the guard.
    That is the same defect as the notification side above, in the opposite
    direction, and it is the more dangerous one: a false positive here means
    the guard stays quiet when it should block.

    `scripts/lib/shellcmd.py` already blanks heredoc bodies and comments and
    splits on shell operators, so it is reused rather than re-derived.

    A parse failure returns False, leaving the guard ARMED. The asymmetry is
    deliberate: a wrongly-armed guard costs one tool call, a wrongly-discharged
    one costs the incident it exists to prevent.
    """
    if simple_commands is None or git_subcommand is None:
        return False
    argvs = simple_commands(command)
    if not argvs:
        return False
    for argv in argvs:
        parsed = git_subcommand(argv)
        if not parsed:
            continue
        sub, rest, _env = parsed
        if sub == "worktree" and any(a == "list" for a in rest):
            return True
    return False


def declares_clean(text):
    """True when a CLEAN stopping-point declaration appears outside code."""
    if not text:
        return False
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in text.splitlines():
        if not in_fence:
            m = FENCE_OPEN_RX.match(line)
            if m:
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                continue
            if RX_CLEAN.search(INLINE_CODE_RX.sub("", line)):
                return True
        else:
            m = FENCE_CLOSE_RX.match(line)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                in_fence = False
    return False


def is_task_notification(record):
    """True for a genuine harness task-notification record.

    Keyed on the record's `origin.kind`, never on the literal text
    `<task-notification>` appearing in a block. Substring matching is
    spoofable, and self-spoofing here is not hypothetical: THIS FILE contains
    that literal string, so a tool_result from reading this source -- or the
    README row describing it, or its own test file -- would register as a
    notification and reset the baseline, falsely blocking a declaration whose
    liveness check was performed correctly.

    `no-push-without-self-review.py` already made this exact choice for the
    same reason, and its suite carries the negative case. Reused rather than
    re-derived.
    """
    origin = record.get("origin")
    return (
        isinstance(origin, dict)
        and origin.get("kind") in ("task-notification", "task_notification")
    )


def scan(path):
    """Return (last_text, dispatch_idx, notification_idx, liveness_idx).

    Indices are line numbers in the transcript, or -1 when absent.
    """
    last_text = ""
    dispatch = -1
    notification = -1
    liveness = -1
    i = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            i += 1
            try:
                event = json.loads(line)
            except Exception:
                continue

            role = event.get("type") or event.get("role")
            blocks = (event.get("message") or {}).get("content") or event.get(
                "content"
            ) or []

            # Decided once per RECORD, from structured metadata, so no block's
            # text can manufacture one.
            if is_task_notification(event) and role != "assistant":
                notification = i

            if isinstance(blocks, str):
                if role == "assistant" and blocks.strip():
                    last_text = blocks
                continue

            if not isinstance(blocks, list):
                continue

            for b in blocks:
                if not isinstance(b, dict):
                    continue
                kind = b.get("type")

                if kind == "tool_use":
                    name = (b.get("name") or "").lower()
                    if name in DISPATCH_TOOLS:
                        dispatch = i
                    elif name in LIVENESS_TOOLS:
                        liveness = i
                    elif name == "bash":
                        cmd = (b.get("input") or {}).get("command") or ""
                        if is_liveness_command(cmd):
                            liveness = i

                elif kind == "text":
                    if role == "assistant" and b.get("text", "").strip():
                        last_text = b["text"]

    return last_text, dispatch, notification, liveness


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_text, dispatch, notification, liveness = scan(path)
    except Exception:
        return 0  # fail open

    if not last_text or not declares_clean(last_text):
        return 0
    if dispatch < 0:
        return 0  # no subagent was ever dispatched

    # A liveness check taken after the most recent notification discharges it.
    # When no notification ever arrived, a check after the dispatch counts.
    baseline = notification if notification >= 0 else dispatch
    if liveness > baseline:
        return 0

    key = hashlib.sha256(last_text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-live-agent-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "This message declares a CLEAN stopping point, a subagent was "
                    "dispatched in this session, and no liveness check was run "
                    "after the last task-notification.\n\n"
                    "A completion notification is NOT terminal. The harness says so "
                    "in the notification itself: it fires each time the agent stops "
                    "with no live children, and the same task-id may notify more "
                    "than once. Measured in ai-config#3689: an agent notified "
                    "completed, the session merged its PR and declared clean, and "
                    "the agent then ran another hour and opened a third PR.\n\n"
                    "Check before declaring, then say what you found:\n"
                    "  ListAgents\n"
                    "  git worktree list --porcelain   # a `locked` line naming a "
                    "claude agent means a live pid holds it\n\n"
                    "If it is still running, declare "
                    "`**Stopping Point**: Not a clean stopping point / work remains "
                    "queued: <agent> still running`. Never `--force` a worktree "
                    "removal to make the signal go away -- see "
                    "memories/subagent-worktrees.md."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
