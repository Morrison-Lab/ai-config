#!/usr/bin/env python3
"""PreToolUse guard: a checksum or commit SHA typed into a forge body needs a reading.

A digest is a *measured* value, exactly as a clock time is. It cannot be
recalled, inferred, or approximated -- it is either read out of a command's
output or it is invented. `flag-unmeasured-timestamp.py` is this guard's
sibling and its model: same shape, same surfaces, same fail-open contract, a
different class of unmeasurable value.

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
    the outgoing body (a forge comment / issue / PR body, or an edit to a
        tracked file) contains a digest-shaped token, meaning a run of 7 to 64
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

It also does not fire on a hex token the session read in *this* turn and is
now quoting, which is the overwhelmingly common case and the one a noisier
guard would make unbearable.

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


RX_HEX = re.compile(r"(?<![0-9a-zA-Z])([0-9a-fA-F]{%d,%d})(\.{3}|…)?" % (MIN_HEX, MAX_HEX))

RX_DIGEST_WORD = re.compile(
    r"(?:md5|sha-?1|sha-?256|sha-?512|sha|hashe?[sd]?|digest|checksum|blob|oid|commit)",
    re.I,
)

# A hex run inside a URL path is almost always a link to something real (a
# commit page, a gist, a raw blob), and the session may never have printed it.
RX_URLISH = re.compile(r"[a-z]+://\S*$", re.I)

NOTE = (
    "Unmeasured-digest reminder: this {surface} states `{token}`, which is "
    "shaped like a {kind} and does not appear in any tool result or user "
    "message in this session's transcript.\n\n"
    "A digest is a measured value -- it is read out of a command's output or "
    "it is invented, and the two are indistinguishable once written. Run the "
    "command that produces it (`md5 <file>`, `shasum -a 256 <file>`, "
    "`git rev-parse <ref>`) and paste what it returned.\n\n"
    "If the value legitimately comes from outside this session -- an upstream "
    "advisory, a lockfile, a vendor release page -- say where, and carry on. "
    "This is a reminder, not a refusal."
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
    before = body[max(0, start - KEYWORD_WINDOW):start]
    if RX_URLISH.search(before):
        return False, None
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
                # Tool results and user turns are the two places a real value
                # can enter the session from outside the model.
                if role not in ("user", "tool_result", "toolResult"):
                    continue
                seen |= hex_tokens_in(json.dumps(rec.get("message", rec)))
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


def unmeasured_digest(body, transcript_path):
    """(token, kind) for the first unmeasured digest-shaped token, else None."""
    if not isinstance(body, str) or not body.strip():
        return None
    seen = _transcript_hex(transcript_path)
    if seen is None:
        # No readable transcript means no evidence either way. Fail open
        # rather than warn on every digest in a session we cannot inspect.
        return None
    for m in RX_HEX.finditer(body):
        is_digest, kind = _is_digest_shaped(body, m)
        if not is_digest:
            continue
        token = m.group(1)
        if _measured(token, seen):
            continue
        return token, kind
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
    body = _extract_body_text(command, cwd)
    if not isinstance(body, str) or not body.strip():
        return None, None, None
    noun = "issue" if re.search(r"\bissue\b", command, re.I) else "pull request"
    return "body", body, f"{noun} body"


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


def main() -> int:
    try:
        payload, is_dry_run = _read_payload()
        if not payload or _post_from_payload is None:
            return 0

        tool_name = payload.get("tool_name") or payload.get("toolName") or ""
        tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
        cwd = payload.get("cwd") or os.getcwd()
        tpath = payload.get("transcript_path") or payload.get("transcriptPath") or ""

        kind, body, surface, _is_notebook = _post_from_payload(tool_name, tool_input, cwd)
        if kind != "body" or not body:
            kind, body, surface = _create_post(tool_name, tool_input, cwd)
        if kind != "body" or not body:
            return 0

        found = unmeasured_digest(body, tpath)
        if not found:
            if is_dry_run:
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
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        surface_desc = surface or "comment body"
        context = NOTE.format(surface=surface_desc, token=token, kind=kind_desc)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Unmeasured-digest reminder: this {surface_desc} states "
                f"`{token}`, which never appeared in this session's transcript. "
                f"Run the command that produces it and paste what it returned.")
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
