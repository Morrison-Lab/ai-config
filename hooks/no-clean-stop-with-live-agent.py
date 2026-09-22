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
after everything that could have put an agent in flight. That is the decidable
condition:

    the final message declares a CLEAN stopping point
    AND a subagent was dispatched in this session
    AND no liveness check appears after BOTH the last task-notification
        and the last dispatch

A liveness check is trusted INDEFINITELY once it clears that bar: nothing
relates it to the declaration in time. So `dispatch, notification, check,
[twenty unrelated turns], declare clean` discharges, even with an agent that
was live when the check ran and is live still. Bounding the check to the
declaring turn would close that, and would also widen the arm, which is the
wrong default for a blocking guard (see the note below) without a measurement
of how often a legitimate session checks in one turn and declares in the next.
Tracked as ai-config#3749.

The second half of that last line is not redundant with the first. Keying only
on the notification left the guard silent in the corpus's own standard shape --
dispatch, read the result, check liveness, dispatch a sidecar, declare clean --
because the sidecar is running at declaration time and has never notified. It
would then fire only once that agent FINISHED, which inverts the guard against
the very incident below.

Monitors are deliberately out of scope. A monitor watching an already-merged PR
is not outstanding work, and blocking on one would fire on nearly every session
that ever armed a watch -- which is how a guard gets switched off, taking the
real cases with it (`shared/principles/deterministic-tools.md`).

Blocks rather than warns, because the claim is wrong to SEND: a clean
declaration is what tells a reader the session may be closed, so its cost is
paid by whoever acts on it. The remedy costs one tool call.

That last sentence is load-bearing wherever this file breaks an ambiguity
toward arming, and it is NOT the generic blocking-guard case.
`shared/workflow/algorithmatize-checks.md` says a blocking guard's false
positive costs "a stalled turn and a workaround search", so a blocking guard
gets no default lean and wants the narrowest matcher that still catches the
real cases. That reasoning is about a guard that STOPS AN ACTION: the author
wanted to do a thing, cannot, and has to find another way. A `Stop` guard
stops nothing. It declines to end the turn, and the author always has another
tool call available -- run `ListAgents`, then say the same sentence again. No
action is blocked and there is nothing to work around, which is why the cost
here really is one tool call rather than a stalled turn.

The corpus's caution still binds on the OTHER axis, though: a matcher that
arms on prose it should not read as a declaration produces a refusal the
author cannot discharge by checking anything, because nothing was ever live.
So the lean toward arming is taken only where the ambiguity is about EVIDENCE
(an unparseable command, an unterminated fence, an order that was never
established), and never to widen what counts as a declaration -- which is why
an indented code block is excluded below rather than read as prose.

Fails OPEN on any parse trouble, and fires at most once per distinct message.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile


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

# CommonMark's indented code block, which `scripts/lib/fences.py` does not
# model. RX_CLEAN opens with `^\s*`, so without this an example declaration
# written as an indented block matches.
RX_INDENTED_CODE = re.compile(r"^(?: {4,}|\t)")

# Tools that dispatch background work whose execution outlives the call.
# `Workflow` belongs here for the same reason `Agent` and `Task` do: its own
# tool definition says it "returns immediately with a task ID, and a
# <task-notification> arrives when the workflow completes", which is exactly
# the async shape this guard exists to catch.
#
# `invoke_subagent` is Antigravity's name for the same thing, and it reaches
# this hook unrewritten: plugins/ai-config/claude-hook-adapter.py translates
# tool names on the LIVE PreToolUse payload, but forwards `transcriptPath`
# untouched, so a Stop hook reading the transcript itself sees the native
# name. Ten sibling hooks in this directory already match it for that reason.
# Omitting a name does not weaken the guard, it disables it: `main()` returns
# 0 outright when no dispatch was seen.
DISPATCH_TOOLS = {"agent", "task", "workflow", "invoke_subagent"}

# Tools that answer "is it still running?". ListAgents is the direct one; a
# worktree lock query is the indirect one the measured case had in hand.
LIVENESS_TOOLS = {"listagents"}

# Shell tools, whose command text is parsed for a worktree query. Same reason
# as above: the transcript carries each harness's native name, so matching
# only "bash" would ignore a real liveness check run anywhere else. The set
# matches hooks/no-unshipped-commit.py's and remind-both-sides-from-git.py's.
SHELL_TOOLS = {"bash", "run_command", "execute_command", "terminal", "shell"}

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

try:
    from fences import strip_fences
