#!/usr/bin/env python3
"""Regression tests for triage-backlog.py.

The load-bearing property is coverage: every input issue yields exactly one
plan row, so the summary's examined count equals the input count.  The
per-bucket cases are negative controls in the fail-fast sense -- each bucket
is shown to be reachable on a synthetic fixture, so a zero in that bucket
against the real backlog is a measurement rather than an unrun rule.
"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "tb", Path(__file__).parent / "triage-backlog.py"
)
tb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tb)

passes = 0
failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


FIXTURE = [
    {"number": 1, "title": "test", "labels": []},
    {"number": 2, "title": "no-foo.py blocks every push after a retraction", "labels": []},
    {"number": 3, "title": "question everything", "labels": []},
    {"number": 4, "title": "review https://example.com/some-repo", "labels": []},
    {"number": 5, "title": "should gia always be a conductor session?", "labels": []},
    {"number": 6, "title": "check-thing.py reports a breach but never an approach", "labels": []},
    {"number": 7, "title": "run oppo", "labels": []},
    {"number": 8, "title": "run oppo", "labels": [{"name": "enhancement"}]},
    {"number": 9, "title": "sync-nlb-checker.py runs the sync on --help", "labels": ["bug"]},
    {"number": 10, "title": "Revisit adding a project .mcp.json", "labels": ["low-priority"]},
    {"number": 11, "title": "already triaged item", "labels": ["P2"]},
    {"number": 12, "title": "Fix bug", "labels": []},
    {"number": 13, "title": "no sacred cows", "labels": []},
]

plan = tb.classify(FIXTURE, {})
by = {r["number"]: r for r in plan}

check("one row per input issue", len(plan) == len(FIXTURE))
check("junk title is not-planned", by[1]["disposition"] == "not-planned")
check("severe phrase is P1", by[2]["disposition"] == "P1")
check("bare aphorism is P3", by[3]["disposition"] == "P3")
check("reading assignment URL is P3", by[4]["disposition"] == "P3")
check("question is P3", by[5]["disposition"] == "P3")
check("ordinary defect defaults to P2", by[6]["disposition"] == "P2")
check("older of two same-title issues keeps its disposition", by[7]["disposition"] == "P3")
check("newer same-title issue is duplicate of the older", by[8]["disposition"] == "duplicate" and by[8]["duplicate_of"] == 7)
check("bug label without severe phrase is P2", by[9]["disposition"] == "P2")
check("low-priority label is P3", by[10]["disposition"] == "P3")
check("existing priority label is kept", by[11]["disposition"] == "P2" and "already" in by[11]["reason"])
check("short title with an action verb is P2", by[12]["disposition"] == "P2")
check("short title with no action verb is P3", by[13]["disposition"] == "P3")

plan2 = tb.classify(FIXTURE, {3: "P1", 8: "P3"})
by2 = {r["number"]: r for r in plan2}
check("override replaces heuristic", by2[3]["disposition"] == "P1")
check("override clears duplicate marking", by2[8]["disposition"] == "P3" and by2[8]["duplicate_of"] is None)

# --apply --dry-run: every non-skipped row yields exactly one gh call, and a
# row already carrying its label yields none.
calls = tb.apply_plan(plan, None, dry_run=True)
check("dry-run call count skips the already-labelled row", calls == len(plan) - 1)

check("comment count reads ints", tb.comment_count(3) == 3)
check("comment count reads lists", tb.comment_count([{}, {}]) == 2)
check("comment count reads gh totalCount objects", tb.comment_count({"totalCount": 4}) == 4)

try:
    tb.parse_override("5=P9")
    check("bad override disposition is rejected", False)
except Exception:
    check("bad override disposition is rejected", True)

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
