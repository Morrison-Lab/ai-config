#!/usr/bin/env python3
"""PreToolUse reminder: an absolute claim that a capability is ABSENT, posted to a forge, needs a measurement.

A claim that something IS the case invites a check, because it names a thing
you could go look at. A claim that something CANNOT be done names nothing --
there is no artifact to open -- so it is produced by inference and reads as
having been established. `shared/workflow/verify-the-right-artifact.md` covers
the general substitution; this is the instrument for the one surface where the
claim becomes expensive: a durable, public forge write that a later reader will
act on and that has to be retracted in public when it turns out false.

THE MEASUREMENT (2026-09-17, ai-config#3707 / #3739)
-----------------------------------------------------
One session published two of these within an hour, both to GitHub, both
confidently, both false:

  "Foreground dispatch, the remedy the guard prints, is unavailable -- the
   harness backgrounds every `Agent` call regardless of `run_in_background:
   false`."

Measured afterwards: `run_in_background: false` runs synchronously in 16.3s.
The true statement was much narrower (the tool RESULT lacks the report either
way), and the absolute form sent a reader looking for a harness bug that does
not exist.

  "the provenance chain is unbuildable in this harness ... no key this guard
   could learn will authorize this session's push"

Measured afterwards: the linkage is present on a record the author had not
looked at (`origin.kind == "peer"`, carrying `senderTaskId`). The conclusion
"no fix is possible" was drawn from the wrong record, and it had been used to
justify a decision about what not to build.

Both were retracted in public comments on the same issue. Neither was a
careless sentence: each followed real measurement of an ADJACENT artifact,
which is exactly why re-reading them found nothing wrong.

WHY THIS WARNS RATHER THAN BLOCKS
---------------------------------
Whether a capability claim was measured is not decidable from its text. A
session that HAS exhaustively measured writes the identical sentence, and that
sentence is then the correct and valuable thing to publish -- see this very
repository's #3739, where the exhaustive version ("all four paths are
unreachable, here is each measurement") is the useful comment. Blocking would
suppress the good case to catch the bad one, and the two are lexically
identical. So this only ever adds context, and the question it asks -- did you
measure this, or infer it from something adjacent? -- is one the author can
answer in a second when it is asked at composition time.

It is deliberately NOT a Stop hook over the reply. A wrong claim in chat costs
a correction in the next message. The same claim in a forge comment outlives
the session, gets read by people who were not there, and needs a public
retraction -- so the forge write is the moment worth interrupting.

SCOPE
-----
Two factors must BOTH appear within one window: an absolute negative-capability
idiom, and a tooling/environment noun near it. "The fix is not in this PR" has
no absolute marker. "There is no way to know what the user meant" has no
tooling noun.

Requiring both narrows the field; it does not separate system claims from
ordinary prose, and an earlier draft of this paragraph claimed it did. Measured
2026-09-17 against this corpus's own `shared/**/*.md` in comment-sized
2000-character chunks: 81 of 1992 fire, 4.1%, down from 5.7% before the
branches below were trimmed. Sentences like "No changes will be needed to the
CI workflow" carry both factors while asserting nothing about a capability.

Three branches were narrowed for that reason, each measured as a top noise
source: `regardless of` (a scope qualifier) and bare `unreachable` (a
code-quality term in "unreachable branches") were dropped outright, and the
loose "no X can Y" branch no longer matches a following "be", which is what
"will be needed" and "will be required" turn on. The negated and prefixed
forms are also kept apart, so "is possible" cannot match through an optional
`un`.

4.1% is the honest figure for an advisory reminder rather than a verdict, and
it is the whole reason this warns rather than blocks.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable.

    The pattern `flag-unmeasured-timestamp.py` and `no-empty-promise.py` use.
    Fails open, per the file-wide contract.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            key, os.path.join(HERE, name))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_disclosure = _sibling("require-agent-disclosure.py", "_sib_capability_disclosure")
_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_capability_rebuttal")

# Forge-write surfaces. A chat reply is deliberately out of scope (see the
# docstring): the cost this guards against is durability, not wrongness.
#
# The canonical tuple lives in `require-agent-disclosure.py` and is taken as
# the BASE rather than copied, because a fourth hand-maintained copy is how a
# surface goes missing: the first revision of this file wrote its own list and
# silently dropped `discussion_comment_write`, which meets every durability
# criterion the docstring uses (ai-config#3737 round 8). Widening the shared
# tuple itself is ruled out at `flag-unread-commit-citation.py` -- a sibling
# imports it and the meaning of that import would change -- so the extras this
# hook needs are added here, where they affect nothing else.
_CANONICAL_POST_TOOLS = getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_comment_to_pending_review",
    "mcp__github__add_reply_to_pull_request_comment",
    "mcp__github__pull_request_review_write",
    "mcp__github__discussion_comment_write",
))
MCP_POST_TOOLS = tuple(dict.fromkeys(_CANONICAL_POST_TOOLS + (
    "mcp__github__issue_write",
    "mcp__github__update_pull_request",
    "mcp__github__create_pull_request",
)))
BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# The `gh` command shapes that post a durable body. Taken from the siblings
# that already parse them rather than written afresh: the first revision here
# reimplemented the test in two lines and reached none of `gh api
# .../comments`, `gh api .../replies` or `gh pr review --body`, all of which
# this corpus documents and uses (ai-config#3737 round 8).
_NEVER = re.compile(r"(?!)")
RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", _NEVER)
RX_REVIEW_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+pr\s+review\b",
    re.I | re.M,
)

# `glab`'s note forms, which no sibling carries. `skills/gi/SKILL.md` uses
# `glab issue note <N> --message`, `skills/ard/SKILL.md` uses `glab mr note
# <N> -F`, and `skills/claim-pr/SKILL.md` uses `glab mr note create <N>`.
# Position-anchored like the sibling, so prose quoting the command does not
# fire.
RX_GLAB_POST = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"glab\s+(?:issue|mr)\s+(?:note|comment)\b",
    re.I | re.M,
)

# `gh issue|pr create|edit`, which the sibling does not cover because a PR body
# is not a comment. Kept separate so each shape is readable.
RX_GH_CREATE_EDIT = re.compile(
    r"(?:^|[;&|\n])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"gh\s+(?:issue|pr)\s+(?:create|edit)\b",
    re.I | re.M,
)

# Factor 1: the claim is ABSOLUTE. Each idiom asserts that no instance exists,
# which no single observation can establish. Hedged forms ("appears to",
# "I could not get it to") are deliberately absent -- they invite the check
# already, which is the behaviour this exists to produce.
# The negated and the prefixed forms are SEPARATE branches on purpose. Folding
# them into one optional-`un` alternative matches the affirmative "is possible"
# as readily as "is impossible", which would fire on prose asserting that
# something CAN be done -- the exact opposite of this hook's subject.
RX_ABSOLUTE = re.compile(
    r"\b(?:"
    r"(?:is|are|was|were)(?:n't| not) (?:available|possible|supported)"
    r"|(?:is|are|was|were) (?:unavailable|unsupported|unreachable)"
    r"|unbuildable|impossible"
    r"|there(?:'s| is| was) no way (?:to|of)"
    r"|cannot be (?:built|made|done|fixed|reached|achieved|used|recognized"
    r"|parsed|read|detected|measured|observed|recovered)"
    r"|no matter (?:what|how)"
    r"|never (?:works|fires|runs|returns)"
    # Split by MODAL rather than by a blanket `be` exclusion. Round 9 measured
    # the earlier `(?:ever )?(?!be\b)` form failing in both directions at once:
    # it discarded "No transcript can be read by this hook", the passive voice
    # of this hook's own subject matter, while still firing on "No changes will
    # ever be needed to the CI workflow", the noise it was added to suppress --
    # the engine backtracks through the optional group, matches `will` without
    # `ever`, and tests the lookahead against "ever" instead of "be"
    # (ai-config#3737 round 9).
    #
    # `can`/`could` + `be` is a capability claim about the system and SHOULD
    # fire. `will`/`would` + `be` is a claim about future work ("will be
    # needed", "will be required") and should not. The lookahead therefore sits
    # BEFORE the optional group and spans it, so no backtrack can satisfy it.
    r"|no (?:\w+ ){0,3}(?:can|could) (?:ever )?\w+"
    r"|no (?:\w+ ){0,3}(?:will|would) (?!(?:ever )?be\b)(?:ever )?\w+"
    r")\b",
    re.I,
)

# Factor 2: the claim is about the SYSTEM rather than about the work. These are
# the nouns whose behaviour is measurable, so a claim attached to one of them
# is a claim somebody can and should check.
# Every noun is pluralizable. The first revision inflected exactly one entry
# (`dispatch`) and left the rest bare between word boundaries, so "No hooks can
# see this payload, and no agents will ever receive it" -- an absolute claim
# about the system, matching the other factor twice -- was silently discarded.
# The single inflected entry is what made the list read as stem-matched
# (ai-config#3737 round 8). `MCP` and `CI` take no plural and are spelled out.
RX_TOOLING = re.compile(
    r"\b(?:(?:harness(?:es)?|hooks?|guards?|runners?|dispatch(?:er|ers|es|ed)?"
    r"|subagents?|agents?|transcripts?|classifiers?|permissions?|APIs?|CLIs?"
    r"|workflows?|tools?|sessions?|provenance|chains?)|MCP|CI)\b",
    re.I,
)

# How near the two factors must sit. One long paragraph, not one document:
# a capability idiom in the opening and a tooling noun 40 lines later are not
# the same claim.
WINDOW = 400

NOTE = """Capability-claim reminder.

