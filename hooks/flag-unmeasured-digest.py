#!/usr/bin/env python3
"""PreToolUse guard: a checksum or commit SHA typed into a forge body needs a reading.

A digest is a *measured* value, exactly as a clock time is. It cannot be
recalled, inferred, or approximated -- it is either read out of a command's
output or it is invented. `flag-unmeasured-timestamp.py` is this guard's
sibling and its model: same shape, same fail-open contract, a different class
of unmeasurable value.

Not the same *surfaces*, though. That hook is registered on `Write`, `Edit` and
`NotebookEdit` as well as `Bash` and the MCP comment tools; this one is
registered on `Bash` and the MCP tools only, because a digest written into a
file is not yet a claim to anyone. One asymmetry falls out of reusing its body
extraction: a `cat >>` append to a session notebook reaches the notebook branch
and warns, while the same edit through the `Write` tool does not, since nothing
registers this hook there.

THE MEASUREMENT (2026-09-18, ai-config#3779)
--------------------------------------------
While importing course material into `Morrison-Lab/mlg`, a session filed an
issue whose body read:

    (md5 of both: `3e2b9e10...` --- see below)

No command in that session had produced `3e2b9e10`. The two files' real digest
was `fc967f3e60b170150f3bd94158cc776a`, which the session measured three tool
calls *later* and then had to correct the issue to carry. Nothing about the
invented value looked wrong: it was hex, it was the right shape, it sat in
backticks beside a claim the session had genuinely verified by another route
(the files were confirmed identical), and the surrounding sentence was true.
That is the whole hazard -- a fabricated digest is indistinguishable from a
real one by inspection, and it is *more* convincing than the prose around it,
because a hash reads as evidence.

WHY THE PROSE RULE DID NOT REACH IT
------------------------------------
`shared/principles/deterministic-tools.md` and `CLAUDE.md`'s
"Timestamp recaps in local time" both say to derive a measured value from a
reading taken in the moment, and the latter's hook covers clock times. Neither
names a digest. The rule that *would* have caught it --
`metacognitive-monitoring.md`'s "a claim about state gets re-queried" -- is
consulted at read time and broken at composition time, which is the standing
argument for an instrument over a rule.

The near-miss is worth naming, because it is what makes the fabricated value
feel safe to write: the *claim* was checked. The files really were identical.
Only the evidence cited for it was invented, as a placeholder the author
intended to fill in and did not. So a guard keyed on whether the surrounding
assertion is true would never fire; the decidable condition is narrower and
purely lexical -- is this hex string anywhere in the transcript?

WHAT IT CHECKS
--------------
    the outgoing body (a forge comment, an issue or PR body being created or
        edited, or an append to a session notebook or memory file) contains a
        digest-shaped token, meaning a run of 7 to 64
        hex characters that contains at least one of `a`-`f`, and that is
        EITHER
            exactly 32, 40, or 64 characters (md5, sha1, sha256),
            OR followed by an ellipsis, either three dots or the single
                character (a truncation, which is the shape a placeholder
                takes),
            OR preceded within `KEYWORD_WINDOW` characters by a digest word
                (`md5`, `sha`, `sha256`, `hash`, `digest`, `checksum`, `blob`,
                `oid`, `commit`)
    AND no prior tool result, and no prior user message, in the transcript
        contains a hex run having that token as a prefix

The prefix rule is what keeps a legitimate abbreviation quiet. Writing
`fc967f3e...` after running `md5` discharges, because the full digest the
command printed starts with those characters. Writing `3e2b9e10...` does not,
because nothing printed anything starting that way. A short commit SHA quoted
from `git log` discharges for the same reason, and one typed from memory does
not -- which is the correct outcome in both directions.

At least one `a`-`f` is required so that a bare decimal run is never a hit:
a Canvas assignment id (`10134103`), a port, an issue number padded out, and a
row count are all `[0-9]{7,}` and none of them is a digest.

WHAT IT DELIBERATELY DOES NOT CHECK
------------------------------------
Whether the digest is *correct*. A hook cannot recompute an arbitrary file's
hash at PreToolUse time, and a stale-but-real digest (measured, then the file
changed) is a different defect with a different remedy. This guard answers one
question -- was this value ever observed in this session -- and a `yes` is not
a verdict that the value is right.

A token the session measured at any point discharges, not only one measured in
the current turn. Unlike a clock reading, a hash does not expire: the digest of
a file that has not changed is as true an hour later as it was when printed.

THE SECOND SURFACE: A PINNING ARGUMENT (2026-09-20, ai-config#3392)
--------------------------------------------------------------------
Everything above is about a value written into a *body*. A commit SHA passed
as a *command argument* is the same class of unmeasurable value reaching the
same kind of harm by a different route, and no body extractor sees it:

    gh api -X PUT repos/O/R/pulls/N/update-branch -f expected_head_sha=<sha>
    gh pr merge N -R O/R --squash --match-head-commit <sha>

#3392 specified this check on 2026-09-09, after a sweep padded the
abbreviation `4d443b7a` out to forty plausible characters. It was not built,
and on 2026-09-20 the identical mistake recurred on `Lacaedemon/sparta#1615`:
`check-pr-fully-clean.py` prints the head abbreviated, so the full value has
to be re-read, and instead it was invented past the eighth character.

This surface needs none of the digest-shaping heuristics above. The flag name
already establishes that the value is a commit SHA, so the only question left
is whether the session ever observed it -- which makes the check strictly
sharper here than on a prose body.

It is also the surface where the consequence is worst, because the failure is
MISDIAGNOSED rather than merely wrong. A fabricated pin is refused with
`422 expected head sha didn't match current head ref.` (or
`Head branch was modified` on a merge), byte-identical to what a genuine
concurrent writer produces -- and `skills/mwc`, `skills/chores`,
`skills/merge-it` and `shared/workflow/fully-clean.md` all tell the reader
that this error means another writer moved the head, routing to "settle
ownership". So the documented diagnosis sends you into a concurrency
investigation over your own typo. The warning therefore names the remedy
(re-read `--json headRefOid`) and, when the fabricated value's leading
characters WERE observed, says outright that an abbreviation was padded.

RELATION TO `flag-unread-commit-citation.py`
--------------------------------------------
Both can fire on one body naming a commit SHA, and they answer different
questions: that one asks whether you READ the commit you are citing, this one
asks whether the value was ever OBSERVED. A SHA copied from `git log` satisfies
this guard and not that one. The overlap is two warnings on one token, which is
noise worth knowing about rather than a defect in either.

CONTRACT
--------
Warns, never blocks. `metacognitive-monitoring.md`'s claim classes are not
lexically decidable, and a body may legitimately carry a digest this session
never computed -- one quoted from an upstream advisory, a lockfile, or a
vendor's release page. Blocking those would be wrong, and a guard that is
wrong on a legitimate case is a guard that gets switched off, taking the real
cases with it. Fails open on every internal error, per the hooks' file-wide
contract.
"""

