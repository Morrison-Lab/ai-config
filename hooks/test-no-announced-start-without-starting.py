#!/usr/bin/env python3
"""Test the no-announced-start-without-starting guard.

The cases that matter most are the NEGATIVE ones. A guard that blocks every
sentence about what happens next would push authors toward saying less about
sequencing, so the conditional-exemption tests are load-bearing, not padding.

Run: python3 hooks/test-no-announced-start-without-starting.py \
       hooks/no-announced-start-without-starting.py
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def clear_sentinels():
    """The guard fires once per distinct message, keyed by a hash of it.

    Those sentinel files outlive the process, so a second run of this suite
    would see every block case already spent and report a false pass. Clearing
    them is what makes the suite repeatable.
    """
    pattern = os.path.join(tempfile.gettempdir(), ".claude-announced-start-*")
    for path in glob.glob(pattern):
        try:
            os.unlink(path)
        except OSError:
            pass


def say(text):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def run(messages):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        for m in messages:
            fh.write(json.dumps(m) + "\n")
        path = fh.name
    out = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"transcript_path": path}),
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def blocked(text):
    out = run([say(text)])
    if not out:
        return False
    return json.loads(out).get("decision") == "block"


CASES_BLOCK = [
    # The measured instance.
    "I'll start on it while the arrays run.",
    # The other measured instance, with the stopping-point pairing that makes
    # it read as compliance.
    # A realistic closing block: the announcement sits above a multi-sentence
    # Stopping Point declaration, which is why that block is stripped before
    # the tail is taken. Without the strip, the announcement falls outside
    # the window and the measured instance goes unmatched.
    "I'm starting it now: issue, branch, PR.\n\n"
    "**Stopping Point**: Not a clean stopping point / work remains queued: "
    "#1045 awaiting CI. Seven arrays run until 06:30. Then #1016, #1036, "
    "#1015, #1007 and #1000.",
    "I'll begin the refactor.",
    "I am now starting the month_pool propagation fix.",
    "I'll do that now.",
    "Starting on it now.",
    "I'll get started on the migration.",
]

CASES_PASS = [
    # Round-3 review finding on ai-config#3887, verified there by direct
    # execution. "start with" is expository -- it says where an explanation
    # begins, not that work is about to be done -- and the colon-joined
    # delivery shares a splitter sentence with the match, so the tail window
    # alone could not save it.
    "I'll start with the easy part of the analysis: the data looks clean "
    "and complete.",
    "I'll start with the numbers, then the caveats.",
    # The review finding on ai-config#3887: an ordinary mid-reply narrative
    # transition, in a reply that then delivers what it announced. Blocking
    # this is how a guard earns being switched off.
    "Next, I'll summarize the findings below.\n\n"
    "Finding 1 is a false positive; finding 2 is real and is fixed in "
    "4053b6f3. Both are addressed.",
    # An announcement early in a reply that goes on to do the work.
    "I'll start on the combiner change.\n\n"
    "Done: the map is carried through, the article reads it, and the tests "
    "cover the legacy artifact. Pushed as abc1234.",
    # Gated on something outside this turn's control: a real plan.
    "I'll start on it once the review lands.",
    "I'll push after you confirm.",
    "Next, I'll run the spellcheck when CI finishes.",
    "I'll begin the refactor if you'd rather not wait.",
    "I'll resubmit the arrays as soon as the PR merges.",
    "I'll merge it pending your authorization.",
    # Past tense: the work happened.
    "I started on it and filed #1043.",
    "Filed the issue and cut the branch.",
    # No commitment at all.
    "The sweep is 76 of 175 chunks in, with no failures.",
    "**Stopping Point**: Clean stopping point reached.",
    # Quoting the rule must not trip it.
    "The banned shape is `I'll start on it` with nothing following.",
]


def main():
    clear_sentinels()
    failures = 0
    for text in CASES_BLOCK:
        if not blocked(text):
            failures += 1
            print(f"FAIL (should block): {text!r}")
        else:
            print(f"PASS block: {text.splitlines()[0][:60]!r}")
    for text in CASES_PASS:
        if blocked(text):
            failures += 1
            print(f"FAIL (should pass): {text!r}")
        else:
            print(f"PASS allow: {text[:60]!r}")

    # The guard must fire once per distinct message, so a second identical
    # Stop does not block forever.
    clear_sentinels()
    text = "I'll start on the next issue."
    first = blocked(text)
    second = blocked(text)
    if not first or second:
        failures += 1
        print(f"FAIL once-per-message: first={first} second={second}")
    else:
        print("PASS once-per-message")

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
