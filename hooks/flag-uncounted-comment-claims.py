#!/usr/bin/env python3
"""PreToolUse reminder: an outgoing forge-comment body asserts a count or an
enumerated list, with no deriving command anywhere nearby.

`hooks/remind-brief-premises.py` already carries this exact heuristic --
`shared/workflow/challenge-the-assignment.md`'s point that a claim which
merely INSTRUCTS ("here is what I found") reads with the sender's authority
rather than with evidence behind it -- but only on Agent/Task/SendMessage
BRIEFS. A forge comment is the same shape of artifact, posted to a wider
audience, and it went uncovered.

THE INCIDENT (Morrison-Lab/ai-config#2377)
-------------------------------------------
2026-08-26, a sparta ARDIA session. `remind-brief-premises.py` correctly
flagged an unverified "[cardinality] two comments ..." claim inside an Agent
brief. The SAME session then posted TWO forge comments
(`gh pr comment --body-file`) each asserting an enumerated file list recalled
from memory rather than derived. One was wrong: it claimed the fingerprinted
scripts were `cycle-charge-flee` / `interval-labels` /
`multi-unit-form-up-modes` / `group-attack`, when the derived truth was
`brace-vs-unbraced-charge` / `defensive-doctrine-plan` / `interval-labels` /
`reserve-trailing-advance` (and 18 files on `main`). It needed a public
correction comment on sparta#1401.

The pattern/anti-pattern pair this hook exists to enforce, quoted from the
issue: Do paste the deriving command (or its output count) beside any
enumerated claim in a comment body; Don't restate a population from working
memory because a related list was just read -- both slips happened minutes
after reading adjacent-but-different lists.

WHY A SEPARATE HOOK RATHER THAN WIDENING remind-brief-premises.py's OWN MATCH
-------------------------------------------------------------------------
That hook's `PATH` clause is anchored to THIS corpus's own tracked
directories (`shared/`, `memories/`, `skills/`, `hooks/`, `scripts/`,
`codex-skills/`, `CLAUDE.md`, `MEMORY.md`) -- correct for an Agent brief,
which is almost always about ai-config's own corpus state. A forge comment
fires in EVERY repo a session works in, and the incident itself was about
sparta's OWN game-script files, which carry none of those prefixes. So the
claim detector below is deliberately corpus-agnostic: a COUNT plus a
LISTABLE_NOUN, or a listable noun followed by a hand-typed list of
identifier-shaped tokens -- no path anchor at all. The trade is precision:
`remind-brief-premises.py` can key its discharge to the SPECIFIC path a claim
names; this hook cannot, so its discharge (below) is scoped differently on
purpose.

The command-detection and body-extraction machinery is NOT reinvented here.
`flag-uncited-rebuttal.py`'s `parse_comment_post()` already reads a
`gh pr comment` / `gh issue comment` / `gh api .../comments` body from
disk when it is file-based (`--body-file`, `-F body=@file`) or from the
command text when it is a literal (`--body`, `-f body=...`), per this
corpus's own "PowerShell CLI Command Safety" convention that the file is
always written before the `gh` call -- so it already exists by the time this
hook runs. Importing it (per the `_sibling()` pattern `remind-ums-on-scrutiny.py`
and `no-empty-promise.py` already use for a hyphenated module) is what
"the hook can read `--body-file`'s content" in the issue means in practice;
writing a second parser for the same six body-argument shapes would drift
from that one exactly the way `require-agent-disclosure.py`'s own docstring
warns four separate flags did before they were centralised.

WHAT COUNTS AS A CLAIM
-----------------------
Two shapes, deliberately narrower than a bare number-plus-noun anywhere in
the comment, because a forge comment says "found 2 issues" or "three commits"
constantly for things that need no re-deriving (this hook fires on EVERY
outgoing comment in EVERY repo, a far larger and more varied population than
Agent briefs):

  * CARDINALITY -- a COUNT (digit run or a number word) followed, within a
    small gap, by a plural noun drawn from LISTABLE_NOUN -- a curated
    vocabulary of countable, listable ARTIFACTS (files, scripts, lines,
    tests, comments, mentions, sites, findings, PRs, commits, hooks, ...).
    The noun carries the precision burden that `remind-brief-premises.py`'s
    PATH clause carries there: an unscoped "any plural noun" would fire on
    "three days" or "two people" just as readily as "18 files".
  * ENUMERATION -- a LISTABLE_NOUN followed shortly by a hand-typed list of
    two or more IDENTIFIER-shaped tokens (a letter, then at least one
    hyphen/underscore/dot-separated segment) joined by `/` or `,`. This is
    the shape the incident's wrong list took --
    "`cycle-charge-flee` / `interval-labels` / ..." -- and it fires even with
    no explicit numeral in front. The hyphen/underscore/dot requirement is
    what keeps this off ordinary prose lists this corpus posts constantly
    ("Addressed, Rebutted, or Deferred" has no such token in it).

DISCHARGE
---------
Two tiers, both requiring the derivation to be CAUSALLY near this exact
post -- never a whole-session scan.

  1. A counting/listing-shaped command (`grep -c`, `rg --count`, `wc -l`,
     `find ... | wc -l`, `jq ... | length`, or any `grep`/`rg`/`find`/`jq`
     invocation) sitting in a CODE SPAN inside the comment body itself --
     the "paste the deriving command beside the claim" the issue asks for.
  2. The same shape in another SEGMENT of the same Bash call (the
     `N=$(gh api .../comments | jq length); gh pr comment ... --body "..."`
     idiom) -- checked over the command text with the extracted body
     substring removed, so a body that merely MENTIONS the word "grep" in
     prose cannot discharge itself by accident.

A CARDINALITY claim needs a COUNTING command specifically (`grep -c`,
`wc -l`, ...); an ENUMERATION claim is satisfied by any inspecting one
(`grep`, `find`, ...) -- listing files IS deriving the list, the same
asymmetry `remind-brief-premises.py` draws between its "cardinality" and
"content" claim kinds ("listing lines is not counting them" runs the other
way here: listing files *is* deriving an enumeration).

WHY NO TRANSCRIPT-WIDE (WHOLE-SESSION) DISCHARGE
--------------------------------------------------
`remind-brief-premises.py` also discharges a claim from an EARLIER
`grep`/`Read` anywhere in the session transcript, keyed to the SAME path. A
population-agnostic version of that check -- "was ANY counting command run
earlier this session" -- has no path key to scope it, and a real ARDI/PR-
babysitting session runs `grep`/`wc -l`/`find` constantly for unrelated
reasons across dozens of turns. Adding that tier would discharge nearly every
real comment in a live session, which is exactly the over-broad-discharge
failure `remind-brief-premises.py`'s own docstring names -- "silence is
indistinguishable from compliance". So this hook deliberately stops at the
two CAUSALLY-SCOPED tiers above and accepts the narrower coverage.

SCOPE: Bash ONLY, not MCP
--------------------------
`require-agent-disclosure.py` covers both the Bash CLI forms and the
`mcp__github__*` comment tools, because a remote/web session has no `gh` at
all. This hook covers Bash only, per the issue's stated trigger surface
("PreToolUse Bash commands matching gh pr comment / gh issue comment /
gh api ...comments"). Extending it to the MCP tools is a real gap for a
remote session and is left for a follow-up rather than folded in here.

WHY THIS INJECTS RATHER THAN BLOCKS
-------------------------------------
Same posture as every sibling in this file's family
(`remind-brief-premises.py`, `flag-uncited-rebuttal.py`,
`require-agent-disclosure.py`): a missed claim is cheap to correct with a
follow-up comment, while a blocked `gh pr comment` interrupts the one action
that makes work visible to other sessions. Emits only `additionalContext`
and a `systemMessage`; no `permissionDecision`.

Fires once per distinct (command, claim-set) per session, via the same
transcript-path-keyed `/tmp` sentinel `remind-brief-premises.py` uses, so a
retried identical command does not nag twice.

Fails OPEN and SILENT: any parse trouble prints nothing at all.

See `hooks/test-flag-uncounted-comment-claims.py` for the fixtures.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    Same pattern `remind-ums-on-scrutiny.py` and `no-empty-promise.py` use.
    Fails open: if a sibling hook is ever renamed or moved, this hook goes
    silent rather than raising, per the file-wide fail-open contract.
    """
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_premises = _sibling("remind-brief-premises.py", "_sib_comment_cardinality_premises")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_comment_cardinality_rebuttal")

