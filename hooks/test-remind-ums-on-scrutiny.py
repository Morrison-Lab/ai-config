"""Test the remind-ums-on-scrutiny guard.

The value is concentrated in the negative cases. This hook fires on (1)
reading a review of your work and (2) a questioned claim that was then
corrected, and the phrases that signal either also appear when quoting the
rule, confirming a claim, or fetching unrelated issue comments after a UMS
pass. A guard that nags on those gets switched off.

The given example (ai-config#2261): "are you sure about that?" followed by
finding the claim was wrong must remind; the same question followed by
confirming the claim must stay silent.

Run: python3 hooks/test-remind-ums-on-scrutiny.py hooks/remind-ums-on-scrutiny.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

if len(sys.argv) < 2:
    sys.exit(f"Usage: python3 {sys.argv[0]} <path-to-hook>")
HOOK = sys.argv[1]

if not os.path.isfile(HOOK):
    sys.exit(
        f"FATAL: hook not found at {HOOK} -- a missing file would otherwise "
        "read as 'silent' on every case and print a perfect pass"
    )


def txt(s, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [{"type": "text", "text": s}]},
    }


def tool(name, inp, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
    }


def user(s):
    return {"type": "user", "message": {"content": [{"type": "text", "text": s}]}}


Q = user("are you sure about that?")
WRONG = txt("You're right to ask -- I was wrong, the count is 12 not 9.")
SILENT_UPDATE = txt("Actually, the count is 12.")
CONFIRM = txt("On re-checking, the figure holds.")
REVIEW = tool("Bash", {
    "command": 'gh api repos/Morrison-Lab/ai-config/pulls/2262/comments',
})
UMS = tool("Task", {"prompt": "Please run ums.", "description": "ums"})
FIX_SHARED = tool("Edit", {
    "file_path": "shared/workflow/run-ums-proactively.md",
    "old_string": "a",
    "new_string": "b",
})
WRITE_HOOK = tool("Write", {
    "file_path": "hooks/remind-ums-on-scrutiny.py",
    "content": "REVIEW_READ = re.compile(r'**Claude finished|### Verdict')",
})


REMIND = [
    ([Q, WRONG], "given example: are you sure, then I was wrong"),
    ([Q, SILENT_UPDATE], "questioned then corrected without admitting"),
    ([REVIEW], "review comments fetched, no UMS"),
    ([user("**Claude finished** reviewing HEAD. ### Verdict")],
     "user-pasted review body"),
    ([REVIEW, FIX_SHARED], "editing shared/ after a review-read is the fix"),
    ([Q, WRONG, FIX_SHARED], "a corpus edit is not an explicit UMS pass"),
    ([UMS, Q, WRONG], "UMS before the correction does not count"),
    ([UMS, REVIEW], "UMS before the review-read does not count"),
]

SILENT = [
    ([Q], "questioning with no later correction"),
    ([Q, CONFIRM], "questioning then confirming the claim"),
    ([WRONG], "correction with no prior question"),
    ([Q, WRONG, UMS], "explicit ums after the correction"),
    ([REVIEW, UMS], "explicit ums after the review-read"),
    ([Q, WRONG, tool("Skill", {"skill": "ums"})], "Skill ums discharges"),
    ([user("did you push the branch?")], "operational did-you is not questioning"),
    ([user("are you done with this PR?")], "are you done is not are you sure"),
    ([txt("The `are you sure about that?` example is in the fragment."),
      WRONG], "inline-code mention of the example is not a user question"),
    ([WRITE_HOOK], "writing the matcher into a hook file is not a review-read"),
    ([txt("I was wrong about this.")],
     "bare admission without a question is the sibling's case"),
    ([REVIEW], "placeholder -- replaced below for sidechain"),
]

# Replace the last placeholder with a real sidechain case.
SILENT[-1] = (
    [tool("Bash", {
        "command": "gh api repos/x/y/pulls/1/comments",
    }, sidechain=True)],
    "a subagent's review-read is not this session's",
)


def run(events, tmpdir=None):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ)
        env["TMPDIR"] = tmpdir or tempfile.mkdtemp()
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        assert out.returncode == 0, f"non-zero exit: {out.returncode}"
        assert '"decision"' not in out.stdout, "must never emit a block decision"
        return "REMIND" if "[hook: remind-ums-on-scrutiny]" in out.stdout else "silent"
    finally:
        os.unlink(path)


wrong = 0
print("should REMIND:")
for recs, desc in REMIND:
    v = run(recs)
    wrong += v != "REMIND"
    print(f"  {v:<7} {desc}")

print("\nshould stay SILENT:")
for recs, desc in SILENT:
    v = run(recs)
    wrong += v != "silent"
    print(f"  {v:<7} {desc}")

print("\nsentinel scope (one shared sentinel dir):")
shared = tempfile.mkdtemp()
try:
    seq = [
        (run([Q, WRONG], shared), "REMIND", "session A, first prompt"),
        (run([Q, WRONG], shared), "REMIND", "session B, same text and index"),
    ]
    fd, same_path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(Q) + "\n")
        fh.write(json.dumps(WRONG) + "\n")
    try:
        env = dict(os.environ, TMPDIR=shared)
        payload = json.dumps({"transcript_path": same_path})
        out = [
            subprocess.run(["python3", HOOK], input=payload, capture_output=True,
                           text=True, env=env).stdout.strip()
            for _ in range(2)
        ]
        seq.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
        seq.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per epoch"))
    finally:
        os.unlink(same_path)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# Fail open on an unreadable transcript.
out = subprocess.run(
    [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
    capture_output=True, text=True,
)
if out.returncode == 0 and "[hook:" not in out.stdout:
    print("\nPASS: fails open on an unreadable transcript")
else:
    print("\nFAIL: unreadable transcript")
    wrong += 1

total = len(REMIND) + len(SILENT) + len(seq) + 1
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
