#!/usr/bin/env python3
"""UserPromptSubmit reminder: a classifier denial is a sample, not a wall.

ai-config#2994, measured 2026-09-02 (PT): an
`ALLOW_UNREVIEWED_PUSH=1 git push` and the attempt to grant it a permission
rule were denied by the auto-mode permission classifier three times over, and
the session reported the path as permanently closed -- in a blocking report to
the user, in a project memory entry, and in a comment on this repo's own
tracker. With no settings change and no permission rule added, the
byte-identical command then succeeded.

How many of those three denials were the command ITSELF is not settled by the
issue, and this file deliberately does not settle it either. #2994's headline
says "three identical denials" and calls the success "the fourth attempt";
its narrative lists the push, one identical re-run, and an `update-config`
edit adding the allow rule, which would make the success the command's third
attempt. Every claim here is worded to hold under both readings, because the
design turns on the success arriving after the point the session stopped --
not on which attempt number it was.

Repeated denials do not FEEL like a claim. They feel like a measurement: the
thing was tried, and the system said no, again and again. So "I cannot do
this" reads as reporting an observation rather than asserting a fact about the
future, and none of the claim-checking rules that would otherwise fire
(`metacognitive-monitoring.md` on a claim about state, `ardi.md` on verifying
an asserted blocker) engages at all. The conclusion is also self-confirming:
deciding the path is closed means stopping, which destroys the only evidence
that would refute it.

WHAT THE EVIDENCE SUPPORTS, AND WHAT IT DOES NOT
------------------------------------------------
It supports exactly one thing: a denial is a sample, so "cannot" is a
prediction the reading does not license. It does NOT establish that the
classifier is non-deterministic as a standing property of the service. That
reading is n=1 and undated, and the corpus already records a competing one.
`memories/mistake-patterns.md` Pattern 43 reports three denials of one goal in
three different phrasings as "consistent denials, not stochastic ones", and
attributes a later acceptance of the same override to a session restart
refreshing the classifier's per-conversation state.

#2994 does not record whether its successful attempt followed a restart, so
the two readings are unsettled. The reminder this hook prints is right under
either: re-running the identical command once is cheap, and reporting "denied
N times so far" instead of "cannot" is accurate whichever mechanism holds. Any
claim stronger than that would be asserting the thing the incident is about.

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
tool call re-attempting the same command. Fires once per DENIAL of a distinct
command, keyed by a content hash of the command, the number of times it has
been denied in this transcript, and the transcript path: a reminder repeated
every turn is noise, and noise is what gets a guard ignored, but each fresh
denial is new information and gets its own one-time reminder. At most one
reminder is printed per prompt, the OLDEST unreminded one, so several denied
commands surface over several prompts rather than all at once -- oldest
because the original command is the one the evidence is about, and the newest
is whatever the session most recently reworded it into.

The number in that key is the RUNNING TOTAL, which only ever grows. The number
that decides the ADVICE is the current STRETCH, which resets -- so the two are
deliberately different. Keying on the stretch would swallow the one reminder
the reset exists to produce: denied, allowed to run, denied again would
compute a stretch of 1, match the sentinel already written for the first
denial, and say nothing. The message reports the total and turns on the
stretch, which is why both are computed.

The stretch resets when the permission layer LET THE COMMAND THROUGH -- not
when it succeeded. That is a choice about what the number means, not a
concession to what the transcript can show. Measured over the same corpus on
2026-09-02: every one of 49,517 Bash tool results carries `is_error`, and all
1,036 whose content begins `Exit code N` carry it true, so a nonzero exit is
visible. What `is_error` does NOT do is separate a failure from a refusal --
it is true on 1,822 results against those 1,036 -- and content-sniffing for
"fatal:" matches any command that merely PRINTS such a line.

(An earlier draft of this paragraph asserted the opposite, that a Bash failure
"frequently carries no `is_error` at all" and that the exit status lands in
the carrier's `toolUseResult`. Both are false: absent zero times out of
49,517, and `toolUseResult` carries `stdout`/`stderr` and no exit-status key.
The claim came from a review and was written down without being re-derived,
which is the one thing this file's own subject matter argues against. It is
recorded rather than deleted because the design it justified is unchanged.)

"Permitted" is the property the count needs anyway, and that is the actual
argument. The number the message quotes answers "how many times has the
classifier refused this in a row", so an attempt the classifier allowed ends
the run whatever the command then did. A denial of any OTHER kind does not: a
permission-rule refusal, a hook refusal, and the user's own rejection all
leave the classifier's run intact. The user case is the one that matters most
-- resetting there would answer a decision to respect with a recommendation
to re-run.

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
                            cannot determine the safety of Bash right now
                            ..."
  user-rejected          6  "The user doesn't want to proceed with this tool
                            use. ..."

`automode-unavailable` is deliberately out of scope. It is transient too, so
retrying is reasonable, but it is the classifier being ABSENT rather than the
classifier denying, and #2994's finding is about a decision that varied -- not
about an outage. Widening to it is a separate change with its own evidence.

WHAT THE SECOND DENIAL CHANGES, AND WHAT IT DOES NOT
-----------------------------------------------------
Past the first denial of the stretch, the reminder stops RECOMMENDING a
further re-run and starts warning against rephrasing. It does not tell the
session to stop re-running, and that distinction is load-bearing enough to
state twice, because the obvious message here would reproduce the incident
exactly.

#2994's success arrived after three denials, on either reading of how many
were the command itself. A message answering the second denial with "hand the
user the decision" and nothing else would stop the session short of the thing
that worked -- which is precisely what the incident session did. So the
second-denial branch says an identical re-run is still supported, and reserves
"hand the user the decision" for the case where the session stops anyway.

What it does warn off is variation, which is Pattern 43's actual mechanism:
"each denied variant makes the classifier more suspicious", its three denials
being three different phrasings of one override. A byte-identical re-run
presents no new variant, so that mechanism does not reach it.

That warning cannot hang off either count, and getting this wrong is easy:
rephrasing produces a NEW command, so each variant carries a stretch of 1 and
a total of 1, and a warning attached to a second denial never fires in the one
shape Pattern 43 measured. It keys instead on how many distinct commands are
standing denied with no re-attempt -- the candidate count, which is the only
trace rephrasing leaves. A command the classifier later allowed drops out of
that count, because an allowed run is a re-attempt: an escalation that has
relented is not one to warn about. The number still cannot tell three
phrasings of one goal from three unrelated commands, so the text says "if they
are rephrasings of one goal" rather than asserting it.

On the second denial itself the hook states the tension and stops. Pattern
43's Do bullet says to stop probing after the second denial of the same goal
and hand the user the decision; #2994 measured a success after three denials.
Both are in this corpus, neither has been retired, and a guard is the wrong
place to settle it -- so the message puts both to the user, which is what
Pattern 43's Do bullet asks for anyway. Reconciling the two texts is tracked
as ai-config#3008.

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
"""
import hashlib
import json
import os
import sys
import tempfile