import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))

# How far back from a hex token to look for a word that makes it a digest.
KEYWORD_WINDOW = 48

# Hex runs shorter than this are too common in ordinary prose to test.
MIN_HEX = 7
MAX_HEX = 64

# Lengths that are a digest on their own, with no keyword needed.
CANONICAL_LENGTHS = {32, 40, 64}


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    The same pattern `flag-unmeasured-timestamp.py` uses to reach
    `no-unmeasured-clock-claim.py`. Fails open, per the file-wide contract.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_stamp = _sibling("flag-unmeasured-timestamp.py", "_sib_unmeasured_digest_stamp")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_unmeasured_digest_rebuttal")

# Body extraction is reused verbatim rather than re-implemented, so this guard
# and its sibling cannot disagree about which tool calls post a body, how a
# `--body-file` is read off disk, or which heredoc is the payload.
_post_from_payload = getattr(_stamp, "_post_from_payload", None)
_extract_body_text = getattr(_rebuttal, "extract_body_text", None)
_short_flag_body = getattr(_stamp, "_short_flag_body", None)
_extract_heredoc_bodies = getattr(_stamp, "_extract_heredoc_bodies", None)

# glab spells the body `-d`/`--description`, which none of the `gh`-shaped
# body regexes match. Without this the glab arm of RX_CREATE_POST is dead.
RX_GLAB_DESCRIPTION = re.compile(
    r"(?<![^\s])(?:-d|--description)[= ]+(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)')", re.S)

