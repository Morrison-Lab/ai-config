"""Test the flag-cop-out-offer guard.

Two design choices carry the value, and each has its own negative case.

TAIL-ANCHORED: the failure is a recap that CLOSES on an offer. An offer
mid-message followed by real substance is usually a question posed in passing,
so it must not warn.

NOT whole-message: unlike no-placeholder-reply, the offer is one sentence at
the end of a long reply, so the matcher searches the tail rather than matching
the entire message.

The corpus-quoting case matters here too but is weaker by construction: prose
ABOUT the rule usually discusses the phrases mid-document, which the tail
anchor already excludes.

Run: python3 hooks/test-flag-cop-out-offer.py hooks/flag-cop-out-offer.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def reply(text):
    """A project-thread reply: the user-visible text lives in a TOOL payload.

    The harness delivers a thread session's prose this way and no other way,
    so a transcript from one carries no assistant text block at all.
    """
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__hearthbot__reply",
         "input": {"text": text}}]}}


LONG = ("Setup job 143472 completed in 19m32s and the array is running. " * 12)

CASES = [
    # The reported incidents, verbatim.
    ([TOOL, say("The results are ready.\n\nSay the word and I'll push and "
                "open it now.")], True,
     "'say the word' closing a recap warns (the reported case)"),
    ([TOOL, say("I'll keep digging at the row-count mismatch unless you'd "
                "rather I spend the remaining hours on meeting material.")],
     True, "'unless you'd rather' warns (the 2.5-hour stall)"),
    ([TOOL, say("Array is queued.\n\nWant me to kick off the re-run now?")],
     True, "'want me to' warns"),
    ([TOOL, say("Both files are safe.\n\nLet me know if you want the "
                "coefficients pulled out.")], True,
     "'let me know if' warns"),
    ([TOOL, say("Ready to push when you are.")], True,
     "'ready to X when you are' warns"),

    # ai-config#3694: `flag-session-boundaries` appends a stopping-point
    # declaration to every reply, and for a non-clean stop it puts the pending
    # work AFTER that declaration. In a busy session the block outruns
    # TAIL_CHARS on its own, so obeying that rule pushed the actual closing
    # move out of this hook's window and made it blind. Measured on
    # ucdavis/bcs, 2026-09-15.
    ([TOOL, say("Built and pushed the figure.\n\nOFFER -- the strongest "
                "version is a chart. Say the word and I will add it to "
                "#1016.\n\n**Stopping Point**: Not a clean stopping point / "
                "work remains queued: " + LONG)], True,
     "an offer warns even when a long stopping-point block follows it"),
    ([TOOL, say("Merged #1019 and filed #1020.\n\n**Stopping Point**: Not a "
                "clean stopping point / work remains queued: " + LONG)], False,
     "a stopping-point block with no offer before it stays silent"),

    # The first patch for #3694 cut everything from the marker onward, which
    # made the pending-work section -- where flag-session-boundaries puts the
    # remaining work, and calls it the most visible element of the reply -- a
    # permanently safe place to park an offer. A worse blind spot than the one
    # being closed. Caught in review on ai-config#3695.
    ([TOOL, say("Merged and pushed.\n\n**Stopping Point**: Not a clean "
                "stopping point / work remains queued: the array is mid-run. "
                "Want me to push the fix now?")], True,
     "an offer at the END of the pending-work block still warns"),

    # The second patch handed back the post-marker region WHOLE, with no tail
    # slice, which let an aside buried mid-block fire with paragraphs of
    # status after it -- reintroducing inside the pending-work section the
    # exact false positive TAIL_CHARS exists to prevent. Caught in review on
    # ai-config#3695; both windows are tails now.
    ([TOOL, say("Merged and pushed.\n\n**Stopping Point**: Not a clean "
                "stopping point / work remains queued: would you like me to "
                "try that? " + LONG)], False,
     "an aside mid-pending-block, with status after it, stays silent"),

    # Negatives that decide the anchoring.
    ([TOOL, say("Want me to do this? No -- it was already authorized, so I "
                "did it. " + LONG)], False,
     "an offer phrase EARLY in a long reply does not warn"),
    ([TOOL, say("Pushed as a5591a67 and opened #679. I did not commit the "
                "regenerated artifact, which is a large binary.")], False,
     "a past-tense report does not warn"),
    ([TOOL, say("This needs your decision because it is destructive: "
                "should I force-push over the other session's commit?")],
     False, "a plain question with no offer wording does not warn"),
    ([TOOL], False, "a turn with no assistant prose does not warn"),
    ([TOOL, say("Nothing changed since the last poll.")], False,
     "a no-change tick does not warn"),

    # The reply-tool payload. In a project-thread session this is the ONLY
    # channel the user reads, so a reader that walks assistant text blocks
    # alone sees an empty turn and the guard never fires. Measured
    # 2026-09-19: a closing offer whose phrase is in OFFERS, well inside
    # TAIL_CHARS, went unflagged for exactly this reason.
    ([TOOL, reply("The request is withdrawn and the PR is unblocked. "
                  "Say the word and I'll merge it.")], True,
     "an offer inside a reply-tool payload warns"),
    ([TOOL, reply("Withdrew the review request; the scorer exited 0 on "
                  "1755bc6.")], False,
     "a reply-tool payload with no offer stays silent"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        r = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        # Must never block, and must SURFACE the warning. Asserting on stderr
        # alone cannot tell a surfaced warning from discarded output, so the
        # positive signal is `systemMessage` on stdout.
        assert '"decision": "block"' not in r.stdout, "guard must never block"
        if not r.stdout.strip():
            return False
        payload = json.loads(r.stdout)
        assert "systemMessage" in payload, "warn-only Stop hook must emit systemMessage"
        return "offer" in payload["systemMessage"].lower()
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected warn={expected}, got {got})")
            failures += 1

    # Once-per-message sentinel: a second run over the same message is silent.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("Say the word and I'll push.")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=env).stderr
    second = subprocess.run([sys.executable, HOOK], input=payload,
                            capture_output=True, text=True, env=env).stderr
    os.unlink(path)
    if "flag-cop-out-offer" in first and "flag-cop-out-offer" not in second:
        print("PASS: warns once per distinct message"); passes += 1
    else:
        print("FAIL: sentinel did not suppress the repeat"); failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