# Reused verbatim -- all four are already corpus-agnostic in
# remind-brief-premises.py (they operate on arbitrary text, not on the PATH
# clause), so nothing here re-derives them.
COUNT = getattr(
    _premises, "COUNT",
    r"\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero|no",
)
NOT_PLURAL = getattr(_premises, "NOT_PLURAL", {
    "is", "was", "has", "does", "goes", "this", "its", "us", "thus",
    "less", "plus", "yes", "as", "hers", "theirs", "whose",
})
NOT_A_NOUN = getattr(_premises, "NOT_A_NOUN", re.compile(r"[_./\d]"))
DERIVE_ANY = getattr(
    _premises, "DERIVE_ANY",
    re.compile(
        r"\b(?:git\s+)?(?:grep|rg|ag|ack)(?![-\w])|\bsed\s+-n\b|\bwc\s+-"
        r"|\bjq(?![-\w])|\|\s*length\b",
    ),
)
DERIVE_COUNT = getattr(
    _premises, "DERIVE_COUNT",
    re.compile(
        r"\b(?:git\s+)?(?:grep|rg|ag)(?![-\w])\s+(?:-[a-z]*c[a-z]*\b|--count\b)"
        r"|\bwc\s+-[a-z]*l\b|\|\s*wc\b|\|\s*length\b|\bcount\s*\(",
    ),
)
visible_prose = getattr(_premises, "visible_prose", lambda t: t)
code_segments = getattr(_premises, "code_segments", lambda t: [])