# The sibling covers the surfaces that COMMENT on an existing thread. The
# measurement behind this guard was an issue being CREATED, whose body never
# passes through any of them, so the creation and edit forms are added here
# rather than widened there -- a clock stamp in a fresh issue body is a
# different question, and #2903 deliberately scoped that hook to comments.
RX_CREATE_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:gh|glab)\s+(?:issue|pr|mr)\s+(?:create|edit)\b",
    re.I | re.M,
)


# Bounded on BOTH sides. Without the trailing lookahead MAX_HEX bounds
# nothing: a 120-character hex dump still matches its first 64 characters
# and reads as a canonical sha256.
RX_HEX = re.compile(r"(?<![0-9a-zA-Z])([0-9a-fA-F]{%d,%d})(?![0-9a-zA-Z])(\.{3}|…)?" % (MIN_HEX, MAX_HEX))

# Each alternative is boundary-anchored. Without that, `sha` matches inside
# "shall", "shared" and "shape", and `oid` inside "avoid" and "android" -- so
# ordinary prose supplies the keyword for any hex-looking run near it, and a
# corpus whose PR bodies say "shared/" constantly warns on nearly everything.
RX_DIGEST_WORD = re.compile(
    r"(?<![A-Za-z])"
    r"(?:md5|sha-?1|sha-?256|sha-?512|sha|hashe?[sd]?|digest|checksum|blob|oid|commit)"
    r"(?![A-Za-z])",
    re.I,
)

# A hex run inside a URL path is almost always a link to something real (a
# commit page, a gist, a raw blob), and the session may never have printed it.
# Matched against everything on the line before the token rather than against
# the keyword window: a raw.githubusercontent.com permalink or a nested-group
# GitLab commit URL puts far more than KEYWORD_WINDOW characters between the
# scheme and the SHA, and losing the exemption there warns on an ordinary link.
RX_URLISH = re.compile(r"[a-z][a-z0-9+.-]*://\S*$", re.I)

NOTE = (
    "Unmeasured-digest reminder: this {surface} states `{token}`, which is "
    "shaped like {kind} and does not appear in any tool result or user "
    "message in this session's transcript.\n\n"
    "A digest is a measured value -- it is read out of a command's output or "
    "it is invented, and the two are indistinguishable once written. Run the "
    "command that produces it (`md5 <file>`, `shasum -a 256 <file>`, "
    "`git rev-parse <ref>`) and paste what it returned.\n\n"
    "If the value legitimately comes from outside this session -- an upstream "
    "advisory, a lockfile, a vendor release page -- say where, and carry on. "
    "This is a reminder, not a refusal."
)

# The pin surface (ai-config#3392). A flag that pins an operation to a head
# commit takes the FULL 40 characters, and the value can only have been read --
# from `--json headRefOid`, from `git rev-parse`, or from the user. There is no
# derivation, so unlike the body surface this needs no length/keyword heuristic:
# any hex passed here that the session never observed is fabricated.
#
# Both `=` and whitespace separate a flag from its value, and the MCP spelling
# `expectedHeadSha` arrives as a JSON key, so a colon is a separator too.
# Anchored at the START of a shell word (see `_pins_in`). `(?:=|:)?` covers the
# attached spellings; an empty group 2 means the value is the following word.
#
# The hex run is NOT capped at 40. A cap plus a trailing boundary silently
# SKIPS anything longer -- a SHA-256 repository's 64-character head, or a value
# mistakenly concatenated with something else -- since no backtracked length
# can satisfy the boundary. Skipping is the one outcome a guard must not have,
# so the run is open-ended and the length is simply not this check's business.
RX_PIN_WORD = re.compile(
    r"(expected_head_sha|expectedHeadSha|--match-head-commit)"
    r"(?:[=:]([0-9a-fA-F]{7,}))?$"
)