# The classifier's own denial, as it appears in the tool result.
#
# Two guards sit on this text path, and both were measured on 2026-09-02
# across the same 1110 transcripts: all 79 classifier denials carry
# `is_error: true` on the block and start with this sentence. The `is_error`
# requirement is what stops a SUCCESSFUL read whose output happens to begin
# with a stored denial -- a `jq` of a saved transcript, a `head` of a log --
# from reading as a denial of the read itself.
CLASSIFIER_MARKER = (
    "Permission for this action was denied by the Claude Code auto mode "
    "classifier"
)

# The structured form of the same fact, carried on the tool_result's CARRIER
# record rather than on the block. Used as an alternative signal, not as the
# only one: the field is present in the harness layout measured on 2026-09-02,
# and a layout that drops it must still be readable from the text.
CLASSIFIER_KIND = "automode-blocked"

BASH_TOOLS = (
    "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
)


def identity(name, inp):
    """Return (key, raw) naming "the same command" across a retry.

    The KEY collapses whitespace deliberately: a re-attempt that differs only
    in indentation or line wrapping IS a retry, and treating it as one
    produces silence, the safe direction for a guard that can only nag.

    The second return value is the command UNTOUCHED, because the two uses
    pull opposite ways and sharing one string got it wrong. The message asks
    for a byte-identical re-run and quotes the command underneath, so a
    displayed string that merely matches is worse than useless: collapsing a
    newline inside a multi-line script turns `... 2>&1\necho x` into
    `... 2>&1 echo x`, which is a different command in shell, and the change
    is invisible -- unlike the length truncation, which marks itself. A
    session re-issuing the displayed text would produce exactly the reworded
    variant this hook's own message warns against.
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
    collapsed = " ".join(raw.split())
    if not collapsed:
        return "", ""
    return name + "\x00" + collapsed, raw


def is_classifier_denial(record, block):
    """True only for the auto-mode classifier's own refusal."""
    if record.get("toolDenialKind") == CLASSIFIER_KIND:
        return True
    if not block.get("is_error"):
        return False
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    if not isinstance(content, str):
        return False
    return content.lstrip().startswith(CLASSIFIER_MARKER)


# The user's own rejection, verbatim from the 6 measured `user-rejected`
# records. Checked as a second signal beside `toolDenialKind`, because this is
# the one case where a missing field would do real harm: the hook would answer
# a decision to respect with a recommendation to re-run.
USER_DENIAL_MARKER = "The user doesn't want to proceed with this tool use"


