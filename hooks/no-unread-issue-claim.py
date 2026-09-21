#!/usr/bin/env python3
"""Stop guard: reporting an issue as open or blocked without having read its comments.

An issue BODY is frozen at filing time. Its COMMENTS carry everything since:
the measurement that already ran, the PR that already shipped half of it, the
decision that was already taken. So a claim about what an issue still needs is
a claim about its comments, and reading only the body cannot support it.

THE MEASUREMENT (2026-09-21, ai-config#3823)
---------------------------------------------
Twice on `Lacaedemon/sparta`, and the second time is what this guard is for.

  1. 2026-09-18, #1544. A session claimed the issue from its body alone and
     proposed a state dump that had already merged in #1553. It cost a wasted
     claim, a draft PR opened and closed as obsolete (#1608), and a public
     correction. `warn-claim-without-comments-read.py` was built for it.
  2. 2026-09-21, #1566. A session read the body down to its `## Options`
     heading and stopped, then told the user across many turns that the issue
     needed THEIR decision, and that two P2 issues were blocked behind it. The
     decision had been taken, recorded in a design doc, and closed out; the
     issue's five comments said so, and three commits naming that work sat in
     the repository's recent history. It surfaced only when the user asked
     "what do I need to do on 1566?".

WHY THE SECOND SHAPE NEEDS ITS OWN INSTRUMENT
----------------------------------------------
The first shape already has one. `warn-claim-without-comments-read.py` is
registered and fires on a CLAIM posted without the comments read, and an
earlier draft of this paragraph said a prose memory had covered it --- which
is wrong twice over, since no memory entry about #1544 exists and the thing
that covers it is a merged sibling hook.

The two shapes fail in opposite directions, and that is what leaves a gap
between the guards rather than an overlap.

Claiming an issue and redoing merged work COLLIDES with reality quickly: you
open the file and the change is already there, so the mistake reports itself
even when nothing catches it first.

Escalating -- saying an issue is blocked, or awaits a human -- produces
nothing that can collide. It reads as diligence, it survives recap after
recap, and it is falsified only when a person reads it. In the measured case
it also compounded: downstream plans about two unrelated issues were built on
the false premise, so one unread comment thread produced repeated wrong
advice.

WHAT IT CHECKS
--------------
    the final assistant message asserts that issue #N is open work, is
        blocked, awaits a decision, or is waiting on the user
    AND no command in the transcript read #N's COMMENTS

A body-only read does NOT discharge it. `gh issue view <N> --json body` and
`--json title,body` are exactly what produced both measured failures, so
treating them as sufficient would make the guard inert on its own cases.

WHAT DISCHARGES IT
------------------
Any command that actually returns the comments for that number:
`gh issue view <N> --comments`, `--json comments`, `gh api .../issues/<N>/comments`,
`glab issue view <N> --comments`, or an MCP issue read naming comments.

The number must match. Reading #12's comments says nothing about #34, and a
guard that accepted any comment read anywhere would pass the moment a session
looked at one unrelated issue.

WHAT IT DOES NOT SEE
--------------------
Only the FINAL assistant text block of the turn. A claim made earlier in the
same turn, followed by an unrelated closing line, is invisible to it. That is
a real gap rather than a design choice, kept because the alternative -- every
assistant block in the turn -- multiplies the false-positive surface this
guard is most at risk from, and the final recap is where escalations to the
user actually land.

Several natural phrasings trip no cue: "can wait for now", "I have paused
work on it", "stays as-is until you say otherwise". The cue list is
deliberately narrow, on the standing argument that a guard which warns on
legitimate cases gets switched off and takes the real ones with it.

A cue and its issue must share a SENTENCE, so a list whose lead-in names the
subject is missed:

    Remaining on #12:
    - a written migration script
    - your decision on rollout timing

This is a known gap, and it was closed once and then deliberately reopened.
A `_list_subject` discriminator attached an item's cue to a colon-terminated
lead-in naming exactly one issue. Review found four ways it mis-attached:
two lead-ins in one paragraph sent the second issue's claim to the FIRST and
left the real one unnamed; a blank line between lead-in and list -- the
idiomatic Markdown form -- defeated it entirely; `J. Smith said` read as a
list item; and an issue named only in passing ("while #12 was building in
CI:") captured a list about something else.

The first is why it is gone rather than refined. This file argues throughout
that a silent miss is worse than a spurious warning, and that is right as far
as it goes -- but it assumed those were the only two outcomes.
MISATTRIBUTION is a third, and it is worse than both: the guard names an
issue whose comments WERE read, while the issue that actually went unread is
never mentioned. A reader acting on that warning is actively misdirected and
the real claim still escapes. A guard is allowed to miss things; it is not
allowed to point somewhere false.

Closing this properly needs the lead-in's SCOPE to be decidable -- where the
list it governs begins and ends, and whether the issue it names is the
subject or merely background -- which is discourse structure rather than
lexis.

A single letter and a period opens `J. Smith reviewed it` exactly as it opens
`a. the migration script`, and admitting both shapes as boundaries was
measured to split a real claim away from its own issue number across a
semantic line break. The two are separated by CASE rather than by
punctuation: an initial is capitalised and is neutralised before the split,
while a lowercase lettered item still ends a sentence. A capitalised lettered
list (`A. first item`) is therefore not a boundary, and a lowercase initial
(`e. coli`) is one. Both are rare, and neither can be told from its twin
without knowing whether a list is in progress.

The same rule declines to neutralise a period that itself follows a period,
so a dotted abbreviation ending a sentence (`... in the U.S. Now ...`) still
ends it. The cost is a double initial written closed up: `J.R. Smith` keeps
`R.` as a terminator and can split a claim there. That shape was never
handled, and admitting it would reopen the abbreviation case, which is the
worse of the two -- it merges sentences rather than splitting them, and a
merge is what produces a warning naming the wrong issue.

An unclosed fence leaves the rest of the message as prose rather than
swallowing it, which is `fences.strip_code`'s default and is the right
direction here: swallowing would let one stray backtick run silence every
claim after it.

ON BUILDING THIS AT THE SECOND OCCURRENCE
------------------------------------------
`shared/principles/deterministic-tools.md` sets the bar at the third
occurrence, and ai-config#3823 -- this guard's own issue -- recorded the
decision to FILE rather than build, explicitly because two is not three.

Building it anyway reverses that, so the reversal is recorded here rather
than left silent, per `shared/workflow/incidents-dont-repeal-decisions.md`.
The reason is not a third occurrence: it is that `no-mistake-without-a-hook`
does not accept a filed issue as discharging a mistake, and the session had
by then filed three mechanism proposals against one built mechanism, which is
the shape of filing becoming an escape rather than a schedule.

The three were ai-config#3817, #3821 and #3823, against ai-config#3818 as the
one that session had built **at the moment the decision was taken**.

That qualifier is load-bearing and was missing. #3821 was itself built and
merged at 09:31 PT the same morning, half an hour before this file's round-5
commit, so by then the ratio was two built against two filed rather than one
against three. The condition the argument rests on flipped inside the same
session -- which is exactly what
`shared/writing/timestamp-volatile-claims.md` exists for: a built-versus-filed
count is a claim about a moment, not a standing fact. The judgment still
stands on the reasoning above it; the arithmetic it cited does not.

That list is NOT derivable by query, and an earlier draft of this paragraph
claimed it was. It cited

    gh issue list -R Morrison-Lab/ai-config --state all --author <user> \
      --search 'Hook: in:title created:2026-09-20..2026-09-21'

and reported it as returning exactly those three. It returns seven, and the
draft was written after that output had been read -- three rows were kept and
the rest dropped, with the result presented as what the query returned. The
query cannot give the intended figure at all: the login is shared across
concurrent sessions, so it cannot separate one session's filings from
another's, and #3818 is a pull request, which `gh issue list` never returns.

The numbers above are therefore identified from the session's own history and
labelled as such. A citation that does not survive being re-run is worse than
an honest recollection, because it transfers the reader's trust to something
that was never checked.

A reader who thinks the third-occurrence bar should have held is disagreeing
with a judgment that was made knowingly, not catching an oversight.

CONTRACT
--------
Warns, never blocks. An issue can legitimately BE blocked, and saying so is
often the correct report -- the guard cannot know which, only that the
cheapest supporting evidence was never gathered. Fails open on every internal
error, per the hooks' file-wide contract.
"""