RX_BARE_SHA = re.compile(r"^[0-9a-fA-F]{7,}$")

# Shell metacharacters that end a word regardless of adjacent whitespace.
# Redirections are included: `--match-head-commit <sha>>log` is a pin plus a
# redirect to `sh`, so the value must not absorb the `>`.
SHELL_OPERATORS = frozenset(";&|()<>")

PIN_NOTE = (
    "Unmeasured-pin reminder: this command pins `{flag}` to `{token}`, which "
    "never appeared in any tool result or user message in this session's "
    "transcript.{padded}\n\n"
    "A pinning SHA is a measured value. Read it at the point of use --\n"
    "    gh pr view <N> --json headRefOid --jq .headRefOid\n"
    "-- rather than constructing it from an abbreviation.\n\n"
    "This matters more than an ordinary unmeasured value, because the failure "
    "is misdiagnosed rather than merely wrong: a fabricated pin is refused "
    "with `422 expected head sha didn't match current head ref.` (or "
    "`Head branch was modified` on a merge), which is byte-identical to what "
    "a genuine concurrent writer produces. The corpus tells you that error "
    "means another writer moved the head and routes you to settle ownership, "
    "so following it sends you into a concurrency investigation over your own "
    "typo. Re-read the head and compare before investigating anything.\n\n"
    "This is a reminder, not a refusal."
)

PADDED_NOTE = (
    " Its leading `{prefix}` DID appear, so an abbreviation was padded out to "
    "40 characters rather than the full value being read."
)


def hex_tokens_in(text):
    """Every hex run in `text`, lowercased, as a set. Used for the transcript side."""
    out = set()
    if not isinstance(text, str):
        return out
    for m in RX_HEX.finditer(text):
        out.add(m.group(1).lower())
    return out


def _is_digest_shaped(body, match):
    """(is_digest, kind) for one hex match, by length, truncation, or nearby keyword."""
    token = match.group(1)
    truncated = bool(match.group(2))
    if not re.search(r"[a-fA-F]", token):
        return False, None
    start = match.start(1)
    line_start = body.rfind("\n", 0, start) + 1
    if RX_URLISH.search(body[line_start:start]):
        return False, None
    before = body[max(line_start, start - KEYWORD_WINDOW):start]
    if len(token) in CANONICAL_LENGTHS and not truncated:
        return True, {32: "an md5 digest", 40: "a sha1 digest",
                      64: "a sha256 digest"}[len(token)]
    if truncated:
        return True, "a truncated digest or commit SHA"
    if RX_DIGEST_WORD.search(before):
        return True, "a digest or commit SHA"
    return False, None


def _transcript_hex(transcript_path):
    """Every hex run appearing in a prior tool result or user message.

    Reads the JSONL transcript directly rather than reusing the clock hook's
    `scan()`, which returns a turn boundary and a clock reading and discards
    the tool output this guard needs. A digest measured earlier in the session
    and quoted now is fine, so unlike the clock guard there is no turn
    boundary here -- a hash does not expire.
    """
    seen = set()
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
                role = (rec.get("type") or rec.get("role") or "")
                # A tool result arrives as a `user` record whose message.content
                # holds a block of type "tool_result"; no record carries a
                # top-level type of "tool_result". `user` is therefore the whole
                # of it, and it covers the user's own turns too -- the two places
                # a value can enter the session from outside the model.
                if role != "user":
                    continue
                # `toolUseResult` sits beside `message` and can hold the whole
                # stdout where `message.content` was truncated, so read both.
                seen |= hex_tokens_in(json.dumps(rec.get("message", "")))
                seen |= hex_tokens_in(json.dumps(rec.get("toolUseResult", "")))
    except Exception:
        return None
    return seen


def _measured(token, seen):
    """True when some observed hex run has `token` as a prefix."""
    token = token.lower()
    for obs in seen:
        if obs.startswith(token):
            return True
    return False