def permitted(record, block):
    """True when the permission layer let this call through.

    Deliberately NOT "the call succeeded", which is not decidable here -- see
    the module docstring's stretch paragraph. Any denial, of any kind, leaves
    the classifier's run of refusals intact.
    """
    if record.get("toolDenialKind"):
        return False
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(
            c.get("text") or "" for c in content if isinstance(c, dict))
    if isinstance(content, str) and content.lstrip().startswith(
            USER_DENIAL_MARKER):
        return False
    return True


def records(path):
    """Yield each transcript record once.

    The harness sometimes REPLAYS a record into the same file -- same `uuid`,
    same `parentUuid`, same timestamp, hundreds of lines apart. Measured
    2026-09-02: 4 of 1191 transcripts under `~/.claude/projects` carry 4,435
    such duplicates between them. None has yet landed on a classifier denial,
    which is why this is a guard rather than a bug report.

    Counting one would be worse than merely wrong. A single denial would read
    as two, so the reminder would say "you have already re-run it" when
    nothing was re-run, withhold the one instruction #2994 asked for, and
    tell the session to report a count that is double the truth -- inside a
    message whose closing line is "report what was measured".

    A record with no `uuid` is passed through, since synthetic and older
    records have none and dropping them would cost real coverage.
    """
    seen = set()
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            uid = rec.get("uuid") if isinstance(rec, dict) else None
            if uid is not None:
                if uid in seen:
                    continue
                seen.add(uid)
            yield rec


def read_transcript(path):
    """Return (attempts, denied, ran, labels).

    attempts  [(index, key)] for every tool call, in transcript order
    denied    key -> [index of each call the classifier denied]
    ran       key -> [index of each call that produced any other result]
    labels    key -> the human-readable command
    """
    uses = {}
    attempts = []
    denied = {}
    ran = {}
    labels = {}

    for i, rec in enumerate(records(path)):
        # A subagent's denial is not this session's to retry, and its
        # transcript is a separate file anyway. Same guard, and same reasoning,
        # as remind-ums-after-error.py's.
        # `null`, `[]` and `5` are valid JSON lines with no `.get`. Without
        # this guard one of them raises, `main`'s blanket except swallows it,
        # and the whole scan is lost -- silently, for the rest of the session.
        # Same defect class as the stdin guard in `main`, on the surface that
        # carries thousands of lines instead of one.
        if not isinstance(rec, dict):
            continue
        if rec.get("isSidechain"):
            continue
        blocks = (rec.get("message") or {}).get("content") or rec.get("content")
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                key, raw = identity(b.get("name") or "", b.get("input") or {})
                if key:
                    uses[b.get("id")] = (i, key)
                    attempts.append((i, key))
                    labels[key] = raw
            elif b.get("type") == "tool_result":
                seen = uses.get(b.get("tool_use_id"))
                if not seen:
                    continue
                at, key = seen
                if is_classifier_denial(rec, b):
                    denied.setdefault(key, []).append(at)
                elif permitted(rec, b):
                    ran.setdefault(key, []).append(at)

    return attempts, denied, ran, labels


def unretried(path):
    """Return (candidates, shapes) for the denials with no re-attempt.

    Each candidate is (label, key, stretch, total). `stretch` is the run of
    denials since the classifier last let the command through, which is what
    the advice turns on; `total` is every denial of it in this transcript,
    which is what the message reports and what the sentinel keys on, because
    it never goes back down. `shapes` is simply how many candidates there
    are -- distinct commands standing denied with no re-attempt -- which is
    the only visible trace of a session rephrasing one goal. A command the
    classifier later allowed is excluded by the candidate filter itself,
    because an allowed run IS a re-attempt: counting it would report an
    escalation that has already relented. Deriving `shapes` separately was
    tried and dropped; it differed from the candidate count only for a
    re-attempt with no recorded result, which is a transcript still being
    written rather than a distinction worth carrying.

    Ordered by each command's FIRST denial. The command denied earliest is
    the original; a command first denied later is what the session reworded
    it into. Reporting the newest first replays #2994 by naming the settings
    edit before the push, and citing "with no settings change" as the reason
    to re-run it -- and ordering by each command's most RECENT denial has the
    same effect as soon as the session interleaves them.
    """
    attempts, denied, ran, labels = read_transcript(path)
    out = []
    for key, hits in denied.items():
        last = max(hits)
        if any(j > last for j, other in attempts if other == key):
            continue
        floor = max(ran.get(key) or [-1])
        out.append((labels.get(key, ""), key,
                    sum(1 for j in hits if j > floor), len(hits), min(hits)))
    # `min(hits)`, not `last`. Sorting on the most recent denial of each
    # command reorders them whenever the session interleaves -- push denied,
    # workaround denied, push denied again puts the workaround first, which is
    # the ordering this sort exists to prevent.
    out.sort(key=lambda row: row[4])
    candidates = [row[:4] for row in out if row[0]]
    return candidates, len(candidates)


