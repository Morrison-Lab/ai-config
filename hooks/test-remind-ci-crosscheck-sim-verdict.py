"""Test the remind-ci-crosscheck-sim-verdict hook.

Builds a synthetic transcript per case and feeds the hook a UserPromptSubmit
payload pointing at it. The hook must print a reminder when a verdict-shaped
figure follows a LOCAL sim run with no CI-side read in between, and print
NOTHING otherwise.

Three properties this suite is written to pin, because each is a way the
design could be wrong while still looking like it works:

  1. It must never exit non-zero and never emit a `block` decision. This hook
     may only ADD context.
  2. ORDER is the whole mechanism, not mere presence. A CI read BEFORE the
     local run does not discharge a claim made after it -- a guard that
     ignored ordering would pass a naive presence-only suite while silently
     excusing the exact sequence the hook exists to catch.
  3. `gh pr checks` must NOT count as a CI read. It reports check STATE, never
     a verdict's numbers, so admitting it would discharge the obligation with
     nobody having looked at a CI-side figure.

Run:  python3 hooks/test-remind-ci-crosscheck-sim-verdict.py \
          hooks/remind-ci-crosscheck-sim-verdict.py
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


def bash(cmd, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {
            "content": [{"type": "tool_use", "name": "Bash",
                         "input": {"command": cmd}}]
        },
    }


LOCAL = bash(
    "SPARTA_DEMO_STATE_FULL=1 tools/demo/dump-state.sh "
    "demos/inputs/relief-fighting-withdrawal.json 190,260,460 /tmp/tx"
)
ANALYZE = bash(
    "godot --headless --path . -s tools/demo/analyze_transcript.gd -- /tmp/tx"
)
CLAIM = txt("Locally this still reports `uid0 overlap worst=1.611`.")
CI = bash("gh run view 32593819162 -R Lacaedemon/sparta --log")
# The reviewer-reproduced false NEGATIVE: `gh run view` appears only inside a
# quoted body being POSTED, not executed. A raw `search()` over the command
# string discharges on it; a shlex split cannot, because the body is one
# dequoted argument token of a `gh pr comment`.
QUOTED_CI = bash(
    'gh pr comment 1374 --body "Investigated via gh run view 123; still digging."'
)

REMIND = [
    ([LOCAL, CLAIM], "dump-state then a worst= figure, no CI read"),
    ([ANALYZE, CLAIM], "analyze_transcript then a worst= figure"),
    ([bash("GODOT_BIN=godot website/tools/dump-demo-states.sh /tmp/tx"),
      txt("The catalog sweep reports 24/25 verdicts on that clip.")],
     "catalog dump then an N/M verdicts figure"),
    ([bash("tools/ci/website-demo-defect-sweep.sh /tmp/tx out.md ."),
      txt("That clip now shows overlap (uid0) where it did not before.")],
     "sweep then a metric(uidN) figure"),
    ([bash("bash tools/check.sh validate test demo_defects"),
      txt("The scan comes back FAIL uid0 on the relieved block.")],
     "check.sh demo_defects then a PASS/FAIL uidN figure"),
    ([LOCAL, txt("uid0's `nnd_min` sits at 0.98 through the peel-back.")],
     "dump then an nnd_min figure"),
    # ORDER is the mechanism. A CI read that PRECEDES the local run cannot
    # discharge a claim made after it -- this is the case a presence-only
    # implementation would wrongly silence.
    ([CI, LOCAL, CLAIM], "CI read BEFORE the local run does not discharge"),
    # A later local run re-opens the obligation a previous CI read closed.
    ([LOCAL, CI, txt("ok"), LOCAL, CLAIM],
     "a second local run after the CI read re-opens it"),
    # A CI marker that only appears inside a quoted argument never ran.
    ([LOCAL, QUOTED_CI, CLAIM],
     "`gh run view` inside a quoted --body is text being posted, not a CI read"),
    ([LOCAL, bash('echo "gh api repos/o/r/commits/x/check-runs"'), CLAIM],
     "a CI api path echoed as a string is not a CI read"),
    # The CI markers are only meaningful as arguments of `gh`. Another
    # program that happens to take `run view` as its own subcommand must not
    # discharge -- without the command-word test, `_is_ci_read`'s positional
    # checks alone would admit it.
    ([LOCAL, bash("npm run view"), CLAIM],
     "`run view` as another program's subcommand is not a gh CI read"),
    ([LOCAL, bash("pnpm api repos/o/r/commits/x/check-runs"), CLAIM],
     "an api-shaped path passed to a non-gh program is not a CI read"),
    # `gh pr checks` reports state, never a verdict figure.
    ([LOCAL, bash("gh pr checks 1374 -R Lacaedemon/sparta"), CLAIM],
     "gh pr checks is check STATE, not a CI-side figure"),
]

SILENT = [
    ([CLAIM], "a verdict figure with no local run anywhere"),
    ([CI, txt("CI reports `25/25 verdicts passed`.")],
     "a figure read straight off CI"),
    ([LOCAL, CI, CLAIM], "CI read BETWEEN the local run and the claim"),
    ([LOCAL, bash("gh api repos/o/r/commits/abc/check-runs"), CLAIM],
     "a check-runs API read discharges"),
    ([LOCAL, bash("gh api repos/o/r/issues/1374/comments --paginate"), CLAIM],
     "reading the PR's posted comments discharges"),
    ([LOCAL, bash("gh api repos/o/r/actions/jobs/97083575763"), CLAIM],
     "an actions/jobs read discharges"),
    # The reviewer-reproduced false POSITIVE: a later, unrelated local run must
    # not re-arm a claim that was already cross-checked when it was made.
    ([LOCAL, CI, CLAIM, LOCAL],
     "a local run AFTER a discharged claim does not re-arm it"),
    ([LOCAL, CI, CLAIM, LOCAL, CI, LOCAL],
     "further activity after a discharged claim still does not re-arm it"),
    ([LOCAL, bash("GODOT_BIN=godot tools/demo/dump-state.sh a.json 8 /tmp/t"),
      CI, CLAIM],
     "env-prefixed local run still discharges via the CI read after it"),
    ([LOCAL, bash("gh api repos/o/r/actions/runs/123 --jq .event"), CLAIM],
     "an actions/runs api read discharges"),
    # A fixed-index read of argv is over-tight in two ways that both fire on the
    # commonest spellings, so the markers are found among POSITIONAL args instead.
    ([LOCAL, bash("GH_PAGER=cat gh run view 123 -R o/r --log"), CLAIM],
     "an env prefix shifts the command word off index 0 and must still discharge"),
    ([LOCAL, bash("gh api --paginate repos/o/r/commits/abc/check-runs"), CLAIM],
     "a flag BEFORE the path shifts it off index 2 and must still discharge"),
    ([LOCAL, bash("env GH_PAGER=cat gh api --paginate repos/o/r/actions/jobs/1"),
      CLAIM],
     "a lead word plus an env prefix plus a leading flag, all at once"),
    ([LOCAL, txt("The dump finished; nothing to report yet.")],
     "a local run with no verdict figure after it"),
    ([txt("Before dumping: the analyzer reports worst= for each metric."),
      LOCAL],
     "the figure PRECEDES the local run, so it came from elsewhere"),
    ([LOCAL, txt("The table is:\n```\nPASS uid0 overlap worst=2.43\n```\n")],
     "figure inside a code fence is raw tool output being shown"),
    ([LOCAL, txt("CI said:\n\n> FAIL uid0 overlap worst=0.98\n\nnoted.")],
     "figure inside a blockquote is a quotation"),
    ([bash("godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://test"),
      txt("The suite reports FAIL uid0 overlap worst=1.6")],
     "a GUT run is not a sim/transcript tool"),
    ([bash("git log --oneline -5"), CLAIM],
     "an unrelated command is not a sim/transcript tool"),
    ([LOCAL, txt("uid0 overlap worst=1.611 locally.", sidechain=True)],
     "a SUBAGENT's message is not my outgoing message"),
    ([bash("tools/demo/dump-state.sh x.json 8 /tmp/tx", sidechain=True), CLAIM],
     "a SUBAGENT's local run does not arm the guard"),
]


def run(recs, sentinel_dir=None):
    """Run the hook against a synthetic transcript."""
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    own_dir = sentinel_dir is None
    if own_dir:
        sentinel_dir = tempfile.mkdtemp()
    try:
        p = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": tpath}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=sentinel_dir),
        )
    finally:
        os.unlink(tpath)
        if own_dir:
            shutil.rmtree(sentinel_dir, ignore_errors=True)
    if p.returncode != 0:
        return f"EXIT{p.returncode}"
    if '"decision"' in p.stdout or '"block"' in p.stdout:
        return "BLOCKED"
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

# The sentinel suppresses a repeat of the SAME claim and must not reach across
# sessions. Two distinct transcripts carrying identical text at an identical
# record index are different sessions, so both must remind; only the second
# run against the SAME transcript is a repeat.
print("\nsentinel scope (one shared sentinel dir):")
shared = tempfile.mkdtemp()
try:
    seq = [
        (run([LOCAL, CLAIM], shared), "REMIND", "session A, first prompt"),
        (run([LOCAL, CLAIM], shared), "REMIND", "session B, same text and index"),
    ]
    fd, same_path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in (LOCAL, CLAIM):
            fh.write(json.dumps(r) + "\n")
    try:
        env = dict(os.environ, TMPDIR=shared)
        payload = json.dumps({"transcript_path": same_path})
        out = [
            subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                           text=True, env=env).stdout.strip()
            for _ in range(2)
        ]
        seq.append(("REMIND" if out[0] else "silent", "REMIND",
                    "same transcript, first prompt"))
        seq.append(("REMIND" if out[1] else "silent", "silent",
                    "same transcript again -- fires once per claim"))
    finally:
        os.unlink(same_path)
finally:
    shutil.rmtree(shared, ignore_errors=True)

for got, want, desc in seq:
    wrong += got != want
    print(f"  {got:<7} {desc}")

# Degenerate inputs must fail OPEN and SILENT, never crash.
print("\nfails open and silent:")
degenerate = []
p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
degenerate.append((("silent" if not p.stdout.strip() else "REMIND") if p.returncode == 0
                   else f"EXIT{p.returncode}", "silent", "unparseable payload"))
p = subprocess.run([sys.executable, HOOK], input=json.dumps({"transcript_path": "/nope"}),
                   capture_output=True, text=True)
degenerate.append((("silent" if not p.stdout.strip() else "REMIND") if p.returncode == 0
                   else f"EXIT{p.returncode}", "silent", "missing transcript"))
for got, want, desc in degenerate:
    wrong += got != want
    print(f"  {got:<7} {desc}")

total = len(REMIND) + len(SILENT) + len(seq) + len(degenerate)
print(f"\n{total - wrong}/{total} correct" + ("" if wrong == 0 else f"  ({wrong} WRONG)"))
sys.exit(1 if wrong else 0)