def unmeasured_digest(body, transcript_path, assume_unmeasured=False):
    """(token, kind) for the first unmeasured digest-shaped token, else None.

    `assume_unmeasured` is for `--dry-run`, where the caller is probing the
    body shape and supplies no transcript. Treating "no transcript" as fail-open
    there makes the affordance inert under every input, which is a reused
    construct whose purpose did not transfer: the sibling's dry-run warns
    because its check does not depend on transcript *contents*.
    """
    if not isinstance(body, str) or not body.strip():
        return None
    seen = _transcript_hex(transcript_path)
    if seen is None:
        if not assume_unmeasured:
            # In a live hook invocation, no readable transcript means no
            # evidence either way. Fail open rather than warn on every digest
            # in a session we cannot inspect.
            return None
        seen = set()
    for m in RX_HEX.finditer(body):
        is_digest, kind = _is_digest_shaped(body, m)
        if not is_digest:
            continue
        token = m.group(1)
        if _measured(token, seen):
            continue
        return token, kind
    return None


def _executable_text(command):
    """`command` with heredoc payloads and shell comments removed.

    The pin flags are matched as literal text, so any occurrence in a command
    that merely WRITES documentation -- a heredoc authoring a skill file that
    shows `gh pr merge --match-head-commit <sha>` as an example, or a
    commented-out earlier attempt -- would otherwise warn about a command that
    never runs. This corpus documents its own invocations constantly, so that
    false positive is routine rather than contrived, and a guard that warns on
    a legitimate case is one that gets switched off.

    `strip_heredocs` is the sibling's, reused so this guard and the body
    surface cannot disagree about where a heredoc ends.
    """
    if not isinstance(command, str):
        return ""
    strip = getattr(_stamp, "strip_heredocs", None) or getattr(
        _rebuttal, "strip_heredocs", None)
    if strip is not None:
        try:
            command = strip(command)
        except Exception:
            pass
    return _strip_comments(command)


