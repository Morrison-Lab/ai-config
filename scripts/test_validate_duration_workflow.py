#!/usr/bin/env python3
"""Run validate-duration.yml's issue step against a stub gh (ai-config#3384).

The stub answers `gh api` from a fixture through the step's own --jq filter,
run by the real jq, and records every other gh call, so the test covers the
filter and each branch: no issue, open, accepted recently, accepted long ago,
and fixed. The `run:` block comes from yaml.safe_load, which already dedents
it (shared/coding/yaml-embedded-script-double-dedent.md).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/validate-duration.yml"
STEP = "Open or update the tracking issue"
TITLE = "validate job on main has slowed down"
MARKER = "<!-- validate-duration-tracking -->"
STUB = """#!/bin/bash
if [ "$1" = api ]; then
  while [ "$#" -gt 0 ] && [ "$1" != --jq ]; do shift; done
  jq -r "$2" "$FIXTURE"
  exit
fi
echo "$*" >> "$LOG"
"""

steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["check"]["steps"]
script = next(s["run"] for s in steps if s.get("name") == STEP)
now = datetime.now(timezone.utc)


def ago(days: int) -> str:
    return (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def issue(number: int, state: str = "open", reason: str | None = None, closed: str | None = None,
          title: str = TITLE, body: str | None = MARKER, **extra) -> dict:
    return {"number": number, "state": state, "state_reason": reason, "closed_at": closed,
            "title": title, "body": body, **extra}


def run(items: list[dict]) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "gh").write_text(STUB)
        (d / "gh").chmod(0o755)
        (d / "report.txt").write_text("report\n")
        (d / "fixture.json").write_text(json.dumps(items))
        env = dict(os.environ, PATH=f"{d}{os.pathsep}{os.environ['PATH']}",
                   FIXTURE=str(d / "fixture.json"), LOG=str(d / "log"),
                   GH_REPO="o/r", RUN_URL="https://example.invalid/run", LAG_DAYS="28")
        done = subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=d, env=env,
                              capture_output=True, text=True)
        log = (d / "log").read_text().splitlines() if (d / "log").exists() else []
        return done.returncode, log


failures = 0
cases = [
    ("no tracking issue opens one and fails", [issue(5, title="other", body=None),
                                               issue(4, pull_request={})], 1, "issue create"),
    ("an open issue gets a comment", [issue(7), issue(3, "closed", "completed", ago(90))],
     0, "issue comment 7"),
    ("a recent not-planned close only warns", [issue(8, "closed", "not_planned", ago(10))], 0, None),
    ("an old not-planned close opens a new issue", [issue(9, "closed", "not_planned", ago(40))],
     1, "issue create"),
    ("a fixed issue opens a new one", [issue(10, "closed", "completed", ago(3)), issue(2)],
     1, "issue create"),
    ("an issue without the marker is ignored", [issue(11, body="no marker")], 1, "issue create"),
]
for name, items, want_code, want_call in cases:
    code, log = run(items)
    ok = code == want_code and (log == [] if want_call is None
                                else len(log) == 1 and log[0].startswith(want_call))
    print(("PASS: " if ok else "FAIL: ") + name + ("" if ok else f" -- exit {code}, calls {log}"))
    failures += not ok

print(f"\n{len(cases) - failures} passed, {failures} failed")
sys.exit(1 if failures else 0)