except Exception as _exc:  # broken install
    print("no-clean-stop-with-live-agent: cannot load scripts/lib/fences.py "
          "({0}); fenced examples will be read as prose".format(_exc),
          file=sys.stderr)
    strip_fences = None


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
    """True when a CLEAN stopping-point declaration appears outside a fence.

    Fences are stripped with `scripts/lib/fences.py`, the repo's shared
    CommonMark implementation, rather than re-derived here. The hand-rolled
    pair that stood here first missed a multi-backtick span and, worse, let an
    UNCLOSED fence swallow every following line -- so a declaration written
    below an unterminated example block was invisible and the guard silently
    discharged. That pair is still live in `require-stopping-point.py`, the
    sibling it was copied from, where the consequence runs the other way (it
    asks for a declaration that is present); filed as ai-config#3748 rather
    than fixed here, since it is a different hook's behavior. `swallow_unclosed=False` is passed EXPLICITLY rather than
    taken from `fences.py`'s default: it is an evidence ambiguity resolved
    toward arming, per the module docstring, and a later change to that
    default would otherwise flip this hook to the discharging direction with
    nothing in this file's suite pointing at the cause.

    Lines indented four or more spaces are skipped. `fences.py` recognises a
    fence at indent 0-3 and has no handling for CommonMark's indented code
    blocks, so an example declaration written as an indented block -- or
    inside a fence nested in a list item, which indents the fence itself --
    was read as prose and armed the guard. That is the widening direction the
    module docstring rules out: the author cannot discharge it by checking
    anything, because nothing was live. This hook's own block message tells
    the author to write a declaration, which is exactly when they are most
    likely to indent one.

    Inline code spans are NOT stripped. A strip was written here first and
    removed as dead code: RX_CLEAN is line-anchored and its optional prefixes
    are a list bullet, an ordered marker, a heading marker and `**`, so a
    backtick can never precede `Stopping Point` in a matching line. Stripping
    could therefore only ever CREATE a match (`` `x`Stopping Point: Clean ``),
    which is the false-arm direction. Mutation testing confirmed it: deleting
    the call left every assertion green, which is the signal this file already
    records for the removed lookahead.
    """
    if not text:
        return False
    if strip_fences is None:
        # Broken install: scan the raw text. Arms more often, never less.
        return bool(RX_CLEAN.search(text))
    for line in strip_fences(text, swallow_unclosed=False).splitlines():
        if RX_INDENTED_CODE.match(line):
            continue
        if RX_CLEAN.search(line):
            return True
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