def _strip_comments(command):
    """`command` with shell comments removed, quote state carried throughout.

    ONE character stream, not a line at a time. That distinction is the whole
    of round 5: a quoted argument may legitimately span physical lines --

        gh pr merge 1 -R o/r --body "first line
        second line #still inside the quote --match-head-commit <sha>" --squash

    -- and a per-line scanner starts each line with `quote = None`, so it reads
    that second `#` as opening a comment, truncates the line, and discards the
    pin flag that follows it. Silent under-detection, on the surface this guard
    exists for. Scanning the whole string carries the open quote across the
    newline, where it belongs.

    Why a scanner rather than a regex at all: quoting is context-sensitive --
    whether a character is quoted depends on unbounded text to its left -- so
    no regex over the text can decide it. Three earlier attempts each passed
    their own tests and failed the next shape:

      - `#.*$` per line read `--body "Closes #123"` as a comment and dropped
        everything after it.
      - Blanking quoted regions first mis-paired delimiters: a contraction
        (`don't`) paired with the opening quote of an unrelated quoted region
        later in the line and swallowed a real `#` between them.
      - A per-line scanner fixed both and still could not see across a
        newline.

    On an UNBALANCED quote it follows `sh`: the string runs on, so no later
    `#` is a comment. That errs toward scanning too much rather than too
    little, which is the safe direction -- a spurious warning costs a glance,
    a missed pin costs the thing this guard is for.

    Self-contained on purpose: an earlier version delegated to a sibling and
    silently reverted to the bug whenever that import failed.
    """
    out = []
    quote = None
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if quote is None:
            if c == "\\":
                out.append(command[i:i + 2])
                i += 2
                continue
            if c in ('"', "'"):
                quote = c
            elif c == "#" and (i == 0 or command[i - 1].isspace()):
                # Drop to end of line, keeping the newline so line structure
                # (and any following command) survives.
                j = command.find("\n", i)
                if j == -1:
                    break
                i = j
                continue
        elif c == quote:
            quote = None
        elif c == "\\" and quote == '"':
            # Backslash escapes inside double quotes only; inside single
            # quotes `sh` treats it literally and nothing escapes the closer.
            out.append(command[i:i + 2])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _shell_words(command):
    """`command` split into shell words, quote characters consumed.

    The pin flags must be matched against WORDS, not against raw text, and the
    difference is a real false positive rather than a nicety. Scanning raw text
    cannot tell

        gh pr merge 1 -R o/r --match-head-commit <sha>

    from a command whose `--body` argument merely QUOTES that shape as prose:

        gh issue create -R o/r --body "a sweep padded it out via
                                       -f expected_head_sha=<sha> and it failed"

    The second pins nothing -- it files a bug report -- and this corpus writes
    exactly that prose constantly, including in the issue this hook implements.
    Split into words, the body is ONE word that merely contains the flag text,
    while a real pin flag BEGINS its word, so anchoring the match at word start
    separates them with no heuristic.

    Quote characters are consumed, so `--match-head-commit "<sha>"` yields the
    bare sha as its own word, and `-f 'expected_head_sha=<sha>'` yields one word
    beginning with the flag -- both still match, which is why this is a
    precision fix rather than a narrowing one.

    Line continuations (`\\<newline>` or `\\<return><newline>`) are spliced away
    outside quotes and inside double quotes, matching `sh` semantics, so a flag
    and its value separated across physical lines by a backslash continuation
    become adjacent words. Inside single quotes, `sh` preserves backslash and
    newline literally, so they are not spliced there.
    """
    words = []
    cur = []
    quote = None
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if quote is None:
            if c == "\\":
                if i + 1 < n and command[i + 1] == "\n":
                    i += 2
                    continue
                if i + 2 < n and command[i + 1:i + 3] == "\r\n":
                    i += 3
                    continue
                cur.append(command[i + 1:i + 2])
                i += 2
                continue
            if c in ('"', "'"):
                quote = c
            elif c.isspace() or c in SHELL_OPERATORS:
                # A shell metacharacter ends a word whether or not whitespace
                # surrounds it, so `<sha>&&echo done` is three words to `sh`
                # and must be three here. Splitting on whitespace alone glues
                # the operator onto the value, `RX_BARE_SHA`'s whole-word
                # anchor then rejects it, and the pin is SKIPPED -- which this
                # module's own docstring calls the one outcome a guard must
                # not have. Found by review of the word-splitting round.
                if cur:
                    words.append("".join(cur))
                    cur = []
            else:
                cur.append(c)
        elif c == quote:
            quote = None
        elif c == "\\" and quote == '"':
            if i + 1 < n and command[i + 1] == "\n":
                i += 2
                continue
            if i + 2 < n and command[i + 1:i + 3] == "\r\n":
                i += 3
                continue
            cur.append(command[i + 1:i + 2])
            i += 2
            continue
        else:
            cur.append(c)
        i += 1
    if cur:
        words.append("".join(cur))
    return words


def _longest_observed_prefix(token, seen):
    """The longest observed hex run that is a strict prefix of `token`, else None.

    This is what separates "padded an abbreviation" from "invented outright".
    `_measured` asks whether an observed run *starts with* the token (a short
    citation of a long known SHA, which is fine); this asks the mirror question,
    whether the token starts with an observed run (a long value built out of a
    short known one, which is the fabrication).
    """
    token = token.lower()
    best = None
    for obs in seen:
        if len(obs) < len(token) and token.startswith(obs) and len(obs) >= 7:
            if best is None or len(obs) > len(best):
                best = obs
    return best