def message(label, stretch, total, shapes=1):
    """The reminder text.

    `stretch` decides the advice, `total` is what gets reported. Quoting the
    stretch under session-total wording ("denied once so far") would tell the
    session to under-report the exact number this hook exists to make
    accurate. `shapes` decides whether the variation warning is included: it
    keys on distinct denied COMMANDS rather than on either count, because
    rephrasing produces a new command with a stretch of 1 every time, so a
    warning attached to a repeat count can never reach the shape Pattern 43
    actually measured.
    """
    # An indented block rather than an inline value, so a multi-line command
    # keeps its line structure instead of being collapsed into a different
    # shell command. The six-space indent is display framing and is the one
    # thing here that is not the command: a quoted heredoc's terminator is
    # indented with the rest, so the block is a faithful RENDERING of the
    # command rather than a copy-paste-ready one. Truncation marks itself
    # with an ellipsis; a whitespace collapse would not, which is why the
    # collapsed matching key is never what gets displayed.
    text = label if len(label) <= 300 else label[:297] + "..."
    shown = "\n".join("      " + line for line in text.splitlines()) or "      "
    run = "once" if stretch == 1 else f"{stretch} times"
    session = "once" if total == 1 else f"{total} times"
    if stretch == total:
        seen = f"denied a tool call {run} in this session"
    else:
        seen = (f"denied a tool call {run} in a row -- {session} in this "
                "session, with an allowed run in between")
    head = (
        "Retry reminder: the auto-mode permission classifier " + seen +
        ", and no later call re-attempted it.\n"
        "  denied:\n" + shown + "\n"
    )
    if stretch == 1:
        act = (
            "A denial is a sample, not a wall. ai-config#2994 measured a "
            "byte-identical command succeeding after three denials, with no "
            "settings change and no permission rule added. Re-run the same "
            "command once before treating this path as closed.\n"
        )
    else:
        # Deliberately NOT a verdict either way. The corpus is in genuine
        # tension here: Pattern 43's Do bullet says stop probing after the
        # second denial of the same goal and hand the user the decision,
        # while #2994 measured the same command succeeding after three
        # denials. This hook is not the place to settle that, so it states
        # both and gives the decision to the person the Do bullet names.
        act = (
            "You have already re-run it, and the corpus pulls both ways from "
            "here. mistake-patterns Pattern 43 says to stop probing after "
            "the classifier's second denial of the same goal and hand the "
            "user the decision (push manually, restart the session, add a "
            "permission rule); #2994 measured a byte-identical command "
            "succeeding after three denials. Put both to the user and let "
            "them choose, rather than settling it by declaring the path "
            "closed.\n"
        )
    warn = ""
    if shapes > 1:
        warn = (
            f"{shapes} distinct commands are standing denied by the "
            "classifier, none of them re-attempted since its last denial. "
            "If they are rephrasings of one goal, stop generating "
            "new shapes: Pattern 43 records each denied variant making the "
            "classifier more suspicious, until it denied even the sanctioned "
            "paths. An identical re-run is not a new variant; a reworded one "
            "is.\n"
        )
    return (
        head + act + warn +
        "Either way, report what was measured, not a prediction: "
        f"\"denied {session} so far\", never \"cannot\" or \"is not "
        "self-serviceable\". Concluding the path is closed also destroys the "
        "only evidence that would refute it.\n"
        "If the denial was already handled -- you retried under a different "
        "shape the classifier accepts, or you moved on to other work as the "
        "denial message itself suggests -- disregard this and carry on."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    # `null`, `[]`, `"x"` and `5` all parse cleanly and have no `.get`, so
    # without this the hook exits 1 with a traceback on input the docstring
    # promises to fail open and silent on.
    if not isinstance(payload, dict):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        candidates, shapes = unretried(path)
    except Exception:
        return 0

    for label, key, stretch, total in candidates:
        # Keyed on the transcript path as well as the command, so the sentinel
        # is per session: without it, two sessions denied the same command
        # share one sentinel in /tmp and the second session is silenced. Keyed
        # on the RUNNING TOTAL as well, so every fresh denial of an
        # already-reported command gets its own one-time reminder -- that is
        # when the advice changes, and when the session most needs it. The
        # total is used rather than the stretch the message quotes, because
        # the stretch returns to 1 after a success and would collide with the
        # sentinel already written for the first denial.
        digest = hashlib.sha256(
            f"{path}:{key}:{total}".encode()).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-retry-before-blocked-{digest}")
        if os.path.exists(sentinel):
            continue
        try:
            open(sentinel, "w").close()
        except Exception:
            pass
        print(message(label, stretch, total, shapes))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