import json
import os
import re
import sys

# Code regions are quoted material, not assertions. A recap explaining THIS
# guard cites its own trigger phrases, and every such citation is an assertion
# in form and a quotation in fact.
#
# The shared stripper in `scripts/lib/fences.py` does the work rather than a
# local regex, for the reason its own docstring gives: a whole-document
# backtick-run pattern pairs runs across the file, so a four-backtick fence
# wrapping a three-backtick example throws every later region out of phase and
# the quoted text reads back as prose. That shape is not hypothetical for THIS
# guard, since documenting it means quoting its own trigger phrases inside a
# nested fence.
_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from fences import strip_code  # type: ignore
except Exception:  # pragma: no cover - only where the shared library is absent
    strip_code = None

if strip_code is None:
    def strip_code(text, fence_replacement=" ", span_replacement=" "):
        """Fallback for a checkout without the shared library.

        It carries the nesting bug described above. That is deliberate: a
        degraded stripper still removes the common single-fence case, and
        failing open is this file's contract.
        """
        text = re.sub(r"```[\s\S]*?```", fence_replacement, text)
        return re.sub(r"`[^`\n]*`", span_replacement, text)


# A blockquote line. `fences.strip_code` does not cover these, and a quoted
# recap is quoted material by exactly the argument a fenced one is.
QUOTE = re.compile(r"(?m)^[ \t]*>[^\n]*$")


