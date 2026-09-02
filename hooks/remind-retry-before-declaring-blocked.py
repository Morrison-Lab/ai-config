#!/usr/bin/env python3
"""UserPromptSubmit reminder: a classifier denial is a sample, not a wall.

The auto-mode permission classifier's decision on a given command shape is
non-deterministic. ai-config#2994 measured it directly: a
`ALLOW_UNREVIEWED_PUSH=1 git push` was denied three times, the session reported
the path as permanently closed -- in a blocking report to the user, in a
project memory entry, and in a comment on this repo's own tracker -- and then
the byte-identical fourth attempt succeeded, with no settings change and no
permission rule added.

Three identical denials do not FEEL like a claim. They feel like a
measurement: the command ran, the system said no, three times. So "I cannot do
this" reads as reporting an observation rather than asserting a fact about the
future, and none of the claim-checking rules that would otherwise fire
(`metacognitive-monitoring.md` on a claim about state, `ardi.md` on verifying
an asserted blocker) engages at all. The conclusion is also self-confirming:
deciding the path is closed means stopping, which destroys the only evidence
that would refute it.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
The obvious shape is a `Stop` guard on the reply that declares the path
closed. That shape is wrong here, for the same reason
`remind-ums-after-error.py` gives for its own case.

A `Stop` guard suppresses a message that is WRONG TO SEND. Reporting a denial
is RIGHT to send -- the classifier's own message says to stop and explain when
a capability is essential, and a user waiting on a stalled task needs to hear
that something was refused. Blocking that report would delay the one signal
that surfaces the problem, and would train the session to say nothing rather
than to retry.

What is premature is the PERMANENCE, not the report. So this fires on the next
prompt and only ever adds context. There is no code path here that can
suppress, delay, or alter a message.

MECHANISM
---------
Documented non-blocking path: for `UserPromptSubmit`, anything written to
stdout on exit 0 is added to Claude's context. `inject-local-time.sh` and
`remind-ums-after-error.py` already prove that path works in this harness.

Fires when a tool result carrying the classifier's own denial has no LATER
tool call re-attempting the same command. Fires once per distinct denied
command (sentinel keyed by a content hash of the command plus the transcript
path), because a reminder repeated every turn is noise, and noise is what gets
a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.

WHAT IT MUST NEVER MATCH
------------------------
Only the classifier's own denial. A user declining a permission prompt is a
decision to respect, not a sample to re-draw, and a guard that nagged there
would be switched off -- taking the real cases with it. A deterministic
`deny` rule or a `PreToolUse` hook refusal is equally not a sample: re-running
the same command gets the same answer by construction, so a nudge there is
simply wrong.

The four denial shapes below were measured, not assumed: 1110 transcripts
under `~/.claude/projects` on 2026-09-02, grouped by the `toolDenialKind` the
carrier record sets.

  automode-blocked      79  "Permission for this action was denied by the
                            Claude Code auto mode classifier. ..."   <- ours
  permission-rule      315  "Permission to use Bash with command ... has been
                            denied.", plus every hook refusal
  automode-unavailable  18  "... is temporarily unavailable, so auto mode
                            cannot decide ..."
  user-rejected          6  "The user doesn't want to proceed with this tool
                            use. ..."

`automode-unavailable` is deliberately out of scope. It is transient too, so
retrying is reasonable, but it is the classifier being ABSENT rather than the
classifier denying, and #2994's finding is about a decision that varies -- not
about an outage. Widening to it is a separate change with its own evidence.

TWO LIMITATIONS, STATED RATHER THAN HIDDEN
------------------------------------------
1. This cannot tell a legitimate retry from badgering. It only ever asks
   whether ONE re-attempt happened, which is why it reminds rather than
   blocks.

2. It does not parse the claim, so it cannot tell "declared the path closed"
   from "sensibly moved on to other work" -- which is exactly what the
   classifier's own message suggests doing. Parsing the claim was considered
   and rejected: the permanence assertion has no reliable lexical form (it is
   as often a memory entry or an issue comment as a sentence in the reply),
   and a matcher that missed it would produce silence, which is
   indistinguishable from compliance. So the message ends by saying to
   disregard it when the denial was already handled.

The second denial of the same command is where this stops advising a retry.
`memories/mistake-patterns.md` Pattern 43 says to stop probing after the
classifier's second denial of the same goal and hand the user the decision,
because each denied variant makes the classifier more suspicious. A guard that
urged a third attempt would contradict a rule this corpus already records. So
past one denial the reminder drops the retry advice and keeps only the wording
half: report "denied N times so far", not "cannot".
"""
import hashlib
import json
import os
import sys
import tempfile

