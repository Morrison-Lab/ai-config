#!/usr/bin/env python3
"""Tests for `flag-nonconvergent-review.py`.

The boundaries matter more than the positive case: a loop that IS converging,
and a short loop, must stay silent, or the guard fires on ordinary ARDI and
gets switched off.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
HOOK = os.path.join(HERE, "flag-nonconvergent-review.py")

spec = importlib.util.spec_from_file_location("fncr", HOOK)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def warns(counts, cats=None):
    cats = cats if cats is not None else [set() for _ in counts]
    return mod.verdict(counts, cats)[0]


# --- the measured case ----------------------------------------------------
# hac.sap#43's shape: many rounds, the same category returning.
recurring = [{"test-coverage"}, {"test-coverage"}, {"test-coverage", "x"},
             {"test-coverage"}]
check("a category recurring across four rounds warns",
      warns([3, 5, 2, 3], recurring), True)

# Counts that end no lower than they started across the window.
check("counts that do not narrow warn", warns([5, 3, 4, 6]), True)
# ...and a jagged loop that still ENDS lower is narrowing, not flat.
check("a jagged but narrowing loop is silent", warns([10, 9, 15, 7]), False)

# --- a converging loop must stay silent -----------------------------------
# This is the ordinary ARDI shape and the one that must never fire, or the
# guard fires on success.
check("a narrowing loop is silent", warns([8, 5, 3, 1]), False)
check("a loop that reached clean is silent", warns([8, 5, 3, 0]), False)
check("...even with a recurring category, if it reached clean",
      warns([3, 2, 1, 0], recurring), False)

# A category must recur across at least RECUR_ROUNDS rounds. A one-off
# category in each round, over a narrowing loop, is an ordinary review --
# lowering the threshold to 1 makes every long review fire.
check("distinct categories each appearing once do not warn",
      warns([8, 5, 3, 1], [{"a"}, {"b"}, {"c"}, {"d"}]), False)
# The boundary: exactly two rounds sharing a category is still not enough.
check("a category in exactly two rounds does not warn",
      warns([8, 5, 3, 1], [{"a"}, {"a"}, {"c"}, {"d"}]), False)
# ...and three is.
check("a category in three rounds warns",
      warns([8, 5, 3, 1], [{"a"}, {"a"}, {"a"}, {"d"}]), True)

# --- short loops ----------------------------------------------------------
check("one round is silent", warns([5]), False)
check("three rounds are silent", warns([5, 4, 3]), False)
check("three rounds with a recurrence are still silent",
      warns([5, 4, 3], recurring[:3]), False)
check("no rounds at all is silent", warns([]), False)

# --- a category must recur across ROUNDS, not within one ------------------
# Three findings of one category in a single round is a normal review.
one_round_many = [{"a"}, {"b"}, {"c"}, {"a", "a", "a"}]
check("a category three times in ONE round does not count as recurrence",
      mod.verdict([1, 1, 1, 4], one_round_many)[0]
      == mod.verdict([1, 1, 1, 4], [{"a"}, {"b"}, {"c"}, {"a"}])[0], True)

# --- the detail names what triggered it -----------------------------------
warn, detail = mod.verdict([3, 5, 2, 3], recurring)
check("the recurring category is named", "test-coverage" in detail, True)
warn, detail = mod.verdict([5, 3, 4, 6], [set() for _ in range(4)])
check("a flat trend says so", "not narrowing" in detail, True)

# --- transcript scanning --------------------------------------------------
def transcript(entries):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return path


tp = transcript([
    {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "[FINDINGS_COUNT: 3]\n"
         '<!-- review-data: {"findings":[{"category":"test-coverage"}]} -->'}]}},
    {"type": "user", "message": {"content": [
        {"type": "tool_result", "content": [
            {"type": "text", "text": '[FINDINGS_COUNT: 2] "category": "test-coverage"'}]}]}},
])
counts, cats = mod.scan(tp)
check("counts are read from assistant text", counts[0], 3)
check("counts are read from a tool result too", counts[1], 2)
check("categories are read", "test-coverage" in cats[0], True)
os.unlink(tp)

# A transcript with no verdicts at all must yield nothing, so an empty
# result is distinguishable from a clean loop.
tp = transcript([{"type": "assistant", "message": {"content": [
    {"type": "text", "text": "no verdict here"}]}}])
check("a transcript with no verdicts yields no counts", mod.scan(tp)[0], [])
os.unlink(tp)


# --- end to end -----------------------------------------------------------
def run_hook(payload, env=None):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True,
                       env=env if env else dict(os.environ))
    return p.returncode, p.stdout


rounds = [{"type": "assistant", "message": {"content": [{"type": "text", "text":
          f'[FINDINGS_COUNT: {n}] "category": "test-coverage"'}]}}
          for n in (4, 6, 3, 5)]
tp = transcript(rounds)
rc, out = run_hook({"transcript_path": tp})
check("end to end: exits 0 (warns, never blocks)", rc, 0)
check("end to end: emits additionalContext", "additionalContext" in out, True)
check("end to end: no permissionDecision", "permissionDecision" in out, False)
check("end to end: names the round count", "4 adversarial review rounds" in out, True)

# Fires once per round count: a second call with the same transcript is quiet.
rc, out2 = run_hook({"transcript_path": tp})
check("end to end: silent on a repeat call (sentinel)", out2.strip(), "")

env = dict(os.environ, ANTIGRAVITY_AGENT="1")
tp2 = transcript(rounds + [rounds[0]])          # a fifth round -> new key
rc, out3 = run_hook({"transcript_path": tp2}, env=env)
check("systemMessage suppressed under ANTIGRAVITY_AGENT",
      "systemMessage" in json.loads(out3), False)
os.unlink(tp); os.unlink(tp2)

# A converging transcript stays silent end to end.
tp = transcript([{"type": "assistant", "message": {"content": [{"type": "text",
                "text": f"[FINDINGS_COUNT: {n}]"}]}} for n in (8, 5, 3, 1)])
rc, out = run_hook({"transcript_path": tp})
check("end to end: silent on a converging loop", out.strip(), "")
os.unlink(tp)

# --- fails open -----------------------------------------------------------
for payload in ('[1,2,3]', '"x"', 'null', '42', 'not json', ''):
    p = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True)
    check(f"fails open on {payload[:10]!r}", (p.returncode, p.stderr.strip()), (0, ""))

rc, out = run_hook({"transcript_path": "/nonexistent/path.jsonl"})
check("a missing transcript is silent", (rc, out.strip()), (0, ""))
rc, out = run_hook({})
check("a payload with no transcript_path is silent", (rc, out.strip()), (0, ""))

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
