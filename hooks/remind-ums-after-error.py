#!/usr/bin/env python3
"""UserPromptSubmit reminder: an admitted error owes a UMS pass.

CLAUDE.md's "Run UMS proactively" section makes discovering you were wrong a
trigger in its own right. It is the trigger with no artifact: nothing merges,
no check turns green, and the correction *feels* like the completion when it
is only the input. So the pass is skipped, and the same class of error recurs
within hours.

WHY THIS INJECTS RATHER THAN BLOCKS
-----------------------------------
The obvious shape here is a `Stop` hook that blocks the outgoing message,
copying `no-offer-to-file.py`. That shape is wrong for this rule, and the
distinction is the whole reason this file exists.

A `Stop` guard suppresses a message that is WRONG TO SEND -- an offer that
should have been an action. Suppressing it improves the message.

An error admission is RIGHT to send. Blocking it would suppress the honest
correction itself, delay it reaching the user, and -- for a guard sitting
between the model and the user -- silently remove the very signal that would
have surfaced the mistake. Admitting must always be free and immediate; it is
the RECORDING that has to follow.

So this fires on the next prompt instead, and only ever adds context. There is
no code path here that can suppress, delay, or alter a message.

MECHANISM
---------
Documented non-blocking path: for `UserPromptSubmit`, anything written to
stdout on exit 0 is added to Claude's context. `inject-local-time.sh` already
proves that path works in this harness. Deliberately NOT using a `Stop` hook's
`additionalContext`, which is documented for `UserPromptSubmit` rather than
for `Stop`, and was not verified here.

It stays silent when the pass already happened: a memory/skills/shared write, a
UMS-mentioning subagent dispatch, or a `ums` invocation recorded LATER in the
transcript than the admission clears the obligation. So a turn that admits an
error and immediately records it is never nagged.

Fires once per distinct admission (sentinel keyed by content hash), because a
reminder repeated every turn is noise, and noise is what gets a guard ignored.

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Typographic apostrophe, spelled as an escape rather than embedding the
# glyph, so this file stays pure ASCII per
# shared/coding/ascii-punctuation-in-source.md while still matching "I
# should've" as typed by a model that prefers the curly form.
_APOS = "['\u2019]"

# First-person admissions only. Correcting SOMEONE ELSE ("the review was
# wrong", "the docs are incorrect") must never fire this -- hence an explicit
# first-person subject in every pattern rather than a bare "was wrong".
# Every bare `i` alternative carries `\b`. Without it the pattern matches the
# trailing "I" of any word ending in that letter, so "The API was wrong about
# this endpoint" fired as a first-person admission -- a third-person statement,
# which the docstring above says this regex must never match. Found on
# ai-config#1752's review for the `should have` alternative, which was anchored
# then while its six siblings were not (ai-config#1756).
ADMISSION = re.compile(
    r"""(
      \bi\s+was\s+(wrong|mistaken|incorrect)
    | \bi\s+got\s+(that|this|it)\s+wrong
    | my\s+(mistake|error)\b
    | my\s+(earlier|previous|prior|last)\s+
        (claim|statement|report|answer|assertion|reading|count)\s+
        was\s+(wrong|incorrect|false)
    | \bi\s+(mischaracterized|misread|miscounted|misdiagnosed|misremembered)
    | \bi\s+(incorrectly|wrongly|falsely)\s+
        (said|claimed|stated|reported|assumed|described|characterized)
    # Quantitative self-correction (ai-config#1210). The adverb form above
    # requires an explicit "incorrectly"/"wrongly"; a retraction of a figure
    # rarely carries one -- "I overstated the waste" is a first-person
    # admission of having been wrong by any reading, and was silent.
    # `overclaimed` needs no alternative of its own: over + claimed.
    | \bi\s+(over|under)(stated|estimated|counted|reported|claimed)
    # `myself` needs an alternative of its OWN, because `my\b` cannot match
    # inside that word -- which is why ai-config#1210's proposed
    # `(my|this|the)` silently regressed "correcting myself". Its position is
    # not load-bearing: `re` backtracks, so `(my|myself|this)` matches
    # identically; `myself` leads for readability only.
    # `the` is deliberately absent: "correcting the reviewer" is correcting
    # SOMEONE ELSE, which the first-person rule above exists to exclude.
    | correcting\s+(myself|my|this)\b
    | retracting\s+(my|that\s+claim)
    | \bi\s+(need\s+to\s+)?retract\b
    # Omission self-critique (ai-config#1751): "I should have proactively
    # found the open PRs" is a first-person admission of a behavioral gap,
    # not a factual retraction, so none of the patterns above catch it.
    # "should have" + past participle is always retrospective in English
    # ("should have" as an unfulfilled past obligation); the possessive
    # reading ("I should have this ready by Friday", main-verb "have") is
    # future-oriented and must NOT fire, so the word right after "have" is
    # excluded when it signals that NP reading (a determiner/possessive)
    # rather than a verb.
    | \bi\s+should(?:""" + _APOS + r"""ve|\s+have)\s+
        (?!(?:this|that|it|these|those|my|your|his|her|their|our
            |the|a|an|some|no)\b)
        \w+
    )""",
    re.I | re.X,
)

# A write to any of these is a recorded learning.
UMS_PATH = re.compile(
    r"(memories?/|MEMORY\.md|CLAUDE\.md|/skills/|^skills/|/shared/|^shared/)",
    re.I,
)
# `\b` is the wrong boundary for a bare action word here: this pattern is
# applied to Bash COMMAND TEXT, and `-`, `/`, and `.` are all non-word
# characters, so `\bums\b` matched inside
# `cat shared/workflow/run-ums-proactively.md` -- reading the fragment that
# states the UMS rule discharged the reminder to follow it (ai-config#1965).
# The hook fails open, so that discharge was silent.
#
# `.` is deliberately NOT excluded on its own. Rejecting a bare dot would also
# reject a sentence-final period, so `run ums.` -- the commonest phrasing in a
# dispatch prompt -- would stop matching. What marks a path is a dot with a
# word character AFTER it (`ums.md`), not a dot at a full stop.
#
# Same idiom as hooks/no-empty-promise.py's SKILL_WORD, which diagnosed this
# first; keep the two spellings identical.
_NOT_PATH = r"(?<![\w/-])"
_NOT_PATH_END = r"(?![\w/-]|\.\w)"

UMS_WORD = re.compile(
    _NOT_PATH + r"ums" + _NOT_PATH_END +
    r"|update\s+memories"
    r"|" + _NOT_PATH + r"record[- ]learnings" + _NOT_PATH_END +
    r"|" + _NOT_PATH + r"memorize" + _NOT_PATH_END,
    re.I,
)

FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")


def visible_prose(text):
    """Drop code fences, blockquotes, and inline code.

    Quoting the rule while discussing it is the main false-positive source,
    and it is nearly always inside one of those three.
    """
    text = FENCE.sub(" ", text)
    text = QUOTED.sub(" ", text)
    return TICKED.sub(" ", text)


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (admission_text, admitted_at, recorded_at)."""
    admit_txt, admit_at, ums_at = None, -1, -1

    for i, m in enumerate(records(path)):
        # A subagent's own turns are not my outgoing message.
        #
        # Field name measured, not assumed: across 138 real transcripts under
        # ~/.claude/projects, all 29,465 assistant records carry the key
        # spelled exactly `isSidechain` (9,561 of them true), and no variant
        # spelling (`is_sidechain`, `sideChain`) occurs anywhere. On that
        # harness layout the true records sit in `subagents/agent-*.jsonl`
        # rather than in the session transcript, so on the UserPromptSubmit
        # path this guard is defensive rather than load-bearing. It is kept
        # because it costs one dict lookup and is the correct reading if a
        # subagent transcript is ever passed here, or if sidechain turns are
        # inlined into the parent transcript again as they once were.
        if m.get("isSidechain"):
            continue
        if m.get("type") != "assistant":
            continue
        blocks = (m.get("message") or {}).get("content") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            if not isinstance(b, dict):
                continue

            if b.get("type") == "text":
                hit = ADMISSION.search(visible_prose(b.get("text", "")))
                if hit:
                    admit_txt, admit_at = hit.group(0).strip(), i

            elif b.get("type") == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    continue
                blob = ""
                if name in ("Write", "Edit", "NotebookEdit"):
                    blob = str(inp.get("file_path", ""))
                    if UMS_PATH.search(blob):
                        ums_at = i
                    continue
                if name in ("Task", "Agent"):
                    blob = str(inp.get("prompt", "")) + str(inp.get("description", ""))
                elif name == "Bash":
                    blob = str(inp.get("command", ""))
                elif name == "Skill":
                    blob = str(inp.get("skill", ""))
                if blob and UMS_WORD.search(blob):
                    ums_at = i

    return admit_txt, admit_at, ums_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        admit_txt, admit_at, ums_at = scan(path)
    except Exception:
        return 0

    if not admit_txt:
        return 0
    if ums_at >= admit_at:  # already recorded after the admission
        return 0

    # Keyed on the transcript path too, so the sentinel is per session. Without
    # it, two sessions producing the same admission at the same record index
    # share one sentinel in /tmp, and the second session's reminder is
    # suppressed for as long as that /tmp survives.
    key = hashlib.sha256(f"{path}:{admit_txt}:{admit_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ums-after-error-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        "UMS reminder: an earlier turn in this session admitted an error "
        f'("{admit_txt}"), and no memory, skill, or shared-fragment write has '
        "been recorded since.\n"
        "CLAUDE.md ('Run UMS proactively') makes discovering you were wrong a "
        "trigger in its own right, firing now rather than at the next merge, "
        "clean verdict, or wrap-up. It is the trigger that leaves no artifact, "
        "so nothing else will prompt it.\n"
        "Record what you believed and what displaced it -- both halves, per "
        "'Record both the pattern and the anti-pattern'. Delegate the pass to "
        "a subagent; that is pre-authorized standing sidecar work.\n"
        "If this reminder is a false positive (you were correcting someone "
        "else's claim, or quoting the rule), disregard it and carry on."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