This {surface} contains an absolute claim that something CANNOT be done:

    "{quote}"

A claim that a capability is ABSENT names no artifact, so it cannot be checked
the way a positive claim can -- which is why it tends to be inferred from one
adjacent observation and then published as established
(`shared/workflow/verify-the-right-artifact.md`).

Before this goes out, answer one question: did you measure THIS, or measure
something next to it? Specifically --

  * Which artifact did you actually read, and is it the one the claim is about?
  * What would have to be true for the claim to be FALSE, and could the thing
    you read have shown that?
  * If the claim is "no X can Y", did you enumerate X, or check one X?

If it is measured, say what you measured inline -- that is what makes the
comment useful rather than merely confident. If it is inferred, narrow the
sentence to what you saw.

A forge comment outlives the session and gets read by people who were not
here, so this one needs a public retraction if it is wrong."""


def _extract_body(tool_name, tool_input):
    """(body, surface) for a forge write, or (None, None)."""
    if not isinstance(tool_input, dict):
        return None, None
    if tool_name in MCP_POST_TOOLS:
        for key in ("body", "text"):
            val = tool_input.get(key)
            if isinstance(val, str) and val.strip():
                return val, "comment body"
        return None, None
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script") or "")
        if not isinstance(command, str):
            return None, None
        # Only a forge write; a local `git commit -m` is not this surface.
        # Each shape is position-anchored, so prose or a heredoc quoting the
        # command does not count as issuing it.
        if not (RX_COMMENT_POST.search(command)
                or RX_REVIEW_POST.search(command)
                or RX_GLAB_POST.search(command)
                or RX_GH_CREATE_EDIT.search(command)):
            return None, None
        return command, "forge command"
    return None, None


def _findings(body):
    """The first absolute claim that also sits near a tooling noun, else None."""
    for hit in RX_ABSOLUTE.finditer(body):
        start = max(0, hit.start() - WINDOW)
        end = min(len(body), hit.end() + WINDOW)
        if RX_TOOLING.search(body[start:end]):
            return hit
    return None


# A sentence ends at `.`/`!`/`?` followed by whitespace and then something that
# can OPEN a sentence. A bare `.` is not enough: `16.3` has no space after it,
# `verify-the-right-artifact.md for` is followed by a lowercase word, and a URL
# is both -- so the first version of `_quote` cut the reminder mid-token and
# produced quotes opening `md for context;` and `3 seconds so` (ai-config#3737
# round 8). The quote IS the hook's product, so a mangled one degrades the only
# thing it delivers.
RX_SENTENCE_END = re.compile(r"[.!?][\"'`)\]]*\s+(?=[A-Z\"'`*(\[])")


def _quote(body, hit):
    """The sentence the hit sits in, trimmed for the reminder."""
    start = 0
    for m in RX_SENTENCE_END.finditer(body, 0, hit.start()):
        start = m.end()
    end = len(body)
    tail = RX_SENTENCE_END.search(body, hit.end())
    if tail:
        end = tail.start() + 1
    quote = " ".join(body[start:end].split())
    return quote[:300] + ("..." if len(quote) > 300 else "")


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    try:
        tool_name = payload.get("tool_name") or ""
        body, surface = _extract_body(tool_name, payload.get("tool_input") or {})
        if not body:
            return 0

        hit = _findings(body)
        if hit is None:
            return 0

        # Fire once per distinct (tool, body), so an edit-and-retry of the same
        # text through the same tool is not re-flagged. The first version of
        # this comment said `(surface, body)`, which is strictly coarser --
        # `surface` takes two values across seven MCP tools -- and the sentence
        # after it already said the right thing (ai-config#3737 round 8). The
        # TOOL is in the key deliberately: the measured incident published one claim to an
        # issue comment and then the same claim into a PR body, and those are
        # two publications, each worth its own question. Keying on the body
        # alone silently suppressed the second -- caught by a test, not by
        # reading the code.
        key = hashlib.sha256(
            f"{tool_name}\x00{body}".encode("utf-8", "replace")).hexdigest()[:16]
        sentinel = os.path.join(tempfile.gettempdir(),
                                f".claude-capability-claim-{key}")
        if os.path.exists(sentinel):
            return 0
        try:
            open(sentinel, "w").close()
        except Exception:
            pass

        context = NOTE.format(surface=surface, quote=_quote(body, hit))
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                f"Capability-claim reminder: this {surface} asserts something "
                f"cannot be done. Did you measure that, or infer it from an "
                f"adjacent artifact?")
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
