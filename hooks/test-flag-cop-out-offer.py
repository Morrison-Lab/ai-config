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
