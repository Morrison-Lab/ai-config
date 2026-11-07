#!/usr/bin/env python3
"""Tests for check-unowned-issues.py, with a known-unowned negative control.

A zero from the checker means nothing until it has been seen to report a
KNOWN unowned issue (shared/principles/fail-fast.md).
"""
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "cui", Path(__file__).parent / "check-unowned-issues.py")
cui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cui)

NOW = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
failures = 0


def check(name, condition):
    global failures
    print(("ok   " if condition else "FAIL ") + name)
    failures += 0 if condition else 1


def issue(number, labels, created="2026-11-07T07:00:00Z", prs=0, comments=()):
    return {"repo": "gha", "number": number, "title": f"t{number}", "labels": labels,
            "created_at": created, "open_pr_refs": prs, "comments": list(comments)}


found = cui.find_unowned([issue(1563, ["P1"])], NOW)
check("known unowned P1 is reported and overdue", len(found) == 1 and found[0]["overdue"])

found = cui.find_unowned([issue(2, ["P1"], created="2026-11-07T08:50:00Z")], NOW)
check("P1 inside the grace period is reported, not overdue",
      len(found) == 1 and not found[0]["overdue"])

check("linked open PR owns the issue", cui.find_unowned([issue(3, ["P1"], prs=1)], NOW) == [])
check("claim comment owns the issue",
      cui.find_unowned([issue(4, ["P1"], comments=["Claimed by thread X"])], NOW) == [])
check("unlabeled issue is ignored", cui.find_unowned([issue(5, ["bug"])], NOW) == [])

found = cui.find_unowned([issue(6, ["P2"])], NOW)
check("old P2 is reported but never overdue", len(found) == 1 and not found[0]["overdue"])

found = cui.find_unowned([issue(7, ["owed-followup"])], NOW)
check("owed-followup issue is overdue after the grace period",
      len(found) == 1 and found[0]["overdue"])

found = cui.find_unowned([issue(8, ["P2"]), issue(9, ["P1"])], NOW)
check("P1 sorts before P2", [i["number"] for i in found] == [9, 8])

for body in ["Owner: alice", "Owner: @alice", "owner:bob", "Claimed by X"]:
    check(f"claim recognized: {body!r}",
          cui.find_unowned([issue(10, ["P1"], comments=[body])], NOW) == [])
check("unrelated comment is not a claim",
      len(cui.find_unowned([issue(11, ["P1"], comments=["Reproduced on main"])], NOW)) == 1)

full_page = [{"title": "a ][ b"}] * cui.PER_PAGE
fake_pages = {1: full_page, 2: [{"title": "c"}]}
real_fetch = cui.fetch_page
cui.fetch_page = lambda path, page: fake_pages[page]
rows = cui.gh("repos/x/y/issues")
cui.fetch_page = real_fetch
check("explicit paging joins pages and leaves '][' inside titles alone",
      len(rows) == cui.PER_PAGE + 1 and rows[0]["title"] == "a ][ b" and rows[-1]["title"] == "c")

import subprocess


def fake_load_repo(repo):
    if repo == "bad":
        raise subprocess.CalledProcessError(1, "gh")
    return [issue(12, ["P1"])]


cui.load_repo = fake_load_repo
got, failed = cui.load(["bad", "good"])
check("one unreadable repo is reported and the others still load",
      failed == ["bad"] and [i["number"] for i in got] == [12])

sys.exit(1 if failures else 0)