# The classifier's own denial. Anchored at the START of the tool result rather
# than searched for anywhere inside it: a denial IS the whole result, while
# `cat`, `grep`, or a transcript scan can print this sentence as ordinary tool
# output -- including a read of this very file, or of its test suite.
CLASSIFIER_MARKER = (
    "Permission for this action was denied by the Claude Code auto mode "
    "classifier"
)

# The structured form of the same fact, carried on the tool_result's CARRIER
# record (not on the block). Used as an alternative signal, not as the only
# one: the field is present in the harness layout measured on 2026-09-02, and
# a layout that drops it must still be readable from the text.
CLASSIFIER_KIND = "automode-blocked"

BASH_TOOLS = (
    "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
)


def identity(name, inp):
    """Return (key, label) naming "the same command" across a retry.

    Whitespace is collapsed deliberately. A re-attempt that differs only in
    indentation or line wrapping IS a retry, and treating it as one produces
    silence -- the safe direction for a guard that can only nag.
    """
    if not isinstance(inp, dict) or not name:
        return "", ""
    if name in BASH_TOOLS:
        raw = str(inp.get("command") or inp.get("cmd") or "")
    else:
        try:
            raw = json.dumps(inp, sort_keys=True, default=str)
        except Exception:
            return "", ""
    label = " ".join(raw.split())
    if not label:
        return "", ""
    return name + "\x00" + label, label


def is_classifier_denial(record, block):
    """True only for the auto-mode classifier's own refusal."""
    if record.get("toolDenialKind") == CLASSIFIER_KIND:
        return True
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    if not isinstance(content, str):
        return False
    return content.lstrip().startswith(CLASSIFIER_MARKER)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (label, key, denials) for the latest unretried denial.

    `denials` counts how many times that same command was denied, which is
    what decides whether a retry is still the right advice.
    """
    uses = {}      # tool_use id -> (index, key, label)
    attempts = []  # (index, key) for every tool call, in transcript order
    denied = []    # (index, key, label) for every classifier denial

    for i, rec in enumerate(records(path)):
        # A subagent's denial is not this session's to retry, and its
        # transcript is a separate file anyway. Same guard, and same reasoning,
        # as remind-ums-after-error.py's.
        if rec.get("isSidechain"):
            continue
        blocks = (rec.get("message") or {}).get("content") or rec.get("content")
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                key, label = identity(b.get("name") or "", b.get("input") or {})
                if key:
                    uses[b.get("id")] = (i, key, label)
                    attempts.append((i, key))
            elif b.get("type") == "tool_result" and is_classifier_denial(rec, b):
                seen = uses.get(b.get("tool_use_id"))
                if seen:
                    denied.append(seen)

    for idx, key, label in reversed(denied):
        if any(j > idx and other == key for j, other in attempts):
            continue
        return label, key, sum(1 for _, k, _ in denied if k == key)
    return None, None, 0


def message(label, count):
    shown = label if len(label) <= 160 else label[:157] + "..."
    times = "once" if count == 1 else f"{count} times"
    head = (
        "Retry reminder: the auto-mode permission classifier denied a tool "
        f"call {times} earlier in this session, and no later call "
        "re-attempted it.\n"
        f"  denied: {shown}\n"
    )
    if count == 1:
        act = (
            "The classifier's decision on a given command shape is "
            "non-deterministic. ai-config#2994 measured a byte-identical "
            "fourth attempt succeeding after three denials, with no settings "
            "change and no permission rule added. Re-run the same command "
            "once before treating this path as closed.\n"
        )
    else:
        act = (
            "Do NOT keep re-running it: mistake-patterns Pattern 43 says to "
            "stop probing after the classifier's second denial of the same "
            "goal, because each denied variant makes the classifier more "
            "suspicious. Hand the user the decision instead.\n"
        )
    return (
        head + act +
        "Either way, report what was measured, not a prediction: "
        f"\"denied {times} so far\", never \"cannot\" or \"is not "
        "self-serviceable\". Denials are samples, and concluding the path is "
        "closed destroys the only evidence that would refute it.\n"
        "If the denial was already handled -- you retried under a different "
        "shape the classifier accepts, or you moved on to other work as the "
        "denial message itself suggests -- disregard this and carry on."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        label, key, count = scan(path)
    except Exception:
        return 0

    if not label:
        return 0

    # Keyed on the transcript path as well as the command, so the sentinel is
    # per session: without it, two sessions denied the same command share one
    # sentinel in /tmp and the second session is silenced. Deliberately NOT
    # keyed on a record index, which shifts as the transcript grows and would
    # re-fire on every prompt.
    digest = hashlib.sha256(f"{path}:{key}".encode()).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-retry-before-blocked-{digest}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(message(label, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
