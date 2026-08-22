#!/usr/bin/env python3
"""Stop-hook guard: a promise about future behaviour owes a MECHANISM.

Standing `cai` (2026-08-19): "no empty promises; every promise ('going
forward, I will/won't' etc) must be accompanied by an implemented mechanism
for ensuring accountability (for example, a memory + hook pair)".

WHY A PROSE RULE CANNOT CARRY THIS ONE
--------------------------------------
The rule is itself a promise about future behaviour, so a version of it that
ships as prose alone is an instance of the thing it forbids. That is not a
rhetorical point: a promise is composed at exactly the moment a correction
lands, when the corpus is not being read, and it *feels* like the corrective
action rather than like a substitute for one. Nothing downstream detects it --
no file changes, no check turns red, and the reply reads as responsive.

WHY THIS BLOCKS RATHER THAN REMINDS
-----------------------------------
The opposite call from remind-ums-after-error.py and
no-mistake-without-a-hook.py, and for a reason that inverts cleanly.

An error admission is RIGHT to send, so blocking it would suppress an honest
correction; those hooks therefore inject on the next prompt instead. An
undischarged promise is WRONG to send: it costs the user a turn spent reading
a commitment that nothing will keep, and delivering it first buys nothing,
because the mechanism is what the promise was for. So this guard sits at
`Stop`, where the reply can still gain its mechanism before going out.

Nothing here suppresses a correction. Admitting a mistake, reporting a fact,
and apologizing all pass untouched; only the forward-looking commitment is
matched, and only when the same turn produced no durable mechanism.

TWO KINDS OF PROMISE, TWO KINDS OF MECHANISM
--------------------------------------------
A RULE promise commits to a class of future occasions -- "going forward I'll
always X". A DEBT promise commits to one specific outstanding action -- "I owe
#1937 the ARDI loop", "the UMS pass is owed by me".

They are both promises and they owe different things, which is why the guard
now asks a different question of each.

A rule is kept by something DURABLE: a write to a rule surface (`CLAUDE.md`,
`AGENTS.md`, `memories/`, `shared/`, `skills/`, `hooks/`,
`.claude/settings.json`), a filed issue, or a `memorize`/`ums` invocation.

A debt is kept by something that will FIRE: `ScheduleWakeup`, `CronCreate`, a
scheduled task, the `schedule`/`loop`/`workaround-watcher` skill, or the
repo's own detached PR poller. A durable record clears a debt too -- it is the
always-available floor, and the right answer when the debt is somebody else's
to schedule -- but it is the wrong instinct when the debt is yours and has a
next step, because a memory entry documents an outstanding ARDI loop without
running one. That asymmetry is the whole reason for the split: before it, the
cheapest way past a blocked "I owe #N the ARDI loop" was to write a memory
entry and re-send the same sentence, leaving the debt documented and still
undelivered.

The implication runs one way only. A timer does NOT clear a rule promise: it
fires once and dies, so admitting it there would let an unrelated wakeup
launder "going forward I'll always X".

Order within the turn does not matter -- the mechanism is normally built
before the closing message that states the rule.

Prose does NOT discharge, and neither does a read. Both are the same mistake
from opposite ends: a check keyed on a rule-surface path merely APPEARING
would pass "going forward I'll add `hooks/x.py`" -- the exact near-miss this
guard exists for -- and would also pass any turn that happened to `Read` or
`grep` a rule file, which is most of them. See `discharges()`.

There is deliberately no "not mechanizable" escape, unlike
no-mistake-without-a-hook.py. That hook needs one because a one-off factual
slip has no decidable condition to key a hook on. A promise always has at
least one mechanism available -- writing it down durably, which is the memory
half of the user's own "memory + hook pair" -- so the honest alternative to
building one is to not make the promise, and state the fact without it.

FALSE POSITIVES
---------------
Discussing this rule quotes its own trigger phrases constantly, this docstring
included. Matching runs over `visible_prose` from remind-ums-after-error.py,
which drops fenced blocks, blockquotes, and inline code -- so write an example
in backticks and it cannot fire. Capability statements ("I'll never be able to
know the exact time") are excluded explicitly rather than left to luck.

Fails OPEN and fires at most once per promise per session: a guard that wedges
a session costs more than the lapse it prevents.

Directive from the user, 2026-08-22 (ai-config#1946): "phrases with 'owe' ...
should be triggers for our no-empty-promises guards; the models should be
pushed or forced to create and report a mechanism for delivering on what they
owe, such as scheduling a timer or other PR-watcher to trigger the next step
of the ardi loop when it is time".
"""
import hashlib
import importlib.util
import json
import os
import re
import shlex
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location("_sib", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_ums = _sibling("remind-ums-after-error.py")

# Reuse the sibling's code-region stripping rather than copying it, so the two
# cannot drift. The fallback exists only so this hook degrades to silence
# instead of crashing when the sibling is missing.
visible_prose = getattr(_ums, "visible_prose", None)

# A first-person commitment about a CLASS of future occasions. Each
# alternative pairs a first-person modal with a generalizer, because "I'll
# open the PR now" is a statement about the next action and carries no
# promise at all -- the generalizer is what turns it into one.
#
# `_APOS` spells the typographic apostrophe a model actually emits as an
# escape rather than embedding the glyph, so this file stays pure ASCII per
# shared/coding/ascii-punctuation-in-source.md and still matches it.
_APOS = "['\u2019]"
_SUBJ = r"(?:i|we)"
_SUBJ_OBJ = r"(?:me|us)"
_MODAL = (r"(?:" + _APOS + r"ll|\s+will|\s+shall|\s+am\s+going\s+to|"
          + _APOS + r"m\s+going\s+to)")
_NEG = r"(?:\s+won" + _APOS + r"?t|\s+will\s+not)"

# Two kinds of promise, split because they owe DIFFERENT mechanisms.
#
# A RULE promise commits to a class of future occasions ("going forward I'll
# always X"). What keeps it is something durable that outlives the session.
#
# A DEBT promise commits to one specific outstanding action ("I owe #1937 the
# ARDI loop"). What keeps it is something that will actually FIRE -- an armed
# timer or watcher. See `discharges()` for why the two discharge sets differ.
_RULE_SRC = r"""(
    # Explicit temporal generalizer anywhere in the same sentence as a
    # first-person modal, in either order.
    #
    # `every time`/`each time` were here and are deliberately gone. They are
    # ordinary technical connectives in this corpus -- "we will lose the
    # summary every time compaction fires" describes a mechanism and promises
    # nothing -- and no phrasing test separates that from a commitment. The
    # commitment sense is already carried by `always`/`never` below. Removing
    # the ambiguous generalizer beats narrowing it, per
    # shared/workflow/learn-from-review-findings.md.
      (?:going\s+forward|from\s+now\s+on|from\s+here\s+on(?:\s+out)?
       |henceforth|in\s+(?:the\s+)?future|next\s+time)
      [^.!?\n]{0,80}?\b """ + _SUBJ + r"(?:" + _MODAL + r"|" + _NEG + r""")\b
    | \b """ + _SUBJ + r"(?:" + _MODAL + r"|" + _NEG + r""")\b
      [^.!?\n]{0,80}?
      (?:going\s+forward|from\s+now\s+on|from\s+here\s+on(?:\s+out)?
       |henceforth|in\s+(?:the\s+)?future|next\s+time)

    # "always"/"never" bound directly to the modal. The lookahead drops
    # capability statements -- "I'll never be able to know" is a limitation,
    # not a commitment.
    | \b """ + _SUBJ + _MODAL + r"""\s+
      (?:always|never)(?!\s+(?:be\s+able|know\b|have\s+access|see\b))

    # "I won't do that again" / "I will no longer do that".
    | \b """ + _SUBJ + _NEG + r"""
      (?!\s+(?:be\s+able|know\b|have\s+access|see\b|ever\s+see))
      \b[^.!?\n]{0,80}?\bagain\b
    | \b """ + _SUBJ + _MODAL + r"""\s*no\s+longer\b

    # Bare performatives, which need no generalizer to be promises.
    | \b """ + _SUBJ + r"""\s+(?:promise|commit)\s+to\b
    )"""

# A promise stated as an outstanding DEBT rather than as a modal.
# "The UMS pass is owed by me" commits to future behaviour with no modal
# anywhere in it, and it reads as bookkeeping rather than as a
# commitment, so it passes self-review more easily than "I'll do X"
# does -- which makes it the worse form, not a lesser one.
#
# Bound to a first-person OWNER deliberately. This corpus discusses owed
# work constantly ("an owed UMS pass", "the pass is owed", "a pass is
# owed" all appear in shared/workflow/run-ums-proactively.md as ordinary
# rule prose), so a bare `owed` would fire on every reply that cites
# those rules. That is the trap hooks/no-placeholder-reply.py avoids by
# anchoring rather than matching a substring.
_DEBT_SRC = r"""(
      \bowed\s+by\s+""" + _SUBJ_OBJ + r"""\b
    | \b """ + _SUBJ + r"""\s+(?:still\s+)?owe\b
    )"""

RULE = re.compile(_RULE_SRC, re.I | re.X)
DEBT = re.compile(_DEBT_SRC, re.I | re.X)
# Kept as the union so any consumer asking "is this a promise at all?" still
# gets one answer.
PROMISE = re.compile(_RULE_SRC + r"|" + _DEBT_SRC, re.I | re.X)

# `\b` is the wrong boundary for a bare action word: `-` and `/` are non-word
# characters, so `\bums\b` matches INSIDE
# `shared/workflow/run-ums-proactively.md`, and `cat`-ing that file discharged
# a promise. Anchor on path characters too.
#
# `.` is deliberately NOT excluded on its own. A first attempt used
# `(?![\w./-])`, which also rejected a sentence-final period, so `run ums.`
# stopped discharging -- the commonest phrasing of all. What marks a path is a
# dot with a word character AFTER it (`ums.md`), not a dot at a full stop.
_NOT_PATH = r"(?<![\w/-])"
_NOT_PATH_END = r"(?![\w/-]|\.\w)"

# Durable, inspectable rule surfaces. Wider than remind-ums-after-error.py's
# UMS_PATH, deliberately: a recorded learning is one kind of mechanism, and a
# hook or a harness setting is another that fragment's rule has no interest
# in. Each alternative demands a FILE rather than a bare directory, so a
# promise that merely mentions `shared/` in passing cannot discharge itself.
MECHANISM_PATH = re.compile(
    r"(?:\bmemories?/[\w.-]+\.md"
    r"|\bMEMORY\.md"
    r"|\b(?:CLAUDE|AGENTS|GEMINI)\.md"
    r"|\bshared/[\w./-]+\.md"
    r"|\bskills/[\w./-]+"
    r"|\bhooks/[\w.-]+\.(?:py|sh)"
    r"|\bhooks\.json"
    r"|\binstall-hooks\.py"
    r"|\.claude/settings(?:\.local)?\.json"
    r"|\b(?:commands|cursor-rules|codex-skills)/[\w./-]+"
    r"|\.cursor(?:-plugin)?/[\w./-]+)",
    re.I,
)

# Two kinds of "action word", split because they live in different payloads
# and only one of them is ever a shell command.
#
# FILING_CMD is a real command line. Seeing it in a `bash` payload means the
# command ran.
FILING_CMD = re.compile(
    r"\bgh\s+issue\s+create\b|\bglab\s+issue\s+create\b"
    r"|" + _NOT_PATH + r"issue_write" + _NOT_PATH_END,
    re.I,
)

# SKILL_WORD names a SKILL, invoked through the Skill/Task tools -- never a
# shell command. It is therefore only evidence inside a dispatch payload.
# Treating it as evidence in a `bash` payload made `grep -n ums README.md`
# and `grep -c memorize CLAUDE.md` discharge a promise, which is the opposite
# of this module's own rule that a read discharges nothing.
SKILL_WORD = re.compile(
    r"" + _NOT_PATH + r"ums" + _NOT_PATH_END +
    r"|update\s+memories"
    r"|" + _NOT_PATH + r"record[- ]learnings" + _NOT_PATH_END +
    r"|" + _NOT_PATH + r"memorize" + _NOT_PATH_END,
    re.I,
)

# Tools that ARM a later firing -- the delivery mechanism a DEBT owes.
#
# Verified against 232 local transcripts on 2026-08-22 rather than assumed:
# `ScheduleWakeup` appears 302 times as a tool name, `CronCreate` 18. The set
# otherwise follows hooks/no-unmonitored-pr.py's own `SCHEDULE` regex, which
# already treats exactly these as "a PR is being watched" -- so reading a
# scheduler call as a delivery mechanism is precedent in this repo rather
# than a new claim.
#
# Deliberately ABSENT:
#   * `CronList`, `CronDelete`, `list_scheduled_tasks` -- a read and a
#     teardown. `CronList` appears 13 times in those same transcripts, so the
#     near-miss is real, and a `create|update` anchor is what excludes it.
#   * `Monitor` (126 occurrences). Whether it spans turns or completes inside
#     the one that called it was not established here, and an in-turn wait
#     would have already finished by `Stop` -- so admitting it could discharge
#     a debt about what happens AFTER the wait. A `ScheduleWakeup` beside it
#     costs one call.
SCHEDULER_TOOL = re.compile(
    r"(?:^|__)(?:"
    r"schedulewakeup"
    r"|croncreate|cronupdate"
    r"|(?:create|update)_scheduled_task"
    r"|(?:create|update)_trigger"
    r"|send_later"
    r")$",
    re.I,
)

# Skills whose whole purpose is to arm a later firing. Matched against the
# `skill` FIELD exactly, never against brief prose: the noun/verb ambiguity
# that defeated three review rounds of `discharges()` ("what does the
# schedule skill do?") cannot arise against an exact field comparison.
#
# `ardi` is deliberately NOT here, and that exclusion is the point of the
# whole change. A debt sentence is composed in the closing recap AFTER a
# round has run and is waiting -- so admitting `ardi` would discharge
# precisely the reply this guard was extended to catch.
SCHEDULER_SKILLS = {"schedule", "loop", "workaround-watcher"}

# The repo's own detached poller, RUN rather than merely named.
#
# WHY A LEXER RATHER THAN A REGEX
# -------------------------------
# This started as a bare path match and took three consecutive review rounds,
# each closing one bypass and leaving the next:
#
#   round 1: `cat hooks/monitor-open-prs.py`          -- no execution required
#   round 2: `sh -c "cat hooks/monitor-open-prs.py"`  -- `-c` wrapping a read
#   round 3: `bash -x -c "cat ..."`, `python3.11 -c "cat ..."`
#                                                     -- a flag between the
#                                                        interpreter and `-c`,
#                                                        or a versioned name
#
# Every one of those is an ordinary command, and every one silently discharged
# a debt with nothing armed. The pattern across the three is not three
# oversights: matching a shell command with a regex asks the wrong question,
# because "is this token being EXECUTED?" is a fact about shell grammar and
# not about character adjacency. Per
# shared/coding/least-flexible-tool.md, the least-flexible construct that does
# this job is a shell lexer, so `shlex` replaces the regex rather than gaining
# a fourth lookahead.
#
# `_poller_executed()` below asks the grammatical question directly: is a
# whole token equal to a poller path, and is it either the command head or
# introduced by an interpreter? A `-c` argument is a nested command string, so
# it is re-tested on its own rather than special-cased -- which is why
# `bash -c "python3 hooks/monitor-open-prs.py --monitor"`, a genuine arming,
# still discharges while `sh -c "cat ..."` does not.
#
# Where it cannot parse (unbalanced quotes) or cannot see (a shell function,
# `eval`, a path built from a variable), it returns False. That direction is
# deliberate: a missed arming is visible to its author and one plainer command
# from clearing, whereas a false discharge defeats the guard silently, which is
# what all three rounds above actually cost.
_POLLER_PATH = re.compile(
    r"hooks/(?:monitor-open-prs|no-unmonitored-pr|ensure-open-pr-monitor)\.py")

# The whole token must BE a path. Without this, `python3 -c "print(open(
# 'hooks/monitor-open-prs.py').read())"` recurses into a nested command whose
# first token merely CONTAINS the path, and a head-position check alone would
# read that as an execution.
_POLLER_TOKEN = re.compile(
    r"^(?:[~.]?/)?[\w.@/-]*"
    r"hooks/(?:monitor-open-prs|no-unmonitored-pr|ensure-open-pr-monitor)\.py$")

# `python3.11` and `/usr/bin/env python3` are ordinary ways to name an
# interpreter, so match the basename with an optional version suffix rather
# than a fixed list of literals.
_INTERPRETER = re.compile(
    r"^(?:[\w.@/-]*/)?(?:python[\d.]*|bash|sh|zsh|dash|ksh)$", re.I)

# A SHELL specifically, which is a narrower question than "an interpreter".
# Only a shell's `-c` takes a nested COMMAND LINE; `python -c` takes Python
# SOURCE, so a bare path after it is an expression (`hooks / monitor - open -
# prs.py`) that raises NameError rather than running anything. Re-testing a
# Python `-c` argument under shell semantics read that as an execution.
_SHELL = re.compile(r"^(?:[\w.@/-]*/)?(?:bash|sh|zsh|dash|ksh)$", re.I)

# `VAR=value` prefixes a command without changing what runs.
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# A `-c`-shaped flag hands the NEXT token to the interpreter as a command
# STRING. Combined short flags (`-ec`) count; `-check` does not.
_DASH_C_FLAG = re.compile(r"^(?:-[a-z]*c|--command)$", re.I)

# Tokens that may precede the interpreter without changing what runs.
_EXEC_PREFIX = re.compile(r"^(?:nohup|command|exec|time|env|setsid|stdbuf)$",
                          re.I)


def _command_head(tokens, index):
    """Return (head token introducing TOKENS[INDEX], reached via a `-c`).

    Walks back past flags, `VAR=value` prefixes, and `nohup`-style wrappers,
    none of which change what runs. A `-c`-shaped flag along the way is
    reported rather than skipped, because it changes what the token IS: an
    argument to the interpreter rather than a script operand.
    """
    via_dash_c = False
    previous = index - 1
    while previous >= 0:
        token = tokens[previous]
        if _DASH_C_FLAG.match(token):
            via_dash_c = True
        elif not (token.startswith("-") or _EXEC_PREFIX.match(token)
                  or _ASSIGNMENT.match(token)):
            break
        previous -= 1
    return (tokens[previous] if previous >= 0 else "", via_dash_c)


def _poller_executed(command, depth=0):
    """True when COMMAND actually runs one of the poller scripts."""
    if depth > 2 or not _POLLER_PATH.search(command):
        return False
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return False  # unbalanced quotes: unparseable, so do not discharge

    for index, token in enumerate(tokens):
        # A SHELL's `-c` argument is a nested command line, so re-test it on
        # its own terms. A Python interpreter's `-c` argument is source code,
        # where a bare path is an expression rather than an execution -- so it
        # is not re-tested, and nothing in it can discharge by looking like a
        # command head.
        if _DASH_C_FLAG.match(token) and index + 1 < len(tokens):
            head, _ = _command_head(tokens, index)
            if _SHELL.match(head) and _poller_executed(tokens[index + 1],
                                                       depth + 1):
                return True
            continue
        # `shlex` splits on whitespace and quoting, NOT on shell operators, so
        # `python3 hooks/monitor-open-prs.py; echo done` yields the token
        # `hooks/monitor-open-prs.py;` and the anchored match below rejects it.
        # Strip a trailing operator run rather than dropping the `$` anchor,
        # which is what keeps `cat hooks/monitor-open-prs.py` from matching a
        # token that merely ENDS with the path.
        if not _POLLER_TOKEN.match(token.rstrip(";&|")):
            continue
        if index == 0:
            return True  # `./hooks/monitor-open-prs.py`
        head, via_dash_c = _command_head(tokens, index)
        if via_dash_c:
            continue  # an argument to `-c`, not a script operand
        if _INTERPRETER.match(head):
            return True
    return False


# Tools that WRITE. Lowercased at the comparison, since the same tool is
# spelled `Write`/`Edit` by one harness and `create`/`edit` by another.
WRITE_TOOLS = {
    "write", "edit", "multiedit", "notebookedit",
    "create", "update", "str_replace_editor", "apply_patch",
}

# What makes a shell command a write rather than a read.
BASH_WRITE = re.compile(
    # A redirect, but NOT `2>`/`&>` (an fd-prefixed stderr redirect) and not
    # one aimed at /dev/null -- `cat shared/x.md 2>/dev/null` is a read.
    r"(?<![0-9&])>>?\s*(?!/dev/null)[^\s&|]"
    r"|\btee\b|\bsed\s+-i\b|\bgit\s+(?:add|commit|apply|mv|rm)\b"
    r"|--write\b|\bmkdir\b",
    re.I,
)
# `mv`/`cp` and a bare `patch` are deliberately absent. `cp shared/x.md /tmp/`
# copies OUT of a rule surface and writes nothing to it, and the destination is
# not decidable from a substring match -- so they discharged reads. Losing the
# rare genuine `cp` INTO a rule surface costs a false positive, which this
# guard's own block message tells the author how to clear in one command.


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (rule_txt, debt_txt, durable, scheduled) for the CURRENT turn.

    Both promise kinds are tracked separately, because they discharge on
    different things and a reply can carry one of each. Resolving them at the
    call site rather than here keeps this function reporting observations and
    leaves the policy in `main()`.

    Scope resets at each real user prompt, so "the same turn" is what the
    comparison actually tests. A promise left undischarged in an earlier turn
    was already blocked when it was composed; re-blocking it every turn after
    would wedge the session.

    Order within the turn is deliberately NOT tested, which is where this
    parts company with no-mistake-without-a-hook.py. That hook scans the whole
    session, so it needs an index comparison for "after the admission" to mean
    anything. Here the window is one turn, and the ordinary shape is to build
    the mechanism first and state the rule in the closing message -- so
    requiring the write to come after the promise would block the correct
    case and pass almost nothing else.
    """
    rule_txt = debt_txt = None
    # tool_use ids whose call LOOKED like a mechanism, pending their result,
    # keyed by WHICH mechanism it looked like. A call is only evidence once it
    # did not come back an error: permission denial is an ordinary way for a
    # write to fail, and an attempted write ships nothing.
    pending = {"durable": set(), "scheduled": set()}
    failed = set()

    for m in records(path):
        kind = m.get("type")
        blocks = (m.get("message") or {}).get("content") or []

        # A subagent's turns are not mine, and -- measured, not assumed --
        # they are not here at all. Across 232 local transcripts on
        # 2026-08-20, 0 of the 126 SESSION transcripts carried a single
        # `isSidechain` record; all 106 that did were `subagents/agent-*.jsonl`
        # files. A Stop hook is handed the session transcript, so reading a
        # subagent's writes from here would be dead code. See
        # `discharges()` for what a delegated build discharges on instead.
        if m.get("isSidechain"):
            continue

        if kind == "user":
            # A tool_result arrives as a `user` record; a real prompt does not.
            is_tool_result = isinstance(blocks, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in blocks
            )
            for b in (blocks if isinstance(blocks, list) else []):
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                if b.get("is_error"):
                    failed.add(b.get("tool_use_id"))
            if not is_tool_result:
                rule_txt = debt_txt = None
                for ids in pending.values():
                    ids.clear()
                failed.clear()
            continue

        if kind != "assistant" or not isinstance(blocks, list):
            continue

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "text":
                raw = b.get("text") or ""
                if not raw.strip():
                    continue
                prose = visible_prose(raw)
                hit = RULE.search(prose)
                if hit:
                    rule_txt = hit.group(0).strip()
                hit = DEBT.search(prose)
                if hit:
                    debt_txt = hit.group(0).strip()

            elif b.get("type") == "tool_use":
                kind_of = discharges(b.get("name") or "", b.get("input") or {})
                if kind_of:
                    pending[kind_of].add(b.get("id"))

    # A call with no result at all still counts: the Stop hook can fire before
    # the result lands, and withholding discharge there would block a turn that
    # did the work. Only an explicit error disqualifies.
    durable = bool(pending["durable"] - failed)
    scheduled = bool(pending["scheduled"] - failed)
    return rule_txt, debt_txt, durable, scheduled


def discharges(name, inp):
    """Which kind of mechanism does this tool call SHIP, if any?

    Returns `"durable"`, `"scheduled"`, or `None`.

    The two are not interchangeable, and keeping them apart is the whole
    point of the distinction. A durable write outlives the session and so
    keeps a standing rule; a timer fires once and dies, so it can deliver one
    owed action and encodes no rule at all. Letting a scheduler discharge a
    RULE promise would let an unrelated wakeup launder "going forward I'll
    always X" -- which is why `main()`, not this function, decides which
    kinds satisfy which promise.

    Naming a rule surface is not shipping one, in either direction:

      * Prose does not discharge at all. The whole near-miss this guard
        exists for is the promise that names its own mechanism in the future
        tense ("going forward I'll add `hooks/x.py`"), and any check keyed on
        the path appearing in the text passes exactly that sentence.
      * A READ does not discharge either. `Read`, `Grep`, and `cat` over a
        rule surface are what ordinary work in this corpus looks like, so
        matching any tool whose payload mentions such a path would discharge
        nearly every turn.

    So each tool kind is asked the question its own payload can answer.

    A DELEGATED build is the case this cannot see, and saying so plainly
    beats guessing. A subagent's own writes are not in this transcript --
    0 of 126 session transcripts carried an `isSidechain` record when that
    was measured -- and a dispatch brief is prose, so no reading of its
    wording is evidence about what the agent did. Two earlier rounds of
    review narrowed exactly that wording heuristic before a third found it
    still matching bare nouns, so it is not reintroduced here.

    What a delegated build discharges on instead is the parent's own next
    act: staging or committing the artifact (`git add hooks/x.py`) is a
    `bash` write against a rule surface and discharges normally, and that
    is how such work actually ends. A turn that dispatches a build, makes
    a promise, and stops before touching the result is the residual false
    positive -- deliberate, named, and one command from clearing.
    """
    if not isinstance(inp, dict):
        return None
    low = name.lower()

    # An arming call, identified by TOOL NAME. Nothing about the scheduled
    # prompt's wording is read: three review rounds on #1724 defeated exactly
    # that judgment inside this function, and the name is the decidable part.
    #
    # The residual is therefore an arming that carries the wrong work -- a
    # wakeup scheduled for something else discharges a debt it will never
    # deliver. That is bounded by the same turn's own reporting duty (state
    # the fire time and what fires), and it is a far smaller error than the
    # alternative the guard had before: pushing every owed action toward a
    # memory entry that delivers nothing at all.
    if SCHEDULER_TOOL.search(low):
        # `stop: true` ENDS a dynamic loop rather than arming one, and the
        # tool's own schema ignores every other field when it is set.
        if inp.get("stop") is True:
            return None
        # `noop` is deliberately NOT treated the same way, though the two look
        # alike. Read against ScheduleWakeup's own schema rather than inferred
        # from the field name: `noop` decides how the tick is DISPLAYED
        # ("consecutive noop:true ticks are collapsed in the user's terminal
        # view"), and it is "required unless `stop` is true" -- so it is
        # mandatory on every genuine arming, and a quiet hold is precisely the
        # `noop: true` case. Excluding it would reject about half of all real
        # armings.
        return "scheduled"

    if low in WRITE_TOOLS:
        target = " ".join(
            str(inp.get(k, "")) for k in ("file_path", "path", "notebook_path")
        )
        return "durable" if MECHANISM_PATH.search(target) else None

    if low == "bash":
        cmd = str(inp.get("command", ""))
        if FILING_CMD.search(cmd):
            return "durable"
        # A shell write needs BOTH a rule surface and something that writes to
        # it, so `cat shared/workflow/ardi.md` reads as the read it is.
        #
        # This runs BEFORE the poller test, and the order is load-bearing
        # rather than stylistic. The three poller scripts live under `hooks/`,
        # so MECHANISM_PATH matches them too -- and testing the arming first
        # meant `git add hooks/no-unmonitored-pr.py && git commit` returned
        # "scheduled" where it had returned durable before this change. A RULE
        # promise now demands "durable" specifically, so that reordering
        # silently blocked a turn whose author had shipped the mechanism, and
        # handed them a message telling them to do what they had just done.
        #
        # Durable is the stronger claim, so when a command is both a write and
        # a mention of the poller, the write wins.
        if MECHANISM_PATH.search(cmd) and BASH_WRITE.search(cmd):
            return "durable"
        if _poller_executed(cmd):
            return "scheduled"
        return None

    if low in ("task", "agent", "skill"):
        # ONLY an action word. A brief naming a path is not evidence about
        # what the agent will do with it, and no reading of the wording can
        # make it one: "read hooks/x.py", "summarize the latest edit to
        # shared/x.md", "who wrote shared/x.md" all cite a rule surface while
        # writing nothing. Two rounds of review narrowed a verb heuristic here
        # and a third found `edit`, `update`, `record`, `author`, and `patch`
        # still matching as bare NOUNS, so the heuristic is abandoned rather
        # than narrowed again.
        #
        # SKILL_WORD is evidence HERE and nowhere else. `ums`/`memorize`
        # name skills invoked through this very tool, so a brief carrying
        # one is a request to run it. The same token in a `bash` payload is
        # a search term, which is why the two regexes are separate.
        #
        # A brief that merely DISCUSSES a pass ("summarize what the ums
        # skill does") still discharges, and that is a deliberate residual
        # rather than an oversight: separating discussion from request is
        # the same wording judgment that three earlier rounds defeated on
        # this branch, and the over-discharge is bounded to briefs that name
        # a recording skill without asking for one -- rare next to the
        # delegation this corpus actually encourages.
        # A delegated build discharges on the parent staging the artifact
        # afterwards, per this function's docstring; scan() cannot see the
        # subagent's own writes, so nothing here tries to.
        #
        # The scheduling skills are matched against the `skill` FIELD exactly
        # rather than against the brief, so that same ambiguity cannot reach
        # them: "what does the schedule skill do?" is prose in `args`, never
        # the value of `skill`.
        # `.split(":")[-1]` because a plugin exposes the same skill under a
        # qualified name -- `workaround-watcher` and `ai-config:workaround-watcher`
        # are both live in the same listing, and only the bare one matched.
        skill = str(inp.get("skill", "")).strip().lower().split(":")[-1]
        if skill in SCHEDULER_SKILLS:
            return "scheduled"
        blob = " ".join(str(inp.get(k, "")) for k in
                        ("prompt", "description", "skill", "args"))
        if FILING_CMD.search(blob) or SKILL_WORD.search(blob):
            return "durable"
        return None

    return None


RULE_REASON = (
    "Standing rule (shared/workflow/no-empty-promises.md, from the user's "
    "own `cai`): no empty promises. A commitment about how you will behave "
    "from now on dies with this conversation unless something durable "
    "outlives it -- so the promise is the report of the work, never the "
    "work.\n\n"
    "Ship one of these in this turn, then say what you shipped:\n"
    "  * a memory or rule entry (memories/, CLAUDE.md, AGENTS.md, or a "
    "shared/ fragment) -- the minimum, and always available;\n"
    "  * a hook, when the condition is decidable from the transcript -- "
    "model it on hooks/no-offer-to-file.py, add tests, register it in "
    "hooks/hooks.json, and do NOT activate it before its PR merges "
    "(README's activation gate);\n"
    "  * a filed issue, when the mechanism is real work someone must "
    "schedule.\n\n"
    "A scheduled timer does NOT clear this one. A wakeup fires once and "
    "dies, so it can deliver a specific owed action but encodes no standing "
    "rule -- and a rule is what you just committed to.\n\n"
    "Delegated the build to a subagent? Its writes are not in this "
    "transcript (measured: 0 of 126 session transcripts carried a sidechain "
    "record), so stage or commit the artifact -- `git add <path>` -- and "
    "this clears.\n\n"
    "If none of those is worth building, the honest move is to drop the "
    "promise and state the fact without it -- 'I was wrong about X, and here "
    "is Y' costs the user nothing and claims nothing."
)

DEBT_REASON = (
    "Standing rule (shared/workflow/no-empty-promises.md, from the user's "
    "own `cai`): no empty promises. An owed action is the sharpest case, "
    "because naming the debt reads as accountability while closing the item "
    "on the record -- so nobody, including you, returns to it. The session "
    "ends and the ARDI round, the re-review, the follow-up never happen.\n\n"
    "What an owed ACTION needs is something that will actually FIRE. Arm one "
    "of these now, then say what you armed and at what clock time:\n"
    "  * `ScheduleWakeup` -- a timer carrying the next step (per CLAUDE.md's "
    "'State the actual time when reporting a scheduled check-in', report the "
    "clock time it returns, not the delay);\n"
    "  * `CronCreate` or a scheduled task, for a check-in that must survive "
    "this session;\n"
    "  * the `schedule` / `loop` / `workaround-watcher` skill;\n"
    "  * the detached poller -- `python3 hooks/monitor-open-prs.py` -- when "
    "the debt is a PR to watch.\n\n"
    "A durable record still clears this too (memories/, CLAUDE.md, "
    "AGENTS.md, a shared/ fragment, or a filed issue), and it is the right "
    "answer when the debt is somebody else's to schedule. It is the WRONG "
    "answer when the debt is yours and has a next step: a memory entry "
    "documents an outstanding ARDI loop, it does not run one.\n\n"
    "If there is genuinely no next step to arm, drop the debt language and "
    "state the plain fact instead -- '#N is open awaiting re-review' reports "
    "the state and claims nothing."
)


def main() -> int:
    if visible_prose is None:
        return 0  # sibling unavailable; degrade to silence

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        rule_txt, debt_txt, durable, scheduled = scan(path)
    except Exception:
        return 0  # fail open

    # A RULE promise is checked first and against the STRICTER requirement.
    # A turn can carry one of each, and the rule's mechanism satisfies the
    # debt as well, so resolving in this order never blocks twice for one
    # under-discharged turn.
    if rule_txt and not durable:
        promise_txt, reason = rule_txt, RULE_REASON
    elif debt_txt and not (durable or scheduled):
        promise_txt, reason = debt_txt, DEBT_REASON
    else:
        return 0

    key = hashlib.sha256(
        f"{path}:{promise_txt}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-promise-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            "[hook: no-empty-promise] Your reply commits to future behaviour "
            f"(\"{promise_txt}\") and this turn shipped no mechanism to keep "
            "it.\n\n" + reason
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