def visible_prose(text):
    """Drop fenced blocks, blockquotes and code spans, keeping offsets sane.

    A period is substituted rather than a space so the removed region acts as
    a sentence BOUNDARY: the cue and the issue reference must co-occur in one
    sentence, and a code span between them should separate rather than join.
    """
    if not isinstance(text, str):
        return ""
    text = strip_code(text, fence_replacement=".", span_replacement=".")
    # `QUOTE` is line-anchored, so what replaces a blockquote line makes no
    # difference: the newlines around it already separate what remains.
    # Substituting a period here would read as load-bearing and is not --
    # mutating it to the empty string leaves every case green.
    return QUOTE.sub("", text)


# An issue reference. This guard is about issues, and a PR's comments are a
# different question with its own guards, so `PR #12` is excluded -- by
# `RX_PR_PREFIX` below, which reads what precedes the number, and not here.
#
# A `(?<!pull/)` lookbehind used to sit in this pattern, and the comment above
# it credited the exclusion of pull URLs to it. It never did any work: a pull
# URL is `.../pull/1622` with no `#` at all, so nothing in a real URL puts
# `pull/` immediately before a `#`, and the test that was written to justify
# the lookbehind passes with it deleted because its fixture contains no `#`.
# The remaining lookbehind is load-bearing -- it keeps `abc#12` from matching.
RX_ISSUE = re.compile(
    r"(?<![A-Za-z0-9])#(\d{1,7})(?![0-9])"
)


def issue_key(number):
    """Canonicalise an issue number so both sides of the check compare equal.

    The assertion and the discharging command are matched as strings, and
    nothing forces them to be written the same way: `#0012` in a recap against
    `issue view 12 --comments` in the transcript are the same issue and are
    not the same string. Comparing the raw captures reports a read issue as
    unread, which is the misattributing warning this file rates worst.
    """
    return number.lstrip("0") or "0"
