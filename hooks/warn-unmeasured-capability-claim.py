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
Two factors must BOTH appear within one window, which is what keeps this quiet:
an absolute negative-capability idiom, and a tooling/environment noun near it.
"The fix is not in this PR" has no absolute marker. "There is no way to know
what the user meant" has no tooling noun. Requiring both is what separates a
claim about the SYSTEM from ordinary hedged prose, and the system claims are
the ones a reader acts on.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Forge-write surfaces. A chat reply is deliberately out of scope (see the
# docstring): the cost this guards against is durability, not wrongness.
MCP_POST_TOOLS = (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
    "mcp__github__issue_write",
    "mcp__github__update_pull_request",
    "mcp__github__create_pull_request",
    "mcp__github__pull_request_review_write",
    "mcp__github__add_comment_to_pending_review",
)
BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# Factor 1: the claim is ABSOLUTE. Each idiom asserts that no instance exists,
# which no single observation can establish. Hedged forms ("appears to",
# "I could not get it to") are deliberately absent -- they invite the check
# already, which is the behaviour this exists to produce.
RX_ABSOLUTE = re.compile(
    r"\b(?:"
    r"is (?:not available|unavailable)"
    r"|are (?:not available|unavailable)"
    r"|unbuildable|unreachable|impossible"
    r"|there is no way to"
    r"|cannot be (?:built|made|done|fixed|reached|achieved|used|recognized)"
    r"|regardless of"
    r"|no matter (?:what|how)"
    r"|never (?:works|fires|runs|returns)"
    r"|no (?:\w+ ){0,3}(?:can|will|could) (?:ever )?\w+"
    r")\b",
    re.I,
)

# Factor 2: the claim is about the SYSTEM rather than about the work. These are
# the nouns whose behaviour is measurable, so a claim attached to one of them
# is a claim somebody can and should check.
RX_TOOLING = re.compile(
    r"\b(?:harness|hook|guard|runner|dispatch(?:er|es|ed)?|subagent|agent|"
    r"transcript|classifier|permission|API|CLI|MCP|workflow|CI|tool|session|"
    r"provenance|chain)\b",
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
        if not re.search(r"\b(?:gh|glab)\s+(?:issue|pr|mr)\b", command):
            return None, None
        if not re.search(r"\b(?:comment|create|edit)\b", command):
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


def _quote(body, hit):
    """The sentence the hit sits in, trimmed for the reminder."""
    start = body.rfind(".", 0, hit.start())
    start = 0 if start == -1 else start + 1
    end = body.find(".", hit.end())
    end = len(body) if end == -1 else end + 1
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

        # Fire once per distinct (surface, body), so an edit-and-retry of the
        # same text on the same surface is not re-flagged. The TOOL is in the
        # key deliberately: the measured incident published one claim to an
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