# The one piece of real reuse this hook exists to do: reading a comment's
# body off disk (`--body-file`, `-F body=@file`) or out of the command text
# (`--body`, `-f body=...`) for `gh pr comment` / `gh issue comment` /
# `gh api .../comments` and `.../comments/N/replies`. See the module
# docstring's "not reinvented here" section.
parse_comment_post = getattr(_rebuttal, "parse_comment_post", None)

# ---------------------------------------------------------------- vocabulary
# Countable, listable ARTIFACTS -- the noun carries the precision burden a
# path anchor carries in remind-brief-premises.py. Deliberately excludes
# generic measure words (minutes, dollars, times, people, days) that would
# fire on ordinary cardinality prose no forge comment needs to re-derive.
LISTABLE_NOUN_PATTERN = (
    r"files?|scripts?|lines?|tests?|comments?|mentions?|sites?"
    r"|occurrences?|references?|instances?|entries?|findings?"
    r"|issues?|prs?|pulls?|commits?|threads?|checks?|workflows?"
    r"|functions?|methods?|classes?|modules?|examples?|cases?"
    r"|items?|rows?|columns?|records?|changes?|edits?|fixes?"
    r"|bugs?|errors?|warnings?|hooks?|skills?|memories?|branches?"
    r"|repos?|repositories?|places?|spots?|locations?|callers?"
    r"|usages?|matches?|hits?|results?|rounds?|regressions?"
)
LISTABLE_NOUN_RE = re.compile(r"(?:" + LISTABLE_NOUN_PATTERN + r")", re.I)

# An identifier- or filename-shaped token: a letter, then at least one
# hyphen/underscore/dot-separated segment. Requiring that separator is what
# keeps this off an ordinary word list ("Addressed, Rebutted, or Deferred"
# has no such token), while still matching `cycle-charge-flee`, `foo.gd`,
# `some_script`.
TOKEN = r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+"

# CARDINALITY: `\bCOUNT (gap words) PLURAL_LISTABLE_NOUN\b`. The 0-2 word gap
# mirrors remind-brief-premises.py's `plural_after` window.
CARDINALITY_RE = re.compile(
    rf"\b({COUNT})\s+(?:[\w./-]+\s+){{0,2}}?([A-Za-z][\w./-]*)\b", re.I,
)

# ENUMERATION: a listable noun, an optional short gap (never crossing a
# sentence boundary) and optional colon, then >=2 TOKENs joined by `/` or `,`.
ENUM_RE = re.compile(
    rf"\b(?:{LISTABLE_NOUN_PATTERN})\b[^\n.:]{{0,24}}?:?\s*"
    rf"({TOKEN}(?:\s*(?:,|/)\s*{TOKEN}){{1,}})",
    re.I,
)


