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

WHAT DISCHARGES IT
------------------
A tool call in the same turn that actually SHIPS something durable: a write to
a rule surface (`CLAUDE.md`, `AGENTS.md`, `memories/`, `shared/`, `skills/`,
`hooks/`, `.claude/settings.json`), a filed issue, or a `memorize`/`ums`
invocation. Order within the turn does not matter -- the mechanism is normally
built before the closing message that states the rule.

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
"""
import hashlib
import importlib.util
import json
import os
import re
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
_MODAL = (r"(?:" + _APOS + r"ll|\s+will|\s+shall|\s+am\s+going\s+to|"
          + _APOS + r"m\s+going\s+to)")
_NEG = r"(?:\s+won" + _APOS + r"?t|\s+will\s+not)"

PROMISE = re.compile(
    r"""(
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
    )""",
    re.I | re.X,
)

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
    r"|\b(?:commands|cursor-rules|codex-skills)/[\w./-]+)",
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
    """Return (promise_text, mechanism_written) for the CURRENT turn.

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
    promise_txt = None
    # tool_use ids whose call LOOKED like a mechanism, pending their result.
    # A call is only evidence once it did not come back an error: permission
    # denial is an ordinary way for a write to fail, and an attempted write
    # ships nothing.
    pending = set()
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
                promise_txt = None
                pending.clear()
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
                hit = PROMISE.search(visible_prose(raw))
                if hit:
                    promise_txt = hit.group(0).strip()

            elif b.get("type") == "tool_use":
                if discharges(b.get("name") or "", b.get("input") or {}):
                    pending.add(b.get("id"))

    # A call with no result at all still counts: the Stop hook can fire before
    # the result lands, and withholding discharge there would block a turn that
    # did the work. Only an explicit error disqualifies.
    return promise_txt, bool(pending - failed)


def discharges(name, inp):
    """Does this tool call actually SHIP a mechanism?

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
        return False
    low = name.lower()

    if low in WRITE_TOOLS:
        target = " ".join(
            str(inp.get(k, "")) for k in ("file_path", "path", "notebook_path")
        )
        return bool(MECHANISM_PATH.search(target))

    if low == "bash":
        cmd = str(inp.get("command", ""))
        if FILING_CMD.search(cmd):
            return True
        # A shell write needs BOTH a rule surface and something that writes to
        # it, so `cat shared/workflow/ardi.md` reads as the read it is.
        return bool(MECHANISM_PATH.search(cmd) and BASH_WRITE.search(cmd))

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
        blob = " ".join(str(inp.get(k, "")) for k in
                        ("prompt", "description", "skill", "args"))
        return bool(FILING_CMD.search(blob) or SKILL_WORD.search(blob))

    return False


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
        promise_txt, mech = scan(path)
    except Exception:
        return 0  # fail open

    if not promise_txt or mech:
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
            "[hook: no-empty-promise] Your reply promises future behaviour "
            f"(\"{promise_txt}\") and this turn wrote no mechanism to keep "
            "it.\n\n"
            "Standing rule (shared/workflow/no-empty-promises.md, from the "
            "user's own `cai`): no empty promises. A commitment about how you "
            "will behave from now on dies with this conversation unless "
            "something durable outlives it -- so the promise is the report of "
            "the work, never the work.\n\n"
            "Ship one of these in this turn, then say what you shipped:\n"
            "  * a memory or rule entry (memories/, CLAUDE.md, AGENTS.md, or "
            "a shared/ fragment) -- the minimum, and always available;\n"
            "  * a hook, when the condition is decidable from the transcript "
            "-- model it on hooks/no-offer-to-file.py, add tests, register it "
            "in hooks/hooks.json, and do NOT activate it before its PR merges "
            "(README's activation gate);\n"
            "  * a filed issue, when the mechanism is real work someone must "
            "schedule.\n\n"
            "Delegated the build to a subagent? Its writes are not in this "
            "transcript (measured: 0 of 126 session transcripts carried a "
            "sidechain record), so stage or commit the artifact -- "
            "`git add <path>` -- and this clears.\n\n"
            "If none of those is worth building, the honest move is to drop "
            "the promise and state the fact without it -- 'I was wrong about "
            "X, and here is Y' costs the user nothing and claims nothing."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