# A PR reference immediately before the number: `PR #12`, `pull request #12`.
#
# `for` is admitted ONLY directly after a PR-referring noun, which is the
# scoped middle option between the two failures already measured here:
#
#   too narrow (`PR|pull request|pull` alone) -- "The PR for #12 is awaiting
#       review" fires, crediting the PR's cue to the issue.
#   too broad (`fix|patch|branch ... for`) -- "Apply the fix for #12, it
#       still needs your input" goes SILENT, swallowing exactly the claim
#       this guard exists to catch.
#
# Anchoring `for` to the PR noun excludes the first without reaching the
# second, because "fix"/"patch"/"branch" never precede it here.
# EVERY whitespace run is bounded, which is what makes the lookback window
# below sound. With `\s*` or `\s+` the pattern's longest possible match has
# no limit, so no finite window can be proved not to change a verdict --
# padding a gap past the window silently turns the exclusion off.
#
# Two rounds were needed to get this right, and the second is the instructive
# one: the first bounded the two obvious runs and left `pull\s+request`
# unbounded, then asserted an exact maximum computed as though it had been
# bounded too. The arithmetic was right about the runs it counted. Bounding
# "the whitespace" is not a thing you can check by rereading the sentence you
# just wrote; it is a thing you check by counting the quantifiers.
#
# Eight is past any real spacing, including a line wrap and a nested list
# indent, and is pinned in both directions by test cases at 8 and at 9.
RX_PR_PREFIX = re.compile(
    r"(?:\bPR|\bpull\s{0,8}request|\bpull)\b\s{0,8}(?:for\s{0,8})?$", re.I)

# How far back of an issue reference the PR prefix is looked for.
#
# Scanning the whole preceding text instead re-scanned from the start of the
# sentence for EVERY match in it, and a bare newline is deliberately not a
# sentence boundary here, so a recap of one `blocked on #N` line per issue
# stays a single sentence. Measured: 136 KB of that shape took 10.05 seconds,
# against this hook's own 10-second budget in `hooks.json` -- so a long enough
# legitimate recap silently turned the guard off, on exactly the transcript it
# was written for.
#
# The window is derived from the pattern rather than chosen. Summing the
# longest alternative and every bounded run gives
# `pull` + 8 + `request` + 8 + `for` + 8 = 38 characters, and the window is
# past that with room to spare.
#
# A test exercises a prefix at that full length, so the floor is pinned by a
# case rather than by this arithmetic. The previous comment claimed the suite
# asserted a floor it did not: every window down to 20 passed, because no
# case came near the maximum. A derivation nothing exercises is a guess with
# a sum next to it.
PREFIX_WINDOW = 48

# A sentence boundary.
#
# A BARE newline must NOT split, and that is the whole subtlety. This repo
# writes semantic line breaks, so an ordinary claim is routinely wrapped at a
# clause boundary with no terminator:
#
#     The naming question in #12
#     still needs your decision.
#
# Splitting there puts the cue and the number in different "sentences" and the
# guard goes silent -- a false NEGATIVE on its core function, which is strictly
# worse here than the false positive it would be trading away: a guard that
# fails to fire collides with nothing and is falsified only when a person
# reads it, which is the same asymmetry this file exists to police.
#
# So a newline ends a sentence only where it is a HARD boundary: a blank line
# (paragraph), or the next line opening a list item. Those are what make a
# bulleted recap several claims rather than one, which was the reported
# defect.
#
# A semicolon does split, and that loses any claim whose subject sits on one
# side and whose cue sits on the other:
#
#     #12 is filed; it still needs your call.
#     I looked at #12; it is still blocked on your decision.
#
# An earlier comment here called that shape "rare in recaps". That was an
# assertion with nothing behind it, and it is not obviously true -- a pronoun
# back-reference across a semicolon is an ordinary way to write a status
# line. It is recorded as a known, unmeasured gap rather than argued away.
# The semicolon is kept because it does close a measured false positive
# ("several PRs pending; #12 is an example"), and because resolving the
# trade properly needs pronoun resolution, which is well past what a lexical
# guard should attempt.
# Bullet markers, deliberately wider than `-*+`: a lettered or roman `a)` /
# `ii)` list, or a Unicode bullet, is the same structure and was cross-
# attaching cues between items because the narrower set did not see it.
#
# NUMBERED items are NOT boundaries. A numbered list usually ELABORATES one
# claim introduced by a lead-in line ("the two remaining tasks for #12:
# 1. ... 2. it still needs your sign-off"), so splitting there separates the
# claim from its own subject -- the same silent miss the bare-newline split
# caused. A digit can also open a continuation line by accident. Bulleted
# items, by contrast, are typically independent status lines, which is the
# shape that produced the original cross-attachment.
# A line-leading numeric enumerator, whose trailing `.` or `)` is punctuation
# rather than a sentence end.
RX_ENUMERATOR = re.compile(r"(?m)^([ \t]*\d+)[.)](?=\s)")

