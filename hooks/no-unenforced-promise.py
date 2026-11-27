#!/usr/bin/env python3
"""PreToolUse guard: a standing promise sent to a person must name the hook that keeps it.

Ezra, 2026-11-26 23:01 PST, "why haven't you written a check": that evening
the coordinator told him "From now on, I'll check every PR for conflicts" and
"Until the hook lands, I'll get the conflict check from a thread". Nothing
enforced either sentence, and the hook was still only queued.
no-empty-promise.py was already registered, and neither message was stopped:
it runs at Stop, after a hearthbot post has reached the person, and a memory
write discharges it, which is what the coordinator had done.

A standing commitment about one's own future behaviour is kept only by a
mechanism that runs without the agent remembering, so a commitment that names
no such mechanism is a promise nothing keeps. The condition is decidable from
the outgoing text and the plugin's own files:

    a paragraph of the message makes a standing first-person commitment
    AND that paragraph names no hook, script or workflow file that exists
        in ai-config (hooks/, scripts/, .github/workflows/) or in the
        current repository (tools/, scripts/, hooks/, .github/workflows/)

Standing commitments are:

  * a future marker ("from now on", "going forward", "moving forward",
    "henceforth", "from here on", "in future", "hereafter") in a sentence
    with a first-person modal (I'll, I will, I'm going to, I won't, we'll);
  * a first-person "always", "never", "make sure", "be sure to",
    "remember to" or "make a point of" ("I'll always read the PR first");
  * a stopgap ("until the hook lands, I'll ...", "until X merges, we'll ...").

The named mechanism must already exist on disk, so "going forward I'll check,
and I'll add hooks/x.py" is still refused. A file that exists in the plugin
copy has merged into ai-config main (the copy is the marketplace plugin).
A gha check cannot be verified from here; the honest form is to state what
the check does ("gha's check-x fails a PR that ..."), which is not a promise
and does not match.

Text in code spans, in double or curly quotes and on blockquote lines is a
quotation, so promise wording there is skipped; a mechanism named inside
backticks still counts. Runs on every outgoing hearthbot text tool
(post_message, reply, update_message, edit_message, message_thread,
message_coordinator), because a promise relayed to the coordinator reaches
the person in the coordinator's summary.

There is no resend escape and no override variable: the way past is to build
the mechanism first and name it, or to state the fact without the promise.
Fails OPEN on any parse trouble.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from sibling import load_sibling

    _offer = load_sibling(__file__, "no-offer-to-file.py", "no_offer_to_file", required=True)
    sentence_around = _offer.sentence_around
    strip_code = _offer.strip_code
except Exception:
    sys.exit(0)

TOOL_RX = re.compile(
    r"^mcp__hearthbot__(reply|post_message|update_message|edit_message"
    r"|message_thread|message_coordinator)$"
)
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

_MODAL = (
    r"\b(I|we)(\s*['\u2019](ll|m going to|re going to)"
    r"| will| shall| am going to| are going to| won['\u2019]t| will not)\b"
)
FUTURE_RX = re.compile(
    r"\b(from now on|going forward|moving forward|henceforth|from here on"
    r"|in (the )?future|hereafter|from this point on)\b",
    re.I,
)
MODAL_RX = re.compile(_MODAL, re.I)
HABIT_RX = re.compile(
    # "I'll always be here to help" is a courtesy, not a work commitment
    # (review of ai-config#6159), so "always/never be" is left out.
    _MODAL + r"( now)? ((always|never)\b(?! be\b)|make sure|be sure to|remember to"
    r"|make a point of)",
    re.I,
)
STOPGAP_RX = re.compile(
    r"\buntil\b[^.!?\n]{0,80}?\b(lands?|merges?|ships?|is merged|is in place|is live"
    r"|goes in|exists)\b[^.!?\n]{0,40}?" + _MODAL,
    re.I,
)
# Quoted words are a report of someone's words, not this message's promise.
QUOTED_RX = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d|^[ \t]*>.*$', re.M)
NAME_RX = re.compile(r"[\w./-]*?([\w-]+\.(?:py|sh|ya?ml|R))\b|\b([a-z]+(?:-[a-z0-9]+){1,})\b")


def find_promise(prose):
    """The first standing-commitment phrase in `prose`, or None."""
    for m in FUTURE_RX.finditer(prose):
        if MODAL_RX.search(sentence_around(prose, m.start(), m.end())):
            return m.group(0)
    for rx in (HABIT_RX, STOPGAP_RX):
        m = rx.search(prose)
        if m:
            return m.group(0)
    return None


def _dirs():
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    out = [os.path.join(ROOT, d) for d in ("hooks", "scripts", os.path.join(".github", "workflows"))]
    out += [os.path.join(cwd, d) for d in ("tools", "scripts", "hooks",
                                          os.path.join(".github", "workflows"))]
    return out


def names_mechanism(paragraph):
    """True when `paragraph` names a hook, script or workflow that exists."""
    dirs = _dirs()
    for m in NAME_RX.finditer(paragraph):
        name = m.group(1) or m.group(2)
        candidates = [name] if m.group(1) else [name + ext for ext in (".py", ".sh", ".yml")]
        for d in dirs:
            if any(os.path.isfile(os.path.join(d, c)) for c in candidates):
                return True
    return False


def find_unenforced(text):
    """(phrase, paragraph) for the first promise whose paragraph names no mechanism."""
    for paragraph in re.split(r"\n\s*\n", text):
        prose = QUOTED_RX.sub(" ", strip_code(paragraph))
        phrase = find_promise(prose)
        if phrase and not names_mechanism(paragraph):
            return phrase, paragraph.strip()
    return None


MESSAGE = os.path.join(ROOT, "hooks", "messages", "no-unenforced-promise.md")
FALLBACK = ("[hook: no-unenforced-promise] This message makes a standing promise "
            "(\"{phrase}\") and names no existing hook or check that keeps it. "
            "Build the mechanism first and name it, or state the fact without the promise.")


def reason_for(phrase):
    try:
        with open(MESSAGE, encoding="utf-8") as fh:
            template = fh.read().strip()
    except Exception:
        template = FALLBACK
    return template.replace("{phrase}", phrase.strip())


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or not TOOL_RX.match(str(payload.get("tool_name") or "")):
        return 0
    inp = payload.get("tool_input")
    text = inp.get("text") if isinstance(inp, dict) else None
    if not isinstance(text, str) or not text.strip():
        return 0
    try:
        hit = find_unenforced(text)
    except Exception:
        return 0
    if not hit:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason_for(hit[0]),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