def find_claims(body_text):
    """[(kind, quote)] for every cardinality/enumeration claim in body_text.

    Scans `visible_prose(body_text)` -- fences and blockquotes dropped,
    inline code unwrapped -- so a code span cannot itself supply a claim's
    noun (matching remind-brief-premises.py's NOT_A_NOUN reasoning) while an
    identifier a poster wrote in backticks (the common case for a file list)
    still reads as plain text.
    """
    prose = visible_prose(body_text)
    found, seen = [], set()

    for m in CARDINALITY_RE.finditer(prose):
        noun = m.group(2)
        low = noun.lower()
        if not low.endswith("s"):
            continue
        if low in NOT_PLURAL or NOT_A_NOUN.search(noun):
            continue
        if not LISTABLE_NOUN_RE.fullmatch(low):
            continue
        quote = " ".join(m.group(0).split())
        key = ("cardinality", quote.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(("cardinality", quote))

    for m in ENUM_RE.finditer(prose):
        quote = " ".join(m.group(0).split())
        key = ("enumeration", quote.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(("enumeration", quote))

    return found


def _derived_in_body(body_text, need_count):
    """A counting/listing command sits in one of body_text's own code spans."""
    for _n, seg in code_segments(body_text):
        if DERIVE_COUNT.search(seg):
            return True
        if not need_count and DERIVE_ANY.search(seg):
            return True
    return False


def _derived_in_other_segments(command, body_text, need_count):
    """A counting/listing command sits elsewhere in the same Bash call.

    The extracted body substring is removed first, so a body that merely
    MENTIONS "grep" in ordinary prose cannot discharge itself -- this must
    be shell text the command would actually run, not text the command
    would merely post.
    """
    if body_text and body_text in command:
        outside = command.replace(body_text, "", 1)
    else:
        outside = command
    if need_count:
        return bool(DERIVE_COUNT.search(outside))
    return bool(DERIVE_ANY.search(outside))


def evaluate(command, cwd, tpath=""):
    """Return the undischarged claims as [(kind, quote)].

    Split out of `main` so the test suite can exercise it directly, per
    `shared/workflow/algorithmatize-checks.md`'s test-one-clause-at-a-time
    guidance that the sibling hooks in this file already follow.
    """
    if parse_comment_post is None:
        return []
    try:
        parsed = parse_comment_post(command, cwd)
    except Exception:
        return []
    if not parsed:
        return []
    _owner, _repo, _number, body_text = parsed
    if not body_text or not body_text.strip():
        return []

    found = find_claims(body_text)
    if not found:
        return []

    undischarged = []
    for kind, quote in found:
        need_count = kind == "cardinality"
        if _derived_in_body(body_text, need_count):
            continue
        if _derived_in_other_segments(command, body_text, need_count):
            continue
        undischarged.append((kind, quote))
    return undischarged


NOTE = (
    "This forge-comment body asserts a count or an enumerated list, and a "
    "posted comment is where an unverified population survives best -- once "
    "it is on the record, a reader treats it as checked rather than as "
    "recalled from memory.\n\n"
    "Unverified claim(s):\n{claims}\n\n"
    "Either paste the deriving command beside the claim in the comment "
    "body, or run one before posting. A count needs a counting command "
    "(`grep -c`, `wc -l`, `find ... | wc -l`); listing files is enough for "
    "an enumerated list, but not for a count.\n\n"
    "If you already derived these (a command run earlier in this same Bash "
    "call, or already pasted in the body), this is a false positive -- post "
    "anyway."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    cwd = payload.get("cwd") or os.getcwd()

    try:
        tpath = payload.get("transcript_path") or ""
        undischarged = evaluate(command, cwd, tpath)
        if not undischarged:
            return 0

        key = hashlib.sha256(
            (tpath + "|" + command + "|"
             + "|".join(q for _, q in undischarged)).encode()
        ).hexdigest()[:16]
        sentinel = os.path.join(
            tempfile.gettempdir(), f".claude-comment-cardinality-{key}"
        )
        if os.path.exists(sentinel):
            return 0
        try:
            open(sentinel, "w").close()
        except Exception:
            pass

        listed = "\n".join(
            f'  - [{k}] "{q}"' for k, q in undischarged[:3]
        )
        if len(undischarged) > 3:
            listed += f"\n  - ... and {len(undischarged) - 3} more"

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": NOTE.format(claims=listed),
            },
            "systemMessage": (
                f"Forge comment asserts a count/enumeration ({len(undischarged)} "
                "unverified claim(s)); paste the deriving command or verify "
                "first."
            ),
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