# A personal initial: one letter, standing alone, before a capitalised word.
# Its period is punctuation inside a name rather than a sentence end, and
# treating it as a terminator was measured to cut a claim off from its own
# issue number -- `#12 is outstanding, per J. Smith's review, and it still
# needs your call` split at `J.` and left the cue in a sentence with no
# number in it.
#
# The lookbehind excludes a preceding PERIOD as well as a letter, and the
# period is the half that was missing. Excluding a letter keeps an acronym
# ending a real sentence (`... opened the PR. It still needs your call`)
# splitting normally. Without the period, the LAST letter of a dotted
# abbreviation matched instead: in `#12 is closed in the U.S. Now #34 needs
# your call`, the `S` is preceded by a period rather than a letter, and an
# English sentence after such an abbreviation ordinarily begins with a
# capital, so the lookahead matched too. The terminator was deleted, the two
# sentences merged, and the guard warned about #12 -- which the message says
# is CLOSED -- while the real claim about #34 went unnamed. That is
# misattribution, which this file rates worse than a miss. `P.S.`, `E.U.`,
# `U.K.`, `D.C.` and `U.N.` all reproduce it.
#
# The cost is a double initial written with no space: `J.R. Smith` keeps
# `R.` as a terminator. `J.` does not match there either, since no space
# follows it, so the shape was never handled and this does not regress it.
RX_INITIAL = re.compile(r"(?<![A-Za-z.])([A-Z])\.(?=\s+[A-Z])")

# `J. Smith` opens a wrapped line in the same shape `a. first item` does, and
# the letter form below cannot tell them apart. It does not have to: the
# initial's period is removed by `RX_INITIAL` before this pattern ever runs,
# so what reaches here is `J Smith` and no marker matches. The division is by
# CASE rather than by punctuation, which is why both stay simple -- an
# initial is capitalised and a lettered list item conventionally is not.
RX_SENTENCE = re.compile(
    r"(?<=[.!?;])\s+"                    # a terminator, then any whitespace
    r"|\n\s*\n"                          # a blank line: paragraph boundary
    r"|\n(?=[ \t]*(?:[-*+•‣◦]|"   # a bulleted item
    r"[A-Za-z][.)]|[ivxIVX]+[.)])\s)"    # or a lettered / roman item
)