def timestamp_key(record):
    """A record's own timestamp, or None when it carries none that parses.

    Copied in shape from hooks/no-unshipped-commit.py's `_timestamp_key`,
    which solves the same ordering problem for the same reason.
    """
    stamp = record.get("timestamp")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def scan(path):
    """Return (last_text, dispatch_idx, notification_idx, liveness_idx, ordered).

    The three indices are ORDINALS INTO CHRONOLOGICAL ORDER, not line numbers,
    and -1 when absent. Only their relative order is ever compared, and only
    when `ordered` is True -- that flag is part of the contract, not a
    diagnostic: it says whether chronology was ESTABLISHED at all, and a
    caller that compares the ordinals without consulting it is reading an
    order the transcript never supplied.

    File order is not time order. A context compaction replays earlier records,
    appending them below newer ones while they keep their original timestamps
    -- the "last X in the transcript" unsoundness
    `memories/claude-code-transcripts.md` names, and the one
    `hooks/no-unshipped-commit.py` already fixes this way. It matters here
    specifically: a replayed liveness check from BEFORE the dispatch would land
    below a genuine notification in file order and discharge the guard, which
    fails silently because every record parses and the reader simply holds the
    wrong one.

    Records are sorted by their own timestamps, stably, and ONLY when every
    record carrying an event of interest has one that parses and compares. A
    mix of stamped and unstamped records has no total order to impose, and
    neither do aware and naive stamps together, so file order stands in both
    cases rather than a guessed one.

    `last_text` is deliberately NOT reordered. This is a `Stop` hook, so the
    message under judgement is the one just appended, which is the last in FILE
    order whatever the timestamps say.
    """
    last_text = ""
    events = []  # (timestamp_key, file_position, kind)
    position = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            position += 1
            try:
                event = json.loads(line)
            except Exception:
                continue

            # Each RECORD is walked under its own guard. `main()` fails open on
            # any exception, so without this a single record of an unexpected
            # shape -- a string-valued `message`, a bare JSON list, a tool_use
            # whose `input` is a string, a null `text` -- would abort the scan
            # and silently disable the guard for the WHOLE session, with no
            # output. That is the discharging direction, reached by exactly the
            # malformed input this hook is most likely to meet: the Antigravity
            # adapter already handles a subagent argument arriving as a JSON
            # string (plugins/ai-config/claude-hook-adapter.py). Aborting the
            # scan loses the guard.
            #
            # The per-block work has its OWN guard below, so a raising block
            # costs that block alone. A single record-level try wrapping the
            # block loop was measurably worse than it reads: a record holding
            # a malformed text block followed by two dispatches lost BOTH
            # dispatches, so "at most one event" was false. An argv-array
            # `command` is an ordinary schema for the foreign shell tools
            # SHELL_TOOLS deliberately covers, so this is not a contrived
            # shape (ai-config#3692 review).
            try:
                stamp = timestamp_key(event)
                role = event.get("type") or event.get("role")
                blocks = (event.get("message") or {}).get("content") or event.get(
                    "content"
                ) or []

                # Decided once per RECORD, from structured metadata, so no
                # block's text can manufacture one.
                if is_task_notification(event) and role != "assistant":
                    events.append((stamp, position, "notification"))

                if isinstance(blocks, str):
                    if role == "assistant" and blocks.strip():
                        last_text = blocks
                    continue

                if not isinstance(blocks, list):
                    continue

                # Collected per record, then joined with a NEWLINE. Keeping
                # only the LAST non-empty block dropped a declaration followed
                # by any further text in the same message ("... Clean stopping
                # point reached", then "Let me know if anything else"), which
                # discharged the guard on a message that plainly declared.
                #
                # The separator is a deliberate choice with a cost on each
                # side, not a free one, and a test pins it either way. `""`
                # would concatenate as rendered and miss a declaration split
                # across two blocks. `"\n"` introduces a line boundary the
                # rendered message does not have, so two blocks reading
                # "Do not write " / "**Stopping Point**: Clean ..., ever."
                # arm the guard although the sentence is a prohibition. That
                # is the arming direction on a `Stop` guard, discharged by one
                # tool call, whereas the `""` miss is the incident itself.
                texts = []
                for b in blocks:
                    try:
                        if not isinstance(b, dict):
                            continue
                        kind = b.get("type")

                        if kind == "tool_use":
                            name = (b.get("name") or "").lower()
                            if name in DISPATCH_TOOLS:
                                events.append((stamp, position, "dispatch"))
                            elif name in LIVENESS_TOOLS:
                                events.append((stamp, position, "liveness"))
                            elif name in SHELL_TOOLS:
                                raw = b.get("input")
                                cmd = raw.get("command") if isinstance(
                                    raw, dict
                                ) else None
                                if isinstance(cmd, str) and is_liveness_command(
                                    cmd
                                ):
                                    events.append((stamp, position, "liveness"))

                        elif kind == "text":
                            piece = b.get("text")
                            if isinstance(piece, str) and piece.strip():
                                texts.append(piece)
                    except Exception:
                        continue

                if role == "assistant" and texts:
                    last_text = "\n".join(texts)
            except Exception:
                continue

    # `ordered` records whether chronology was actually ESTABLISHED. Three
    # cases, and only the third is ambiguous:
    #
    #   every event stamped  -> sort by stamp. Authoritative, and the point of
    #                           stamping: memories/claude-code-transcripts.md
    #                           documents a compaction replaying earlier
    #                           records BELOW newer ones while they keep their
    #                           original stamps, so file order lies here and
    #                           the stamps do not.
    #   no event stamped     -> file order, and nothing contradicts it. A
    #                           transcript with no stamps at all is read in the
    #                           order it was written, which is the ordinary
    #                           reading and must stay sound.
    #   some stamped         -> neither signal covers the set, and a partial
    #                           sort would interleave measured times with
    #                           guessed ones. Same for aware and naive stamps
    #                           together, which do not compare. Ambiguous.
    #
    # An ambiguous order ARMS rather than discharges, per the asymmetry this
    # module states: a wrongly-armed guard costs one tool call, a wrongly-
    # discharged one costs the incident.
    stamps = [e[0] for e in events]
    ordered = True
    if events and any(s is not None for s in stamps):
        if all(s is not None for s in stamps):
            try:
                events.sort(key=lambda e: (e[0], e[1]))
            except TypeError:
                ordered = False
        else:
            ordered = False
    # No fallback re-sort here. When `ordered` is False the only uses of the
    # ordinals are a presence test (`dispatch < 0`) and a comparison the
    # caller short-circuits on `ordered`, so a re-sort by file position is
    # unobservable -- it survived its own deletion under mutation, which is
    # the signal this file already records for the removed lookahead and the
    # removed inline-code strip.

    dispatch = notification = liveness = -1
    for ordinal, (_stamp, _position, kind) in enumerate(events):
        if kind == "dispatch":
            dispatch = ordinal
        elif kind == "notification":
            notification = ordinal
        else:
            liveness = ordinal

    return last_text, dispatch, notification, liveness, ordered


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
        last_text, dispatch, notification, liveness, ordered = scan(path)
    except Exception:
        return 0  # fail open

    if not last_text or not declares_clean(last_text):
        return 0
    if dispatch < 0:
        return 0  # no subagent was ever dispatched

    # A liveness check discharges the guard only if it comes after EVERY event
    # that could have put an agent in flight -- the most recent notification
    # AND the most recent dispatch.
    #
    # Taking the notification alone was wrong in the discharging direction, and
    # wrong on the corpus's own standard shape: dispatch, read the result,
    # check liveness, dispatch a sidecar, declare clean. There the second agent
    # is running at declaration time and has never notified, so pinning the
    # baseline to the last notification left the guard silent exactly while an
    # agent was live -- and firing only once that agent had FINISHED, which
    # inverts it against the incident it was built for (ai-config#3689).
    baseline = max(notification, dispatch)

    # An order that was never established cannot show a check came later.
    if ordered and liveness > baseline:
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
                    "after the last task-notification OR the last dispatch, "
                    "whichever came later.\n\n"
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
                    "skills/clean-worktrees/SKILL.md; read the lock itself per "
                      "memories/subagent-worktrees.md."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
