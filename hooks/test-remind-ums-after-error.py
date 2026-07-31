"""Test the remind-ums-after-error hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder for a genuine
first-person admission with no recording after it, and print NOTHING for
everything else.

Two properties this suite is specifically written to pin, because both are
what the design got wrong on the first attempt elsewhere:

  1. It must never exit non-zero and never emit a `block` decision. This hook
     may only ADD context; suppressing an error admission is the failure mode
     it exists to avoid.
  2. Correcting someone ELSE's claim, or quoting the rule, must stay silent.

Run:  python3 hooks/test-remind-ums-after-error.py hooks/remind-ums-after-error.py
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


ADMIT = txt("Checking that again -- I was wrong about the repo being public.")

REMIND = [
    ([ADMIT], "bare admission, nothing after it"),
    ([ADMIT, user("ok"), txt("Continuing with the next task.")],
     "admission then unrelated work"),
    ([txt("I miscounted: the changelog lists 10, not 9.")], "miscounted"),
    ([txt("My mistake -- that query predated my own pushes.")], "my mistake"),
    ([txt("Correcting myself: rprojroot resolves a different root.")],
     "correcting myself"),
    ([txt("I mischaracterized the exposure as public.")], "mischaracterized"),
    ([txt("Retracting my earlier claim about the hook directory.")], "retracting"),
    ([txt("I incorrectly reported the PR as conflict-free.")], "incorrectly reported"),
    ([ADMIT, tool("Edit", {"file_path": "R/foo.R"})],
     "a write that is NOT to a memory/skill path does not clear it"),
    ([tool("Edit", {"file_path": "memories/tools.md"}), ADMIT],
     "a recording BEFORE the admission does not clear it"),
]

SILENT = [
    ([txt("All checks are green; nothing to correct.")], "no admission at all"),
    ([txt("The review was wrong about the pathspec.")],
     "correcting SOMEONE ELSE, not myself"),
    ([txt("That claim in the docs is incorrect.")], "someone else's claim"),
    ([txt("The reviewer's suggestion was mistaken.")], "reviewer was mistaken"),
    ([txt("The rule fires on phrases like `I was wrong` in a message.")],
     "quoting the trigger inside inline code"),
    ([txt("The user wrote:\n\n> I was wrong about that\n\nso the rule applies.")],
     "trigger inside a blockquote"),
    ([txt("Example:\n```\nI was wrong\n```\nthat is the pattern.")],
     "trigger inside a code fence"),
    ([ADMIT, tool("Edit", {"file_path": "memories/preferences.md"})],
     "admission then a memory write clears it"),
    ([ADMIT, tool("Write", {"file_path": "/repo/shared/workflow/x.md"})],
     "admission then a shared-fragment write clears it"),
    ([ADMIT, tool("Task", {"prompt": "Run a ums pass recording this"})],
     "admission then a UMS subagent dispatch clears it"),
    ([ADMIT, tool("Bash", {"command": "git commit -m 'ums: record it'"})],
     "admission then a ums commit clears it"),
    ([txt("I was wrong about that.", sidechain=True)],
     "a SUBAGENT's admission is not my outgoing message"),
]


def run(recs, sentinel_dir=None):
    """Run the hook against a synthetic transcript.

    `sentinel_dir` shares one sentinel directory across calls, so a caller can
    exercise the dedup key itself; the default gives each case a fresh one.
    """
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    own_dir = sentinel_dir is None
    if own_dir:
        sentinel_dir = tempfile.mkdtemp()
    try:
        p = subprocess.run(
            ["python3", HOOK],
            input=json.dumps({"transcript_path": tpath}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=sentinel_dir),
        )
    finally:
        os.unlink(tpath)
        if own_dir:
            shutil.rmtree(sentinel_dir, ignore_errors=True)

    if p.returncode != 0:
        sys.exit(f"FATAL: hook exited {p.returncode}\n{p.stderr.strip()}")
    if "\"decision\"" in p.stdout or "block" in p.stdout.lower():
        sys.exit(
            "FATAL: hook emitted a block-shaped decision. This hook must only "
            f"ever add context, never suppress a message.\n{p.stdout}"
        )
    return "REMIND" if p.stdout.strip() else "silent"


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

# The sentinel suppresses a repeat of the SAME admission, and must not reach
# across sessions. Two distinct transcripts carrying identical text at an
# identical record index are different sessions, so both must remind; only the
# second run against the SAME transcript is a repeat. Sharing one sentinel dir
# is what makes the distinction observable -- with the transcript path dropped
# from the key, case 2 below goes silent.
print("\nsentinel scope (one shared sentinel dir):")
shared = tempfile.mkdtemp()
try:
    seq = [
        (run([ADMIT], shared), "REMIND", "session A, first prompt"),
        (run([ADMIT], shared), "REMIND", "session B, same text and index"),
    ]
    fd, same_path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(ADMIT) + "\n")
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
                    "same transcript again -- fires once per admission"))
    finally:
        os.unlink(same_path)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

total = len(REMIND) + len(SILENT) + len(seq)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