# Asserting that the issue still needs something. Deliberately narrow: an
# ordinary mention of an issue number is not a claim about its state, and a
# guard that fired on every `#N` would be noise and get switched off.
CUES = [
    r"\bblocked\s+(?:on|by)\b",
    r"\bawait(?:s|ing)\b",
    r"\bwaiting\s+(?:on|for)\b",
    r"\bneeds?\s+(?:your|a\s+human|the\s+user|a\s+decision|an\s+answer)",
    r"\byour\s+(?:call|decision|answer|input)\b",
    # "that one is yours rather than mine" -- the commonest way an escalation
    # is actually phrased, and the shape the measured case used. Without it
    # the guard misses its own originating sentence.
    r"\b(?:is|are|stays?|remains?)\s+yours\b",
    r"\byours\s+(?:to\b|rather\s+than\b)",
    r"\bstill\s+(?:open|unanswered|outstanding|needs)\b",
    r"\bremains?\s+(?:open|unanswered|outstanding|blocked)\b",
    r"\bunanswered\b",
    r"\bgates?\b",
    r"\bopen\s+work\b",
    r"\bnot\s+(?:yet\s+)?(?:started|done|decided)\b",
    r"\bpending\b",
]
RX_CUE = re.compile("|".join(CUES), re.I)

# "Did something read issue N's comments?" is `warn-claim-without-comments-read.py`'s
# question, already answered there, and this file asks it about the same
# surfaces. Reimplementing it was a mistake with a measured cost.
#
# The reimplementation matched by PROXIMITY over a serialized blob: an
# `issue_read` call with the number somewhere near the substring `comments`,
# or an `issue view` whose `--json` value was followed eventually by the word
# `comments`. Both accept things that did not read any comments --
# `{"method": "get_labels", "include_comments": false}` discharges on the key
# name, and `--json title,body  # will check comments next` discharges on a
# shell comment. A false discharge is the worst outcome available here: the
# guard goes silent on exactly the claim it exists to catch, and nothing
# reports that it did.
#
# The sibling's versions are structural. `mcp_reads_comments` compares
# `tool_input["method"]` to `get_comments`; `_json_includes_comments` splits
# the `--json` value on commas and tests for the exact token. Borrowing them
# fixes both, keeps the two guards agreeing about what a read IS, and means a
# fix to either reaches both.
_HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None. Fails open, as ever."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            key, os.path.join(_HOOKS_DIR, name))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_claim = _sibling("warn-claim-without-comments-read.py", "_sib_unread_claim")
command_reads_comments = getattr(_claim, "command_reads_comments", None)
mcp_reads_comments = getattr(_claim, "mcp_reads_comments", None)
# The transcript walker and the command extractor come from the same place,
# for the same reason. `_tool_uses` reads the Antigravity `tool_calls` shape
# as well as the block-list one, and `_payload_commands` yields a command
# from `command`, `cmd` or `CommandLine` whatever the tool is NAMED. An
# earlier version of this file walked only block lists and matched the tool
# name `Bash` exactly, which made a genuine comments read invisible in an
# Antigravity transcript -- in a file that special-cases Antigravity nine
# lines from the end.
_tool_uses = getattr(_claim, "_tool_uses", None)
_payload_commands = getattr(_claim, "_payload_commands", None)

NOTE = (
    "Unread-issue reminder: this message reports issue #{n} as open, blocked, "
    "or awaiting a decision, and nothing in this session read #{n}'s "
    "COMMENTS.\n\n"
    "An issue's BODY is frozen at filing time. Its comments carry what has "
    "happened since -- the measurement that already ran, the PR that already "
    "shipped half of it, the decision that was already taken. A body-only "
    "read cannot support a claim about what the issue still needs.\n\n"
    "    gh issue view {n} --comments\n\n"
    "Also worth one look: whether the work landed already --\n\n"
    "    git log --oneline -20 | grep -i '#{n}'\n\n"
    "Measured twice on the same repository (ai-config#3823). The second time, "
    "a decision that had already been taken and documented was reported to "
    "the user as theirs to make, across several turns, and two unrelated "
    "issues were described as blocked behind it.\n\n"
    "If the issue genuinely is blocked, say so -- this is a reminder, not a "
    "refusal."
)