def unmeasured_pin(command, transcript_path, assume_unmeasured=False):
    """(flag, token, padded_prefix) for an unmeasured pinning SHA, else None.

    Deliberately not routed through `unmeasured_digest`: that applies
    digest-shaping heuristics (canonical lengths, a nearby keyword, a URL
    exemption) which exist to keep an ordinary prose body from warning on every
    hex run. None of that judgment is wanted here. The flag name already
    establishes that the value is a commit SHA, so the only question left is
    whether the session ever saw it.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    pins = _pins_in(_shell_words(_executable_text(command)))
    if not pins:
        return None
    seen = _transcript_hex(transcript_path)
    if seen is None:
        if not assume_unmeasured:
            # Live invocation with no readable transcript: no evidence either
            # way, so fail open rather than warn on every pinned command.
            return None
        seen = set()
    # Every pin in the command, not just the first. A chained call can carry
    # two, and a measured one first must not mask a fabricated one after it.
    for flag, token in pins:
        if _measured(token, seen):
            continue
        return flag, token, _longest_observed_prefix(token, seen)
    return None


def _pins_in(words):
    """[(flag, sha)] for every pinning argument among `words`.

    Anchored at word start, which is the whole of the prose exemption: a real
    pin flag BEGINS its word, while a `--body` argument quoting one is a single
    word that merely contains it.

    Two spellings, because both occur: the value attached to the flag
    (`expected_head_sha=<sha>`, `--match-head-commit=<sha>`) and the value as
    the following word (`--match-head-commit <sha>`).
    """
    found = []
    for idx, word in enumerate(words):
        m = RX_PIN_WORD.match(word)
        if not m:
            continue
        flag, attached = m.group(1), m.group(2)
        if attached:
            found.append((flag, attached))
            continue
        # Value as the next word. Only a bare flag takes one, and only a
        # hex-shaped next word is its value -- anything else means the flag
        # was named without a value (a `--help` listing, a quoted mention).
        if idx + 1 < len(words) and RX_BARE_SHA.match(words[idx + 1]):
            found.append((flag, words[idx + 1]))
    return found


def _pin_command(tool_name, tool_input):
    """The shell command for a Bash tool call, or the serialized MCP pin args."""
    bash_names = getattr(_stamp, "BASH_TOOL_NAMES", {"Bash"})
    if tool_name in bash_names:
        cmd = tool_input.get("command")
        return cmd if isinstance(cmd, str) else None
    # The MCP merge/update tools carry the pin as a named parameter rather than
    # in a command string; serializing the input lets one regex cover both.
    if isinstance(tool_name, str) and tool_name.startswith("mcp__"):
        for key in ("expectedHeadSha", "expected_head_sha"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return "{}={}".format(key, val)
    return None


def _create_post(tool_name, tool_input, cwd):
    """(kind, body, surface) for an issue/PR CREATE or EDIT the sibling misses."""
    if _extract_body_text is None:
        return None, None, None
    bash_names = getattr(_stamp, "BASH_TOOL_NAMES", {"Bash"})
    if tool_name not in bash_names:
        return None, None, None
    command = (tool_input.get("command") or tool_input.get("CommandLine")
               or tool_input.get("cmd") or tool_input.get("script"))
    if not isinstance(command, str) or not RX_CREATE_POST.search(command):
        return None, None, None
    body = _resolve_body(command, cwd)
    if not isinstance(body, str) or not body.strip():
        return None, None, None
    noun = "issue" if re.search(r"\bissue\b", command, re.I) else "pull request"
    return "body", body, f"{noun} body"


def _resolve_body(command, cwd):
    """The body this create/edit would post, from whichever form carries it.

    Four forms, tried in order, because the measured case defeated the first
    one on its own. `flag-uncited-rebuttal.py`'s `extract_body_text` assumes
    "the file is always written before the `gh` call -- so it already exists by
    the time this hook runs". That is false for this corpus's own documented
    convention for a backtick-safe body:

        SC=/tmp/scratch
        cat > "$SC/issue.md" <<'EOF'
        ... body ...
        EOF
        gh issue create --body-file "$SC/issue.md"

    The path keeps an unexpanded `$SC`, and the heredoc that writes it is in
    the SAME Bash call, so at PreToolUse time no file exists under any
    resolution. Reading the heredoc body straight out of the command text is
    what reaches it -- and that shape is the common case here, not a corner.
    """
    for get in (lambda: _extract_body_text(command, cwd),
                lambda: _short_flag_body(command, cwd) if _short_flag_body else None):
        try:
            body = get()
        except Exception:
            body = None
        if isinstance(body, str) and body.strip():
            return body
    m = RX_GLAB_DESCRIPTION.search(command)
    if m:
        got = m.group(1) if m.group(1) is not None else m.group(2)
        if got and got.strip():
            return got
    if _extract_heredoc_bodies:
        try:
            joined = "\n".join(_extract_heredoc_bodies(command))
        except Exception:
            joined = ""
        if joined.strip():
            return joined
    return None


def _read_payload():
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def _pin_context(pin_hit):
    """(context, one_line_summary) for a pin hit."""
    flag, token, prefix = pin_hit
    padded = PADDED_NOTE.format(prefix=prefix) if prefix else ""
    context = PIN_NOTE.format(flag=flag, token=token, padded=padded)
    summary = (
        f"Unmeasured-pin reminder: `{flag}` is pinned to `{token}`, which "
        f"never appeared in this session's transcript. Re-read it with "
        f"`gh pr view <N> --json headRefOid --jq .headRefOid`.")
    return context, summary


def _emit_pin(pin_hit):
    """Print the pin warning on its own.

    Deliberately NO fire-once sentinel, unlike the body path below. A quoted
    digest can legitimately come from outside the session, so re-warning about
    the same body is noise; a pinning SHA cannot, so a value unmeasured on one
    attempt is still unmeasured on a retry, and the retry is exactly when the
    reminder is wanted.
    """
    context, summary = _pin_context(pin_hit)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = summary
    print(json.dumps(out))


def main() -> int:
    try:
        payload, is_dry_run = _read_payload()
        if not payload:
            return 0

        tool_name = payload.get("tool_name") or payload.get("toolName") or ""
        ti = payload.get("tool_input")
        if not isinstance(ti, dict):
            ti = payload.get("toolInput")
        tool_input = ti if isinstance(ti, dict) else {}
        cwd = payload.get("cwd") or os.getcwd()
        tpath = payload.get("transcript_path") or payload.get("transcriptPath") or ""

        # The pin surface is evaluated BEFORE the `_post_from_payload is None`
        # gate below, because it does not depend on the sibling's body
        # extraction -- only on `BASH_TOOL_NAMES`, which has its own fallback.
        # Ordering it after that gate would have made the fallback dead code
        # and silently disabled this whole surface whenever the sibling import
        # failed.
        pin_hit = None
        pin_cmd = _pin_command(tool_name, tool_input)
        if pin_cmd:
            pin_hit = unmeasured_pin(pin_cmd, tpath, assume_unmeasured=is_dry_run)

        if _post_from_payload is None:
            if pin_hit:
                _emit_pin(pin_hit)
            return 0

        kind, body, surface, _is_notebook = _post_from_payload(tool_name, tool_input, cwd)
        if kind != "body" or not body:
            kind, body, surface = _create_post(tool_name, tool_input, cwd)
        if kind != "body" or not body:
            if pin_hit:
                _emit_pin(pin_hit)
            return 0

        found = unmeasured_digest(body, tpath, assume_unmeasured=is_dry_run)
        if not found:
            if pin_hit:
                _emit_pin(pin_hit)
            elif is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0
        token, kind_desc = found

        # One warning per distinct (transcript, body, token), so a retried or
        # re-rendered call does not warn twice about the same value.
        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + body + "|" + token).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-unmeasured-digest-{key}")
            if os.path.exists(sentinel):
                # The body warning is spent for this value, but the pin
                # warning has no sentinel and is still owed.
                if pin_hit:
                    _emit_pin(pin_hit)
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        surface_desc = surface or "comment body"
        context = NOTE.format(surface=surface_desc, token=token, kind=kind_desc)
        summary = (
            f"Unmeasured-digest reminder: this {surface_desc} states "
            f"`{token}`, which never appeared in this session's transcript. "
            f"Run the command that produces it and paste what it returned.")
        # A command can both pin a SHA and post a body -- `gh pr merge` takes
        # `--match-head-commit` and `--body` together, and a chained call can
        # do both. They are independent findings with different remedies, so
        # neither is allowed to suppress the other.
        if pin_hit:
            pin_ctx, pin_summary = _pin_context(pin_hit)
            context = pin_ctx + "\n\n----\n\n" + context
            summary = pin_summary + " (A separate unmeasured digest is also "
            summary += "flagged in this command's body.)"
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = summary
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
