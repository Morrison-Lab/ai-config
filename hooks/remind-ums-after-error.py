#!/usr/bin/env python3
"""UserPromptSubmit reminder, and once-per-turn Stop block: an admitted error owes a UMS pass.

CLAUDE.md's "Run UMS proactively" section makes discovering you were wrong a
trigger in its own right. It is the trigger with no artifact: nothing merges,
no check turns green, and the correction *feels* like the completion when it
is only the input. So the pass is skipped, and the same class of error recurs
within hours.

WHY THE PROMPT-TIME REGISTRATION INJECTS RATHER THAN BLOCKS
-----------------------------------------------------------
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

So the UserPromptSubmit registration only ever adds context. No code path
here can suppress, delay, or alter a message; the Stop registration described
below blocks only the END of a turn whose admission was already delivered.

MECHANISM
---------
Documented non-blocking path: for `UserPromptSubmit`, anything written to
stdout on exit 0 is added to Claude's context. `inject-local-time.sh` already
proves that path works in this harness. Deliberately NOT using a `Stop` hook's
`additionalContext`, which is documented for `UserPromptSubmit` rather than
for `Stop`, and was not verified here.

A SECOND, STOP-TIME REGISTRATION (2026-11-12)
--------------------------------------------
A project coordinator said "I was wrong on two counts" through `post_message`
and ran no pass; the user's next message asked why. The scan read only `text`
blocks, so reply-tool text (scripts/lib/tool_names.py) is now scanned too, and
the hook is also registered on Stop (AI_CONFIG_STOP=1). The admission is
already delivered when Stop runs, so blocking the stop suppresses nothing. It
blocks once per turn, never while `stop_hook_active` is set, and a Stop with
that flag exits before the sentinel, so it does not use up the one block.

A project thread usually runs the pass and THEN reports the mistake in its
reply, so UMS work earlier in the same turn (after the last real user turn,
per scripts/lib/transcript_meta.py) discharges an admission too, but only one
whose own text names a file that turn wrote ("recorded in claude-app-projects.md").
A keyword such as "UMS" is not enough: "I have not run UMS yet" names it too. A
second, different mistake admitted after the pass still owes one. A Bash redirect or `tee`
into a memory, skill or shared path, and a GitHub MCP file write to one,
count as UMS work, since those are how a cloud session records a learning.
`sed -i`, `cp` and `mv` into such a path are not recognized.

It stays silent when the pass already happened: a memory/skills/shared write, a
UMS-mentioning subagent dispatch, or a `ums` invocation recorded LATER in the
transcript than the admission clears the obligation. So a turn that admits an
error and immediately records it is never nagged.

An admission in the irrealis mood is not an admission, so a hypothetical
("even if I misread the status") is skipped -- see `IRREALIS_LEAD`.

Fires once per distinct admission PHRASE, bounded by transcript DISTANCE
rather than by session lifetime. The sentinel is still keyed by content hash
and transcript path, and NOT by record index -- putting the index in the KEY
reintroduced the original #2997 bug, where explaining a misfire names the same
phrase again a few records later and that read as a brand-new admission.
Instead the sentinel's file CONTENT holds the record index of the last firing
(see `_sentinel_gate`, `LOOP_WINDOW`): a later occurrence of the same phrase is
a repeat only within LOOP_WINDOW records of it, and fires again beyond that
window. An existence-only sentinel (fire once, ever, per phrase) was wrong the
other direction -- it suppressed a genuinely later, unrelated admission that
happened to share a short common phrase with an earlier one, for the rest of
the session (ai-config#2997 review finding).

Fails OPEN and SILENT: any parse trouble prints nothing at all.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from tool_names import reply_text
except Exception:  # broken install: read assistant text blocks only
    def reply_text(name, inp):  # noqa: D103
        return ""
try:
    from agent_notice import stop_notice
except Exception:
    stop_notice = None
try:
    from transcript_meta import is_real_user_turn
except Exception:  # broken install: no same-turn discharge
    def is_real_user_turn(entry):  # noqa: D103
        return False

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
_ADMISSION_RE = re.compile(
    r"""(
      \bi\s+was\s+(wrong|mistaken|incorrect)
    | \bi\s+got\s+(that|this|it)\s+wrong
    # `\bmy`, not bare `my`: without the anchor a word ENDING in "my" supplied
    # the possessive, so "The dummy error was expected" and "An anatomy
    # error crept in" both fired as first-person admissions (ai-config#1898,
    # the same class as the bare `i` alternatives above).
    | \bmy\s+(mistake|error)\b
    | \bmy\s+(earlier|previous|prior|last)\s+
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
    # Omission admissions & flawed query/scan explanations (ai-config#2775).
    # Catching "my prior query missed it because...", "you are right ... missed",
    # and first-person query/scan filter flaws.
    | \b(?:my|our)\s+(?:(?:prior|previous|earlier|last)\s+)?
        (?:query|scan|check|search|attempt|pass|run|filter|script)\s+
        missed\s+(?!(?:nothing|none|zero|no)\b)
    | \b(?:you\s+are|you""" + _APOS + r"""re)\s+right\b[^\n]*?\b(?:i\s+(?:missed|overlooked)|(?:my|our)\s+\w+\s+missed)\b
    | \bi\s+(?:missed|overlooked)\s+
        (?!(?:out|the\s+point)\b)
        (?:(?:that|this|it|these|those)|(?:(?:the|a|an|that|this|these|those|my|our)\s+)?(?:note|comment|issue|pr|diff|finding|warning|error|file|line)|\w+\s+because)\b
    | \b(?:it|i|we)\s+filtered\s+[^\n.!?]+?\s+rather\s+than\b
    )""",
    re.I | re.X,
)

# Irrealis guard (ai-config#2997). Every alternative above is anchored on a
# verb, and mood is invisible to a verb. So "a posted review is caught even if
# I misread the job status" matched -- a hypothetical describing a mistake that
# explicitly has NOT happened, in a sentence justifying the design that makes
# it not matter. That is the opposite of an admission.
#
# `visible_prose()` below does not reach it: that guard strips fences,
# blockquotes and inline code, which is where a QUOTATION of the rule lives.
# This is ordinary prose whose grammatical mood inverts its meaning.
#
# Matched against the text immediately BEFORE a hit, anchored to end-of-window,
# so only a marker introducing that very clause counts. `\b` leads the
# alternation because "a gif I misread" would otherwise supply the `if`.
#
# Bare `if` is included, and the issue flagged that as the one debatable call
# --- "if I was wrong, ..." is occasionally a hedged real admission. It asked
# for the question to be settled by grepping transcripts rather than by
# intuition, and the transcripts reachable from this container are only the
# session that filed the issue, in which every hit is a quotation of the issue
# text itself. So the corpus could not settle it, and the tie was broken on
# cost: a hedged admission almost always continues into an unhedged one
# ("... then my earlier claim was wrong"), which the alternatives above still
# catch, whereas a false positive here is documented to cost six firings.
#
# The trailing whitespace class allows AT MOST ONE newline between the marker
# and the clause it introduces, so a marker hard-wrapped across one line break
# ("even if\nI misread the status") still counts as irrealis. A run of
# horizontal whitespace matches outright; a newline matches only when the
# lookahead cannot find a further newline (with nothing but horizontal
# whitespace before it), which is exactly a blank line. That keeps a real
# paragraph break ("even if\n\nI was wrong") from being swallowed: the first
# newline's lookahead finds the second one, so the alternative fails and the
# whole match cannot reach `$` (ai-config#2997 review nit).
IRREALIS_LEAD = re.compile(
    r"""\b(?:
        (?:even\s+)?if
      | unless
      | in\s+case
      | whether(?:\s+or\s+not)?
      | lest
      | supposing
      | suppose(?:\s+that)?
      | assuming(?:\s+that)?
    )(?:[^\S\n]|\n(?![^\S\n]*\n))+$""",
    re.I | re.X,
)

# 40 characters holds the longest marker above ("whether or not") plus a
# wrapped line's trailing space, the one newline `IRREALIS_LEAD` now accepts,
# and up to eight columns of indentation on the line the admission continues
# on. Adjacency is enforced by the anchor in `IRREALIS_LEAD`, not by this
# bound.
LEAD_WINDOW = 40


class _AdmissionMatcher:
    """`_ADMISSION_RE` with the irrealis guard applied.

    Exposes `search()` and nothing else, because `search()` plus `.group(0)`
    on what it returns is the entire surface the three consumers use
    (`no-mistake-without-a-hook.py`, `remind-ums-on-scrutiny.py`, and this
    module). Filtering HERE rather than at each call site is what keeps the
    shared-import contract intact: the siblings import `ADMISSION` precisely so
    the detectors cannot drift, and a guard applied in one consumer would
    reintroduce exactly that drift.

    A guarded hit is skipped rather than ending the search, so "even if I
    misread the status. I was wrong about the base branch." still fires on the
    second clause.
    """

    def __init__(self, regex, lead=IRREALIS_LEAD, window=LEAD_WINDOW):
        self.regex = regex
        self.lead = lead
        self.window = window

    def search(self, text, *args, **kwargs):
        for hit in self.regex.finditer(text, *args, **kwargs):
            before = text[max(0, hit.start() - self.window):hit.start()]
            if self.lead.search(before):
                continue
            return hit
        return None


ADMISSION = _AdmissionMatcher(_ADMISSION_RE)

# Measured from the loop ai-config#2997 itself was filed over: the
# re-explanation that named the admitted phrase again landed 2 records after
# the original admission (a user question, then the assistant's reply). A
# real re-explanation exchange can run a turn or two longer than that single
# question-and-answer, so this is not the bare minimum observed but that
# minimum doubled plus a margin -- 6 records, i.e. three user/assistant turn
# pairs -- so an ordinary multi-turn discussion of the same misfire still
# reads as one admission rather than a fresh one partway through.
LOOP_WINDOW = 6


def _sentinel_gate(sentinel_path, admit_at, window=LOOP_WINDOW):
    """Return True iff this occurrence of the phrase should fire.

    The sentinel file's CONTENT is the record index of the last firing, not
    just its existence, so this can tell a repeat (the same explanation
    naming the same phrase a few records later) from a later, unrelated
    admission that happens to share a short common phrase with an earlier
    one. Only the first case is suppressed; the file is updated on every
    actual firing, never on a suppressed repeat, so the window is always
    measured from the most recent firing rather than drifting forward on
    each silent repeat.
    """
    last_at = None
    if os.path.exists(sentinel_path):
        try:
            with open(sentinel_path, encoding="utf-8") as fh:
                last_at = int(fh.read().strip())
        except Exception:
            last_at = None  # unreadable sentinel -- treat as no prior firing
    if last_at is not None and admit_at - last_at <= window:
        return False
    try:
        with open(sentinel_path, "w", encoding="utf-8") as fh:
            fh.write(str(admit_at))
    except Exception:
        pass
    return True


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
# A leading `/` needs splitting apart, because it plays two roles. In a
# PATH (`skills/ums`, `./ums-helper`) it is a separator and must block
# the match; as a slash-COMMAND (`/ums`, `/memorize`) it is how this
# corpus spells the invocation, and blocking that loses a real
# discharge. What separates them is the character BEFORE the slash: a
# path has a word character or a dot there, an invocation has
# whitespace or nothing. So reject `/` only in that context.
# (Review finding on ai-config#1968: the first spelling, `(?<![\\w/-])`,
# rejected both, silently dropping `/ums` as a discharge.)
_NOT_PATH = r"(?<![\w-])(?<![\w.]/)"
_NOT_PATH_END = r"(?![\w/-]|\.\w)"

# `update\s+memories` is the one alternative left unguarded, and deliberately.
# It cannot match a path, because the hyphen form (`update-memories-and-skills`,
# the skill alias) has no whitespace in it. What it CAN match is
# `update memories/git.md` in a dispatch prompt -- which is a genuine UMS
# instruction, so a `_NOT_PATH_END` here would cost a true positive rather
# than removing a false one. The guard is applied where the word alone is
# ambiguous, not everywhere it would parse.
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


# A shell write into a memory, skill or shared path: a redirect or `tee`
# whose target names one. A bare read (`cat memories/x.md`) is not a write,
# and neither is an arrow in quoted text (`echo "a -> shared/x"`): quoted
# strings are blanked first unless they are the redirect's own target, and a
# `>` after `-`, `=`, `<` or `>` is not a redirect. Other writes (`sed -i`,
# `cp`, `mv`) are not recognized.
SHELL_UMS_WRITE = re.compile(
    r"(?:(?<![-=<>])>>?|\btee\b(?:\s+(?:-a|--append))?)\s*[\"']?[^\s\"'|;&<>]*"
    r"(?:memories?/|MEMORY\.md|CLAUDE\.md|skills/|shared/)",
    re.I,
)
_QUOTED_ARG = re.compile(
    r"((?<![-=<>])>>?\s*|\btee\s+(?:(?:-a|--append)\s+)?)?(\"[^\"]*\"|'[^']*')")


def shell_writes_ums_path(command):
    """True when `command` redirects or tees into a memory, skill or shared path."""
    bare = _QUOTED_ARG.sub(lambda m: m.group(0) if m.group(1) else " ", command)
    return bool(SHELL_UMS_WRITE.search(bare))
# A memory, skill or shared path named in a shell command, so its file name
# can be matched against the reply that reports the pass.
SHELL_UMS_TARGET = re.compile(r"[\w./~-]*(?:memories?/|skills/|shared/)[\w./-]+")


def _names(paths):
    """File names of the UMS paths among `paths`."""
    return {os.path.basename(p.rstrip("/")) for p in paths if p and UMS_PATH.search(p)}
GITHUB_FILE_WRITES = ("mcp__github__create_or_update_file", "mcp__github__push_files")


def records(path):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def scan(path):
    """Return (admission_text, admitted_at, recorded_at).

    `recorded_at` is raised to `admitted_at` when UMS work happened earlier in
    the admission's own turn, so a pass followed by the reply that reports the
    mistake counts as discharged.
    """
    admit_txt, admit_at, ums_at = None, -1, -1
    user_at, admit_turn, cites_pass = -1, -1, False
    turn_names = set()  # file names of UMS writes since the last real user turn

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
        tool_calls = []
        text_blocks = []

        is_assistant = m.get("type") == "assistant" or m.get("role") == "assistant"
        blocks = (m.get("message") or {}).get("content") or m.get("content") or []
        if is_real_user_turn(m):
            user_at = i
            turn_names = set()
            continue
        if isinstance(blocks, list):
            for b in blocks:
                if isinstance(b, dict):
                    if b.get("type") == "tool_use":
                        tool_calls.append((b.get("name") or "", b.get("input") or {}))
                        # A project thread replies only through a reply tool,
                        # so its admission lives in the tool input.
                        said = reply_text(b.get("name"), b.get("input"))
                        if said:
                            text_blocks.append(said)
                    elif b.get("type") == "text" and is_assistant:
                        text_blocks.append(b.get("text") or "")
        elif isinstance(blocks, str) and is_assistant:
            text_blocks.append(blocks)

        if m.get("type") == "PLANNER_RESPONSE":
            content = m.get("content")
            if isinstance(content, str):
                text_blocks.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text_blocks.append(b.get("text") or "")
                    elif isinstance(b, str):
                        text_blocks.append(b)

        if m.get("type") == "PLANNER_RESPONSE" or "tool_calls" in m:
            for tc in m.get("tool_calls") or []:
                if isinstance(tc, dict):
                    tname = tc.get("name") or (tc.get("function") or {}).get("name") or ""
                    targs = tc.get("args") or tc.get("input") or (tc.get("function") or {}).get("arguments") or {}
                    if isinstance(targs, str):
                        try:
                            targs = json.loads(targs)
                        except Exception:
                            targs = {"command": targs}
                    tool_calls.append((tname, targs if isinstance(targs, dict) else {}))

        for raw_text in text_blocks:
            hit = ADMISSION.search(visible_prose(raw_text))
            if hit:
                admit_txt, admit_at = hit.group(0).strip(), i
                admit_turn = user_at
                # Earlier same-turn work discharges only an admission whose
                # own text says it was recorded, so a second, different
                # mistake admitted after the pass still owes one.
                cites_pass = any(n and n in raw_text for n in turn_names)

        for name, inp in tool_calls:
            if not isinstance(inp, dict):
                continue
            blob = ""
            if name in GITHUB_FILE_WRITES:
                paths = [str(inp.get("path") or "")]
                files = inp.get("files")
                if isinstance(files, list):
                    paths += [str(f.get("path") or "") for f in files if isinstance(f, dict)]
                if any(UMS_PATH.search(p) for p in paths):
                    ums_at = i
                    turn_names |= _names(paths)
                continue
            if name in ("Write", "Edit", "NotebookEdit", "write", "edit", "write_to_file", "replace_file_content"):
                blob = str(inp.get("file_path") or inp.get("path") or inp.get("TargetFile") or inp.get("target_file") or "")
                if UMS_PATH.search(blob):
                    ums_at = i
                    turn_names |= _names([blob])
                continue
            if name in ("Task", "Agent", "invoke_subagent"):
                ums_parts = [
                    str(inp.get("prompt") or inp.get("Prompt") or ""),
                    str(inp.get("description") or ""),
                    str(inp.get("toolAction") or ""),
                    str(inp.get("toolSummary") or ""),
                ]
                subagents = inp.get("Subagents") or inp.get("subagents")
                if isinstance(subagents, str):
                    try:
                        subagents = json.loads(subagents)
                    except Exception:
                        ums_parts.append(subagents)
                        subagents = None
                if isinstance(subagents, list):
                    for sa in subagents:
                        if isinstance(sa, dict):
                            ums_parts.append(str(sa.get("Prompt") or sa.get("prompt") or ""))
                            ums_parts.append(str(sa.get("Role") or sa.get("role") or ""))
                            ums_parts.append(str(sa.get("TypeName") or sa.get("typeName") or ""))
                        elif isinstance(sa, str):
                            ums_parts.append(sa)
                blob = " ".join(ums_parts)
            elif name in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
                blob = str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or "")
                if shell_writes_ums_path(blob):
                    ums_at = i
                    turn_names |= _names(SHELL_UMS_TARGET.findall(blob))
            elif name == "Skill":
                blob = str(inp.get("skill", ""))
            if blob and UMS_WORD.search(blob):
                ums_at = i

        if cites_pass and admit_at >= 0 and admit_turn < ums_at < admit_at:
            ums_at = admit_at

    return admit_txt, admit_at, ums_at


def main() -> int:
    # The reminder quotes the admission from the transcript, so a curly quote
    # there made a cp1252 console write byte 0x92, which a UTF-8 reader cannot
    # decode (ai-config#1288). Read stdin and write stdout as UTF-8 whatever
    # the console says; nothing here writes quoted text to stderr.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
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
    # it, two sessions producing the same admission share one sentinel in
    # /tmp, and the second session's reminder is suppressed for as long as
    # that /tmp survives.
    # The mode is in the key: the UserPromptSubmit and Stop registrations each
    # owe their own firing, as in no-mistake-without-a-hook.py.
    mode = os.getenv("AI_CONFIG_STOP") or ""
    if mode == "1" and payload.get("stop_hook_active"):
        # Leave the sentinel unused, so the next plain Stop still blocks once.
        return 0
    key = hashlib.sha256(f"{path}:{admit_txt}:{mode}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-ums-after-error-{key}")
    if not _sentinel_gate(sentinel, admit_at):
        return 0

    message = (
        "UMS reminder: this session admitted an error "
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
        "else's claim, quoting the rule, or writing a hypothetical such as "
        "'even if I misread it'), disregard it and carry on. Writing about the "
        "misfire will not re-fire it: the same phrase within a few transcript "
        "records does not fire again, and a phrase wrapped in backticks is "
        "not matched at all."
    )
    if mode == "1":
        # Stop: the admission has already been delivered, so blocking the
        # stop suppresses nothing; it only keeps the turn open for the pass.
        # Without this the reminder waited for the user's NEXT prompt, which
        # in a project thread is the user asking why no pass ran.
        if stop_notice is not None:
            print(stop_notice(payload, message, "remind-ums-after-error"))
        else:
            print(json.dumps({"decision": "block", "reason": message}))  # stop_hook_active checked above
    else:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