def tool_uses(transcript_path):
    """Every `(name, input)` tool call in the transcript, or None.

    The tool NAME is carried alongside the input because the MCP check keys
    on it: `issue_read` is part of the name and never appears in the input,
    so an earlier version that looked only at the input made that whole
    discharge path dead code -- silently, and in exactly the remote sessions
    where `tool-mappings.md` routes this work to MCP because `gh` is absent.
    """
    out = []
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if _tool_uses is None:
                    return None
                for name, payload in _tool_uses(rec):
                    out.append((name, payload))
    except Exception:
        return None
    return out


def comments_were_read(number, uses):
    """True when some tool call in `uses` read issue `number`'s comments.

    Both checks come from `warn-claim-without-comments-read.py`. Where that
    sibling cannot be imported the answer is True, which suppresses the
    warning: a guard that cannot tell whether the evidence was gathered must
    not assert that it was not.
    """
    if None in (command_reads_comments, mcp_reads_comments, _payload_commands):
        return True
    try:
        for name, inp in uses:
            for command in _payload_commands(inp):
                if command_reads_comments(command, number):
                    return True
            if mcp_reads_comments(name, inp, number):
                return True
    except Exception:
        # A borrowed function that raises means this hook can no longer tell
        # a read from an unread issue. Catching per call and carrying on
        # would answer False for every issue in every session -- a universal
        # spurious warning with no diagnostic. Fail open instead, on the same
        # argument as the missing-import case above.
        return True
    return False


def last_assistant_text(transcript_path):
    """The final assistant message's visible text, or ''."""
    text = ""
    if not transcript_path or not os.path.exists(transcript_path):
        return text
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                role = rec.get("type") or rec.get("role")
                blocks = (rec.get("message") or {}).get("content") or rec.get("content") or []
                if isinstance(blocks, list):
                    for b in blocks:
                        if (isinstance(b, dict) and b.get("type") == "text"
                                and role == "assistant" and (b.get("text") or "").strip()):
                            text = b["text"]
                elif isinstance(blocks, str) and role == "assistant" and blocks.strip():
                    text = blocks
    except Exception:
        return ""
    return text


def asserted_issues(text):
    """Issue numbers this text reports as open, blocked, or awaiting someone.

    The cue and the reference must share a SENTENCE. Requiring only that both
    appear in the message would fire on any recap that mentions an issue
    anywhere and says "blocked" about something else entirely.
    """
    out = []
    prose = visible_prose(text)
    # A line-leading enumerator carries a PERIOD, so the terminator rule would
    # split "1. the docs pass" right after the marker -- separating a numbered
    # item from the lead-in that names its subject, which is the silent miss
    # the list-marker branch above deliberately avoids. Neutralize the
    # marker's punctuation first so only real sentence ends split.
    prose = RX_ENUMERATOR.sub(r"\1 ", prose)
    prose = RX_INITIAL.sub(r"\1", prose)
    for sentence in RX_SENTENCE.split(prose):
        if not RX_CUE.search(sentence):
            continue
        for m in RX_ISSUE.finditer(sentence):
            if RX_PR_PREFIX.search(sentence[max(0, m.start() - PREFIX_WINDOW):
                                           m.start()]):
                continue
            out.append(issue_key(m.group(1)))
    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tpath = payload.get("transcript_path") or payload.get("transcriptPath") or ""
        text = last_assistant_text(tpath)
        if not text:
            return 0
        numbers = asserted_issues(text)
        if not numbers:
            return 0
        uses = tool_uses(tpath)
        if uses is None:
            # No readable transcript means no evidence either way. Fail open
            # rather than warn on every issue mention in a session we cannot
            # inspect.
            return 0
        missing = [n for n in numbers if not comments_were_read(n, uses)]
        if not missing:
            return 0
        n = missing[0]
        out = {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": NOTE.format(n=n),
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Unread-issue reminder: #{n} is reported as open or blocked, "
                f"but its comments were never read. Run "
                f"`gh issue view {n} --comments` before asserting what it needs.")
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
